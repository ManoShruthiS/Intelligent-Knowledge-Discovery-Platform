from __future__ import annotations
import logging
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Sequence, Tuple
import database.database as db
from ai.config import KNO_HYBRID_DENSE_WEIGHT, KNO_HYBRID_SEARCH, KNO_LATE_INTERACTION, KNO_RERANKER
from ai.embeddings import EmbeddingService
from ai.grounding_service import verify_grounding
from ai.llm_service import llm_service
from ai.lost_in_middle import reorder_for_lost_in_middle
from ai.orbot_prompts import build_chat_contents, compose_orbot_prompt
from ai.reranker import reranker
from ai.vector_store import vector_store
from ai.query_understanding import analyse as analyse_question, choose_top_k
from ai.conversation_resolver import resolve as resolve_conversation
logger = logging.getLogger(__name__)
MAX_L2_DISTANCE = 1.75
HIGH_RELEVANCE_THRESHOLD = 1.2
INSUFFICIENT_EVIDENCE_DISTANCE = 1.5
DEFAULT_TOP_K = 5
MAX_TOP_K = 10

def _normalize_mode(mode: Optional[str]) -> str:
    if not mode:
        return 'research'
    m = mode.strip().lower()
    if m.startswith('proj'):
        return 'project'
    return 'research'

def _is_greeting(question: str) -> bool:
    greetings = {'hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening', 'you good', 'how are you', 'how are u', 'whats up', "what's up", 'who are you', 'what can you do', 'help', 'thanks', 'thank you', 'cool', 'ok', 'okay', 'awesome', 'great', 'are you good', 'you ok', 'you okay'}
    clean_q = re.sub('[^\\w\\s]', '', question.strip().lower())
    if clean_q in greetings:
        return True
    q_words = clean_q.split()
    return len(q_words) <= 4 and any((phrase in clean_q for phrase in ['you good', 'how are you', 'who are you', 'what can you do', 'whats up', 'what is your name', 'are you good', 'you ok']))

class RAGService:

    def __init__(self):
        self.embedder = EmbeddingService()

    def ask(self, question: str, document_id: Optional[str]=None, workspace_id: Optional[str]=None, top_k: int=DEFAULT_TOP_K, mode: Optional[str]='research', history: Optional[List[Dict]]=None, attachments: Optional[List[Dict]]=None, request_id: Optional[str]=None) -> Dict:
        if not question or not question.strip():
            raise ValueError('Question cannot be empty.')
        rid = request_id or _new_request_id()
        pipeline_start = time.perf_counter()
        understanding = analyse_question(question, user_top_k=top_k)
        resolution = resolve_conversation(question, history or [])
        effective_question = resolution.rewritten_question or understanding.rewritten_question
        if top_k != DEFAULT_TOP_K:
            adaptive_top_k = top_k
        else:
            adaptive_top_k = choose_top_k(understanding.intent)
        top_k = min(max(1, adaptive_top_k), MAX_TOP_K)
        mode_norm = _normalize_mode(mode)
        history = history or []
        attachments = attachments or []
        greeting = _is_greeting(question)
        page_range = _page_constraint_from_question(effective_question or question)
        _emit_request_log(rid, 'start', intent=understanding.intent, scope='workspace' if workspace_id else 'document' if document_id else 'home', mode=mode_norm, top_k=top_k, page_pin=str(page_range) if page_range else '-')
        if document_id:
            target_doc = db.get_document_by_id(document_id)
            if target_doc:
                doc_status = (target_doc.get('status') or '').lower()
                doc_text = (target_doc.get('extracted_text') or target_doc.get('text') or '').strip()
                if doc_status in ('processing', 'pending'):
                    answer = "Your document is still being processed. I'll be ready to answer questions about it once the analysis is complete."
                    total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
                    return {'answer': answer, 'user_question': question, 'effective_question': effective_question, 'sources': [], 'mode': mode_norm, 'used_doc_context': False, 'trace': 'Your document is still being processed.', 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': 0, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': 'document', 'request_id': rid, 'page_pin': None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': 0, 'llm_latency_ms': 0, 'total_latency_ms': total_ms, 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': None}}
                elif doc_status in ('failed', 'error') or not doc_text:
                    answer = "I couldn't access the extracted text for this document. Please retry the document analysis."
                    total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
                    return {'answer': answer, 'user_question': question, 'effective_question': effective_question, 'sources': [], 'mode': mode_norm, 'used_doc_context': False, 'trace': "I couldn't access the extracted text for this document.", 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': 0, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': 'document', 'request_id': rid, 'page_pin': None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': 0, 'llm_latency_ms': 0, 'total_latency_ms': total_ms, 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': None}}
        retrieval_start = time.perf_counter()
        retrieval_query = effective_question or question
        if greeting:
            chunks, total_before_filter = ([], 0)
        else:
            chunks, total_before_filter = self._retrieve(question=retrieval_query, document_id=document_id, workspace_id=workspace_id, top_k=top_k)
            if KNO_LATE_INTERACTION and chunks:
                try:
                    from ai.late_interaction import late_interaction_rerank
                    chunks = late_interaction_rerank(question=retrieval_query, chunks=chunks, top_k=top_k)
                except Exception as exc:
                    logger.debug('Late-interaction rerank skipped: %s', exc)
            if page_range and chunks:
                chunks, _ = _apply_page_pin(chunks, page_range)
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 1)
        high_relevance_chunks = sum((1 for c in chunks if c['similarity'] < HIGH_RELEVANCE_THRESHOLD))
        moderate_relevance_chunks = len(chunks) - high_relevance_chunks
        used_doc_context = bool(chunks)
        if greeting:
            insufficient_evidence = False
            trace = None
            confidence_label = None
        else:
            insufficient_evidence = not chunks or (chunks and chunks[0]['similarity'] > INSUFFICIENT_EVIDENCE_DISTANCE)
            trace = _build_trace(chunks, used_doc_context, mode_norm, insufficient_evidence, high_relevance_chunks, moderate_relevance_chunks)
            confidence_label = _confidence_label(high_relevance_chunks, moderate_relevance_chunks, insufficient_evidence)
        if document_id:
            scope_label = 'document'
        elif workspace_id:
            scope_label = 'workspace'
        else:
            scope_label = 'home'
        # Strict document scope: off-document questions get a redirect, never a
        # general-knowledge answer, so responses stay grounded in the upload.
        if insufficient_evidence and (document_id or workspace_id) and (not greeting):
            answer = 'This content is not in the uploaded document. Please ask about what is in the file.'
            total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
            return {'answer': answer, 'user_question': question, 'effective_question': effective_question, 'sources': [], 'mode': mode_norm, 'used_doc_context': False, 'trace': trace, 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': total_before_filter, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': scope_label, 'request_id': rid, 'page_pin': list(page_range) if page_range else None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': retrieval_ms, 'llm_latency_ms': 0, 'total_latency_ms': total_ms, 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': list(page_range) if page_range else None}}
        llm_start = time.perf_counter()
        try:
            answer = self._call_llm(question=effective_question, mode=mode_norm, history=history, chunks=chunks, attachments=attachments, intent=understanding.intent)
        except Exception:
            raise
        llm_ms = round((time.perf_counter() - llm_start) * 1000, 1)
        grounding = None
        if not greeting and chunks and answer and answer.strip() and llm_service.is_configured:
            try:
                grounding = verify_grounding(question=effective_question, answer=answer, chunks=chunks)
            except Exception as exc:
                logger.warning('Grounding verification failed: %s', exc)
        if grounding:
            confidence_label = grounding.get('confidence') or confidence_label
            insufficient_evidence = grounding.get('support_level') == 'unsupported'
        if document_id:
            scope_label = 'document'
        elif workspace_id:
            scope_label = 'workspace'
        else:
            scope_label = 'home'
        total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
        _emit_request_log(rid, 'done', intent=understanding.intent, scope=scope_label, chunks=len(chunks), total_ms=total_ms, confidence=confidence_label, insufficient_evidence=str(insufficient_evidence).lower())
        # Never show a sources footer for unverified / fallback answers.
        display_sources = [] if (insufficient_evidence or confidence_label == 'unverified' or _is_fallback_answer(answer)) else chunks
        display_used = bool(display_sources)
        return {'answer': answer, 'user_question': question, 'effective_question': effective_question, 'sources': display_sources, 'mode': mode_norm, 'used_doc_context': display_used, 'trace': trace, 'confidence': confidence_label, 'insufficient_evidence': insufficient_evidence, 'high_relevance_chunks': high_relevance_chunks, 'moderate_relevance_chunks': moderate_relevance_chunks, 'total_chunks_retrieved': total_before_filter, 'chunks_used': len(display_sources), 'grounding': grounding, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': scope_label, 'request_id': rid, 'page_pin': list(page_range) if page_range else None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': retrieval_ms, 'llm_latency_ms': llm_ms, 'total_latency_ms': total_ms, 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': list(page_range) if page_range else None}}

    def stream(self, question: str, document_id: Optional[str]=None, workspace_id: Optional[str]=None, top_k: int=DEFAULT_TOP_K, mode: Optional[str]='research', history: Optional[List[Dict]]=None, attachments: Optional[List[Dict]]=None, request_id: Optional[str]=None):
        if not question or not question.strip():
            yield {'type': 'error', 'detail': 'Question cannot be empty.'}
            return
        rid = request_id or _new_request_id()
        pipeline_start = time.perf_counter()
        understanding = analyse_question(question, user_top_k=top_k)
        resolution = resolve_conversation(question, history or [])
        effective_question = resolution.rewritten_question or understanding.rewritten_question
        if top_k != DEFAULT_TOP_K:
            adaptive_top_k = top_k
        else:
            adaptive_top_k = choose_top_k(understanding.intent)
        yield {'type': 'thinking', 'stage': 'searching', 'label': 'Searching documents…', 'request_id': rid}
        top_k = min(max(1, adaptive_top_k), MAX_TOP_K)
        mode_norm = _normalize_mode(mode)
        history = history or []
        attachments = attachments or []
        greeting = _is_greeting(question)
        page_range = _page_constraint_from_question(effective_question or question)
        _emit_request_log(rid, 'start.stream', intent=understanding.intent, scope='workspace' if workspace_id else 'document' if document_id else 'home', mode=mode_norm, top_k=top_k, page_pin=str(page_range) if page_range else '-')
        if document_id:
            target_doc = db.get_document_by_id(document_id)
            if target_doc:
                doc_status = (target_doc.get('status') or '').lower()
                doc_text = (target_doc.get('extracted_text') or target_doc.get('text') or '').strip()
                if doc_status in ('processing', 'pending'):
                    answer_text = "Your document is still being processed. I'll be ready to answer questions about it once the analysis is complete."
                    yield {'type': 'token', 'text': answer_text, 'request_id': rid}
                    yield {'type': 'meta', 'request_id': rid, 'sources': [], 'trace': 'Your document is still being processed.', 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': 0, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': 'document', 'page_pin': None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': 0, 'llm_latency_ms': 0, 'total_latency_ms': round((time.perf_counter() - pipeline_start) * 1000, 1), 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': None, 'request_id': rid}}
                    yield {'type': 'done', 'answer': answer_text, 'request_id': rid}
                    return
                elif doc_status in ('failed', 'error') or not doc_text:
                    answer_text = "I couldn't access the extracted text for this document. Please retry the document analysis."
                    yield {'type': 'token', 'text': answer_text, 'request_id': rid}
                    yield {'type': 'meta', 'request_id': rid, 'sources': [], 'trace': "I couldn't access the extracted text for this document.", 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': 0, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': 'document', 'page_pin': None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': 0, 'llm_latency_ms': 0, 'total_latency_ms': round((time.perf_counter() - pipeline_start) * 1000, 1), 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': None, 'request_id': rid}}
                    yield {'type': 'done', 'answer': answer_text, 'request_id': rid}
                    return
        retrieval_start = time.perf_counter()
        retrieval_query = effective_question or question
        if greeting:
            chunks, total_before_filter = ([], 0)
        else:
            chunks, total_before_filter = self._retrieve(question=retrieval_query, document_id=document_id, workspace_id=workspace_id, top_k=top_k)
            if KNO_LATE_INTERACTION and chunks:
                try:
                    from ai.late_interaction import late_interaction_rerank
                    chunks = late_interaction_rerank(question=retrieval_query, chunks=chunks, top_k=top_k)
                except Exception as exc:
                    logger.debug('Late-interaction rerank skipped: %s', exc)
            if page_range and chunks:
                chunks, _ = _apply_page_pin(chunks, page_range)
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 1)
        if not greeting and chunks:
            yield {'type': 'thinking', 'stage': 'analyzing', 'label': f"Analyzing {len(chunks)} passage{('s' if len(chunks) != 1 else '')}…", 'candidate_count': len(chunks), 'request_id': rid}
        elif not greeting:
            yield {'type': 'thinking', 'stage': 'analyzing', 'label': 'Looking for relevant material…', 'request_id': rid}
        high_relevance_chunks = sum((1 for c in chunks if c['similarity'] < HIGH_RELEVANCE_THRESHOLD))
        moderate_relevance_chunks = len(chunks) - high_relevance_chunks
        used_doc_context = bool(chunks)
        if greeting:
            insufficient_evidence = False
            trace = None
            confidence_label = None
        else:
            insufficient_evidence = not chunks or (chunks and chunks[0]['similarity'] > INSUFFICIENT_EVIDENCE_DISTANCE)
            trace = _build_trace(chunks, used_doc_context, mode_norm, insufficient_evidence, high_relevance_chunks, moderate_relevance_chunks)
            confidence_label = _confidence_label(high_relevance_chunks, moderate_relevance_chunks, insufficient_evidence)
        if document_id:
            scope_label = 'document'
        elif workspace_id:
            scope_label = 'workspace'
        else:
            scope_label = 'home'
        # Strict document scope: off-document questions get a redirect, never a
        # general-knowledge answer, so responses stay grounded in the upload.
        if insufficient_evidence and (document_id or workspace_id) and (not greeting):
            answer_text = 'This content is not in the uploaded document. Please ask about what is in the file.'
            yield {'type': 'token', 'text': answer_text, 'request_id': rid}
            yield {'type': 'meta', 'request_id': rid, 'sources': [], 'trace': trace, 'confidence': 'unverified', 'insufficient_evidence': True, 'high_relevance_chunks': 0, 'moderate_relevance_chunks': 0, 'total_chunks_retrieved': total_before_filter, 'chunks_used': 0, 'grounding': None, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': scope_label, 'page_pin': list(page_range) if page_range else None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': retrieval_ms, 'llm_latency_ms': 0, 'total_latency_ms': round((time.perf_counter() - pipeline_start) * 1000, 1), 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': list(page_range) if page_range else None, 'request_id': rid}}
            yield {'type': 'done', 'answer': answer_text, 'request_id': rid}
            return
        yield {'type': 'thinking', 'stage': 'generating', 'label': 'Writing answer…', 'request_id': rid}
        llm_start = time.perf_counter()
        answer_chunks: List[str] = []
        try:
            for chunk_text in self._call_llm_stream(question=effective_question, mode=mode_norm, history=history, chunks=chunks, attachments=attachments, intent=understanding.intent):
                if not chunk_text:
                    continue
                answer_chunks.append(chunk_text)
                yield {'type': 'token', 'text': chunk_text, 'request_id': rid}
        except Exception as exc:
            logger.exception('Streaming LLM call failed')
            yield {'type': 'error', 'detail': str(exc) or 'Streaming generation failed.', 'request_id': rid}
            return
        llm_ms = round((time.perf_counter() - llm_start) * 1000, 1)
        answer_text = ''.join(answer_chunks)
        grounding = None
        if not greeting and chunks and answer_text and llm_service.is_configured:
            try:
                grounding = verify_grounding(question=effective_question, answer=answer_text, chunks=chunks)
            except Exception as exc:
                logger.warning('Grounding verification failed: %s', exc)
        if grounding:
            confidence_label = grounding.get('confidence') or confidence_label
            insufficient_evidence = grounding.get('support_level') == 'unsupported'
        if document_id:
            scope_label = 'document'
        elif workspace_id:
            scope_label = 'workspace'
        else:
            scope_label = 'home'
        total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
        _emit_request_log(rid, 'done.stream', intent=understanding.intent, scope=scope_label, chunks=len(chunks), total_ms=total_ms, confidence=confidence_label)
        # Never show a sources footer for unverified / fallback answers.
        display_sources = [] if (insufficient_evidence or confidence_label == 'unverified' or _is_fallback_answer(answer_text)) else chunks
        yield {'type': 'meta', 'request_id': rid, 'sources': display_sources, 'trace': trace, 'confidence': confidence_label, 'insufficient_evidence': insufficient_evidence, 'high_relevance_chunks': high_relevance_chunks, 'moderate_relevance_chunks': moderate_relevance_chunks, 'total_chunks_retrieved': total_before_filter, 'chunks_used': len(display_sources), 'grounding': grounding, 'intent': understanding.intent, 'resolved_topics': list(resolution.resolved_topics), 'followup_resolution': {'confident': list(resolution.confident_topics), 'ambiguous': list(resolution.ambiguous_resolutions)}, 'scope': scope_label, 'page_pin': list(page_range) if page_range else None, 'provider_status': llm_service.provider_status(), 'metadata': {'provider': self._active_provider_name(), 'retrieval_latency_ms': retrieval_ms, 'llm_latency_ms': llm_ms, 'total_latency_ms': total_ms, 'late_interaction': bool(KNO_LATE_INTERACTION), 'page_pin': list(page_range) if page_range else None, 'request_id': rid}}
        yield {'type': 'done', 'answer': answer_text, 'request_id': rid}

    def _retrieve(self, question: str, document_id: Optional[str], workspace_id: Optional[str], top_k: int) -> Tuple[List[Dict], int]:
        all_candidates: List[Dict] = []
        try:
            query_embedding = self.embedder.embed_text(question)
            search_k = top_k * (3 if document_id or workspace_id else 1)
            faiss_results = vector_store.search(query_embedding, top_k=search_k)
        except Exception as exc:
            logger.warning('FAISS search failed: %s', exc)
            faiss_results = []
        chunk_ids = [r['chunk_id'] for r in faiss_results]
        db_chunks = db.get_chunks_by_ids(chunk_ids)
        chunk_dict = {c['id']: c for c in db_chunks}
        workspace_doc_ids: set = set()
        if workspace_id:
            workspace_doc_ids = {d['id'] for d in db.get_documents_for_workspace(workspace_id)}
        doc_meta_cache: Dict[str, Optional[Dict]] = {}

        def _filename_for(doc_id: str) -> str:
            if doc_id not in doc_meta_cache:
                meta_doc = db.get_document_by_id(doc_id)
                doc_meta_cache[doc_id] = meta_doc
            m = doc_meta_cache[doc_id]
            return m['filename'] if m else 'Unknown Document'
        for r in faiss_results:
            cid = r['chunk_id']
            distance = r['distance']
            if distance > MAX_L2_DISTANCE:
                continue
            chunk = chunk_dict.get(cid)
            if not chunk:
                continue
            if document_id and chunk['document_id'] != document_id:
                continue
            if workspace_id and chunk['document_id'] not in workspace_doc_ids:
                continue
            all_candidates.append({'document_id': chunk['document_id'], 'filename': _filename_for(chunk['document_id']), 'chunk_id': cid, 'chunk_index': chunk['chunk_index'], 'page_number': chunk['page_number'], 'text': chunk['text'], 'similarity': round(distance, 4), 'distance': distance})
        if KNO_HYBRID_SEARCH and KNO_HYBRID_SEARCH != 'off':
            try:
                from ai.hybrid_search import hybrid_search, reciprocal_rank_fusion
                bm25_results = hybrid_search([question], document_id=document_id, workspace_id=workspace_id, top_k=max(top_k, 30))
                fused = reciprocal_rank_fusion(dense_lists=[all_candidates], sparse_lists=[bm25_results], dense_weight=KNO_HYBRID_DENSE_WEIGHT)
                by_id = {c['chunk_id']: c for c in all_candidates}
                rebuilt: List[Dict] = []
                for rank, item in enumerate(fused[:max(top_k, 30) * 2]):
                    cid = item.get('chunk_id')
                    if not cid:
                        continue
                    if cid in by_id:
                        base = dict(by_id[cid])
                        base['rrf_score'] = float(item.get('rrf_score', 0.0))
                        rebuilt.append(base)
                    else:
                        rows = db.get_chunks_by_ids([cid])
                        if not rows:
                            continue
                        row = rows[0]
                        if document_id and row['document_id'] != document_id:
                            continue
                        if workspace_id:
                            if not workspace_doc_ids:
                                workspace_doc_ids = {d['id'] for d in db.get_documents_for_workspace(workspace_id)}
                            if row['document_id'] not in workspace_doc_ids:
                                continue
                        doc = db.get_document_by_id(row['document_id'])
                        rebuilt.append({'document_id': row['document_id'], 'filename': doc['filename'] if doc else 'Unknown Document', 'chunk_id': cid, 'chunk_index': row['chunk_index'], 'page_number': row['page_number'], 'text': row['text'], 'similarity': 1.5, 'distance': 1.5, 'rrf_score': float(item.get('rrf_score', 0.0)), 'from_bm25': True})
                all_candidates = rebuilt
            except Exception as exc:
                logger.warning('Hybrid search failed; falling back to dense-only: %s', exc)
        total_before_filter = len(all_candidates)
        deduped: Dict[str, Dict] = {}
        for c in all_candidates:
            cid = c['chunk_id']
            if cid not in deduped or c.get('distance', 1000000000.0) < deduped[cid].get('distance', 1000000000.0):
                deduped[cid] = c
        merged = list(deduped.values())
        if reranker.enabled and merged:
            try:
                ranked = reranker.rerank(question, merged, top_k=max(top_k, 8))
                normalized: List[Dict] = []
                for r in ranked:
                    cid = r['chunk_id']
                    base = deduped.get(cid, {}).copy()
                    base.update({'chunk_id': cid, 'text': r.get('text', base.get('text', '')), 'similarity': round(float(r.get('score', 0.0)), 4), 'distance': 1.5 - float(r.get('score', 0.0)), 'rerank_score': float(r.get('score', 0.0)), 'rerank_backend': r.get('rerank_backend', '')})
                    normalized.append(base)
                merged = normalized
            except Exception as exc:
                logger.warning('Reranker crashed: %s', exc)
        if merged:
            try:
                merged = reorder_for_lost_in_middle(merged)
            except Exception as exc:
                logger.warning('Lost-in-middle reorder failed: %s', exc)
        merged = merged[:top_k]
        return (merged, total_before_filter)

    def _call_llm(self, *, question: str, mode: str, history: List[Dict], chunks: List[Dict], attachments: List[Dict], intent: Optional[str]=None) -> str:
        image_attachments = [a for a in attachments or [] if (a.get('type') or '').lower() in ('photo', 'image') and a.get('dataUrl')]
        has_history = bool(history)
        use_chat_path = has_history or bool(image_attachments)
        is_first_turn = not has_history
        if not use_chat_path:
            system_instruction, user_turn = compose_orbot_prompt(question=question, mode=mode, history=None, chunks=chunks, attachments=attachments, is_first_turn=is_first_turn, intent=intent)
            prompt = system_instruction + '\n\n' + user_turn
            task = 'coding' if mode == 'project' else 'research_analysis'
            return llm_service.generate_response(prompt, task=task)
        contents = build_chat_contents(question=question, mode=mode, history=history, chunks=chunks, attachments=attachments, llm_service=llm_service, is_first_turn=is_first_turn, intent=intent)
        from google.genai import types as gtypes
        config = gtypes.GenerateContentConfig(temperature=0.4, top_p=0.9, max_output_tokens=2048)
        task = 'coding' if mode == 'project' else 'research_analysis'
        return llm_service.generate_chat_response(contents, config=config, task=task)

    def _call_llm_stream(self, *, question: str, mode: str, history: List[Dict], chunks: List[Dict], attachments: List[Dict], intent: Optional[str]=None):
        image_attachments = [a for a in attachments or [] if (a.get('type') or '').lower() in ('photo', 'image') and a.get('dataUrl')]
        has_history = bool(history)
        use_chat_path = has_history or bool(image_attachments)
        is_first_turn = not has_history
        if not use_chat_path:
            system_instruction, user_turn = compose_orbot_prompt(question=question, mode=mode, history=None, chunks=chunks, attachments=attachments, is_first_turn=is_first_turn, intent=intent)
            prompt = system_instruction + '\n\n' + user_turn
            task = 'coding' if mode == 'project' else 'research_analysis'
            yield from llm_service.generate_response_stream(prompt, task=task)
            return
        contents = build_chat_contents(question=question, mode=mode, history=history, chunks=chunks, attachments=attachments, llm_service=llm_service, is_first_turn=is_first_turn, intent=intent)
        from google.genai import types as gtypes
        config = gtypes.GenerateContentConfig(temperature=0.4, top_p=0.9, max_output_tokens=2048)
        task = 'coding' if mode == 'project' else 'research_analysis'
        yield from llm_service.generate_chat_response_stream(contents, config=config, task=task)

    def _active_provider_name(self) -> str:
        try:
            names = llm_service.provider_names
            return names[0] if names else 'unknown'
        except Exception:
            return 'unknown'

def insufficient_evidence_after(chunks: List[Dict]) -> bool:
    if not chunks:
        return True
    top = chunks[0]
    if 'rerank_score' in top:
        return float(top['rerank_score']) < 0.2
    return float(top.get('distance', 1000000000.0)) > INSUFFICIENT_EVIDENCE_DISTANCE

def _build_trace(chunks, used_doc_context: bool, mode_norm: str, insufficient_evidence: bool=False, high_relevance_chunks: int=0, moderate_relevance_chunks: int=0) -> str:
    n = len(chunks or [])
    if n == 0:
        if insufficient_evidence:
            return 'Insufficient evidence: no relevant sections found for this question.'
        if not used_doc_context:
            return 'No document context retrieved for this question.'
        return 'No relevant document sections were found.'
    doc_chunks: Dict[str, int] = {}
    for c in chunks:
        fname = c.get('filename') or 'Unknown Document'
        doc_chunks[fname] = doc_chunks.get(fname, 0) + 1
    distinct_docs = len(doc_chunks)
    doc_word = 'document' if distinct_docs == 1 else 'documents'
    parts = [f"Retrieved {n} section{('s' if n != 1 else '')} from {distinct_docs} {doc_word}."]
    for fname, count in doc_chunks.items():
        parts.append(f"  - {fname}: {count} section{('s' if count != 1 else '')}")
    relevance_note = f'({high_relevance_chunks} high-relevance'
    if moderate_relevance_chunks:
        relevance_note += f', {moderate_relevance_chunks} moderate-relevance'
    relevance_note += ')'
    parts.append(relevance_note)
    if insufficient_evidence:
        parts.append('Warning: evidence is weak for this question.')
    return '\n'.join(parts)

def _is_fallback_answer(answer: Optional[str]) -> bool:
    if not answer:
        return False
    low = answer.lower()
    markers = ("couldn't find sufficient evidence", 'temporarily unavailable (likely rate-limit', 'no llm provider is configured', 'no document context retrieved')
    return any(m in low for m in markers)

def _confidence_label(high_relevance_chunks: int, moderate_relevance_chunks: int, insufficient_evidence: bool) -> str:
    if insufficient_evidence:
        return 'unverified'
    total_moderate = high_relevance_chunks + moderate_relevance_chunks
    if high_relevance_chunks >= 3:
        return 'grounded'
    if high_relevance_chunks >= 1 or moderate_relevance_chunks >= 3:
        return 'partial'
    if total_moderate >= 1:
        return 'partial'
    return 'unverified'
INTENT_TEMPLATE_FRAGMENTS = {'definition': 'Structure your answer as:\n  - One-sentence definition up top (the user\'s underlying need).\n  - 2–4 short elaboration paragraphs that unpack the definition.\n  - A concise "Related in this document" line pointing to the closest\n    passages if relevant.\n', 'comparison': 'Structure your answer as a comparison:\n  - A short framing sentence.\n  - One bullet block per item being compared, each grounded in\n    citations, naming what THAT item says.\n  - A "Key differences" subsection synthesising across items.\n  - A "Synthesis" sentence at the end if the documents converge.\n', 'data': 'Treat this as a numerical question. Structure your answer as:\n  - The exact value(s) requested first, with units.\n  - The model / method, dataset, and metric that produced each number.\n  - Keep enough surrounding context so the number is not floating —\n    "X achieved Y on dataset Z" is safer than just "Y".\n', 'method': 'Structure your answer as a methodology walkthrough:\n  - State the method\'s name and one-line purpose.\n  - Walk through the steps in the same order they appear in the\n    source material, citing each step.\n  - Close with a "When this is used" line.\n', 'how_to': 'Structure your answer as a procedural walkthrough:\n  - A short intent statement (what we\'re trying to do).\n  - Numbered steps, each one concrete and self-contained.\n  - A single "Verification" step at the end (how to check it worked).\n', 'findings': 'Structure your answer around the reported findings:\n  - State the headline finding first.\n  - List supporting findings as short bullets, each grounded.\n  - Mention any limitations or caveats the source documents call out.\n', 'explanation': 'Structure your answer as an explanation:\n  - Begin with the mechanism in plain English.\n  - Then walk through the underlying reasoning step by step.\n  - Cite the source passages that justify each step.\n', 'section': "The user is asking about a specific section / page / figure. Honour\nthat constraint — answer ONLY from that section / page where\npossible. If the section's content doesn't cover the question,\nsay so explicitly rather than widening the answer.\n", 'general': 'Answer the question directly. Lead with the substance, then add\nnuance / caveats if the source material supports them.\n'}

def template_for_intent(intent: Optional[str]) -> str:
    return INTENT_TEMPLATE_FRAGMENTS.get((intent or 'general').lower(), INTENT_TEMPLATE_FRAGMENTS['general'])

def _new_request_id() -> str:
    return uuid.uuid4().hex[:12]

def _emit_request_log(request_id: str, event: str, **fields) -> None:
    bits = [f'rid={request_id}', f'event={event}']
    for k, v in fields.items():
        bits.append(f'{k}={v}')
    logger.info('[orbot] ' + ' '.join(bits))

def _page_constraint_from_question(question: str) -> Optional[Tuple[int, int]]:
    if not question:
        return None
    m_range = re.search('\\bpages?\\s+(\\d+)\\s*(?:[-–]\\s*(\\d+))?\\b', question, re.IGNORECASE)
    if not m_range:
        return None
    try:
        a = int(m_range.group(1))
        b = int(m_range.group(2)) if m_range.group(2) else a
        return (min(a, b), max(a, b))
    except (TypeError, ValueError):
        return None

def _apply_page_pin(chunks: List[Dict], page_range: Optional[Tuple[int, int]]) -> Tuple[List[Dict], List[Dict]]:
    if not chunks or not page_range:
        return (chunks, [])
    lo, hi = page_range
    pinned: List[Dict] = []
    rest: List[Dict] = []
    for c in chunks:
        page = c.get('page_number')
        if page is None:
            rest.append(c)
            continue
        try:
            p = int(page)
        except (TypeError, ValueError):
            rest.append(c)
            continue
        if lo <= p <= hi:
            pinned.append(c)
        else:
            rest.append(c)
    return (pinned + rest, [])
rag_service = RAGService()
