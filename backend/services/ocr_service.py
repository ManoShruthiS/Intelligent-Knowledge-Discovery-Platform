from __future__ import annotations
import logging
import os
from typing import Optional
import httpx
import database.database as db
logger = logging.getLogger(__name__)
OCR_THRESHOLD_CHARS = 50

def _is_pdf(mime: str, filename: str) -> bool:
    if mime and 'pdf' in mime.lower():
        return True
    return filename.lower().endswith('.pdf')

def _is_image(mime: str, filename: str) -> bool:
    if mime and mime.lower().startswith('image/'):
        return True
    return any((filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')))

def _gemini_ocr(file_content: bytes, mime: str, filename: str) -> Optional[str]:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)
        model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        prompt = 'You are an OCR engine. Extract ALL the readable text from the attached document/image. Preserve paragraph breaks. Return ONLY the extracted text with no preamble, no commentary, no markdown fences. If you see no text, return an empty string.'
        response = client.models.generate_content(model=model, contents=[prompt, gtypes.Part.from_bytes(data=file_content, mime_type=mime or 'application/pdf')])
        text = (response.text or '').strip()
        if text:
            logger.info(f'Gemini OCR extracted {len(text)} chars from {filename}')
            return text
    except Exception as e:
        logger.warning(f'Gemini OCR failed for {filename}: {e}')
    return None

def _hf_trocr_ocr(file_content: bytes, filename: str) -> Optional[str]:
    token = os.getenv('HF_TOKEN')
    if not token:
        return None
    try:
        import base64
        b64 = base64.b64encode(file_content).decode('ascii')
        model = 'microsoft/trocr-base-handwritten'
        resp = httpx.post(f'https://api-inference.huggingface.co/models/{model}', headers={'Authorization': f'Bearer {token}'}, json={'inputs': b64}, timeout=30.0)
        if resp.status_code != 200:
            logger.warning(f'HF TrOCR returned {resp.status_code}: {resp.text[:200]}')
            return None
        data = resp.json()
        if isinstance(data, list) and data and ('generated_text' in data[0]):
            text = data[0]['generated_text'].strip()
            if text:
                logger.info(f'HF TrOCR extracted {len(text)} chars from {filename}')
                return text
    except Exception as e:
        logger.warning(f'HF TrOCR failed for {filename}: {e}')
    return None

def ocr_if_empty(doc_id: str, file_content: bytes, mime: str, filename: str, existing_text: str) -> dict:
    if existing_text and len(existing_text.strip()) >= OCR_THRESHOLD_CHARS:
        return {'status': 'skipped', 'provider': None, 'text': None}
    if _is_pdf(mime, filename) or _is_image(mime, filename):
        text = _gemini_ocr(file_content, mime or 'application/pdf', filename)
        if text and len(text.strip()) >= OCR_THRESHOLD_CHARS:
            _persist_ocr_result(doc_id, text, 'gemini')
            return {'status': 'ok', 'provider': 'gemini', 'text': text}
        if _is_image(mime, filename):
            text = _hf_trocr_ocr(file_content, filename)
            if text and len(text.strip()) >= OCR_THRESHOLD_CHARS:
                _persist_ocr_result(doc_id, text, 'hf')
                return {'status': 'ok', 'provider': 'hf', 'text': text}
    return {'status': 'failed', 'provider': None, 'text': None}

def _persist_ocr_result(doc_id: str, text: str, provider: str) -> None:
    try:
        db.update_document(doc_id, extracted_text=text, character_count=len(text))
        logger.info(f'OCR ({provider}) persisted {len(text)} chars for {doc_id}')
    except Exception as e:
        logger.exception(f'Failed to persist OCR result for {doc_id}: {e}')
ocr_service = type('O', (), {})()
ocr_service.ocr_if_empty = staticmethod(ocr_if_empty)
