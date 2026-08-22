"""
Document analysis service for KNO.

Provides per-document:
  - summary()    : grounded narrative summary
  - insights()   : structured JSON insights (key concepts, methodology,
                   findings, limitations, important observations)
  - sources()    : raw chunk-level source references

All outputs are grounded strictly in the document's own chunks. No
external knowledge is used; if a section cannot be answered from the
provided text, the service states that explicitly.
"""

import json
import logging
from typing import Dict, List, Optional

import database.database as db
from ai.llm_service import llm_service

logger = logging.getLogger(__name__)

# How many chunks to include in a single analysis prompt.
# 40 chunks * ~4000 chars ≈ 160k characters, well within Gemini 2.5 Flash
# context. Larger papers get stratified sampling below.
MAX_CHUNKS_IN_CONTEXT = 40

# Hard cap on total characters of chunk text we send per request.
MAX_CONTEXT_CHARS = 60000


# ---------- Helpers ---------------------------------------------------------

def _load_document_or_404(document_id: str) -> Dict:
    doc = db.get_document_by_id(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found.")
    return doc


def _get_chunks_sorted(document_id: str) -> List[Dict]:
    chunks = db.get_chunks_for_document(document_id)
    # Already sorted by chunk_index ASC in DB layer, but make explicit.
    chunks.sort(key=lambda c: c.get("chunk_index", 0))
    return chunks


def _stratified_sample(chunks: List[Dict], max_n: int) -> List[Dict]:
    """
    If a document has more than max_n chunks, take a representative sample:
    first K, middle K, last K — preserves abstract/introduction AND
    results/conclusion coverage.
    """
    if len(chunks) <= max_n:
        return chunks
    third = max_n // 3
    head = chunks[:third]
    mid_start = (len(chunks) - third) // 2
    middle = chunks[mid_start:mid_start + third]
    tail = chunks[-third:]
    # Deduplicate by id while preserving order.
    seen = set()
    result = []
    for c in head + middle + tail:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        result.append(c)
    return result


def _format_chunks_for_prompt(chunks: List[Dict]) -> str:
    """Format chunks as a numbered source list the LLM can cite."""
    blocks = []
    total_chars = 0
    for i, chunk in enumerate(chunks, 1):
        page = chunk.get("page_number")
        page_info = f" (page {page})" if page is not None else ""
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        block = f"[CHUNK {i}{page_info}]\n{text}"
        if total_chars + len(block) > MAX_CONTEXT_CHARS:
            # Append truncated version instead of skipping entirely.
            remaining = max(0, MAX_CONTEXT_CHARS - total_chars)
            if remaining > 200:
                block = block[:remaining] + "\n...[truncated]"
                blocks.append(block)
                total_chars += len(block)
            break
        blocks.append(block)
        total_chars += len(block)
    return "\n\n".join(blocks)


def _confidence_label(sources: List[Dict]) -> str:
    """
    Rough confidence label based on how much retrievable context we
    actually have. The frontend renders this as a small badge.
    """
    if not sources:
        return "unverified"
    if len(sources) >= 3:
        return "grounded"
    return "partial"


# ---------- Prompts ---------------------------------------------------------

_BASE_RULES = """You are ORBOT in DOCUMENT ANALYSIS mode.

The user has uploaded a research document. You will read the chunks
provided below and produce a grounded analysis.

NON-NEGOTIABLE RULES:
1. Use ONLY information that appears in the supplied chunks.
2. Do NOT invent citations, paper titles, authors, DOI numbers, URLs,
   page numbers, statistics, experimental results, dataset names, or
   methodology details.
3. If the document does not contain information needed to answer a
   section of the analysis, explicitly say so (e.g.,
   "The document does not report X.").
4. Quote phrases verbatim only when useful; otherwise paraphrase.
5. Distinguish what the document STATES (FACT) from what you are
   INTERPRETING from it (INFERENCE).
6. Never present an inference as if it were a stated fact.
7. Do NOT add information that is common knowledge but not in the
   supplied chunks. If you would do that, say "Not reported in the
   supplied chunks." instead.
8. Do NOT begin with pleasantries or meta-commentary about the task.
   Jump straight into the requested output.
"""

_SUMMARY_PROMPT = """{base}

TASK: Write a grounded summary of this document.

OUTPUT FORMAT (markdown):
- One short paragraph (2-4 sentences) titled "Executive summary".
- Then a section titled "What this document is about" with a 4-8
  sentence explanation aimed at a research student who has not read
  the paper.
- Then a section titled "Key contributions" with a bulleted list of
  the main contributions (2-5 bullets).
- Then a section titled "Methodology at a glance" with a 4-8 sentence
  description of how the work was carried out (datasets used,
  approach, evaluation if reported).
- Then a section titled "Findings" with a bulleted list of the main
  reported results (2-5 bullets). If the document does not report
  findings clearly, write "Not reported in the supplied chunks."

CONSTRAINTS:
- Length: aim for 250-450 words total.
- Do NOT reference chunk numbers in the output.
- Do NOT cite external sources.

=== DOCUMENT CHUNKS ===
{context}
=== END DOCUMENT CHUNKS ===

Begin now.
"""

_INSIGHTS_PROMPT = """{base}

TASK: Extract a structured set of insights from this document.

OUTPUT FORMAT (strict JSON, no markdown wrapper, no commentary):

{{
  "key_concepts": [
    {{ "concept": "<short name>", "why_it_matters": "<1 sentence grounded in the document>" }}
  ],
  "methodology": {{
    "approach": "<2-4 sentence description, OR 'Not reported in the supplied chunks.'>",
    "datasets": [{{ "name": "<dataset name or 'Not reported'>", "role": "<how used>" }}],
    "models_or_algorithms": [{{ "name": "<name>", "purpose": "<short>" }}],
    "evaluation": "<how the work was evaluated, OR 'Not reported.'>"
  }},
  "key_findings": [
    "<each finding a single sentence, grounded in the document>"
  ],
  "metrics": [
    {{ "metric": "<name>", "value": "<value or range>", "context": "<short>" }}
  ],
  "limitations": [
    "<each limitation a single sentence; quote near-verbatim when possible>"
  ],
  "important_observations": [
    "<each observation a single sentence; things a careful reader should notice>"
  ],
  "future_work": [
    "<each future-work item a single sentence, OR 'Not reported in the supplied chunks.'>"
  ]
}}

CONSTRAINTS:
- If a section is genuinely absent from the document, use empty arrays
  or the literal string "Not reported in the supplied chunks."
- Do NOT invent numbers, dataset names, or model names.
- Keep each string concise: one sentence per bullet maximum.
- Return ONLY valid JSON. Do NOT wrap it in ``` fences. Do NOT add any
  prose before or after the JSON.

=== DOCUMENT CHUNKS ===
{context}
=== END DOCUMENT CHUNKS ===
"""


# ---------- Public API ------------------------------------------------------

class DocumentAnalysisService:
    """Generates grounded per-document analyses (summary, insights, sources)."""

    # ---- sources ----
    def sources(self, document_id: str) -> Dict:
        """
        Returns the chunk-level source references for a document.
        No LLM call. Pure data layer.
        """
        doc = _load_document_or_404(document_id)
        chunks = _get_chunks_sorted(document_id)
        sources = [
            {
                "chunk_id": c["id"],
                "chunk_index": c["chunk_index"],
                "page_number": c.get("page_number"),
                "text": c["text"],
                "char_count": len(c.get("text") or ""),
            }
            for c in chunks
        ]
        return {
            "document": {
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "page_count": doc.get("page_count"),
            },
            "sources": sources,
            "total_chunks": len(sources),
            "confidence": _confidence_label(sources),
        }

    # ---- summary ----
    def summary(self, document_id: str) -> Dict:
        doc = _load_document_or_404(document_id)
        chunks = _stratified_sample(_get_chunks_sorted(document_id), MAX_CHUNKS_IN_CONTEXT)
        if not chunks:
            return {
                "document": {"id": doc["id"], "filename": doc["filename"]},
                "summary": "This document has no extractable text content.",
                "sources": [],
                "confidence": "unverified",
            }

        context = _format_chunks_for_prompt(chunks)
        prompt = _SUMMARY_PROMPT.format(base=_BASE_RULES, context=context)

        answer = llm_service.generate_response(prompt, task="summarization")

        return {
            "document": {"id": doc["id"], "filename": doc["filename"]},
            "summary": answer,
            "sources": [
                {
                    "chunk_id": c["id"],
                    "chunk_index": c["chunk_index"],
                    "page_number": c.get("page_number"),
                }
                for c in chunks
            ],
            "confidence": _confidence_label(chunks),
        }

    # ---- insights ----
    def insights(self, document_id: str) -> Dict:
        doc = _load_document_or_404(document_id)
        chunks = _stratified_sample(_get_chunks_sorted(document_id), MAX_CHUNKS_IN_CONTEXT)
        if not chunks:
            return {
                "document": {"id": doc["id"], "filename": doc["filename"]},
                "insights": _empty_insights(),
                "sources": [],
                "confidence": "unverified",
            }

        context = _format_chunks_for_prompt(chunks)
        prompt = _INSIGHTS_PROMPT.format(base=_BASE_RULES, context=context)

        raw = llm_service.generate_response(prompt, task="structured_extraction")

        parsed = self._parse_insights(raw)
        parsed.setdefault("key_concepts", [])
        parsed.setdefault("methodology", _empty_methodology())
        parsed.setdefault("key_findings", [])
        parsed.setdefault("metrics", [])
        parsed.setdefault("limitations", [])
        parsed.setdefault("important_observations", [])
        parsed.setdefault("future_work", [])

        return {
            "document": {"id": doc["id"], "filename": doc["filename"]},
            "insights": parsed,
            "sources": [
                {
                    "chunk_id": c["id"],
                    "chunk_index": c["chunk_index"],
                    "page_number": c.get("page_number"),
                }
                for c in chunks
            ],
            "confidence": _confidence_label(chunks),
        }

    # ---- internals ----
    @staticmethod
    def _parse_insights(raw: str) -> Dict:
        # Strip markdown fences if present
        text = (raw or "").strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"Insights JSON parse failed: {e}; raw head: {raw[:200]}")
        return {}


def _empty_methodology() -> Dict:
    return {
        "approach": "Not reported in the supplied chunks.",
        "datasets": [],
        "models_or_algorithms": [],
        "evaluation": "Not reported in the supplied chunks.",
    }


def _empty_insights() -> Dict:
    return {
        "key_concepts": [],
        "methodology": _empty_methodology(),
        "key_findings": [],
        "metrics": [],
        "limitations": [],
        "important_observations": [],
        "future_work": [],
    }


# Singleton
document_analysis_service = DocumentAnalysisService()
