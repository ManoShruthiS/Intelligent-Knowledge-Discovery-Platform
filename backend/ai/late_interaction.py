from __future__ import annotations
import logging
from typing import Dict, List, Sequence
from ai.embeddings import EmbeddingService
logger = logging.getLogger(__name__)

def _tokenize(text: str) -> List[str]:
    import re
    return [t for t in re.split('\\W+', (text or '').lower()) if t]

def _embed_tokens(embedder: EmbeddingService, tokens: Sequence[str]) -> List[List[float]]:
    if not tokens:
        return []
    try:
        return embedder.embed_texts(list(tokens))
    except Exception:
        return []

def _dot(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    return sum((float(a[i]) * float(b[i]) for i in range(n)))

def _vector_norm(v: List[float]) -> float:
    return sum((float(x) ** 2 for x in v)) ** 0.5

def _cosine(a: List[float], b: List[float]) -> float:
    na = _vector_norm(a)
    nb = _vector_norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)

def late_interaction_rerank(query: str, chunks: Sequence[Dict], top_k: int=5) -> List[Dict]:
    if not chunks:
        return []
    embedder = EmbeddingService()
    q_tokens = _tokenize(query)[:64]
    if not q_tokens:
        return list(chunks[:top_k])
    q_vecs = _embed_tokens(embedder, q_tokens)
    if not q_vecs:
        return list(chunks[:top_k])
    scored: List[Dict] = []
    for c in chunks[:max(top_k * 2, 10)]:
        c_tokens = _tokenize(c.get('text', ''))[:128]
        if not c_tokens:
            continue
        c_vecs = _embed_tokens(embedder, c_tokens)
        if not c_vecs:
            continue
        per_query_best = []
        for qv in q_vecs:
            best = max((_cosine(qv, cv) for cv in c_vecs), default=0.0)
            per_query_best.append(best)
        score = sum(per_query_best) / len(per_query_best) if per_query_best else 0.0
        new = dict(c)
        new['late_score'] = float(score)
        new['rerank_backend'] = (new.get('rerank_backend') or '') + '+late'
        scored.append(new)
    scored.sort(key=lambda c: float(c.get('late_score', 0.0)), reverse=True)
    return scored[:top_k]
