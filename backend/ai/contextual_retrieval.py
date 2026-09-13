from __future__ import annotations
import json
import logging
import sqlite3
from typing import Dict, List, Optional
import database.database as db
from ai.llm_service import llm_service
logger = logging.getLogger(__name__)
CONTEXT_GENERATION_PROMPT = "You are an indexing assistant for a research\nretrieval system. Given a short document excerpt and a chunk of it, write a\nsingle concise sentence (≤ 30 words) that describes the document and where\nthe chunk sits within it. The goal is to give a future retriever the\ncontext it needs to decide if this chunk answers a user's question.\n\nDocument metadata:\n- Filename: {filename}\n- Author: {author}\n- Year: {year}\n- Document title: {title}\n\nDocument excerpt (first ~500 chars):\n{excerpt}\n\nChunk:\n{chunk}\n\nReply with ONLY the single context sentence — no preamble, no quotes."

def generate_chunk_context(*, filename: str, author: Optional[str], year: Optional[int], title: Optional[str], excerpt: str, chunk_text: str) -> Optional[str]:
    if not llm_service.is_configured:
        return None
    if not chunk_text or not chunk_text.strip():
        return None
    try:
        prompt = CONTEXT_GENERATION_PROMPT.format(filename=filename or 'Unknown', author=author or 'Unknown', year=year or 'Unknown', title=title or filename or 'Unknown', excerpt=(excerpt or '')[:500], chunk=(chunk_text or '')[:800])
        ctx = llm_service.generate_response(prompt, task='research_analysis')
        ctx = (ctx or '').strip().strip('"').strip("'")
        if not ctx or len(ctx) < 5:
            return None
        return ctx[:400]
    except Exception as exc:
        logger.warning('Context generation failed: %s', exc)
        return None

def _ensure_column():
    conn = db.get_connection()
    try:
        try:
            conn.execute('ALTER TABLE document_chunks ADD COLUMN context_prefix TEXT')
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()

def store_context_prefix(chunk_id: str, prefix: Optional[str]) -> None:
    _ensure_column()
    conn = db.get_connection()
    try:
        conn.execute('UPDATE document_chunks SET context_prefix = ? WHERE id = ?', (prefix, chunk_id))
        conn.commit()
    finally:
        conn.close()

def get_context_prefix(chunk_id: str) -> Optional[str]:
    _ensure_column()
    conn = db.get_connection()
    try:
        cur = conn.execute('SELECT context_prefix FROM document_chunks WHERE id = ?', (chunk_id,))
        row = cur.fetchone()
        return row['context_prefix'] if row else None
    finally:
        conn.close()

def get_context_prefixes_bulk(chunk_ids: List[str]) -> Dict[str, str]:
    _ensure_column()
    if not chunk_ids:
        return {}
    conn = db.get_connection()
    try:
        placeholders = ','.join(['?'] * len(chunk_ids))
        cur = conn.execute(f'SELECT id, context_prefix FROM document_chunks WHERE id IN ({placeholders})', chunk_ids)
        return {row['id']: row['context_prefix'] or '' for row in cur.fetchall()}
    finally:
        conn.close()

def text_with_prefix(chunk_id: str, chunk_text: str) -> str:
    prefix = get_context_prefix(chunk_id)
    if not prefix:
        return chunk_text
    return f'{prefix}\n\n{chunk_text}'

def contextualize_document_chunks(*, document_id: str, chunks: List[Dict], max_chunks: int=200) -> int:
    if not chunks:
        return 0
    doc = db.get_document_by_id(document_id)
    if not doc:
        return 0
    written = 0
    excerpt = (doc.get('extracted_text') or '')[:1500]
    for c in chunks[:max_chunks]:
        cid = c.get('id') if 'id' in c else None
        if not cid:
            try:
                rows = db.get_chunks_for_document(document_id)
                for row in rows:
                    if row.get('chunk_index') == c.get('chunk_index'):
                        cid = row['id']
                        break
            except Exception:
                cid = None
        if not cid:
            continue
        prefix = generate_chunk_context(filename=doc.get('filename') or '', author=doc.get('author'), year=doc.get('year'), title=doc.get('title') or doc.get('filename') or '', excerpt=excerpt, chunk_text=c.get('text', '') or '')
        if prefix:
            store_context_prefix(cid, prefix)
            written += 1
    return written
