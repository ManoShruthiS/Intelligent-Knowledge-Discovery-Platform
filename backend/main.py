import logging
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import httpx
from services.document_processor import process_document, UnsupportedFileTypeError, DocumentProcessingError
import database.database as db
from ai.chunker import DocumentChunker
from ai.vector_store import vector_store
from ai.embeddings import EmbeddingService
from ai.document_analysis_service import document_analysis_service, LLMUnavailableError
from ai.llm_service import LLMNotConfiguredError
from ai.llm_service import llm_service
from services.workspace_services import notes_service, brief_service, project_plan_service, experiments_service, research_gap_service, synthesis_service
from services.metadata_extractor import metadata_extractor
from services.document_tagger import tagger
from services.ingest import ingest_document, persist_upload as _persist_upload_shared
from services.ocr_service import ocr_service
from services.citations_service import list_citations, create_citation, delete_citation, format_citation, extract_citation_candidates
from services.discovery_service import search_research
from services.github_service import search_repositories
from services.datasets_service import search_datasets
from services.learning_service import search_learning
from services.citation_graph_service import citation_graph_service
from ai.config import feature_flags as _feature_flags
from ai.contextual_retrieval import contextualize_document_chunks
from ai.hybrid_search import bm25_index as _bm25_index
from services.graphrag_service import graphrag_service as _graphrag_service
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
import shutil
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'data', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

def _persist_upload(content: bytes, doc_id: str, original_filename: str) -> str | None:
    ext = os.path.splitext(original_filename)[1].lower()
    if not ext:
        return None
    safe_name = f'{doc_id}{ext}'
    path = os.path.join(UPLOADS_DIR, safe_name)
    try:
        with open(path, 'wb') as fh:
            fh.write(content)
        return path
    except Exception as exc:
        logger.warning(f'Failed to persist upload {original_filename}: {exc}')
        return None
DEFAULT_CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:5174', 'http://localhost:5175', 'http://localhost:3000', 'http://127.0.0.1:5173', 'http://127.0.0.1:5174', 'http://127.0.0.1:5175', 'http://127.0.0.1:3000', 'https://ikdp-frontend.onrender.com']
chunker = DocumentChunker()

def _contextualize_for_document(document_id: str, inserted_chunks: list, max_chunks: int=50) -> int:
    from ai.config import KNO_CONTEXTUAL_RETRIEVAL
    if not KNO_CONTEXTUAL_RETRIEVAL or not llm_service.is_configured:
        return 0
    return contextualize_document_chunks(document_id=document_id, chunks=inserted_chunks, max_chunks=max_chunks)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info('Application started – database initialized')
    yield
    logger.info('Shutting down – flushing FAISS index to disk')
    try:
        vector_store._save()
    except Exception as exc:
        logger.error(f'Failed to flush FAISS index on shutdown: {exc}')
    logger.info('Shutdown complete')
app = FastAPI(title='Intelligent Knowledge Discovery Platform API', lifespan=lifespan)
_env_origins = os.getenv('CORS_ALLOWED_ORIGINS')
if _env_origins:
    _allowed_origins = [o.strip() for o in _env_origins.split(',') if o.strip()]
else:
    _allowed_origins = DEFAULT_CORS_ORIGINS
app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_origin_regex='https://.*\\.onrender\\.com', allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def _paginate(items, offset: int, limit: int) -> dict:
    total = len(items)
    return {'items': items[offset:offset + limit], 'total': total, 'offset': offset, 'limit': limit}
import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
_LLM_ENDPOINTS = {'/api/ask', '/api/search'}
_LLM_PREFIXES = ('/api/workspaces/', '/api/documents/')
_LLM_SUFFIXES = ('/compare', '/research-gap', '/synthesis', '/auto-draft', '/auto-generate')

class RateLimiter:

    def __init__(self, general_limit: int=60, llm_limit: int=10, window: int=60):
        self.general_limit = general_limit
        self.llm_limit = llm_limit
        self.window = window
        self._requests: dict = defaultdict(list)

    def _is_llm(self, path: str) -> bool:
        if path in _LLM_ENDPOINTS:
            return True
        if path.startswith(_LLM_PREFIXES):
            return any((path.endswith(s) for s in _LLM_SUFFIXES))
        return False

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get('x-forwarded-for')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'

    def check(self, request: Request) -> None:
        now = time.time()
        ip = self._client_ip(request)
        key = f"{ip}:{('llm' if self._is_llm(request.url.path) else 'gen')}"
        limit = self.llm_limit if self._is_llm(request.url.path) else self.general_limit
        self._requests[key] = [t for t in self._requests[key] if t > now - self.window]
        if len(self._requests[key]) >= limit:
            from fastapi.responses import JSONResponse
            raise HTTPException(status_code=429, detail='Rate limit exceeded. Try again later.')
        self._requests[key].append(now)
_rate_limiter = RateLimiter()

@app.middleware('http')
async def rate_limit_middleware(request: Request, call_next):
    try:
        _rate_limiter.check(request)
    except HTTPException as exc:
        from starlette.responses import JSONResponse as _JSONResponse
        return _JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
    return await call_next(request)


def _get_client_id(request: Request) -> Optional[str]:
    """Read the stable per-browser UUID sent by the frontend as X-Client-Id header."""
    return request.headers.get('x-client-id') or request.headers.get('X-Client-Id') or None

@app.get('/', include_in_schema=False)
def root_endpoint(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        from fastapi.responses import HTMLResponse
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IKDP API Server</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 32px;
            max-width: 550px;
            width: 100%;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }
        .badge {
            display: inline-block;
            background: #10b98120;
            color: #10b981;
            border: 1px solid #10b98140;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 16px;
        }
        h1 { margin: 0 0 8px 0; font-size: 1.5rem; color: #ffffff; }
        p { color: #94a3b8; line-height: 1.6; margin-bottom: 24px; }
        .links { display: flex; gap: 12px; flex-wrap: wrap; }
        .btn {
            display: inline-flex;
            align-items: center;
            padding: 10px 18px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-secondary { background: #334155; color: #f8fafc; }
        .btn-secondary:hover { background: #475569; }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">● Server Online</span>
        <h1>Intelligent Knowledge Discovery Platform API</h1>
        <p>You have reached the backend API server. To view interactive documentation or verify system health, use the links below.</p>
        <div class="links">
            <a href="/docs" class="btn btn-primary">API Documentation (/docs)</a>
            <a href="/api/health" class="btn btn-secondary">Health Check</a>
        </div>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html_content)
    return {
        "name": "Intelligent Knowledge Discovery Platform API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

@app.get('/api', include_in_schema=False)
def api_root():
    return {
        "name": "Intelligent Knowledge Discovery Platform API",
        "status": "online",
        "health": "/api/health",
        "docs": "/docs"
    }

@app.get('/api/health')
def health_check():
    from ai.config import ai_config
    return {'status': 'healthy', 'message': 'Backend is running!', 'ai_configuration': 'configured' if ai_config.is_gemini_configured else 'not configured'}

@app.get('/api/health/deep')
def deep_health_check():
    checks = {}
    try:
        conn = db.get_connection()
        conn.execute('SELECT 1')
        conn.close()
        checks['database'] = {'status': 'healthy'}
    except Exception as exc:
        checks['database'] = {'status': 'unhealthy', 'detail': str(exc)}
    try:
        ntotal = vector_store.index.ntotal if vector_store.index else 0
        checks['faiss'] = {'status': 'healthy', 'vectors': ntotal, 'has_vectors': ntotal > 0}
    except Exception as exc:
        checks['faiss'] = {'status': 'unhealthy', 'detail': str(exc)}
    try:
        from ai.llm_service import llm_service
        configured = [p.name for p in llm_service.providers if getattr(p, '_configured', True)]
        checks['llm'] = {'status': 'healthy' if configured else 'degraded', 'configured_providers': configured}
    except Exception as exc:
        checks['llm'] = {'status': 'unhealthy', 'detail': str(exc)}
    overall = 'healthy' if all((c['status'] == 'healthy' for c in checks.values())) else 'degraded'
    return {'status': overall, 'checks': checks, 'feature_flags': _feature_flags()}

@app.post('/api/documents/upload')
async def upload_document(request: Request, file: UploadFile=File(...), workspace_id: Optional[str]=Form(None), background_tasks: BackgroundTasks=None):
    client_id = _get_client_id(request)
    if not file.filename:
        raise HTTPException(status_code=400, detail='No file uploaded.')
    fname = file.filename
    ext = '.' + fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
    if ext and ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=400, detail=f'Unsupported file type: {ext}. Allowed: ' + ', '.join(sorted(ALLOWED_UPLOAD_EXTS)))
    MAX_BYTES = 25 * 1024 * 1024
    try:
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(status_code=413, detail=f'File too large. Maximum size is {MAX_BYTES // (1024 * 1024)} MB.')
        result = process_document(content, fname)
        result['status'] = 'ready'
        doc_record = db.create_document(result, client_id=client_id)
        if workspace_id:
            try:
                db.add_document_to_workspace(workspace_id, doc_record['id'])
            except Exception as ws_err:
                logger.warning(f"Could not link doc {doc_record['id']} to workspace {workspace_id}: {ws_err}")
        _persist_upload(content, doc_record['id'], fname)
        try:
            mime = file.content_type or ''
            ocr_result = ocr_service.ocr_if_empty(doc_record['id'], content, mime, fname, result.get('text', ''))
            if ocr_result['status'] == 'ok':
                logger.info('OCR via %s enriched %s (%d chars)', ocr_result['provider'], fname, len(ocr_result.get('text') or ''))
                result['text'] = ocr_result['text']
        except Exception as ocr_exc:
            logger.warning(f'OCR service skipped for {fname}: {ocr_exc}')
        if background_tasks is not None:
            background_tasks.add_task(ingest_document, doc_record['id'], result, bm25_index=_bm25_index, graphrag_service=_graphrag_service, contextual_retrieval_fn=_contextualize_for_document)
        if background_tasks is not None and result.get('text'):
            background_tasks.add_task(metadata_extractor.extract_and_persist, doc_record['id'], result['text'], result.get('file_type', ''))
            background_tasks.add_task(tagger.tag_and_persist, doc_record['id'], result['text'])
        elif background_tasks is None:
            try:
                ingest_document(doc_record['id'], result, bm25_index=_bm25_index, graphrag_service=_graphrag_service, contextual_retrieval_fn=_contextualize_for_document)
            except Exception as ingest_exc:
                logger.exception(f"Ingest pipeline failed for {doc_record['id']}: {ingest_exc}")
        return doc_record
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DocumentProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'Document upload failed for {fname}')
        raise HTTPException(status_code=500, detail='An unexpected error occurred during document processing.')

@app.post('/api/documents/import')
async def import_document(payload: dict):
    import ipaddress
    import socket
    from urllib.parse import urlparse
    import httpx
    url = payload.get('url')
    title = payload.get('title', 'Imported Document')
    author = payload.get('author')
    year = payload.get('year')
    if not url:
        raise HTTPException(status_code=400, detail='URL is required.')
    DEFAULT_ALLOWED_DOMAINS = ('arxiv.org', 'openalex.org', 'crossref.org', 'doi.org', 'huggingface.co', 'semanticscholar.org', 'aclweb.org', 'acm.org', 'ieee.org', 'springer.com', 'sciencedirect.com', 'nature.com', 'aclanthology.org', 'jmlr.org', 'biorxiv.org', 'medrxiv.org')
    env_domains = os.getenv('IMPORT_ALLOWED_DOMAINS')
    allowed_domains = tuple((d.strip().lower() for d in (env_domains.split(',') if env_domains else DEFAULT_ALLOWED_DOMAINS) if d.strip()))

    def _is_allowed_host(host: str) -> bool:
        host = (host or '').lower().rstrip('.')
        if not host:
            return False
        return any((host == d or host.endswith('.' + d) for d in allowed_domains))

    def _is_safe_ip(addr: str) -> bool:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False
        return True

    def _validate_url(target: str) -> str:
        try:
            parsed = urlparse(target)
        except Exception:
            raise HTTPException(status_code=400, detail='Invalid URL.')
        if parsed.scheme not in ('http', 'https'):
            raise HTTPException(status_code=400, detail='URL scheme must be http or https.')
        if parsed.username or parsed.password:
            raise HTTPException(status_code=400, detail='URLs with embedded credentials are not allowed.')
        host = parsed.hostname
        if not host:
            raise HTTPException(status_code=400, detail='URL must include a hostname.')
        if not _is_allowed_host(host):
            raise HTTPException(status_code=403, detail=f"Host '{host}' is not in the allow-list of trusted research sources. Add it to IMPORT_ALLOWED_DOMAINS or import the document manually.")
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80))
        except socket.gaierror:
            raise HTTPException(status_code=400, detail=f"Could not resolve host '{host}'.")
        for info in infos:
            sockaddr = info[4]
            if not _is_safe_ip(sockaddr[0]):
                raise HTTPException(status_code=403, detail=f"Host '{host}' resolves to a non-public address and is not allowed.")
        return host
    try:
        _validate_url(url)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f'Import URL validation failed for {url}: {e}')
        raise HTTPException(status_code=400, detail='Invalid import URL.')
    fname = url.split('/')[-1].split('?')[0]
    if not fname or '.' not in fname:
        fname = title.replace(' ', '_') + '.pdf'

    def _follow_redirect_safe(request, follow_response):
        try:
            _validate_url(str(request.url))
        except HTTPException:
            raise
        return follow_response
    try:
        async with httpx.AsyncClient(timeout=30.0, event_hooks={'response': [_follow_redirect_safe]}) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            content = response.content
        MAX_BYTES = 25 * 1024 * 1024
        if len(content) > MAX_BYTES:
            raise HTTPException(status_code=413, detail=f'File too large. Maximum size is {MAX_BYTES // (1024 * 1024)} MB.')
        result = process_document(content, fname)
        if title:
            result['title'] = title
        if author:
            result['author'] = author
        if year:
            result['year'] = int(year)
        result['status'] = 'ready'
        doc_record = db.create_document(result)
        _persist_upload(content, doc_record['id'], fname)
        try:
            ocr_result = ocr_service.ocr_if_empty(doc_record['id'], content, 'application/pdf', fname, result.get('text', ''))
            if ocr_result['status'] == 'ok':
                result['text'] = ocr_result['text']
        except Exception:
            pass
        try:
            stats = ingest_document(doc_record['id'], result, bm25_index=_bm25_index, graphrag_service=_graphrag_service, contextual_retrieval_fn=_contextualize_for_document)
            if stats.errors:
                logger.warning(f"Ingest partial errors for {doc_record['id']}: {stats.errors}")
        except Exception:
            logger.exception(f"Ingest pipeline failed for {doc_record['id']}")
        return doc_record
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f'Failed to download document: {str(e)}')
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DocumentProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'Document import failed for {url}')
        raise HTTPException(status_code=500, detail='An unexpected error occurred during document import.')

@app.get('/api/documents/{document_id}/metadata')
def get_document_metadata(document_id: str):
    payload = db.get_document_metadata_status(document_id)
    if payload is None:
        raise HTTPException(status_code=404, detail='Document not found.')
    return payload

@app.post('/api/documents/{document_id}/metadata/retry')
def retry_document_metadata(document_id: str, background_tasks: BackgroundTasks):
    doc = db.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found.')
    text = doc.get('extracted_text') or ''
    if not text.strip():
        raise HTTPException(status_code=400, detail='Document has no extractable text.')
    db.update_document_metadata_status(document_id, 'pending')
    background_tasks.add_task(metadata_extractor.extract_and_persist, document_id, text, doc.get('file_type', ''))
    return {'status': 'scheduled', 'document_id': document_id}

@app.post('/api/documents/{document_id}/enrich/related')
def enrich_related_papers(document_id: str, payload: Optional[dict]=None, max_results: int=5):
    doc = db.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found.')
    payload = payload or {}
    query = payload.get('query')
    if not query:
        title = doc.get('title') or doc.get('filename') or ''
        author = doc.get('author') or ''
        query = f'{title} {author}'.strip() or doc.get('filename', '')
    max_results = int(payload.get('max_results') or max_results)
    results = enricher.suggest_related(query, max_results=max_results)
    return {'query': query, 'results': results}

@app.post('/api/documents/{document_id}/enrich/datasets')
def enrich_related_datasets(document_id: str, payload: Optional[dict]=None, max_results: int=6):
    doc = db.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found.')
    payload = payload or {}
    keywords = payload.get('keywords') or []
    if not keywords:
        title_words = (doc.get('title') or doc.get('filename') or '').split()
        keywords = [w for w in title_words if len(w) > 3][:6]
    max_results = int(payload.get('max_results') or max_results)
    results = recommender.recommend(keywords, max_results=max_results)
    return {'keywords': keywords, 'results': results}

@app.get('/api/documents')
def get_documents(request: Request, offset: int=0, limit: int=50):
    try:
        client_id = _get_client_id(request)
        docs = db.get_documents(client_id=client_id)
        return _paginate(docs, offset, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve documents.')

@app.put('/api/documents/{document_id}/star')
def toggle_document_star(document_id: str, payload: dict):
    try:
        starred = payload.get('starred', False)
        db.update_document_starred(document_id, starred)
        return {'success': True, 'starred': starred}
    except Exception as e:
        logger.exception(f'Failed to toggle star for document {document_id}')
        raise HTTPException(status_code=500, detail='Failed to update document.')

@app.post('/api/documents')
def create_document_endpoint(payload: dict):
    try:
        content = payload.get('content', '')
        title = payload.get('title', 'Untitled')
        doc_type = payload.get('document_type', 'markdown')
        doc_data = {'filename': title, 'title': title, 'file_type': doc_type, 'file_size': len(content.encode('utf-8')), 'character_count': len(content), 'text': content, 'page_count': 1}
        doc = db.create_document(doc_data)
        workspace_id = payload.get('workspace_id')
        if workspace_id and doc.get('id'):
            db.add_document_to_workspace(workspace_id, doc['id'])
        if content and doc.get('id'):
            chunks = chunker.chunk_document(doc)
            if chunks:
                embedder = EmbeddingService()
                texts = [c['text'] for c in chunks]
                embeddings = embedder.embed_texts(texts)
                for chunk, emb in zip(chunks, embeddings):
                    chunk['embedding'] = emb
                db.create_chunks(doc['id'], chunks)
                inserted_chunks = db.get_chunks_for_document(doc['id'])
                chunk_ids = [c['id'] for c in inserted_chunks]
                vector_store.add_embeddings(chunk_ids, embeddings)
        return {'document': doc}
    except Exception as e:
        logger.exception('Document creation failed')
        raise HTTPException(status_code=500, detail='Failed to create document.')

@app.put('/api/documents/{document_id}')
def update_document_endpoint(document_id: str, payload: dict):
    try:
        updates = {}
        if 'title' in payload:
            updates['title'] = payload['title']
        if 'content' in payload:
            updates['extracted_text'] = payload['content']
            updates['character_count'] = len(payload['content'])
        doc = db.update_document(document_id, **updates)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        if 'content' in payload and payload['content']:
            reloaded = db.get_document_by_id(document_id)
            if reloaded:
                chunks = chunker.chunk_document(reloaded)
                if chunks:
                    embedder = EmbeddingService()
                    texts = [c['text'] for c in chunks]
                    embeddings = embedder.embed_texts(texts)
                    for chunk, emb in zip(chunks, embeddings):
                        chunk['embedding'] = emb
                    db.create_chunks(document_id, chunks)
                    inserted_chunks = db.get_chunks_for_document(document_id)
                    chunk_ids = [c['id'] for c in inserted_chunks]
                    vector_store.add_embeddings(chunk_ids, embeddings)
        return {'document': doc}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'Document update failed for {document_id}')
        raise HTTPException(status_code=500, detail='Failed to update document.')

@app.get('/api/workspaces/{workspace_id}/documents')
def list_workspace_documents(workspace_id: str):
    try:
        if not db.get_workspace_by_id(workspace_id):
            raise HTTPException(status_code=404, detail='Workspace not found.')
        docs = db.get_workspace_documents(workspace_id)
        return {'documents': docs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to list workspace documents.')

@app.get('/api/documents/{document_id}')
def get_document(document_id: str):
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve the document.')

@app.get('/api/documents/{document_id}/file')
def get_document_file(document_id: str):
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        from fastapi.responses import FileResponse
        candidates = []
        ft = (doc.get('file_type') or '').lower()
        ext_map = {'pdf': ['.pdf'], 'docx': ['.docx'], 'markdown': ['.md', '.markdown'], 'txt': ['.txt'], 'csv': ['.csv'], 'xlsx': ['.xlsx'], 'json': ['.json'], 'jupyter notebook': ['.ipynb'], 'python': ['.py'], 'javascript': ['.js', '.jsx'], 'typescript': ['.ts', '.tsx'], 'java': ['.java'], 'c': ['.c', '.h'], 'c++': ['.cpp', '.hpp', '.cc'], 'go': ['.go'], 'rust': ['.rs'], 'ruby': ['.rb'], 'shell': ['.sh', '.bash'], 'html': ['.html', '.htm'], 'css': ['.css'], 'xml': ['.xml'], 'yaml': ['.yaml', '.yml'], 'toml': ['.toml'], 'png': ['.png'], 'jpg': ['.jpg', '.jpeg'], 'gif': ['.gif'], 'webp': ['.webp'], 'bmp': ['.bmp']}
        candidates = ext_map.get(ft, [])
        for ext in candidates:
            path = os.path.join(UPLOADS_DIR, f'{document_id}{ext}')
            if os.path.isfile(path):
                media_type = 'application/pdf' if ext == '.pdf' else None
                return FileResponse(path, media_type=media_type, filename=doc.get('filename') or f'document{ext}')
        raise HTTPException(status_code=404, detail='Original file is not available for this document.')
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to serve file for document {document_id}: {e}')
        raise HTTPException(status_code=500, detail='Failed to retrieve the file.')

@app.get('/api/documents/{document_id}/chunks')
def get_document_chunks(document_id: str):
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        chunks = db.get_chunks_for_document(document_id)
        return chunks
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve chunks.')

@app.get('/api/chunks/{chunk_id}/highlight')
def get_chunk_highlight(chunk_id: str):
    import json as _json
    try:
        rows = db.get_chunks_by_ids([chunk_id])
        if not rows:
            raise HTTPException(status_code=404, detail='Chunk not found.')
        chunk = rows[0]
        bboxes_raw = chunk.get('bboxes_json')
        bboxes = _json.loads(bboxes_raw) if bboxes_raw else []
        return {'document_id': chunk['document_id'], 'chunk_index': chunk['chunk_index'], 'page_number': chunk.get('page_number'), 'bboxes': bboxes, 'page_width': chunk.get('page_width'), 'page_height': chunk.get('page_height')}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to load highlight for chunk {chunk_id}: {e}')
        raise HTTPException(status_code=500, detail='Failed to load highlight.')

@app.get('/api/documents/{document_id}/versions')
def list_document_versions(document_id: str):
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        return {'versions': db.get_document_versions(document_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'List versions failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to list document versions.')

@app.post('/api/documents/{document_id}/versions')
def create_document_version(document_id: str):
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found.')
        version = db.create_document_version(doc_id=document_id, title=doc.get('title') or doc.get('filename', 'Untitled'), content=doc.get('extracted_text', ''))
        return version
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Create version failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to create document version.')

@app.delete('/api/documents/{document_id}')
def delete_document(document_id: str, background_tasks: BackgroundTasks):
    try:
        success = db.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail='Document not found.')
        try:
            _bm25_index.remove_document(document_id)
        except Exception as bm25_exc:
            logger.warning('BM25 remove_document failed for %s: %s', document_id, bm25_exc)
        try:
            _graphrag_service.remove_document(document_id)
        except Exception as graph_exc:
            logger.warning('GraphRAG remove_document failed for %s: %s', document_id, graph_exc)

        def _rebuild_after_delete():
            try:
                vector_store.rebuild_index()
                logger.info(f'Background FAISS rebuild after delete of {document_id} completed')
            except Exception as exc:
                logger.error(f'Background FAISS rebuild after delete of {document_id} failed: {exc}')
        background_tasks.add_task(_rebuild_after_delete)
        return {'status': 'success', 'message': 'Document deleted; vector index rebuild queued.'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to delete document {document_id}: {e}')
        raise HTTPException(status_code=500, detail='Failed to delete the document.')
from ai.rag_service import rag_service

class SearchQuery(BaseModel):
    query: str
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    top_k: int = 5
ALLOWED_UPLOAD_EXTS = {'.pdf', '.docx', '.txt', '.md', '.markdown', '.csv', '.xlsx', '.json', '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.h', '.cpp', '.hpp', '.cc', '.go', '.rs', '.rb', '.sh', '.bash', '.html', '.htm', '.css', '.xml', '.yaml', '.yml', '.toml', '.ipynb', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

class MessageData(BaseModel):
    role: str
    content: str

class AttachmentData(BaseModel):
    type: str
    name: str
    dataUrl: Optional[str] = None
    documentId: Optional[str] = None

class AskQuery(BaseModel):
    question: Optional[str] = None
    message: Optional[str] = None
    query: Optional[str] = None
    mode: str = 'Research'
    history: List[MessageData] = []
    attachments: List[AttachmentData] = []
    document_id: Optional[str] = None
    documentId: Optional[str] = None
    workspace_id: Optional[str] = None
    workspaceId: Optional[str] = None
    top_k: int = 5
    persist_conversation: Optional[bool] = False
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = ''

class NoteCreate(BaseModel):
    title: Optional[str] = 'Untitled Note'
    content: str = ''

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class ResourceCreate(BaseModel):
    title: str
    url: Optional[str] = ''
    description: Optional[str] = ''
    resource_type: str = 'learning_source'

@app.post('/api/search')
def search_documents(payload: SearchQuery):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail='Query cannot be empty.')
    try:
        embedder = EmbeddingService()
        query_embedding = embedder.embed_text(payload.query)
        search_k = payload.top_k * 5 if payload.document_id else payload.top_k
        faiss_results = vector_store.search(query_embedding, top_k=search_k)
        if not faiss_results:
            return []
        chunk_ids = [res['chunk_id'] for res in faiss_results]
        db_chunks = db.get_chunks_by_ids(chunk_ids)
        chunk_dict = {c['id']: c for c in db_chunks}
        final_results = []
        for faiss_res in faiss_results:
            cid = faiss_res['chunk_id']
            if cid in chunk_dict:
                chunk = chunk_dict[cid]
                if payload.document_id and chunk['document_id'] != payload.document_id:
                    continue
                if payload.workspace_id and chunk['document_id'] not in [d['id'] for d in db.get_documents_for_workspace(payload.workspace_id)]:
                    continue
                result = {'chunk_id': cid, 'document_id': chunk['document_id'], 'chunk_index': chunk['chunk_index'], 'page_number': chunk['page_number'], 'text': chunk['text'], 'distance': faiss_res['distance']}
                final_results.append(result)
                if len(final_results) >= payload.top_k:
                    break
        return final_results
    except Exception as e:
        logger.error(f'Search error: {e}')
        raise HTTPException(status_code=500, detail='An error occurred during search.')

@app.post('/api/ask')
def ask_question(payload: AskQuery):
    q_text = payload.question or payload.message or payload.query or ''
    if not q_text.strip():
        raise HTTPException(status_code=400, detail='Question cannot be empty.')
    doc_id = payload.document_id or payload.documentId
    ws_id = payload.workspace_id or payload.workspaceId
    try:
        response = rag_service.ask(question=q_text.strip(), mode=payload.mode, history=payload.history, attachments=payload.attachments, document_id=doc_id, workspace_id=ws_id, top_k=payload.top_k)
        return response
    except Exception as e:
        logger.error(f'Ask API error: {e}')
        error_msg = str(e) if str(e) else 'An unexpected error occurred.'
        raise HTTPException(status_code=500, detail=error_msg)

@app.post('/api/ask/stream')
def ask_question_stream(payload: AskQuery):
    import json as _json
    from fastapi.responses import StreamingResponse
    q_text = payload.question or payload.message or payload.query or ''
    if not q_text.strip():
        raise HTTPException(status_code=400, detail='Question cannot be empty.')
    doc_id = payload.document_id or payload.documentId
    ws_id = payload.workspace_id or payload.workspaceId
    conv_id = None
    if getattr(payload, 'persist_conversation', False):
        try:
            from services.conversation_service import conversation_service
            conv = conversation_service.ensure_conversation(conversation_id=getattr(payload, 'conversation_id', None), user_id=getattr(payload, 'user_id', None), document_id=doc_id, workspace_id=ws_id)
            conv_id = conv['id'] if isinstance(conv, dict) else getattr(conv, 'id', None)
            conversation_service.save_message(conv_id, role='user', text=q_text.strip(), mode=payload.mode)
        except Exception as exc:
            logger.warning('Failed to persist stream user message: %s', exc)

    def _format_event(event_name: str, data: dict) -> bytes:
        return f'event: {event_name}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n'.encode('utf-8')

    def _event_stream():
        try:
            last_meta_sources = []
            for event in rag_service.stream(question=q_text.strip(), mode=payload.mode, history=payload.history, attachments=payload.attachments, document_id=doc_id, workspace_id=ws_id, top_k=payload.top_k):
                ev_type = event.get('type', 'message')
                if ev_type == 'token':
                    yield _format_event('token', {'text': event.get('text', '')})
                elif ev_type == 'thinking':
                    yield _format_event('thinking', {'stage': event.get('stage'), 'label': event.get('label'), 'candidate_count': event.get('candidate_count')})
                elif ev_type == 'meta':
                    last_meta_sources = event.get('sources', [])
                    yield _format_event('meta', {'sources': last_meta_sources, 'trace': event.get('trace'), 'confidence': event.get('confidence'), 'insufficient_evidence': event.get('insufficient_evidence', False), 'high_relevance_chunks': event.get('high_relevance_chunks', 0), 'moderate_relevance_chunks': event.get('moderate_relevance_chunks', 0), 'total_chunks_retrieved': event.get('total_chunks_retrieved', 0), 'chunks_used': event.get('chunks_used', 0), 'metadata': event.get('metadata', {}), 'request_id': event.get('request_id') or event.get('metadata', {}).get('request_id'), 'provider_status': event.get('provider_status') or (rag_service._active_provider_name() if hasattr(rag_service, '_active_provider_name') else {}), 'page_pin': event.get('page_pin'), 'conversation_id': conv_id or event.get('conversation_id')})
                elif ev_type == 'followups':
                    yield _format_event('followups', {'suggested_followups': event.get('suggested_followups', [])})
                elif ev_type == 'smart_citations':
                    yield _format_event('smart_citations', {'citations': event.get('citations', [])})
                elif ev_type == 'done':
                    ans = event.get('answer', '')
                    if conv_id and getattr(payload, 'persist_conversation', False):
                        try:
                            from services.conversation_service import conversation_service
                            conversation_service.save_message(conv_id, role='orbot', text=ans, mode=payload.mode, sources=last_meta_sources)
                        except Exception as exc:
                            logger.warning('Failed to persist stream assistant message: %s', exc)
                    yield _format_event('done', {'answer': ans, 'conversation_id': conv_id or event.get('conversation_id')})
                elif ev_type == 'error':
                    yield _format_event('error', {'detail': event.get('detail', 'Unknown error')})
        except Exception as e:
            logger.exception(f'Stream API error: {e}')
            yield _format_event('error', {'detail': str(e) or 'Streaming failed.'})
    return StreamingResponse(_event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})

@app.post('/api/workspaces')
def create_workspace(request: Request, payload: WorkspaceCreate):
    try:
        client_id = _get_client_id(request)
        ws = db.create_workspace(payload.name, payload.description, client_id=client_id)
        return ws
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to create workspace.')

@app.get('/api/workspaces')
def get_workspaces(request: Request, offset: int=0, limit: int=50):
    try:
        client_id = _get_client_id(request)
        return _paginate(db.get_all_workspaces(client_id=client_id), offset, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve workspaces.')

@app.get('/api/workspaces/{workspace_id}')
def get_workspace(workspace_id: str):
    try:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail='Workspace not found.')
        docs = db.get_documents_for_workspace(workspace_id)
        ws['documents'] = docs
        return ws
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve workspace.')

@app.put('/api/workspaces/{workspace_id}')
def update_workspace(workspace_id: str, payload: WorkspaceCreate):
    try:
        ws = db.update_workspace(workspace_id, payload.name, payload.description)
        if not ws:
            raise HTTPException(status_code=404, detail='Workspace not found.')
        return ws
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to update workspace.')

@app.delete('/api/workspaces/{workspace_id}')
def delete_workspace(workspace_id: str):
    try:
        success = db.delete_workspace(workspace_id)
        if not success:
            raise HTTPException(status_code=404, detail='Workspace not found.')
        return {'status': 'success', 'message': 'Workspace deleted successfully.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to delete workspace.')

@app.post('/api/workspaces/{workspace_id}/documents/{document_id}')
def add_document_to_workspace(workspace_id: str, document_id: str):
    try:
        if not db.get_document_by_id(document_id):
            raise HTTPException(status_code=404, detail='Document not found.')
        success = db.add_document_to_workspace(workspace_id, document_id)
        if not success:
            if not db.get_workspace_by_id(workspace_id):
                raise HTTPException(status_code=404, detail='Workspace not found.')
        return {'status': 'success', 'message': 'Document added to workspace.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to add document to workspace.')

@app.delete('/api/workspaces/{workspace_id}/documents/{document_id}')
def remove_document_from_workspace(workspace_id: str, document_id: str):
    try:
        success = db.remove_document_from_workspace(workspace_id, document_id)
        if not success:
            raise HTTPException(status_code=404, detail='Relationship not found.')
        return {'status': 'success', 'message': 'Document removed from workspace.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to remove document from workspace.')

@app.get('/api/workspaces/{workspace_id}/notes')
def get_notes(workspace_id: str):
    try:
        return db.get_workspace_notes(workspace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve workspace notes.')

@app.post('/api/workspaces/{workspace_id}/notes')
def create_note_endpoint(workspace_id: str, payload: NoteCreate):
    try:
        note = db.create_note(workspace_id, payload.title or 'Untitled Note', payload.content or '')
        return note
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to create note.')

@app.put('/api/notes/{note_id}')
def update_note_endpoint(note_id: str, payload: NoteUpdate):
    try:
        note = db.update_note(note_id, payload.title, payload.content)
        return note
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to update note.')

@app.delete('/api/notes/{note_id}')
def delete_note_endpoint(note_id: str):
    try:
        success = db.delete_note(note_id)
        if not success:
            raise HTTPException(status_code=404, detail='Note not found.')
        return {'status': 'success', 'message': 'Note deleted successfully.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to delete note.')

@app.get('/api/workspaces/{workspace_id}/resources')
def get_resources(workspace_id: str):
    try:
        return db.get_workspace_resources(workspace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to retrieve workspace resources.')

@app.post('/api/workspaces/{workspace_id}/resources')
def create_resource_endpoint(workspace_id: str, payload: ResourceCreate):
    try:
        resource = db.create_resource(workspace_id, payload.resource_type, payload.title, payload.url or '', payload.description or '')
        return resource
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to create resource.')

@app.delete('/api/resources/{resource_id}')
def delete_resource_endpoint(resource_id: str):
    try:
        success = db.delete_resource(resource_id)
        if not success:
            raise HTTPException(status_code=404, detail='Resource not found.')
        return {'status': 'success', 'message': 'Resource deleted successfully.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to delete resource.')

@app.get('/api/documents/{document_id}/summary')
def get_document_summary(document_id: str, force_regenerate: bool=False):
    try:
        return document_analysis_service.summary(document_id, force_regenerate=force_regenerate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Summary API error for {document_id}: {e}')
        raise HTTPException(status_code=500, detail='An unexpected error occurred while generating the summary.')

@app.get('/api/documents/{document_id}/insights')
def get_document_insights(document_id: str, force_regenerate: bool=False):
    try:
        return document_analysis_service.insights(document_id, force_regenerate=force_regenerate)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Insights API error for {document_id}: {e}')
        raise HTTPException(status_code=500, detail='An unexpected error occurred while extracting insights.')

@app.get('/api/documents/{document_id}/sources')
def get_document_sources(document_id: str):
    try:
        return document_analysis_service.sources(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Sources API error for {document_id}: {e}')
        raise HTTPException(status_code=500, detail='An unexpected error occurred while retrieving sources.')

@app.delete('/api/documents/{document_id}/analysis')
def delete_document_analysis_cache(document_id: str, kind: Optional[str]=None):
    if kind and kind not in ('summary', 'insights'):
        raise HTTPException(status_code=400, detail="kind must be 'summary' or 'insights'.")
    try:
        if not db.get_document_by_id(document_id):
            raise HTTPException(status_code=404, detail='Document not found.')
        conn = db.get_connection()
        cursor = conn.cursor()
        if kind:
            cursor.execute('DELETE FROM document_analysis_cache WHERE document_id = ? AND analysis_kind = ?', (document_id, kind))
        else:
            cursor.execute('DELETE FROM document_analysis_cache WHERE document_id = ?', (document_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return {'status': 'success', 'deleted': deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Analysis-cache delete failed for {document_id}: {e}')
        raise HTTPException(status_code=500, detail='Failed to clear analysis cache.')

class NoteIn(BaseModel):
    title: str
    content: str
    kind: str = 'note'
    source_message_id: Optional[str] = None

class NoteUpdate(BaseModel):
    title: str
    content: str

@app.get('/api/workspaces/{workspace_id}/notes')
def list_workspace_notes(workspace_id: str, offset: int=0, limit: int=50):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    notes = notes_service.list(workspace_id)
    paginated = _paginate(notes, offset, limit)
    paginated['workspace_id'] = workspace_id
    return paginated

@app.post('/api/workspaces/{workspace_id}/notes')
def create_workspace_note(workspace_id: str, payload: NoteIn):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return notes_service.create(workspace_id, payload.title, payload.content, kind=payload.kind, source_message_id=payload.source_message_id)
    except Exception as e:
        logger.error(f'Note create failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to create note.')

@app.put('/api/notes/{note_id}')
def update_note(note_id: str, payload: NoteUpdate):
    try:
        updated = notes_service.update(note_id, payload.title, payload.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail='Failed to update note.')
    if not updated:
        raise HTTPException(status_code=404, detail='Note not found.')
    return updated

@app.delete('/api/notes/{note_id}')
def delete_note(note_id: str):
    if not notes_service.delete(note_id):
        raise HTTPException(status_code=404, detail='Note not found.')
    return {'status': 'success'}

@app.get('/api/workspaces/{workspace_id}/brief')
def get_research_brief(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    return brief_service.get(workspace_id)

class BriefUpdate(BaseModel):
    topic: Optional[str] = None
    problem: Optional[str] = None
    research_question: Optional[str] = None
    objectives: Optional[str] = None
    papers_reviewed: Optional[str] = None
    key_findings: Optional[str] = None
    common_limitations: Optional[str] = None
    potential_gap: Optional[str] = None
    proposed_direction: Optional[str] = None
    open_questions: Optional[str] = None
    current_stage: Optional[str] = None

@app.put('/api/workspaces/{workspace_id}/brief')
def update_research_brief(workspace_id: str, payload: BriefUpdate):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    fields = payload.model_dump(exclude_none=True)
    return brief_service.update(workspace_id, fields)

@app.post('/api/workspaces/{workspace_id}/brief/auto-draft')
def auto_draft_brief(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return brief_service.auto_draft(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Auto-draft brief failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to auto-draft brief.')

@app.get('/api/workspaces/{workspace_id}/project-plan')
def get_project_plan(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    return project_plan_service.get(workspace_id)

class ProjectPlanUpdate(BaseModel):
    problem_statement: Optional[str] = None
    objectives: Optional[str] = None
    requirements: Optional[str] = None
    architecture: Optional[str] = None
    technology_stack: Optional[str] = None
    components: Optional[str] = None
    data_flow: Optional[str] = None
    implementation_stages: Optional[str] = None
    testing_strategy: Optional[str] = None
    evaluation_metrics: Optional[str] = None
    deployment_plan: Optional[str] = None

@app.put('/api/workspaces/{workspace_id}/project-plan')
def update_project_plan(workspace_id: str, payload: ProjectPlanUpdate):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    return project_plan_service.update(workspace_id, payload.model_dump(exclude_none=True))

@app.post('/api/workspaces/{workspace_id}/project-plan/auto-generate')
def auto_generate_project_plan(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return project_plan_service.auto_generate(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Auto-gen project plan failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to auto-generate project plan.')

class ExperimentIn(BaseModel):
    name: str
    model: Optional[str] = None
    dataset: Optional[str] = None
    configuration: Optional[str] = None
    metric: Optional[str] = None
    result: Optional[str] = None
    experiment_date: Optional[str] = None
    notes: Optional[str] = None

class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    dataset: Optional[str] = None
    configuration: Optional[str] = None
    metric: Optional[str] = None
    result: Optional[str] = None
    experiment_date: Optional[str] = None
    notes: Optional[str] = None

@app.get('/api/workspaces/{workspace_id}/experiments')
def list_experiments(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    return {'workspace_id': workspace_id, 'experiments': experiments_service.list(workspace_id)}

@app.post('/api/workspaces/{workspace_id}/experiments')
def create_experiment(workspace_id: str, payload: ExperimentIn):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return experiments_service.create(workspace_id, payload.name, model=payload.model, dataset=payload.dataset, configuration=payload.configuration, metric=payload.metric, result=payload.result, experiment_date=payload.experiment_date, notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put('/api/experiments/{experiment_id}')
def update_experiment(experiment_id: str, payload: ExperimentUpdate):
    updated = experiments_service.update(experiment_id, **payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail='Experiment not found.')
    return updated

@app.delete('/api/experiments/{experiment_id}')
def delete_experiment(experiment_id: str):
    if not experiments_service.delete(experiment_id):
        raise HTTPException(status_code=404, detail='Experiment not found.')
    return {'status': 'success'}

@app.get('/api/workspaces/{workspace_id}/experiments/analytics')
def experiments_analytics(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    return experiments_service.analytics(workspace_id)

@app.post('/api/workspaces/{workspace_id}/research-gap')
def workspace_research_gap(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return research_gap_service.analyze(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Research gap failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to perform research-gap analysis.')

class SynthesisQuery(BaseModel):
    question: Optional[str] = None

@app.post('/api/workspaces/{workspace_id}/synthesis')
def workspace_synthesis(workspace_id: str, payload: SynthesisQuery):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    try:
        return synthesis_service.synthesize(workspace_id, payload.question)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f'Synthesis failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to synthesize workspace.')

class CitationIn(BaseModel):
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    workspace_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: str = 'manual'
    external_id: Optional[str] = None
    abstract: Optional[str] = None

@app.get('/api/citations')
def get_citations(workspace_id: Optional[str]=None):
    return {'citations': list_citations(workspace_id=workspace_id)}

@app.post('/api/citations')
def add_citation(payload: CitationIn):
    result = create_citation(payload.model_dump(exclude_none=True))
    if payload.workspace_id:
        src_type = (payload.source_type or '').lower()
        title_lower = (payload.title or '').lower()
        url_lower = (payload.url or '').lower()
        if 'dataset' in src_type or 'dataset' in title_lower:
            r_type = 'dataset'
        elif 'repo' in src_type or 'code' in src_type or 'github.com' in url_lower or ('gitlab.com' in url_lower):
            r_type = 'repository'
        else:
            r_type = 'learning_source'
        try:
            db.create_resource(workspace_id=payload.workspace_id, resource_type=r_type, title=payload.title, url=payload.url or '', description=payload.abstract or payload.authors or '')
        except Exception as e:
            logger.warning(f'Could not auto-add workspace resource: {e}')
    return result

@app.delete('/api/citations/{citation_id}')
def remove_citation(citation_id: str):
    if not delete_citation(citation_id):
        raise HTTPException(status_code=404, detail='Citation not found.')
    return {'status': 'success'}

@app.post('/api/documents/{document_id}/citations/extract')
def extract_citations_from_document(document_id: str):
    try:
        candidates = extract_citation_candidates(document_id)
    except Exception as e:
        logger.error(f'Citation extract failed: {e}')
        raise HTTPException(status_code=500, detail='Failed to extract citations.')
    return {'document_id': document_id, 'candidates': candidates}

@app.get('/api/citations/format')
def format_citation_endpoint(id: str, style: str='ieee'):
    from services.citations_service import list_citations as _list
    cite = None
    for c in _list(workspace_id=None):
        if c['id'] == id:
            cite = c
            break
    if not cite:
        raise HTTPException(status_code=404, detail='Citation not found.')
    return {'id': id, 'style': style, 'formatted': format_citation(cite, style)}

@app.post('/api/citations/bibliography')
def bibliography(payload: dict):
    style = (payload or {}).get('style', 'ieee')
    ids = (payload or {}).get('ids', []) or []
    from services.citations_service import list_citations as _list
    items = []
    for c in _list(workspace_id=None):
        if c['id'] in ids:
            items.append(format_citation(c, style))
    return {'style': style, 'bibliography': items, 'count': len(items)}

@app.post('/api/citations/export')
def citations_export(payload: dict):
    from services.citations_service import format_bibliography, list_citations as _list, citation_filename
    style = (payload or {}).get('style', 'bibtex')
    ids = (payload or {}).get('ids') or None
    workspace_id = (payload or {}).get('workspace_id') or None
    citations = _list(workspace_id=workspace_id)
    if ids is not None:
        id_set = set(ids)
        citations = [c for c in citations if c.get('id') in id_set]
    text = format_bibliography(citations, style)
    return {'style': style, 'text': text, 'filename': citation_filename(style), 'count': len(citations), 'mime': 'application/x-bibtex' if style == 'bibtex' else 'application/x-research-info-systems' if style == 'ris' else 'text/plain'}

class DiscoveryQuery(BaseModel):
    query: str
    limit_per_source: int = 10
    sort_by: str = 'relevance'
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False
    min_citations: int = 0
    page: int = 1
    page_size: int = 20

@app.post('/api/discover/research')
def discover_research(payload: DiscoveryQuery):
    try:
        return search_research(query=payload.query, limit_per_source=payload.limit_per_source, sort_by=payload.sort_by, year_from=payload.year_from, year_to=payload.year_to, open_access_only=payload.open_access_only, min_citations=payload.min_citations, page=payload.page, page_size=payload.page_size)
    except Exception as e:
        logger.error(f'Discovery failed: {e}')
        raise HTTPException(status_code=500, detail='Discovery failed.')

class GithubQuery(BaseModel):
    query: str
    limit: int = 12
    sort: str = 'best-match'

@app.post('/api/discover/github')
def discover_github(payload: GithubQuery):
    try:
        return search_repositories(payload.query, payload.limit)
    except Exception as e:
        logger.error(f'GitHub search failed: {e}')
        raise HTTPException(status_code=500, detail='GitHub search failed.')

class DatasetsQuery(BaseModel):
    query: str
    limit: int = 12

@app.post('/api/discover/datasets')
def discover_datasets(payload: DatasetsQuery):
    try:
        results = search_datasets(payload.query, payload.limit)
        return {'results': results, 'total': len(results), 'query': payload.query}
    except Exception as e:
        logger.error(f'Datasets search failed: {e}')
        raise HTTPException(status_code=500, detail='Dataset search failed.')

class LearningQuery(BaseModel):
    query: str
    limit: int = 12

@app.post('/api/discover/learning')
def discover_learning(payload: LearningQuery):
    try:
        return search_learning(payload.query, payload.limit)
    except Exception as e:
        logger.error(f'Learning search failed: {e}')
        raise HTTPException(status_code=500, detail='Learning search failed.')

class PaperAnalysisQuery(BaseModel):
    action: str
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None

@app.post('/api/discover/analyze')
def discover_analyze(payload: PaperAnalysisQuery):
    try:
        from ai.llm_service import llm_service, LLMNotConfiguredError
        action = (payload.action or 'summarize').lower()
        action_prompts = {'explain': 'Explain this research paper in clear, accessible terms for a graduate student.', 'summarize': 'Provide a concise 3-5 sentence summary of this research paper.', 'contribution': 'What is the main contribution or novelty of this research paper?', 'limitations': 'What are the main limitations or weaknesses of this research paper?', 'methodology': 'Describe the methodology used in this research paper.', 'opportunities': 'Based on this paper, suggest possible research directions or gaps that could be explored further. Label these as suggestions, not confirmed gaps.'}
        task_desc = action_prompts.get(action, action_prompts['summarize'])
        authors_str = ', '.join(payload.authors or ['Unknown'])[:200]
        prompt = f"""You are ORBOT, an advanced, highly specialized academic research assistant for the KNO platform.\nYour behavior has been fine-tuned for academic rigor. You must strictly adhere to the following rules:\n1. Tone: Maintain a highly professional, academic, and objective tone. Do NOT use conversational filler (e.g., "Sure, here is...").\n2. Factual Grounding: Draw conclusions strictly from the provided abstract and metadata. Do NOT hallucinate external facts or methodologies not mentioned in the text.\n3. Formatting: Use concise, structured markdown. Use bullet points for multiple items. Do NOT output large, unbroken blocks of text.\n4. Hedging: If the abstract does not contain enough information to fully answer the prompt, explicitly state "The provided abstract does not detail this."\n\nPaper Metadata:\n- Title: {payload.title}\n- Authors: {authors_str}\n- Year: {payload.year or 'Unknown'}\n- Venue: {payload.venue or 'Unknown'}\n\nAbstract Context: \n{(payload.abstract or 'Not available')[:2000]}\n\nRequested Task: {task_desc}\n\nExecute the requested task now following the strict guidelines above."""
        result = llm_service.generate_response(prompt, task='discover_analyze')
        return {'action': action, 'result': result}
    except Exception as e:
        logger.error(f'Paper analysis failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

class LandscapeQuery(BaseModel):
    query: str
    papers: Optional[List[dict]] = None
    repositories: Optional[List[dict]] = None

@app.post('/api/discover/landscape')
def discover_landscape(payload: LandscapeQuery):
    try:
        from ai.llm_service import llm_service, LLMNotConfiguredError
        papers = payload.papers or []
        repos = payload.repositories or []
        papers_text = '\n'.join((f"- {p.get('title', 'Untitled')} ({p.get('year', '?')}) [{p.get('source', '')}]" for p in papers[:20])) or 'No papers provided.'
        repos_text = '\n'.join((f"- {r.get('full_name', r.get('title', '?'))}: {r.get('description', '')[:100]}" for r in repos[:8])) or 'No repositories provided.'
        prompt = f'''You are ORBOT, an intelligent research assistant for KNO.\n\nA researcher searched for: "{payload.query}"\n\nRetrieved research papers:\n{papers_text}\n\nRetrieved GitHub repositories:\n{repos_text}\n\nBased ONLY on the above retrieved evidence, generate a research landscape summary with:\n1. **Major Themes** — common topics across papers/repos\n2. **Common Approaches** — frequently used methods or techniques\n3. **Emerging Directions** — recent trends (if any)\n4. **Potentially Underexplored Areas** — label these clearly as suggestions, not confirmed gaps\n5. **Related Search Terms** — 5 specific search queries the researcher should also try\n\nIMPORTANT: Only draw conclusions from the retrieved papers/repos above. Do not fabricate research. Use hedged language like 'appears to be', 'possibly', 'may be worth exploring'.\n\nFormat in clear markdown with headings.'''
        result = llm_service.generate_response(prompt, task='discover_landscape')
        return {'landscape': result, 'query': payload.query}
    except Exception as e:
        logger.error(f'Landscape generation failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

class RefineQuery(BaseModel):
    query: str

@app.post('/api/discover/refine')
def discover_refine(payload: RefineQuery):
    try:
        from ai.llm_service import llm_service, LLMNotConfiguredError
        prompt = f'You are ORBOT, a research assistant for KNO.\n\nA researcher wants to search for: "{payload.query}"\n\nProvide:\n1. 5 refined, specific search queries they should try (more precise than the original)\n2. 3 related research areas they may not have considered\n3. 2-3 key authors or seminal papers to look for (if you know them; otherwise skip)\n\nRespond in JSON format:\n{{\n  "refined_queries": ["query1", "query2", "query3", "query4", "query5"],\n  "related_areas": ["area1", "area2", "area3"],\n  "key_references": ["ref1", "ref2"]\n}}\n\nOnly include real, specific queries. Do not make up paper titles.'
        result = llm_service.generate_response(prompt, task='discover_refine')
        import json, re
        json_match = re.search('\\{[\\s\\S]*\\}', result)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return {'suggestions': parsed, 'raw': result}
            except Exception:
                pass
        return {'suggestions': {'refined_queries': [], 'related_areas': [], 'key_references': []}, 'raw': result}
    except Exception as e:
        logger.error(f'Query refinement failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

class ComparePapersQuery(BaseModel):
    papers: List[dict]

@app.post('/api/discover/compare')
def discover_compare(payload: ComparePapersQuery):
    try:
        from ai.llm_service import llm_service, LLMNotConfiguredError
        if len(payload.papers) < 2:
            raise HTTPException(status_code=400, detail='Need at least 2 papers to compare.')
        papers_desc = ''
        for i, p in enumerate(payload.papers[:5], 1):
            authors = ', '.join((p.get('authors') or [])[:3])
            papers_desc += f"\nPaper {i}: {p.get('title', 'Untitled')}\nAuthors: {authors or 'Unknown'}\nYear: {p.get('year', '?')} | Venue: {p.get('venue', '?')}\nAbstract: {(p.get('abstract') or 'Not available')[:600]}\n"
        prompt = f'You are ORBOT, a research assistant for KNO.\n\nCompare the following {len(payload.papers)} research papers:\n{papers_desc}\n\nCreate a structured comparison table covering:\n- Research Problem\n- Methodology / Approach\n- Dataset Used\n- Key Results\n- Main Contribution\n- Limitations\n\nThen provide a 2-3 sentence synthesis of how these papers relate to each other.\n\nFormat as markdown with a table and a synthesis section.'
        result = llm_service.generate_response(prompt, task='discover_compare')
        return {'comparison': result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Paper comparison failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = ''
    brief_template: Optional[str] = ''
    plan_template: Optional[str] = ''

@app.get('/api/workspace-templates')
def list_workspace_templates():
    return {'templates': db.get_workspace_templates()}

@app.post('/api/workspace-templates')
def create_workspace_template_endpoint(payload: TemplateCreate):
    return db.create_workspace_template(payload.name, payload.description, payload.brief_template, payload.plan_template)

@app.delete('/api/workspace-templates/{template_id}')
def delete_workspace_template_endpoint(template_id: str):
    if not db.delete_workspace_template(template_id):
        raise HTTPException(status_code=404, detail='Template not found.')
    return {'status': 'success'}

@app.post('/api/workspaces/{workspace_id}/apply-template/{template_id}')
def apply_template_to_workspace(workspace_id: str, template_id: str):
    ws = db.get_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail='Workspace not found.')
    tmpl = db.get_workspace_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail='Template not found.')
    import json as _json
    brief_fields = {}
    plan_fields = {}
    if tmpl.get('brief_template'):
        try:
            brief_fields = _json.loads(tmpl['brief_template'])
        except Exception:
            brief_fields = {'topic': tmpl['brief_template']}
    if tmpl.get('plan_template'):
        try:
            plan_fields = _json.loads(tmpl['plan_template'])
        except Exception:
            plan_fields = {'problem_statement': tmpl['plan_template']}
    brief_result = None
    plan_result = None
    if brief_fields:
        brief_result = brief_service.update(workspace_id, brief_fields)
    if plan_fields:
        plan_result = project_plan_service.update(workspace_id, plan_fields)
    return {'status': 'success', 'brief': brief_result, 'project_plan': plan_result}

@app.post('/api/documents/{document_id}/tags')
def add_document_tag(document_id: str, payload: dict):
    tag = (payload or {}).get('tag', '').strip()
    if not tag:
        raise HTTPException(status_code=400, detail='Tag cannot be empty.')
    if not db.get_document_by_id(document_id):
        raise HTTPException(status_code=404, detail='Document not found.')
    db.add_document_tag(document_id, tag)
    return {'status': 'success', 'tags': db.get_document_tags(document_id)}

@app.delete('/api/documents/{document_id}/tags/{tag}')
def remove_document_tag(document_id: str, tag: str):
    removed = db.remove_document_tag(document_id, tag)
    if not removed:
        raise HTTPException(status_code=404, detail='Tag not found.')
    return {'status': 'success', 'tags': db.get_document_tags(document_id)}

@app.get('/api/documents/{document_id}/tags')
def list_document_tags(document_id: str):
    return {'tags': db.get_document_tags(document_id)}

@app.get('/api/tags')
def list_all_tags():
    return {'tags': db.get_all_tags()}

@app.get('/api/settings/providers')
def settings_providers():
    from ai.llm_service import llm_service
    providers = []
    for p in llm_service.providers:
        providers.append({'name': getattr(p, '_label', p.name) or p.name, 'model': getattr(p, 'model', ''), 'supports_vision': bool(p.supports_vision), 'status': 'configured', 'primary': p is llm_service.providers[0] if llm_service.providers else False})
    return {'configured': llm_service.is_configured, 'providers': providers}

@app.get('/api/settings')
def get_settings():
    from ai.config import ai_config
    return {'ui': {'theme': db.get_setting('ui,theme', 'light')}, 'chat': {'default_mode': db.get_setting('chat,default_mode', 'research'), 'history_window': int(db.get_setting('chat,history_window', '16') or '16')}, 'ai': {'primary_provider': db.get_setting('ai,primary_provider', ''), 'provider_configured': ai_config.is_gemini_configured}}

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    default_mode: Optional[str] = None
    history_window: Optional[int] = None

@app.put('/api/settings')
def update_settings(payload: SettingsUpdate):
    if payload.theme is not None:
        db.set_setting('ui,theme', payload.theme)
    if payload.default_mode is not None:
        if payload.default_mode not in ('research', 'project'):
            raise HTTPException(status_code=400, detail="default_mode must be 'research' or 'project'.")
        db.set_setting('chat,default_mode', payload.default_mode)
    if payload.history_window is not None:
        try:
            n = int(payload.history_window)
            if n < 1 or n > 100:
                raise ValueError()
            db.set_setting('chat,history_window', str(n))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail='history_window must be 1..100.')
    return {'status': 'success'}
from services.conversation_service import conversation_service

class ConversationCreate(BaseModel):
    user_id: Optional[str] = None
    scope: str = 'home'
    workspace_id: Optional[str] = None
    title: Optional[str] = None
    mode: str = 'research'

@app.post('/api/conversations')
def create_conversation(payload: ConversationCreate):
    if payload.scope not in ('home', 'workspace'):
        raise HTTPException(status_code=400, detail="scope must be 'home' or 'workspace'.")
    if payload.scope == 'workspace' and (not payload.workspace_id):
        raise HTTPException(status_code=400, detail='workspace_id required for workspace-scope conversations.')
    if payload.workspace_id and (not db.get_workspace_by_id(payload.workspace_id)):
        raise HTTPException(status_code=404, detail='Workspace not found.')
    if payload.mode not in ('research', 'project'):
        raise HTTPException(status_code=400, detail="mode must be 'research' or 'project'.")
    conv = conversation_service.ensure_conversation(user_id=payload.user_id, scope=payload.scope, workspace_id=payload.workspace_id, title=payload.title, mode=payload.mode)
    return conv

class ConversationListQuery(BaseModel):
    user_id: Optional[str] = None
    scope: Optional[str] = None
    workspace_id: Optional[str] = None
    limit: int = 50

@app.get('/api/conversations')
def list_conversations_endpoint(user_id: Optional[str]=None, scope: Optional[str]=None, workspace_id: Optional[str]=None, limit: int=50):
    items = conversation_service.list_for_user(user_id=user_id, scope=scope, workspace_id=workspace_id, limit=limit)
    return {'items': items, 'count': len(items)}

@app.get('/api/conversations/{conversation_id}')
def get_conversation_endpoint(conversation_id: str):
    conv = conversation_service.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    msgs = conversation_service.messages_of(conversation_id)
    return {'conversation': conv, 'messages': msgs}

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    mode: Optional[str] = None

@app.put('/api/conversations/{conversation_id}')
def update_conversation_endpoint(conversation_id: str, payload: ConversationUpdate):
    updates = payload.model_dump(exclude_none=True)
    if 'mode' in updates and updates['mode'] not in ('research', 'project'):
        raise HTTPException(status_code=400, detail="mode must be 'research' or 'project'.")
    updated = conversation_service.rename(conversation_id, payload.title) if 'title' in updates else conversation_service.get(conversation_id)
    if 'mode' in updates and updated:
        updated = db.update_conversation(conversation_id, mode=payload.mode)
    if not updated:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    return updated

@app.delete('/api/conversations/{conversation_id}')
def delete_conversation_endpoint(conversation_id: str):
    if not conversation_service.remove(conversation_id):
        raise HTTPException(status_code=404, detail='Conversation not found.')
    return {'status': 'success'}

class ConversationAppend(BaseModel):
    role: str
    content: str
    sources: Optional[List[dict]] = None
    trace: Optional[str] = None
    confidence: Optional[str] = None
    metadata: Optional[dict] = None
    suggested_followups: Optional[List[str]] = None
    insufficient_evidence: bool = False

@app.post('/api/conversations/{conversation_id}/messages')
def append_conversation_message(conversation_id: str, payload: ConversationAppend):
    if not conversation_service.get(conversation_id):
        raise HTTPException(status_code=404, detail='Conversation not found.')
    try:
        msg = conversation_service.save_message(conversation_id, role=payload.role, content=payload.content, sources=payload.sources, trace=payload.trace, confidence=payload.confidence, metadata=payload.metadata, suggested_followups=payload.suggested_followups, insufficient_evidence=payload.insufficient_evidence)
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class ConversationAskPayload(BaseModel):
    question: str
    mode: str = 'research'
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    history_window: int = 16

@app.post('/api/conversations/ask')
def conversation_ask(payload: ConversationAskPayload):
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail='Question cannot be empty.')
    if payload.mode not in ('research', 'project'):
        raise HTTPException(status_code=400, detail="mode must be 'research' or 'project'.")
    scope = 'workspace' if payload.workspace_id else 'home'
    conv = conversation_service.ensure_conversation(user_id=payload.user_id, scope=scope, workspace_id=payload.workspace_id, conversation_id=payload.conversation_id, title=payload.title, mode=payload.mode)
    history = conversation_service.load_history(conv['id'], max_messages=payload.history_window)
    conversation_service.save_message(conv['id'], role='user', content=payload.question.strip())
    try:
        result = rag_service.ask(question=payload.question.strip(), mode=payload.mode, history=history, document_id=payload.document_id, workspace_id=payload.workspace_id, top_k=5)
    except Exception as e:
        logger.error(f'conversation_ask failed: {e}')
        raise HTTPException(status_code=500, detail=str(e) or 'ORBOT failed to generate an answer.')
    assistant_msg = conversation_service.save_message(conv['id'], role='orbot', content=result.get('answer') or '', sources=result.get('sources'), trace=result.get('trace'), confidence=result.get('confidence'), metadata=result.get('metadata'), suggested_followups=result.get('suggested_followups'), insufficient_evidence=bool(result.get('insufficient_evidence')))
    conv = conversation_service.get(conv['id']) or conv
    return {'conversation': conv, 'user_message_id': assistant_msg['id'], 'result': result}

@app.get('/api/conversations/{conversation_id}/export')
def export_conversation_endpoint(conversation_id: str, format: str='markdown', download: bool=False):
    if not conversation_service.get(conversation_id):
        raise HTTPException(status_code=404, detail='Conversation not found.')
    fmt = (format or 'markdown').lower()
    if fmt in ('txt', 'text', 'plain'):
        body = conversation_service.export_plain_text(conversation_id)
        media = 'text/plain; charset=utf-8'
        ext = 'txt'
    else:
        body = conversation_service.export_markdown(conversation_id)
        media = 'text/markdown; charset=utf-8'
        ext = 'md'
    if download:
        from fastapi.responses import Response
        return Response(content=body, media_type=media, headers={'Content-Disposition': f'attachment; filename="orbot_conversation_{conversation_id}.{ext}"'})
    return {'format': fmt, 'content': body}

class AnswerExportPayload(BaseModel):
    user_question: str
    answer: str
    title: Optional[str] = None
    sources: Optional[List[dict]] = None
    trace: Optional[str] = None
    confidence: Optional[str] = None
    metadata: Optional[dict] = None
    followups: Optional[List[str]] = None
    format: str = 'markdown'
    conversation_id: Optional[str] = None

@app.post('/api/answers/export')
def export_single_answer(payload: AnswerExportPayload):
    try:
        body = conversation_service.export_single_answer(conversation_id=payload.conversation_id, user_question=payload.user_question, answer=payload.answer, sources=payload.sources, trace=payload.trace, confidence=payload.confidence, metadata=payload.metadata, title=payload.title, followups=payload.followups, format=payload.format)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    fmt = (payload.format or 'markdown').lower()
    if fmt in ('txt', 'text', 'plain'):
        return {'format': 'txt', 'content': body, 'mime': 'text/plain; charset=utf-8'}
    return {'format': 'markdown', 'content': body, 'mime': 'text/markdown; charset=utf-8'}

class GroundingCheckPayload(BaseModel):
    question: str
    answer: str
    sources: Optional[List[dict]] = None

@app.post('/api/grounding/verify')
def grounding_verify(payload: GroundingCheckPayload):
    from ai.grounding_service import verify_grounding
    chunks = payload.sources or []
    if not isinstance(chunks, list):
        raise HTTPException(status_code=400, detail='sources must be a list.')
    result = verify_grounding(question=payload.question or '', answer=payload.answer or '', chunks=chunks)
    return result
_TRUSTED_IMPORT_HOSTS = {'arxiv.org', 'www.arxiv.org', 'export.arxiv.org', 'openalex.org', 'api.openalex.org', 'api.crossref.org', 'crossref.org', 'huggingface.co', 'www.huggingface.co', 'github.com', 'raw.githubusercontent.com', 'gist.githubusercontent.com'}

def _is_private_host(hostname: str) -> bool:
    import ipaddress
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(hostname, None)
    except Exception:
        return True
    for info in infos:
        sockaddr = info[4]
        try:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return True
        except ValueError:
            continue
    return False

def _safe_import_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise HTTPException(status_code=400, detail='Only http(s) URLs are allowed for import.')
    host = (parsed.hostname or '').lower()
    if not host:
        raise HTTPException(status_code=400, detail='Import URL must include a hostname.')
    if host not in _TRUSTED_IMPORT_HOSTS:
        raise HTTPException(status_code=400, detail=f"Import host '{host}' is not in the trusted allow-list.")
    if _is_private_host(host):
        raise HTTPException(status_code=400, detail='Import host resolves to a private address.')
    return url

@app.get('/api/orbot/research-trace')
def orbot_research_trace():
    return {'title': 'Research Trace', 'description': 'ORBOT never reveals chain-of-thought. Below is the observable process pipeline.', 'steps': [{'label': 'Query understood', 'description': 'ORBOT parses your question and conversation history.'}, {'label': 'Documents searched', 'description': 'FAISS retrieves semantically similar chunks from your library.'}, {'label': 'Chunks retrieved', 'description': 'Top-K chunks above the similarity threshold are kept.'}, {'label': 'Chunks selected', 'description': 'Chunks are filtered by document/workspace scope.'}, {'label': 'Sources used', 'description': 'Numbered SOURCES appear in the prompt; the model cites them by index.'}, {'label': 'Evidence confidence', 'description': 'HIGH / MEDIUM / LOW / INSUFFICIENT, derived from retrieval metrics.'}, {'label': 'External sources used', 'description': 'Where relevant, ORBOT surfaces arXiv/OpenAlex/Crossref/GitHub/HF links.'}, {'label': 'Answer grounded', 'description': 'The final answer cites sources by file and page. Verify important claims.'}], 'epistemic_labels': {'FACT': 'Directly supported by retrieved context.', 'INFERENCE': 'A reasonable interpretation derived from the context.', 'INTERPRETATION': "The author's framing or claim (paraphrased).", 'UNCERTAINTY': 'Not enough evidence to support the claim.'}, 'external_labels': {'DOCUMENT': 'Information from your uploaded documents.', 'EXTERNAL': 'Information retrieved from external research sources (arXiv/OpenAlex/Crossref/GitHub/HF/YouTube).', 'INFERENCE': 'Reasoning derived from the evidence above.', 'RECOMMENDATION': 'A suggested next step.'}}

@app.get('/api/rag/features')
def rag_features():
    return _feature_flags()

@app.get('/api/rag/bm25/stats')
def rag_bm25_stats():
    try:
        _bm25_index._maybe_reload()
        return {'status': 'ok', 'doc_count': len(_bm25_index._docs), 'enabled': True}
    except Exception as exc:
        return {'status': 'error', 'detail': str(exc), 'enabled': False}

@app.post('/api/rag/bm25/rebuild')
def rag_bm25_rebuild():
    try:
        all_chunks = db.get_all_chunks()
        _bm25_index.rebuild(all_chunks)
        return {'status': 'ok', 'rebuilt': len(all_chunks)}
    except Exception as exc:
        logger.exception('BM25 rebuild failed')
        raise HTTPException(status_code=500, detail=f'BM25 rebuild failed: {exc}')

@app.get('/api/rag/graphrag/stats')
def rag_graphrag_stats():
    backend_kind = 'neo4j' if _graphrag_service.backend and _graphrag_service.backend.__class__.__name__ == '_Neo4jBackend' else 'in-memory'
    return {'enabled': _graphrag_service.enabled, 'ingested_chunks': _graphrag_service._ingested_count, 'backend': backend_kind}

class CitationGraphBuildIn(BaseModel):
    force: bool = False

@app.post('/api/documents/{document_id}/citation-graph/build')
def build_citation_graph(document_id: str, payload: Optional[CitationGraphBuildIn]=None):
    if not db.get_document_by_id(document_id):
        raise HTTPException(status_code=404, detail='Document not found.')
    try:
        graph = citation_graph_service.build_for_document(document_id, force=payload.force if payload else False)
    except Exception as exc:
        logger.exception('Citation graph build failed')
        raise HTTPException(status_code=500, detail=f'Citation graph build failed: {exc}')
    return graph

@app.get('/api/documents/{document_id}/citation-graph')
def get_citation_graph(document_id: str):
    if not db.get_document_by_id(document_id):
        raise HTTPException(status_code=404, detail='Document not found.')
    return db.get_citation_graph_for_document(document_id)

class CitationAddIn(BaseModel):
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    context: Optional[str] = None
    page_number: Optional[int] = None

@app.post('/api/documents/{document_id}/citation-graph/add')
def add_citation_reference(document_id: str, payload: CitationAddIn):
    if not db.get_document_by_id(document_id):
        raise HTTPException(status_code=404, detail='Document not found.')
    try:
        return citation_graph_service.add_reference_manually(document_id, payload.model_dump(exclude_none=True))
    except Exception as exc:
        logger.exception('Add citation reference failed')
        raise HTTPException(status_code=500, detail=f'Add reference failed: {exc}')

class CitationLookupIn(BaseModel):
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None

@app.post('/api/citations/lookup')
def lookup_citation_metadata(payload: CitationLookupIn):
    if not payload.doi and (not payload.arxiv_id):
        raise HTTPException(status_code=400, detail='Provide a DOI or arXiv ID.')
    try:
        ref = citation_graph_service.find_reference_metadata(doi=payload.doi, arxiv_id=payload.arxiv_id)
    except Exception as exc:
        logger.exception('Citation lookup failed')
        raise HTTPException(status_code=500, detail=f'Lookup failed: {exc}')
    if not ref:
        raise HTTPException(status_code=404, detail='No metadata found for the supplied identifier.')
    return ref

class CitationImportIn(BaseModel):
    workspace_id: Optional[str] = None
    reference_id: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None

@app.post('/api/citations/import')
def import_citation_as_document(payload: CitationImportIn):
    from services.document_processor import UnsupportedFileTypeError, DocumentProcessingError
    doi = payload.doi
    arxiv_id = payload.arxiv_id
    if not (doi or arxiv_id or payload.url):
        raise HTTPException(status_code=400, detail='Provide DOI, arXiv ID, or URL.')
    ref = citation_graph_service.find_reference_metadata(doi=doi, arxiv_id=arxiv_id) or {}
    title = payload.title or ref.get('title') or 'Imported paper'
    authors = payload.authors or ref.get('authors')
    year = payload.year or ref.get('year')
    venue = payload.venue or ref.get('venue')
    abstract = payload.abstract or ref.get('abstract')
    pdf_url = None
    if arxiv_id:
        pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
    elif doi and (not pdf_url):
        pdf_url = f'https://doi.org/{doi}'
    elif payload.url:
        pdf_url = payload.url
    if not pdf_url:
        raise HTTPException(status_code=400, detail='Could not derive a PDF URL for this reference.')
    safe_url = _safe_import_url(pdf_url)
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(safe_url, headers={'User-Agent': 'IKDP/1.0 (mailto:dev@example.com)'})
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f'Source returned status {resp.status_code}.')
        if arxiv_id:
            filename = f"{arxiv_id.replace('/', '_')}.pdf"
        elif payload.url and payload.url.lower().endswith('.pdf'):
            filename = safe_url.rsplit('/', 1)[-1] or 'imported.pdf'
        else:
            slug = re.sub('[^A-Za-z0-9._-]+', '_', (title or 'imported')[:60]).strip('_')
            filename = f"{slug or 'imported'}.pdf"
        result = process_document(resp.content, filename)
        doc = db.create_document({**result, 'title': title, 'author': authors.split(',')[0] if authors else None, 'year': year})
        _persist_upload(resp.content, doc['id'], filename)
        chunks = chunker.chunk_document({**result, 'id': doc['id']})
        if chunks:
            embedder = EmbeddingService()
            texts = [c['text'] for c in chunks]
            embeddings = embedder.embed_texts(texts)
            for chunk, emb in zip(chunks, embeddings):
                chunk['embedding'] = emb
            db.create_chunks(doc['id'], chunks)
            inserted = db.get_chunks_for_document(doc['id'])
            vector_store.add_embeddings([c['id'] for c in inserted], embeddings)
        ref_payload = {'source': 'arxiv' if arxiv_id else 'crossref' if doi else 'manual', 'title': title, 'authors': authors, 'year': year, 'venue': venue, 'doi': doi, 'arxiv_id': arxiv_id, 'abstract': abstract, 'url': safe_url, 'imported_document_id': doc['id']}
        saved_ref = db.upsert_citation_reference(ref_payload)
        if payload.workspace_id:
            db.add_document_to_workspace(payload.workspace_id, doc['id'])
        return {'document': doc, 'reference': saved_ref}
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception('Citation import failed')
        raise HTTPException(status_code=500, detail=f'Import failed: {exc}')
