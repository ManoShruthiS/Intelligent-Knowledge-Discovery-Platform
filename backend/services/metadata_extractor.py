from __future__ import annotations
import json
import logging
import os
import re
from typing import Optional
import httpx
import database.database as db
from ai.llm_service import llm_service
logger = logging.getLogger(__name__)

class MetadataExtractionError(Exception):
    pass
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
HF_MODEL = os.getenv('HF_METADATA_MODEL', 'openai/gpt-oss-20b')
_METADATA_PROMPT = 'You are an academic metadata extractor for the KNO research platform.\n\nGiven the first ~2000 characters of a document, return EXACTLY AND ONLY a JSON\nobject with the following keys (use null when unknown):\n\n{{\n  "title":    "the document title or null",\n  "author":   "comma-separated author names or null",\n  "year":     2023\n}}\n\nRules:\n- Do NOT include any prose, markdown fences, or commentary.\n- If the text is too short or obviously not the start of a real document,\n  set every field to null.\n- Title should be the paper/article title, not the file name.\n\nText:\n"""{text}"""\n'
_SUMMARY_PROMPT = 'You are an academic document summarizer for the Intelligent Knowledge Discovery Platform.\n\nGiven the following text from a document, return EXACTLY AND ONLY a JSON\nobject with the following keys (use null when unknown):\n\n{{\n  "executive_summary": "A concise, high-level overview of the entire document (1-2 paragraphs).",\n  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],\n  "entities": ["Entity 1", "Entity 2", "Entity 3"],\n  "actionable_insights": "A short \'so what?\' explaining why this document matters or how its findings can be applied."\n}}\n\nRules:\n- Do NOT include any prose, markdown fences, or commentary.\n- `key_takeaways`: 3-5 critical bullet points.\n- `entities`: Important people, organizations, concepts, or technologies mentioned.\n- Ensure valid JSON.\n\nText:\n"""{text}"""\n'

def _try_groq(text: str) -> Optional[dict]:
    try:
        prompt = _METADATA_PROMPT.format(text=text[:2000])
        raw = llm_service.generate_response(prompt, task='structured_extraction')
        return _parse_response(raw)
    except Exception as e:
        logger.warning(f'Groq metadata extraction failed: {e}')
        return None

def _try_gemini(text: str) -> Optional[dict]:
    try:
        prompt = _METADATA_PROMPT.format(text=text[:2000])
        raw = llm_service.generate_response(prompt, task='structured_extraction')
        return _parse_response(raw)
    except Exception as e:
        logger.warning(f'Gemini metadata extraction failed: {e}')
        return None

def _try_hf_inference(text: str) -> Optional[dict]:
    token = os.getenv('HF_TOKEN')
    if not token:
        return None
    try:
        prompt = _METADATA_PROMPT.format(text=text[:1500])
        resp = httpx.post(f'https://api-inference.huggingface.co/models/{HF_MODEL}', headers={'Authorization': f'Bearer {token}'}, json={'inputs': prompt, 'parameters': {'max_new_tokens': 300, 'temperature': 0.1}}, timeout=30.0)
        if resp.status_code != 200:
            logger.warning(f'HF Inference API returned {resp.status_code}: {resp.text[:200]}')
            return None
        data = resp.json()
        if isinstance(data, list) and data and ('generated_text' in data[0]):
            raw = data[0]['generated_text']
            if prompt in raw:
                raw = raw.split(prompt, 1)[-1]
            return _parse_response(raw)
    except Exception as e:
        logger.warning(f'HF Inference metadata extraction failed: {e}')
    return None

def _parse_response(raw: str) -> Optional[dict]:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith('```'):
        text = re.sub('^```(?:json)?\\s*', '', text)
        text = re.sub('\\s*```\\s*$', '', text)
    match = re.search('\\{[\\s\\S]*\\}', text)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except Exception as e:
        logger.warning(f'Metadata JSON parse failed: {e}')
        return None
    return _normalise(data)

def _normalise(data: dict) -> Optional[dict]:
    if not isinstance(data, dict):
        return None
    out = {}
    out['title'] = _clean_str(data.get('title'), max_len=400)
    out['author'] = _clean_str(data.get('author'), max_len=400)
    out['abstract'] = _clean_str(data.get('abstract'), max_len=2000)
    out['year'] = _clean_year(data.get('year'))
    out['keywords'] = _clean_keywords(data.get('keywords'))
    return out

def _clean_str(value, max_len: int=200) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ('null', 'none', 'n/a', 'unknown'):
        return None
    return s[:max_len] if len(s) > max_len else s

def _clean_year(value) -> Optional[int]:
    if value is None:
        return None
    try:
        y = int(value)
        if 1800 <= y <= 2100:
            return y
    except (TypeError, ValueError):
        return None
    return None

def _clean_keywords(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    seen = set()
    for k in value:
        if not k:
            continue
        s = str(k).strip().lower()
        if not s or s in seen:
            continue
        seen.add(s)
        if len(s) > 50:
            continue
        out.append(s)
        if len(out) >= 8:
            break
    return out

def extract_metadata(text: str, file_type: str='') -> Optional[dict]:
    if not text or len(text.strip()) < 50:
        return None
    for provider_name, provider_fn in (('groq', _try_groq), ('gemini', _try_gemini), ('hf', _try_hf_inference)):
        result = provider_fn(text)
        if result:
            logger.info(f'Metadata extracted via {provider_name}')
            return result
    raise MetadataExtractionError('All metadata providers failed.')

def extract_and_persist(document_id: str, text: str, file_type: str='') -> None:
    try:
        meta = extract_metadata(text, file_type)
        if meta is None:
            db.update_document_metadata_status(document_id, 'skipped')
            return
        db.update_document_metadata(document_id, title=meta.get('title'), author=meta.get('author'), year=meta.get('year'), abstract=meta.get('abstract'), keywords=meta.get('keywords'))
        db.update_document_metadata_status(document_id, 'done')
        logger.info(f'Metadata persisted for document {document_id}')
    except MetadataExtractionError as e:
        logger.error(f'Metadata extraction permanently failed for {document_id}: {e}')
        db.update_document_metadata_status(document_id, 'failed')
    except Exception as e:
        logger.exception(f'Unexpected error extracting metadata for {document_id}: {e}')
        db.update_document_metadata_status(document_id, 'failed')

def generate_summary_and_insights(document_id: str, text: str) -> None:
    import json
    if not text or len(text.strip()) < 50:
        return
    try:
        prompt = _SUMMARY_PROMPT.format(text=text[:10000])
        raw = llm_service.generate_response(prompt, task='structured_extraction')
        data = _parse_response(raw)
        if data:
            abstract = _clean_str(data.get('executive_summary'), max_len=2000)
            keywords = _clean_keywords(data.get('entities'))
            db.update_document_metadata(document_id, abstract=abstract, keywords=keywords, insights=json.dumps(data))
            logger.info(f'Summary & Insights generated for document {document_id}')
    except Exception as e:
        logger.exception(f'Unexpected error generating summary for {document_id}: {e}')
        raise e
metadata_extractor = type('M', (), {})()
metadata_extractor.extract_metadata = staticmethod(extract_metadata)
metadata_extractor.extract_and_persist = staticmethod(extract_and_persist)
metadata_extractor.generate_summary_and_insights = staticmethod(generate_summary_and_insights)
