from __future__ import annotations
import json
import logging
import os
import sqlite3
import threading
from typing import Dict, List, Optional, Sequence
logger = logging.getLogger(__name__)
try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vector_store')
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, 'bm25_index.db')
_lock = threading.Lock()

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute("\n        CREATE VIRTUAL TABLE IF NOT EXISTS bm25_chunks\n        USING fts5(chunk_id UNINDEXED, document_id UNINDEXED,\n                   text, tokenize='porter unicode61')\n    ")
    return conn

class BM25Index:

    def __init__(self):
        self._docs: List[List[str]] = []
        self._meta: List[Dict] = []
        self._dirty = True

    def add_chunk(self, chunk_id: str, document_id: str, text: str) -> None:
        if not text:
            return
        with _lock:
            conn = _get_conn()
            try:
                conn.execute('DELETE FROM bm25_chunks WHERE chunk_id = ?', (chunk_id,))
                conn.execute('INSERT INTO bm25_chunks (chunk_id, document_id, text) VALUES (?, ?, ?)', (chunk_id, document_id, text))
                conn.commit()
            finally:
                conn.close()
            self._dirty = True

    def remove_document(self, document_id: str) -> None:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute('DELETE FROM bm25_chunks WHERE document_id = ?', (document_id,))
                conn.commit()
            finally:
                conn.close()
            self._dirty = True

    def remove_chunk(self, chunk_id: str) -> None:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute('DELETE FROM bm25_chunks WHERE chunk_id = ?', (chunk_id,))
                conn.commit()
            finally:
                conn.close()
            self._dirty = True

    def query(self, queries: Sequence[str], top_k: int=30, document_id: Optional[str]=None, workspace_id: Optional[str]=None) -> List[Dict]:
        queries = [q for q in queries if q and q.strip()]
        if not queries:
            return []
        self._maybe_reload()
        if not self._docs:
            return []
        workspace_doc_ids: Optional[set] = None
        if workspace_id:
            try:
                import database.database as _db
                workspace_doc_ids = {d['id'] for d in _db.get_documents_for_workspace(workspace_id)}
            except Exception:
                workspace_doc_ids = None
        scores = [0.0] * len(self._docs)
        for q in queries:
            tokens = _tokenize(q)
            if not tokens:
                continue
            if BM25Okapi is None:
                logger.debug('rank_bm25 unavailable; skipping BM25 query.')
                return []
            bm = BM25Okapi(self._docs)
            q_scores = bm.get_scores(tokens)
            for i, s in enumerate(q_scores):
                scores[i] += float(s)
        results: List[Dict] = []
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for idx in order:
            meta = self._meta[idx]
            if document_id and meta['document_id'] != document_id:
                continue
            if workspace_doc_ids is not None and meta['document_id'] not in workspace_doc_ids:
                continue
            results.append({'chunk_id': meta['chunk_id'], 'document_id': meta['document_id'], 'text': meta['text'], 'bm25_score': float(scores[idx])})
            if len(results) >= top_k:
                break
        return results

    def _maybe_reload(self) -> None:
        if not self._dirty:
            return
        with _lock:
            try:
                conn = _get_conn()
                cur = conn.execute('SELECT chunk_id, document_id, text FROM bm25_chunks')
                rows = cur.fetchall()
                conn.close()
            except Exception as exc:
                logger.warning('BM25 reload failed: %s', exc)
                rows = []
        docs: List[List[str]] = []
        meta: List[Dict] = []
        for chunk_id, document_id, text in rows:
            tokens = _tokenize(text or '')
            if not tokens:
                continue
            docs.append(tokens)
            meta.append({'chunk_id': chunk_id, 'document_id': document_id, 'text': text or ''})
        self._docs = docs
        self._meta = meta
        self._dirty = False

    def rebuild(self, chunks: Sequence[Dict]) -> None:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute('DELETE FROM bm25_chunks')
                conn.executemany('INSERT INTO bm25_chunks (chunk_id, document_id, text) VALUES (?, ?, ?)', [(c['id'], c['document_id'], c['text']) for c in chunks])
                conn.commit()
            finally:
                conn.close()
            self._dirty = True

def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in re.split('\\W+', text.lower()) if len(t) > 1]
import re

def reciprocal_rank_fusion(dense_lists: Sequence[Sequence[Dict]], sparse_lists: Sequence[Sequence[Dict]], dense_weight: float=0.6, rrf_k: int=60) -> List[Dict]:
    n_dense = max(1, len(dense_lists))
    n_sparse = max(1, len(sparse_lists))
    per_dense = dense_weight / n_dense
    per_sparse = (1.0 - dense_weight) / n_sparse
    scores: Dict[str, float] = {}
    flags: Dict[str, Dict[str, bool]] = {}

    def _ingest(lst: Sequence[Dict], weight: float):
        for rank, item in enumerate(lst):
            cid = item.get('chunk_id')
            if not cid:
                continue
            scores[cid] = scores.get(cid, 0.0) + weight / (rrf_k + rank + 1)
            flags.setdefault(cid, {'from_dense': False, 'from_sparse': False})
    for lst in dense_lists:
        for item in lst:
            cid = item.get('chunk_id')
            if cid:
                flags.setdefault(cid, {'from_dense': False, 'from_sparse': False})['from_dense'] = True
        _ingest(lst, per_dense)
    for lst in sparse_lists:
        for item in lst:
            cid = item.get('chunk_id')
            if cid:
                flags.setdefault(cid, {'from_dense': False, 'from_sparse': False})['from_sparse'] = True
        _ingest(lst, per_sparse)
    fused = []
    for cid, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        fused.append({'chunk_id': cid, 'rrf_score': score, **flags[cid]})
    return fused
bm25_index = BM25Index()

def hybrid_search(queries: Sequence[str], document_id: Optional[str]=None, workspace_id: Optional[str]=None, top_k: int=30) -> List[Dict]:
    return bm25_index.query(queries, top_k=top_k, document_id=document_id, workspace_id=workspace_id)
