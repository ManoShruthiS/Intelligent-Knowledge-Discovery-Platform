from __future__ import annotations
import json
import logging
import re
from typing import Dict, List, Optional
from ai.llm_service import llm_service
logger = logging.getLogger(__name__)
INSUFFICIENT_EVIDENCE_MESSAGE = "I couldn't find enough information about that in the selected document(s)."
_UNCERTAINTY_PHRASES = ("couldn't find", 'could not find', 'not enough information', "don't have enough", 'do not have enough', 'no information', 'not mentioned', 'unable to find')

def validate_lexical_grounding(answer: str, chunks: List[Dict]) -> Dict:
    if not answer or not answer.strip():
        return {'overlap_ratio': 0.0, 'model_claimed_unknown': False, 'sufficient_overlap': False}
    lowered = answer.lower()
    model_claimed_unknown = any((phrase in lowered for phrase in _UNCERTAINTY_PHRASES))
    if model_claimed_unknown or not chunks:
        return {'overlap_ratio': 0.0, 'model_claimed_unknown': model_claimed_unknown, 'sufficient_overlap': False}

    def _tokenize(text: str) -> List[str]:
        return [w.lower() for w in re.findall('\\b\\w{3,}\\b', text)]
    answer_tokens = set(_tokenize(answer))
    if not answer_tokens:
        return {'overlap_ratio': 0.0, 'model_claimed_unknown': False, 'sufficient_overlap': False}
    evidence_tokens: set[str] = set()
    for c in chunks:
        evidence_tokens.update(_tokenize(c.get('text', '')))
    overlap = len(answer_tokens & evidence_tokens) / len(answer_tokens)
    return {'overlap_ratio': round(overlap, 3), 'model_claimed_unknown': model_claimed_unknown, 'sufficient_overlap': overlap >= 0.15}
GROUNDING_CHECK_PROMPT = 'You are an evidence-grounding auditor.\n\nGiven a user\'s question, the assistant\'s answer, and a set of retrieved\ndocument chunks (numbered SOURCES), assess how well the answer is\ngrounded in the chunks.\n\nRespond with EXACTLY this JSON object (no other prose, no Markdown fences):\n\n{\n  "support_level": "high" | "partial" | "low" | "unsupported",\n  "supported_claims": ["short paraphrase 1", ...],\n  "unsupported_claims": ["short paraphrase 1", ...],\n  "note": "one short sentence explaining limits"\n}\n\nDefinitions:\n- "high": every meaningful claim in the answer is supported by at least\n  one SOURCE, and the sources actually support the claim.\n- "partial": most claims are supported, but a few specific claims are\n  not directly supported.\n- "low": the answer touches on the question but most specific claims are\n  not supported by the retrieved chunks.\n- "unsupported": the answer is essentially general knowledge with no\n  meaningful support from the chunks.\n\nRules:\n- Do NOT use the answer\'s claims as evidence for itself.\n- Each entry in supported_claims / unsupported_claims is a SHORT\n  paraphrase (≤ 15 words) — NOT the verbatim text.\n- The "note" should call out caveats (e.g. "Verification is heuristic;\n  some claims may be accurate but not directly present in the cited\n  sources.").\n'

def _format_chunks(chunks: List[Dict]) -> str:
    if not chunks:
        return '(No document chunks retrieved.)'
    parts = []
    for i, c in enumerate(chunks, 1):
        fname = c.get('filename') or 'Unknown'
        page = c.get('page_number')
        page_str = f' (page {page})' if page is not None else ''
        text = (c.get('text') or '').strip()
        if len(text) > 1200:
            text = text[:1200] + ' ...[truncated]'
        parts.append(f'SOURCE {i} — {fname}{page_str}\n{text}')
    return '\n\n'.join(parts)

def _parse_json_response(text: str) -> Optional[Dict]:
    cleaned = (text or '').strip()
    fence = re.search('```(?:json)?\\s*(\\{.*\\})\\s*```', cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except Exception:
        return None

def verify_grounding(*, question: str, answer: str, chunks: List[Dict]) -> Dict:
    empty = {'support_level': 'unsupported', 'supported_claims': [], 'unsupported_claims': [], 'note': 'No document chunks were retrieved, so grounding cannot be verified.', 'confidence': 'unverified'}
    if not answer or not answer.strip():
        return {**empty, 'note': 'Answer was empty.'}
    if not chunks:
        return empty
    user_prompt = f'USER QUESTION:\n{question.strip()}\n\nASSISTANT ANSWER:\n{answer.strip()[:6000]}\n\nRETRIEVED DOCUMENT CHUNKS:\n{_format_chunks(chunks)}\n\nRespond with the JSON object exactly as instructed.'
    prompt = GROUNDING_CHECK_PROMPT + '\n\n' + user_prompt
    try:
        raw = llm_service.generate_response(prompt, task='research_analysis')
    except Exception as exc:
        logger.warning(f'Grounding verification LLM call failed: {exc}')
        return {'support_level': 'low', 'supported_claims': [], 'unsupported_claims': [], 'note': 'Verification service could not run; review the answer against the cited sources manually.', 'confidence': 'partial'}
    parsed = _parse_json_response(raw)
    if not parsed:
        return {'support_level': 'low', 'supported_claims': [], 'unsupported_claims': [], 'note': 'Verification service returned an unparseable response; the answer should be reviewed manually.', 'confidence': 'partial'}
    level = str(parsed.get('support_level') or 'low').lower()
    if level not in ('high', 'partial', 'low', 'unsupported'):
        level = 'low'
    confidence_map = {'high': 'grounded', 'partial': 'partial', 'low': 'partial', 'unsupported': 'unverified'}
    supported = parsed.get('supported_claims') or []
    unsupported = parsed.get('unsupported_claims') or []
    note = str(parsed.get('note') or '').strip() or 'Verification is heuristic; cross-check important claims against the sources.'
    lexical = validate_lexical_grounding(answer, chunks)
    return {'support_level': level, 'supported_claims': [str(c).strip() for c in supported if str(c).strip()][:8], 'unsupported_claims': [str(c).strip() for c in unsupported if str(c).strip()][:8], 'note': note[:500], 'confidence': confidence_map[level], 'lexical_overlap': lexical['overlap_ratio'], 'model_claimed_unknown': lexical['model_claimed_unknown']}
