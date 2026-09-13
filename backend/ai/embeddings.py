from __future__ import annotations
import logging
import os
from typing import List
from ai.config import HF_TOKEN, JINA_API_KEY, KNO_EMBEDDING_MODEL
logger = logging.getLogger(__name__)
_KNOWN_MODELS = {'minilm': {'dim': 384, 'hf_repo': 'sentence-transformers/all-MiniLM-L6-v2'}, 'bge-large': {'dim': 1024, 'hf_repo': 'BAAI/bge-large-en-v1.5'}}

class EmbeddingService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._backend_kind = ''
            cls._instance._model = None
            cls._instance._dim = 0
            cls._instance._model_name = ''
        return cls._instance

    def _initialize(self):
        self._initialized = True

    @property
    def dim(self) -> int:
        self._resolve()
        return self._dim

    @property
    def model_name(self) -> str:
        self._resolve()
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        if not text:
            raise ValueError('Cannot embed empty string')
        self._resolve()
        if self._backend_kind == 'disabled':
            raise RuntimeError('dense embeddings disabled (KNO_EMBEDDING_MODEL=none)')
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._resolve()
        if self._backend_kind == 'disabled':
            return []
        try:
            if self._backend_kind == 'sentence-transformers':
                return self._embed_sentence_transformers(texts)
            if self._backend_kind == 'jina':
                return self._embed_jina(texts)
            if self._backend_kind == 'hf':
                return self._embed_hf(texts)
        except Exception as exc:
            logger.warning('Embedding backend %s failed: %s — falling back to MiniLM', self._backend_kind, exc)
        return self._fallback_minilm(texts)

    def _resolve(self) -> None:
        if self._backend_kind:
            return
        model = (KNO_EMBEDDING_MODEL or 'minilm').lower()
        if model in ('none', 'off', 'disabled', 'bm25', 'bm25-only'):
            self._backend_kind = 'disabled'
            self._dim = 0
            self._model_name = 'disabled'
            return
        if model == 'minilm':
            self._init_sentence_transformers('minilm')
            return
        if model == 'bge-large':
            self._init_sentence_transformers('bge-large')
            return
        if model == 'jina':
            if JINA_API_KEY:
                self._backend_kind = 'jina'
                self._dim = 1024
                self._model_name = 'jina-embeddings-v3'
                return
            logger.warning('JINA_API_KEY missing; falling back to local MiniLM.')
            self._init_sentence_transformers('minilm')
            return
        if model == 'hf':
            if HF_TOKEN:
                self._backend_kind = 'hf'
                self._dim = _KNOWN_MODELS['bge-large']['dim']
                self._model_name = os.getenv('KNO_HF_EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
                return
            logger.warning('HF_TOKEN missing; falling back to local MiniLM.')
            self._init_sentence_transformers('minilm')
            return
        logger.info('Treating KNO_EMBEDDING_MODEL=%r as sentence-transformers repo', model)
        self._init_sentence_transformers_repo(model)

    def _init_sentence_transformers(self, key: str) -> None:
        info = _KNOWN_MODELS[key]
        self._init_sentence_transformers_repo(info['hf_repo'])
        self._dim = info['dim']

    def _init_sentence_transformers_repo(self, repo: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError('sentence-transformers is required for local embeddings') from exc
        logger.info('Loading local embedding model %s', repo)
        self._model = SentenceTransformer(repo)
        self._backend_kind = 'sentence-transformers'
        self._dim = int(self._model.get_sentence_embedding_dimension())
        self._model_name = repo

    def _embed_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        arr = self._model.encode(texts, convert_to_numpy=True)
        return arr.tolist()

    def _embed_jina(self, texts: List[str]) -> List[List[float]]:
        import httpx
        url = 'https://api.jina.ai/v1/embeddings'
        headers = {'Authorization': f'Bearer {JINA_API_KEY}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        payload = {'model': 'jina-embeddings-v3', 'input': texts, 'task': 'retrieval.passage'}
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        vectors = [item['embedding'] for item in data.get('data', [])]
        if not vectors:
            raise RuntimeError('Jina returned no embeddings')
        return vectors

    def _embed_hf(self, texts: List[str]) -> List[List[float]]:
        import httpx
        url = f'https://api-inference.huggingface.co/models/{self._model_name}'
        headers = {'Authorization': f'Bearer {HF_TOKEN}', 'Content-Type': 'application/json'}
        payload = {'inputs': texts, 'options': {'wait_for_model': True}}
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        if not data:
            raise RuntimeError('HF Inference returned empty payload')
        if isinstance(data[0], dict):
            return [list(item.get('embedding', [])) for item in data]
        return [list(map(float, vec)) for vec in data]

    def _fallback_minilm(self, texts: List[str]) -> List[List[float]]:
        if self._backend_kind == 'sentence-transformers' and self._model is not None:
            return self._embed_sentence_transformers(texts)
        self._init_sentence_transformers('minilm')
        return self._embed_sentence_transformers(texts)
