from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
from ai.config import COHERE_API_KEY, HF_TOKEN, JINA_API_KEY, KNO_BGE_RERANKER_MODEL, KNO_RERANKER, KNO_RERANK_TOP_K
logger = logging.getLogger(__name__)

class RerankerUnavailable(Exception):
    pass

@dataclass
class RerankResult:
    chunk_id: str
    text: str
    score: float
    metadata: Dict

    def as_dict(self) -> Dict:
        d = {'chunk_id': self.chunk_id, 'text': self.text, 'score': float(self.score)}
        if self.metadata:
            d.update(self.metadata)
        return d

class _BaseBackend:
    name = 'base'

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        raise NotImplementedError

class _IdentityBackend(_BaseBackend):
    name = 'identity'

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        ordered = sorted(chunks, key=lambda c: float(c.get('distance', c.get('score', 0.0)) or 0.0))
        out: List[Dict] = []
        for c in ordered[:top_k]:
            meta = {k: v for k, v in c.items() if k not in ('text',)}
            distance = float(c.get('distance', 0.0) or 0.0)
            score = max(0.0, min(1.0, 1.0 - distance / 2.0))
            out.append({'chunk_id': c.get('chunk_id'), 'text': c.get('text', ''), 'score': score, **meta, 'rerank_backend': 'identity'})
        return out

class _BgeLocalBackend(_BaseBackend):
    name = 'bge-local'

    def __init__(self, model_name: Optional[str]=None):
        self.model_name = model_name or KNO_BGE_RERANKER_MODEL
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RerankerUnavailable('sentence-transformers is required for the BGE reranker') from exc
            logger.info('Loading local reranker %s', self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        if not chunks:
            return []
        model = self._ensure_model()
        pairs = [(query, c.get('text', '') or '') for c in chunks]
        try:
            raw_scores = model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            raise RerankerUnavailable(f'BGE rerank failed: {exc}') from exc
        scored = list(zip(chunks, raw_scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)
        out: List[Dict] = []
        for c, score in scored[:top_k]:
            meta = {k: v for k, v in c.items() if k not in ('text',)}
            out.append({'chunk_id': c.get('chunk_id'), 'text': c.get('text', ''), 'score': float(score), **meta, 'rerank_backend': self.name})
        return out

class _HuggingFaceBackend(_BaseBackend):
    name = 'hf'

    def __init__(self, token: Optional[str]=None, model: Optional[str]=None):
        self.token = token or HF_TOKEN
        self.model = model or 'BAAI/bge-reranker-base'

    def _is_configured(self) -> bool:
        return bool(self.token)

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        if not self._is_configured():
            raise RerankerUnavailable('HF_TOKEN is not set; HF reranker unavailable.')
        if not chunks:
            return []
        try:
            import httpx
        except ImportError as exc:
            raise RerankerUnavailable('httpx is required for HF reranker') from exc
        payload = {'inputs': {'source_sentence': query, 'sentences': [c.get('text', '') or '' for c in chunks]}}
        headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        url = f'https://api-inference.huggingface.co/models/{self.model}'
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                scores = resp.json()
        except Exception as exc:
            raise RerankerUnavailable(f'HF rerank call failed: {exc}') from exc
        if not isinstance(scores, list) or len(scores) != len(chunks):
            raise RerankerUnavailable(f'HF rerank returned unexpected payload: {scores!r}')
        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)
        out: List[Dict] = []
        for c, score in scored[:top_k]:
            meta = {k: v for k, v in c.items() if k not in ('text',)}
            out.append({'chunk_id': c.get('chunk_id'), 'text': c.get('text', ''), 'score': float(score), **meta, 'rerank_backend': self.name})
        return out

class _CohereBackend(_BaseBackend):
    name = 'cohere'

    def __init__(self, api_key: Optional[str]=None, model: str='rerank-english-v3.0'):
        self.api_key = api_key or COHERE_API_KEY
        self.model = model

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _cohere_sdk_rerank(self, query, docs):
        import cohere
        client = cohere.Client(self.api_key)
        response = client.rerank(model=self.model, query=query, documents=[{'text': d} for d in docs], top_n=len(docs))
        return [r.relevance_score for r in response.results]

    def _http_rerank(self, query, docs):
        import httpx
        url = 'https://api.cohere.com/v1/rerank'
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        payload = {'model': self.model, 'query': query, 'documents': [{'text': d} for d in docs], 'top_n': len(docs)}
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        results = data.get('results') or []
        scores = [0.0] * len(docs)
        for r in results:
            idx = int(r.get('index', -1))
            if 0 <= idx < len(scores):
                scores[idx] = float(r.get('relevance_score', 0.0))
        return scores

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        if not self._is_configured():
            raise RerankerUnavailable('COHERE_API_KEY is not set; Cohere reranker unavailable.')
        if not chunks:
            return []
        docs = [c.get('text', '') or '' for c in chunks]
        try:
            try:
                scores = self._cohere_sdk_rerank(query, docs)
            except ImportError:
                scores = self._http_rerank(query, docs)
        except Exception as exc:
            raise RerankerUnavailable(f'Cohere rerank failed: {exc}') from exc
        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)
        out: List[Dict] = []
        for c, score in scored[:top_k]:
            meta = {k: v for k, v in c.items() if k not in ('text',)}
            out.append({'chunk_id': c.get('chunk_id'), 'text': c.get('text', ''), 'score': float(score), **meta, 'rerank_backend': self.name})
        return out

class _JinaBackend(_BaseBackend):
    name = 'jina'

    def __init__(self, api_key: Optional[str]=None, model: str='jina-reranker-v2-base-multilingual'):
        self.api_key = api_key or JINA_API_KEY
        self.model = model

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: int) -> List[Dict]:
        if not self._is_configured():
            raise RerankerUnavailable('JINA_API_KEY is not set; Jina reranker unavailable.')
        if not chunks:
            return []
        import httpx
        url = 'https://api.jina.ai/v1/rerank'
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        payload = {'model': self.model, 'query': query, 'documents': [c.get('text', '') or '' for c in chunks], 'top_n': len(chunks)}
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            raise RerankerUnavailable(f'Jina rerank failed: {exc}') from exc
        results = data.get('results') or []
        scores = [0.0] * len(chunks)
        for item in results:
            idx = int(item.get('index', -1))
            if 0 <= idx < len(scores):
                scores[idx] = float(item.get('relevance_score', 0.0))
        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)
        out: List[Dict] = []
        for c, score in scored[:top_k]:
            meta = {k: v for k, v in c.items() if k not in ('text',)}
            out.append({'chunk_id': c.get('chunk_id'), 'text': c.get('text', ''), 'score': float(score), **meta, 'rerank_backend': self.name})
        return out

class Reranker:

    def __init__(self, backend: Optional[str]=None, top_k: Optional[int]=None):
        chosen = (backend or KNO_RERANKER or 'none').lower()
        self.top_k = top_k or KNO_RERANK_TOP_K
        self.backend_name = chosen
        self._backend = self._build(chosen)
        self._fallback = _IdentityBackend()

    @staticmethod
    def _build(chosen: str) -> _BaseBackend:
        if chosen in ('', 'none', 'off', 'false', '0'):
            return _IdentityBackend()
        if chosen == 'bge-local':
            return _BgeLocalBackend()
        if chosen == 'hf':
            return _HuggingFaceBackend()
        if chosen == 'cohere':
            return _CohereBackend()
        if chosen == 'jina':
            return _JinaBackend()
        logger.warning('Unknown KNO_RERANKER=%r — using identity', chosen)
        return _IdentityBackend()

    @property
    def enabled(self) -> bool:
        return self.backend_name not in ('', 'none', 'off', 'false', '0', 'identity')

    def rerank(self, query: str, chunks: Sequence[Dict], top_k: Optional[int]=None) -> List[Dict]:
        if not chunks:
            return []
        k = top_k if top_k is not None else self.top_k
        k = max(1, min(k, len(chunks)))
        try:
            results = self._backend.rerank(query, chunks, k)
            if results:
                return results
        except RerankerUnavailable as exc:
            logger.warning('Reranker %s unavailable, falling back: %s', self.backend_name, exc)
        except Exception as exc:
            logger.exception('Reranker %s crashed; falling back: %s', self.backend_name, exc)
        return self._fallback.rerank(query, chunks, k)
reranker = Reranker()
