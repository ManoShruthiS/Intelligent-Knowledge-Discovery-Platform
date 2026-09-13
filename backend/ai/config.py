from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env relative to this file, not just the CWD, so the server
# picks up keys no matter where uvicorn is launched from.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
for _candidate in (_BACKEND_DIR / '.env', Path.cwd() / '.env', _BACKEND_DIR.parent / '.env'):
    try:
        if _candidate.is_file():
            load_dotenv(_candidate, override=False)
    except Exception:
        pass

def _env(name: str, default: str='') -> str:
    v = os.getenv(name)
    return v if v is not None and v.strip() else default

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')

class AIConfig:

    def __init__(self):
        self._gemini_api_key = os.getenv('GEMINI_API_KEY')

    @property
    def is_gemini_configured(self) -> bool:
        return bool(self._gemini_api_key)

    def get_gemini_api_key(self) -> str:
        if not self._gemini_api_key:
            raise ValueError('GEMINI_API_KEY is not configured in the environment.')
        return self._gemini_api_key
ai_config = AIConfig()
KNO_EMBEDDING_MODEL = _env('KNO_EMBEDDING_MODEL', 'minilm').lower()
HF_TOKEN = _env('HF_TOKEN')
JINA_API_KEY = _env('JINA_API_KEY')
COHERE_API_KEY = _env('COHERE_API_KEY')
KNO_RERANKER = _env('KNO_RERANKER', 'none').lower()
KNO_BGE_RERANKER_MODEL = _env('KNO_BGE_RERANKER_MODEL', 'BAAI/bge-reranker-base')
KNO_RERANK_TOP_K = max(5, _env_int('KNO_RERANK_TOP_K', 25))
_KNO_QUERY_REWRITER_DEFAULT = 'rewrite'
KNO_QUERY_REWRITER = _env('KNO_QUERY_REWRITER', _KNO_QUERY_REWRITER_DEFAULT).lower()
if _env_bool('KNO_DISABLE_QUERY_REWRITE', False):
    KNO_QUERY_REWRITER = 'off'
KNO_LOST_IN_MIDDLE = _env_bool('KNO_LOST_IN_MIDDLE', True)
KNO_HYBRID_SEARCH = _env('KNO_HYBRID_SEARCH', 'bm25').lower()
KNO_HYBRID_DENSE_WEIGHT = max(0.0, min(1.0, _env_float('KNO_HYBRID_DENSE_WEIGHT', 0.6)))
KNO_CONTEXTUAL_RETRIEVAL = _env_bool('KNO_CONTEXTUAL_RETRIEVAL', True)
KNO_SELF_CRITIQUE = _env_bool('KNO_SELF_CRITIQUE', True)
KNO_MEMORY_SUMMARIZE_THRESHOLD = _env_int('KNO_MEMORY_SUMMARIZE_THRESHOLD', 0)
KNO_MEMORY_FULL_VERBATIM = _env_bool('KNO_MEMORY_FULL_VERBATIM', True)
KNO_MEMORY_MAX_TOKENS = max(1024, _env_int('KNO_MEMORY_MAX_TOKENS', 80000))
KNO_MEMORY_SOFT_WARN_TOKENS = max(512, _env_int('KNO_MEMORY_SOFT_WARN_TOKENS', 60000))
KNO_AGENTIC = _env_bool('KNO_AGENTIC', True)
KNO_AGENTIC_MAX_STEPS = max(1, _env_int('KNO_AGENTIC_MAX_STEPS', 3))
KNO_GRAPHRAG = _env_bool('KNO_GRAPHRAG', True)
NEO4J_URI = _env('NEO4J_URI')
NEO4J_USER = _env('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = _env('NEO4J_PASSWORD')
KNO_GRAPHRAG_FALLBACK_SQLITE = _env_bool('KNO_GRAPHRAG_FALLBACK_SQLITE', True)
KNO_WEB_FALLBACK = _env_bool('KNO_WEB_FALLBACK', True)
TAVILY_API_KEY = _env('TAVILY_API_KEY')
SERPER_API_KEY = _env('SERPER_API_KEY')
KNO_LATE_INTERACTION = _env_bool('KNO_LATE_INTERACTION', False)

def tier1_enabled() -> bool:
    return KNO_RERANKER not in ('', 'none', 'off', 'false', '0') or KNO_QUERY_REWRITER not in ('', 'off', 'false', '0', 'none') or KNO_LOST_IN_MIDDLE

def tier2_enabled() -> bool:
    return KNO_HYBRID_SEARCH not in ('', 'off', 'false', '0', 'none') or KNO_CONTEXTUAL_RETRIEVAL or KNO_SELF_CRITIQUE or (KNO_MEMORY_SUMMARIZE_THRESHOLD > 0)

def tier3_enabled() -> bool:
    return KNO_AGENTIC or KNO_GRAPHRAG or KNO_WEB_FALLBACK

def feature_flags() -> dict:
    return {'tier1': {'embedding_model': KNO_EMBEDDING_MODEL, 'reranker': KNO_RERANKER, 'query_rewriter': KNO_QUERY_REWRITER, 'lost_in_middle': KNO_LOST_IN_MIDDLE}, 'tier2': {'hybrid_search': KNO_HYBRID_SEARCH, 'hybrid_dense_weight': KNO_HYBRID_DENSE_WEIGHT, 'contextual_retrieval': KNO_CONTEXTUAL_RETRIEVAL, 'self_critique': KNO_SELF_CRITIQUE, 'memory_summarize_threshold': KNO_MEMORY_SUMMARIZE_THRESHOLD}, 'tier3': {'agentic': KNO_AGENTIC, 'agentic_max_steps': KNO_AGENTIC_MAX_STEPS, 'graphrag': KNO_GRAPHRAG, 'graphrag_neo4j_configured': bool(NEO4J_URI and NEO4J_PASSWORD), 'graphrag_fallback_sqlite': KNO_GRAPHRAG_FALLBACK_SQLITE, 'web_fallback': KNO_WEB_FALLBACK, 'tavily_configured': bool(TAVILY_API_KEY), 'serper_configured': bool(SERPER_API_KEY)}}
