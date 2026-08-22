import logging
import time
import re
from typing import List, Dict, Optional, Tuple
from google.genai import types
import database.database as db
from ai.vector_store import vector_store
from ai.embeddings import EmbeddingService
from ai.llm_service import llm_service
from ai.orbot_prompts import compose_orbot_prompt, build_chat_contents

logger = logging.getLogger(__name__)

# Configurable minimum similarity threshold.
# FAISS L2 distance: lower is more similar.
# Since we use all-MiniLM-L6-v2 which produces normalized vectors,
# L2 distance is related to cosine similarity.
MAX_L2_DISTANCE = 1.75
HIGH_RELEVANCE_THRESHOLD = 1.2
INSUFFICIENT_EVIDENCE_DISTANCE = 1.5
DEFAULT_TOP_K = 5
MAX_TOP_K = 10

# Complexity keywords that trigger multi-step retrieval.
COMPLEXITY_KEYWORDS = (
    "compare", "analyze", "analysis", "methodology", "difference",
    "differences", "relationship", "versus", "vs", "pros and cons",
    "advantages", "disadvantages", "trade-offs", "tradeoffs",
)


def _normalize_mode(mode: Optional[str]) -> str:
    """Accepts 'Research' / 'research' / 'Project' / 'project' / None."""
    if not mode:
        return "research"
    m = mode.strip().lower()
    if m.startswith("proj"):
        return "project"
    return "research"


class RAGService:
    def __init__(self):
        self.embedder = EmbeddingService()

    # -- Public entry --------------------------------------------------------

    def ask(
        self,
        question: str,
        document_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        mode: Optional[str] = "research",
        history: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Executes the ORBOT RAG pipeline:

          1. resolve target documents (document_id, workspace_id, or all)
          2. embed the user query
          3. retrieve relevant chunks from FAISS
          4. filter by similarity + target doc scope
          5. compose the layered ORBOT prompt
          6. call Gemini (multi-turn chat with optional inline images)
          7. return structured answer + sources + metadata
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        top_k = min(max(1, top_k), MAX_TOP_K)
        mode_norm = _normalize_mode(mode)
        history = history or []
        attachments = attachments or []

        # Check if user query is a simple greeting / conversational phrase
        clean_q = re.sub(r'[^\w\s]', '', question.strip().lower())
        q_words = clean_q.split()
        is_greeting = clean_q in {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "who are you", "what can you do", "help"} or (len(q_words) <= 3 and any(w in {"hi", "hello", "hey"} for w in q_words))

        # 1. Resolve retrieval scope with latency tracking.
        retrieval_start = time.perf_counter()
        if is_greeting:
            chunks, total_before_filter = [], 0
        else:
            chunks, total_before_filter = self._retrieve_with_stats(
                question=question,
                document_id=document_id,
                workspace_id=workspace_id,
                top_k=top_k,
            )
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 1)

        # 2. Multi-step retrieval for complex queries with sparse results.
        multi_step_used = False
        if (
            len(chunks) < 2
            and self._is_complex_query(question)
        ):
            extra_chunks = self._multi_step_retrieve(
                question=question,
                document_id=document_id,
                workspace_id=workspace_id,
                top_k=top_k,
            )
            if extra_chunks:
                # Merge: deduplicate by chunk_id, keep best distance.
                existing_ids = {c["chunk_id"] for c in chunks}
                for ec in extra_chunks:
                    if ec["chunk_id"] not in existing_ids:
                        chunks.append(ec)
                        existing_ids.add(ec["chunk_id"])
                chunks = sorted(chunks, key=lambda c: c["similarity"])[:top_k]
                multi_step_used = True

        # 3. Relevance classification.
        high_relevance_chunks = sum(
            1 for c in chunks if c["similarity"] < HIGH_RELEVANCE_THRESHOLD
        )
        moderate_relevance_chunks = len(chunks) - high_relevance_chunks
        used_doc_context = bool(chunks)

        # 4. Insufficient evidence detection.
        insufficient_evidence = False
        if not chunks:
            insufficient_evidence = True
        elif chunks and chunks[0]["similarity"] > INSUFFICIENT_EVIDENCE_DISTANCE:
            insufficient_evidence = True

        # 5. Call Gemini with the composed ORBOT prompt.
        llm_start = time.perf_counter()
        try:
            answer = self._call_llm(
                question=question,
                mode=mode_norm,
                history=history,
                chunks=chunks,
                attachments=attachments,
            )
        except Exception:
            # Bubble up to the API layer; the route turns this into HTTP 500.
            raise
        llm_ms = round((time.perf_counter() - llm_start) * 1000, 1)

        # 6. Generate follow-up questions (lightweight second LLM call).
        followups: List[str] = []
        try:
            followups = self._generate_followups(
                question=question,
                answer=answer,
                chunks=chunks,
                mode=mode_norm,
            )
        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")

        # 7. Cross-document attribution for trace.
        trace = _build_trace(
            chunks, used_doc_context, mode_norm, insufficient_evidence,
            high_relevance_chunks, moderate_relevance_chunks,
        )

        # 8. Provider name for metadata.
        provider_name = self._active_provider_name()

        return {
            "answer": answer,
            "sources": chunks,
            "mode": mode_norm,
            "used_doc_context": used_doc_context,
            "trace": trace,
            "confidence": _confidence_label(
                high_relevance_chunks, moderate_relevance_chunks,
                insufficient_evidence,
            ),
            "insufficient_evidence": insufficient_evidence,
            "high_relevance_chunks": high_relevance_chunks,
            "moderate_relevance_chunks": moderate_relevance_chunks,
            "total_chunks_retrieved": total_before_filter,
            "chunks_used": len(chunks),
            "suggested_followups": followups,
            "metadata": {
                "provider": provider_name,
                "retrieval_latency_ms": retrieval_ms,
                "llm_latency_ms": llm_ms,
                "total_latency_ms": round(retrieval_ms + llm_ms, 1),
                "multi_step_retrieval": multi_step_used,
            },
        }

    # -- Internals -----------------------------------------------------------

    def _is_complex_query(self, question: str) -> bool:
        """Detect whether a question likely requires multi-aspect retrieval."""
        q_lower = question.lower()
        return any(kw in q_lower for kw in COMPLEXITY_KEYWORDS)

    def _multi_step_retrieve(
        self,
        question: str,
        document_id: Optional[str],
        workspace_id: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """
        Break a complex question into sub-questions, retrieve for each,
        and merge the results.
        """
        sub_questions = self._split_into_sub_questions(question)
        if not sub_questions:
            return []

        seen_ids: set = set()
        merged: List[Dict] = []
        sub_top_k = max(2, top_k // len(sub_questions))

        for sub_q in sub_questions:
            sub_chunks = self._retrieve(
                question=sub_q,
                document_id=document_id,
                workspace_id=workspace_id,
                top_k=sub_top_k,
            )
            for chunk in sub_chunks:
                if chunk["chunk_id"] not in seen_ids:
                    seen_ids.add(chunk["chunk_id"])
                    merged.append(chunk)

        return sorted(merged, key=lambda c: c["similarity"])[:top_k]

    @staticmethod
    def _split_into_sub_questions(question: str) -> List[str]:
        """
        Simple heuristic decomposition: split on conjunctions and relative
        pronouns that signal multi-part questions.
        """
        # Split on ", and ", " and ", " vs ", " versus ", " while ", " whereas "
        parts = re.split(
            r'\s+(?:and|vs\.?|versus|while|whereas)\s+',
            question,
            flags=re.IGNORECASE,
        )
        sub_parts_buf: List[str] = []
        for part in parts:
            sub_parts = re.split(r'\?\s*', part, flags=re.IGNORECASE)
            for sp in sub_parts:
                sp = sp.strip().rstrip("?.")
                if len(sp.split()) >= 3:
                    sub_parts_buf.append(sp + "?")
        # Deduplicate while preserving order.
        seen: set = set()
        result: List[str] = []
        for q in sub_parts_buf:
            key = q.lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(q)
        return result[:5]  # cap at 5 sub-questions

    def _retrieve(
        self,
        question: str,
        document_id: Optional[str],
        workspace_id: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """Retrieves and filters chunks by similarity + scope."""
        query_embedding = self.embedder.embed_text(question)

        # When filtering, fetch more candidates because some will be discarded.
        search_k = top_k * 5 if (document_id or workspace_id) else top_k
        faiss_results = vector_store.search(query_embedding, top_k=search_k)
        if not faiss_results:
            return []

        chunk_ids = [res["chunk_id"] for res in faiss_results]
        db_chunks = db.get_chunks_by_ids(chunk_ids)
        chunk_dict = {c["id"]: c for c in db_chunks}

        # Pre-fetch workspace docs if needed
        workspace_doc_ids = set()
        if workspace_id:
            workspace_docs = db.get_documents_for_workspace(workspace_id)
            workspace_doc_ids = {d["id"] for d in workspace_docs}

        # Cache document metadata lookups
        doc_meta_cache: Dict[str, Optional[Dict]] = {}

        def _filename_for(doc_id: str) -> str:
            if doc_id not in doc_meta_cache:
                meta = db.get_document_by_id(doc_id)
                doc_meta_cache[doc_id] = meta
            meta = doc_meta_cache[doc_id]
            return meta["filename"] if meta else "Unknown Document"

        relevant: List[Dict] = []
        for faiss_res in faiss_results:
            cid = faiss_res["chunk_id"]
            distance = faiss_res["distance"]

            if distance > MAX_L2_DISTANCE:
                continue
            if cid not in chunk_dict:
                continue

            chunk = chunk_dict[cid]
            if document_id and chunk["document_id"] != document_id:
                continue
            if workspace_id and chunk["document_id"] not in workspace_doc_ids:
                continue

            relevant.append(
                {
                    "document_id": chunk["document_id"],
                    "filename": _filename_for(chunk["document_id"]),
                    "chunk_id": cid,
                    "chunk_index": chunk["chunk_index"],
                    "page_number": chunk["page_number"],
                    "text": chunk["text"],
                    "similarity": round(distance, 4),
                }
            )

            if len(relevant) >= top_k:
                break

        return relevant

    def _retrieve_with_stats(
        self,
        question: str,
        document_id: Optional[str],
        workspace_id: Optional[str],
        top_k: int,
    ) -> Tuple[List[Dict], int]:
        """
        Retrieve chunks and also return the total count of FAISS candidates
        before threshold filtering.
        """
        query_embedding = self.embedder.embed_text(question)

        search_k = top_k * 5 if (document_id or workspace_id) else top_k
        faiss_results = vector_store.search(query_embedding, top_k=search_k)
        total_before_filter = len(faiss_results)

        if not faiss_results:
            return [], 0

        chunk_ids = [res["chunk_id"] for res in faiss_results]
        db_chunks = db.get_chunks_by_ids(chunk_ids)
        chunk_dict = {c["id"]: c for c in db_chunks}

        workspace_doc_ids = set()
        if workspace_id:
            workspace_docs = db.get_documents_for_workspace(workspace_id)
            workspace_doc_ids = {d["id"] for d in workspace_docs}

        doc_meta_cache: Dict[str, Optional[Dict]] = {}

        def _filename_for(doc_id: str) -> str:
            if doc_id not in doc_meta_cache:
                meta = db.get_document_by_id(doc_id)
                doc_meta_cache[doc_id] = meta
            meta = doc_meta_cache[doc_id]
            return meta["filename"] if meta else "Unknown Document"

        relevant: List[Dict] = []
        for faiss_res in faiss_results:
            cid = faiss_res["chunk_id"]
            distance = faiss_res["distance"]

            if distance > MAX_L2_DISTANCE:
                continue
            if cid not in chunk_dict:
                continue

            chunk = chunk_dict[cid]
            if document_id and chunk["document_id"] != document_id:
                continue
            if workspace_id and chunk["document_id"] not in workspace_doc_ids:
                continue

            relevant.append(
                {
                    "document_id": chunk["document_id"],
                    "filename": _filename_for(chunk["document_id"]),
                    "chunk_id": cid,
                    "chunk_index": chunk["chunk_index"],
                    "page_number": chunk["page_number"],
                    "text": chunk["text"],
                    "similarity": round(distance, 4),
                }
            )

            if len(relevant) >= top_k:
                break

        return relevant, total_before_filter

    def _generate_followups(
        self,
        question: str,
        answer: str,
        chunks: List[Dict],
        mode: str,
    ) -> List[str]:
        """
        Make a lightweight LLM call to generate 2-3 follow-up questions
        based on the answer and available source context.
        """
        source_summary = ""
        if chunks:
            filenames = list({c.get("filename", "Unknown") for c in chunks})
            source_summary = f"\nAvailable sources: {', '.join(filenames)}"

        prompt = (
            f"You are a helpful research assistant. Based on the following "
            f"Q&A exchange, generate exactly 2-3 short follow-up questions "
            f"the user might want to ask next. Return ONLY the questions, "
            f"one per line, no numbering or bullets.\n\n"
            f"Original question: {question}\n"
            f"Answer provided: {answer[:800]}"
            f"{source_summary}\n\n"
            f"Follow-up questions:"
        )

        task = "research_analysis"
        raw = llm_service.generate_response(prompt, task=task)
        # Parse: take each non-empty line as a follow-up.
        followups: List[str] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            # Strip leading numbering/bullets if present.
            line = re.sub(r'^[\d\.\-\*\)\]]+\s*', '', line).strip()
            if line and len(line) > 5:
                followups.append(line)
            if len(followups) >= 3:
                break
        return followups

    def _active_provider_name(self) -> str:
        """Return a human-readable label for the active LLM provider."""
        try:
            names = llm_service.provider_names
            return names[0] if names else "unknown"
        except Exception:
            return "unknown"

    def _call_llm(
        self,
        *,
        question: str,
        mode: str,
        history: List[Dict],
        chunks: List[Dict],
        attachments: List[Dict],
    ) -> str:
        """
        Dispatches to Gemini. If conversation history or image attachments
        are present, uses the multi-turn chat path; otherwise falls back to
        the existing single-prompt path.
        """
        image_attachments = [
            a for a in (attachments or [])
            if (a.get("type") or "").lower() in ("photo", "image") and a.get("dataUrl")
        ]

        has_history = bool(history)
        use_chat_path = has_history or bool(image_attachments)

        if not use_chat_path:
            # Single-shot path. Cheaper, more deterministic for document-only Q&A.
            system_instruction, user_turn = compose_orbot_prompt(
                question=question,
                mode=mode,
                history=None,
                chunks=chunks,
                attachments=attachments,
            )
            prompt = system_instruction + "\n\n" + user_turn
            task = "coding" if mode == "project" else "research_analysis"
            return llm_service.generate_response(prompt, task=task)

        # Multi-turn chat path (with optional inline images).
        contents = build_chat_contents(
            question=question,
            mode=mode,
            history=history,
            chunks=chunks,
            attachments=attachments,
            llm_service=llm_service,
        )
        config = types.GenerateContentConfig(
            temperature=0.4,
            top_p=0.9,
            max_output_tokens=2048,
        )
        task = "coding" if mode == "project" else "research_analysis"
        return llm_service.generate_chat_response(contents, config=config, task=task)


rag_service = RAGService()


# ---------- User-facing research activity summary -------------------------

def _build_trace(
    chunks,
    used_doc_context: bool,
    mode_norm: str,
    insufficient_evidence: bool = False,
    high_relevance_chunks: int = 0,
    moderate_relevance_chunks: int = 0,
) -> str:
    """
    Concise, user-visible process trace. Not chain-of-thought. Shows what
    ORBOT looked at, NOT how it reasoned.
    """
    n = len(chunks or [])
    if n == 0:
        if insufficient_evidence:
            return "Insufficient evidence: no relevant sections found for this question."
        if used_doc_context is False and not chunks:
            return "No document context retrieved for this question."
        return "No relevant document sections were found."

    # Cross-document attribution: list distinct documents and their chunk counts.
    doc_chunks: Dict[str, int] = {}
    for c in chunks:
        fname = c.get("filename") or "Unknown Document"
        doc_chunks[fname] = doc_chunks.get(fname, 0) + 1

    distinct_docs = len(doc_chunks)
    doc_word = "document" if distinct_docs == 1 else "documents"

    parts = [f"Retrieved {n} section{'s' if n != 1 else ''} from {distinct_docs} {doc_word}."]
    for fname, count in doc_chunks.items():
        parts.append(f"  - {fname}: {count} section{'s' if count != 1 else ''}")

    relevance_note = f"({high_relevance_chunks} high-relevance"
    if moderate_relevance_chunks:
        relevance_note += f", {moderate_relevance_chunks} moderate-relevance"
    relevance_note += ")"
    parts.append(relevance_note)

    if insufficient_evidence:
        parts.append("Warning: evidence is weak for this question.")

    return "\n".join(parts)


def _confidence_label(
    high_relevance_chunks: int,
    moderate_relevance_chunks: int,
    insufficient_evidence: bool,
) -> str:
    """
    grounded   -> 3+ high-relevance chunks (distance < 1.2) AND no insufficient evidence
    partial    -> 1-2 high-relevance chunks OR 3+ moderate-relevance chunks
    unverified -> nothing retrieved or insufficient evidence
    """
    if insufficient_evidence:
        return "unverified"

    total_moderate = high_relevance_chunks + moderate_relevance_chunks

    if high_relevance_chunks >= 3:
        return "grounded"
    if high_relevance_chunks >= 1 or moderate_relevance_chunks >= 3:
        return "partial"
    if total_moderate >= 1:
        return "partial"
    return "unverified"
