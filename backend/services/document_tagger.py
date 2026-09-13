from __future__ import annotations
import logging
import os
import re
from typing import Optional
import httpx
import database.database as db
logger = logging.getLogger(__name__)
CANDIDATE_LABELS = ['survey paper', 'experimental research', 'thesis or dissertation', 'literature review', 'code repository', 'dataset', 'methodology', 'technical report']
HF_MODEL = os.getenv('HF_TAGGER_MODEL', 'facebook/bart-large-mnli')
_HEURISTIC_RULES = [('survey', ['survey', 'review of', 'systematic review']), ('experiment', ['experiment', 'empirical study', 'benchmark']), ('thesis', ['thesis', 'dissertation']), ('literature-review', ['literature review', 'related work']), ('code', ['github.com', 'import ', 'def ', 'function ']), ('dataset', ['dataset', 'corpus', 'we collected']), ('methodology', ['methodology', 'method', 'approach', 'framework']), ('report', ['technical report', 'white paper'])]

def _try_hf_inference(text: str) -> Optional[list[str]]:
    token = os.getenv('HF_TOKEN')
    if not token:
        return None
    try:
        resp = httpx.post(f'https://api-inference.huggingface.co/models/{HF_MODEL}', headers={'Authorization': f'Bearer {token}'}, json={'inputs': text[:1500], 'parameters': {'candidate_labels': CANDIDATE_LABELS}}, timeout=20.0)
        if resp.status_code != 200:
            logger.warning(f'HF tagger returned {resp.status_code}: {resp.text[:200]}')
            return None
        data = resp.json()
        if not isinstance(data, dict) or 'labels' not in data:
            return None
        labels = data.get('labels', [])
        scores = data.get('scores', [])
        chosen = []
        for label, score in zip(labels, scores):
            if score >= 0.35:
                slug = label.split()[0].lower().replace(',', '')
                if slug not in chosen:
                    chosen.append(slug)
            if len(chosen) >= 4:
                break
        return chosen
    except Exception as e:
        logger.warning(f'HF tagger call failed: {e}')
    return None

def _try_heuristic(text: str) -> list[str]:
    if not text:
        return []
    lower = text.lower()
    matches = []
    for tag, keywords in _HEURISTIC_RULES:
        if any((kw in lower for kw in keywords)):
            matches.append(tag)
    return matches[:4]

def tag_document(text: str) -> list[str]:
    if not text or len(text.strip()) < 50:
        return []
    result = _try_hf_inference(text)
    if result:
        logger.info(f'Tags via HF: {result}')
        return result
    result = _try_heuristic(text)
    logger.info(f'Tags via heuristic: {result}')
    return result

def tag_and_persist(document_id: str, text: str) -> None:
    try:
        tags = tag_document(text)
        if not tags:
            return
        existing = set(db.get_document_tags(document_id))
        new_tags = set((t.lower() for t in tags))
        for t in new_tags - existing:
            db.add_document_tag(document_id, t)
        for t in existing - new_tags:
            db.remove_document_tag(document_id, t)
        logger.info(f'Auto-tags persisted for {document_id}: {new_tags}')
    except Exception as e:
        logger.exception(f'Auto-tagging failed for {document_id}: {e}')
tagger = type('T', (), {})()
tagger.tag_document = staticmethod(tag_document)
tagger.tag_and_persist = staticmethod(tag_and_persist)
