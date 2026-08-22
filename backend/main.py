import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from services.document_processor import process_document, UnsupportedFileTypeError, DocumentProcessingError
import database.database as db
from ai.chunker import DocumentChunker
from ai.vector_store import vector_store
from ai.embeddings import EmbeddingService
from ai.compare_service import compare_service
from ai.document_analysis_service import document_analysis_service
from ai.llm_service import LLMNotConfiguredError
from services.workspace_services import (
    notes_service, brief_service, project_plan_service,
    experiments_service, research_gap_service, synthesis_service,
)
from services.citations_service import (
    list_citations, create_citation, delete_citation,
    format_citation, extract_citation_candidates,
)
from services.discovery_service import search_research
from services.github_service import search_repositories
from services.datasets_service import search_datasets
from services.studio_service import studio_service, list_templates

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Default dev origins. Override with comma-separated CORS_ALLOWED_ORIGINS env var
# (e.g. "https://kno.example.com,http://localhost:5174").
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:3000",
]

chunker = DocumentChunker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database when the application starts
    db.init_db()
    logger.info("Application started – database initialized")
    yield
    # Graceful shutdown
    logger.info("Shutting down – flushing FAISS index to disk")
    try:
        vector_store._save()
    except Exception as exc:
        logger.error(f"Failed to flush FAISS index on shutdown: {exc}")
    logger.info("Shutdown complete")

app = FastAPI(title="Intelligent Knowledge Discovery Platform API", lifespan=lifespan)

# Configure CORS so the React frontend can communicate with the backend.
# Origins can be overridden via CORS_ALLOWED_ORIGINS env var.
_env_origins = os.getenv("CORS_ALLOWED_ORIGINS")
if _env_origins:
    _allowed_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    _allowed_origins = DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _paginate(items, offset: int, limit: int) -> dict:
    """Return a pagination envelope dict."""
    total = len(items)
    return {
        "items": items[offset: offset + limit],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_LLM_ENDPOINTS = {"/api/ask", "/api/search"}
_LLM_PREFIXES = ("/api/workspaces/", "/api/documents/")
_LLM_SUFFIXES = ("/compare", "/research-gap", "/synthesis", "/auto-draft", "/auto-generate")

class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, general_limit: int = 60, llm_limit: int = 10, window: int = 60):
        self.general_limit = general_limit
        self.llm_limit = llm_limit
        self.window = window
        self._requests: dict = defaultdict(list)

    def _is_llm(self, path: str) -> bool:
        if path in _LLM_ENDPOINTS:
            return True
        if path.startswith(_LLM_PREFIXES):
            return any(path.endswith(s) for s in _LLM_SUFFIXES)
        return False

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        now = time.time()
        ip = self._client_ip(request)
        key = f"{ip}:{'llm' if self._is_llm(request.url.path) else 'gen'}"
        limit = self.llm_limit if self._is_llm(request.url.path) else self.general_limit
        self._requests[key] = [t for t in self._requests[key] if t > now - self.window]
        if len(self._requests[key]) >= limit:
            from fastapi.responses import JSONResponse
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
        self._requests[key].append(now)

_rate_limiter = RateLimiter()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        _rate_limiter.check(request)
    except HTTPException as exc:
        from starlette.responses import JSONResponse as _JSONResponse
        return _JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.get("/api/health")
def health_check():
    """Basic health check endpoint to verify the backend and configuration are running."""
    return {
        "status": "healthy", 
        "message": "Backend is running!",
        "ai_configuration": "configured" if ai_config.is_gemini_configured else "not configured"
    }


@app.get("/api/health/deep")
def deep_health_check():
    """Detailed health check that probes database, FAISS index, and LLM providers."""
    checks = {}

    # 1. Database connectivity
    try:
        conn = db.get_connection()
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = {"status": "healthy"}
    except Exception as exc:
        checks["database"] = {"status": "unhealthy", "detail": str(exc)}

    # 2. FAISS index status
    try:
        ntotal = vector_store.index.ntotal if vector_store.index else 0
        checks["faiss"] = {
            "status": "healthy",
            "vectors": ntotal,
            "has_vectors": ntotal > 0,
        }
    except Exception as exc:
        checks["faiss"] = {"status": "unhealthy", "detail": str(exc)}

    # 3. LLM provider availability
    try:
        from ai.llm_service import llm_service
        configured = [p.name for p in llm_service.providers if getattr(p, "_configured", True)]
        checks["llm"] = {
            "status": "healthy" if configured else "degraded",
            "configured_providers": configured,
        }
    except Exception as exc:
        checks["llm"] = {"status": "unhealthy", "detail": str(exc)}

    overall = "healthy" if all(c["status"] == "healthy" for c in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a document upload (PDF, DOCX, TXT, CSV, XLSX, JSON, MD,
    code files, Jupyter notebooks, images), extracts its text,
    persists it to the database, chunks and embeds, and indexes it.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Server-side extension allow-list. Prevents users uploading
    # arbitrary binaries like .exe, .so, .dll, etc.
    fname = file.filename
    ext = ("." + fname.rsplit(".", 1)[-1].lower()) if "." in fname else ""
    if ext and ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: " +
                  ", ".join(sorted(ALLOWED_UPLOAD_EXTS)),
        )

    # Reasonable upper bound — 25 MB is plenty for research papers,
    # datasets, and code files. Larger files should be chunked by the
    # user before upload.
    MAX_BYTES = 25 * 1024 * 1024

    try:
        # Read the file content into memory
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_BYTES // (1024*1024)} MB.",
            )

        # Process the document to extract text and metadata
        result = process_document(content, fname)

        # Store in database (this returns the record without extracted_text)
        doc_record = db.create_document(result)

        # Chunk the document and save to database
        chunks = chunker.chunk_document(result)
        if chunks:
            # Generate embeddings before saving to DB
            embedder = EmbeddingService()
            texts = [c['text'] for c in chunks]
            embeddings = embedder.embed_texts(texts)

            # Attach embeddings to chunks
            for chunk, emb in zip(chunks, embeddings):
                chunk['embedding'] = emb

            db.create_chunks(doc_record["id"], chunks)

            # Fetch the inserted chunks to get their generated IDs
            inserted_chunks = db.get_chunks_for_document(doc_record["id"])
            chunk_ids = [c['id'] for c in inserted_chunks]

            vector_store.add_embeddings(chunk_ids, embeddings)

        return doc_record

    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DocumentProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Document upload failed for {fname}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during document processing.")

@app.get("/api/documents")
def get_documents(offset: int = 0, limit: int = 50):
    """Returns a paginated list of all uploaded documents (metadata only)."""
    try:
        docs = db.get_documents()
        return _paginate(docs, offset, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve documents.")

@app.post("/api/documents")
def create_document_endpoint(payload: dict):
    """Creates a document from raw content (e.g., Markdown for Studio)."""
    try:
        content = payload.get("content", "")
        title = payload.get("title", "Untitled")
        doc_type = payload.get("document_type", "markdown")
        doc_data = {
            "filename": title,
            "title": title,
            "file_type": doc_type,
            "file_size": len(content.encode("utf-8")),
            "character_count": len(content),
            "text": content,
            "page_count": 1,
        }
        doc = db.create_document(doc_data)
        workspace_id = payload.get("workspace_id")
        if workspace_id and doc.get("id"):
            db.add_document_to_workspace(workspace_id, doc["id"])

        if content and doc.get("id"):
            chunks = chunker.chunk_document(doc)
            if chunks:
                embedder = EmbeddingService()
                texts = [c['text'] for c in chunks]
                embeddings = embedder.embed_texts(texts)
                for chunk, emb in zip(chunks, embeddings):
                    chunk['embedding'] = emb
                db.create_chunks(doc["id"], chunks)
                inserted_chunks = db.get_chunks_for_document(doc["id"])
                chunk_ids = [c['id'] for c in inserted_chunks]
                vector_store.add_embeddings(chunk_ids, embeddings)

        return {"document": doc}
    except Exception as e:
        logger.exception("Document creation failed")
        raise HTTPException(status_code=500, detail="Failed to create document.")

@app.put("/api/documents/{document_id}")
def update_document_endpoint(document_id: str, payload: dict):
    """Updates a document's fields (title, content, etc.)."""
    try:
        updates = {}
        if "title" in payload:
            updates["title"] = payload["title"]
        if "content" in payload:
            updates["extracted_text"] = payload["content"]
            updates["character_count"] = len(payload["content"])
        doc = db.update_document(document_id, **updates)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        if "content" in payload and payload["content"]:
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

        return {"document": doc}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Document update failed for {document_id}")
        raise HTTPException(status_code=500, detail="Failed to update document.")

@app.get("/api/workspaces/{workspace_id}/documents")
def list_workspace_documents(workspace_id: str):
    """Returns all documents in a workspace."""
    try:
        if not db.get_workspace_by_id(workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found.")
        docs = db.get_workspace_documents(workspace_id)
        return {"documents": docs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list workspace documents.")

@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    """Returns a specific document's metadata and extracted text."""
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve the document.")

@app.get("/api/documents/{document_id}/chunks")
def get_document_chunks(document_id: str):
    """Returns all chunks for a specific document. Used for development verification."""
    try:
        # Check if doc exists
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        chunks = db.get_chunks_for_document(document_id)
        return chunks
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve chunks.")

@app.get("/api/documents/{document_id}/versions")
def list_document_versions(document_id: str):
    """List all version snapshots for a document."""
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"versions": db.get_document_versions(document_id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List versions failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list document versions.")


@app.post("/api/documents/{document_id}/versions")
def create_document_version(document_id: str):
    """Create a snapshot version of the document's current state."""
    try:
        doc = db.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        version = db.create_document_version(
            doc_id=document_id,
            title=doc.get("title") or doc.get("filename", "Untitled"),
            content=doc.get("extracted_text", ""),
        )
        return version
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create version failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create document version.")


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    """Deletes a document by ID and triggers FAISS rebuild."""
    try:
        success = db.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        # Rebuild vector index because we removed chunks
        vector_store.rebuild_index()
        
        return {"status": "success", "message": "Document deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete the document.")

from ai.rag_service import rag_service

class SearchQuery(BaseModel):
    query: str
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    top_k: int = 5

# Allowed upload extensions (server-side enforcement)
ALLOWED_UPLOAD_EXTS = {
    ".pdf", ".docx", ".txt", ".md", ".markdown",
    ".csv", ".xlsx", ".json",
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".go", ".rs", ".rb", ".sh", ".bash",
    ".html", ".htm", ".css", ".xml", ".yaml", ".yml", ".toml",
    ".ipynb",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}

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
    mode: str = "Research"
    history: List[MessageData] = []
    attachments: List[AttachmentData] = []
    document_id: Optional[str] = None
    documentId: Optional[str] = None
    workspace_id: Optional[str] = None
    workspaceId: Optional[str] = None
    top_k: int = 5

class CompareQuery(BaseModel):
    document_ids: List[str]

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = ""

@app.post("/api/search")
def search_documents(payload: SearchQuery):
    """
    Performs semantic vector search across chunks.
    Optionally restricts to a specific document_id.
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    try:
        embedder = EmbeddingService()
        query_embedding = embedder.embed_text(payload.query)
        
        # If filtering by document_id, fetch more candidates from FAISS
        # because some might belong to other documents and will be filtered out.
        search_k = payload.top_k * 5 if payload.document_id else payload.top_k
        
        faiss_results = vector_store.search(query_embedding, top_k=search_k)
        if not faiss_results:
            return []
            
        # Retrieve actual chunks from DB
        chunk_ids = [res["chunk_id"] for res in faiss_results]
        db_chunks = db.get_chunks_by_ids(chunk_ids)
        
        # Convert DB chunks to a dictionary for fast lookup
        chunk_dict = {c['id']: c for c in db_chunks}
        
        final_results = []
        for faiss_res in faiss_results:
            cid = faiss_res["chunk_id"]
            if cid in chunk_dict:
                chunk = chunk_dict[cid]
                # Apply document filter if requested
                if payload.document_id and chunk['document_id'] != payload.document_id:
                    continue
                
                # Apply workspace filter if requested
                if payload.workspace_id and chunk['document_id'] not in [d['id'] for d in db.get_documents_for_workspace(payload.workspace_id)]:
                    continue
                    
                result = {
                    "chunk_id": cid,
                    "document_id": chunk['document_id'],
                    "chunk_index": chunk['chunk_index'],
                    "page_number": chunk['page_number'],
                    "text": chunk['text'],
                    "distance": faiss_res["distance"]
                }
                final_results.append(result)
                
                if len(final_results) >= payload.top_k:
                    break
                    
        return final_results
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during search.")

@app.post("/api/ask")
def ask_question(payload: AskQuery):
    """
    Answers a user question grounded in retrieved document chunks.
    """
    q_text = payload.question or payload.message or payload.query or ""
    if not q_text.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
        
    doc_id = payload.document_id or payload.documentId
    ws_id = payload.workspace_id or payload.workspaceId

    try:
        response = rag_service.ask(
            question=q_text.strip(),
            mode=payload.mode,
            history=payload.history,
            attachments=payload.attachments,
            document_id=doc_id,
            workspace_id=ws_id,
            top_k=payload.top_k
        )
        return response
    except Exception as e:
        logger.error(f"Ask API error: {e}")
        # Send a clean error message back to the frontend
        error_msg = str(e) if str(e) else "An unexpected error occurred."
        raise HTTPException(status_code=500, detail=error_msg)

# --- WORKSPACES API ---

@app.post("/api/workspaces")
def create_workspace(payload: WorkspaceCreate):
    try:
        ws = db.create_workspace(payload.name, payload.description)
        return ws
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create workspace.")

@app.get("/api/workspaces")
def get_workspaces(offset: int = 0, limit: int = 50):
    try:
        return _paginate(db.get_all_workspaces(), offset, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve workspaces.")

@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    try:
        ws = db.get_workspace_by_id(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found.")
            
        docs = db.get_documents_for_workspace(workspace_id)
        ws["documents"] = docs
        return ws
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve workspace.")

@app.put("/api/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, payload: WorkspaceCreate):
    try:
        ws = db.update_workspace(workspace_id, payload.name, payload.description)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        return ws
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update workspace.")

@app.delete("/api/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str):
    try:
        success = db.delete_workspace(workspace_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        return {"status": "success", "message": "Workspace deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete workspace.")

@app.post("/api/workspaces/{workspace_id}/documents/{document_id}")
def add_document_to_workspace(workspace_id: str, document_id: str):
    try:
        # Check if doc exists first
        if not db.get_document_by_id(document_id):
            raise HTTPException(status_code=404, detail="Document not found.")
            
        success = db.add_document_to_workspace(workspace_id, document_id)
        if not success:
            # Check if workspace exists
            if not db.get_workspace_by_id(workspace_id):
                raise HTTPException(status_code=404, detail="Workspace not found.")
            # If both exist, it's likely a duplicate
            # We treat duplicates safely, returning success
        
        return {"status": "success", "message": "Document added to workspace."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to add document to workspace.")

@app.delete("/api/workspaces/{workspace_id}/documents/{document_id}")
def remove_document_from_workspace(workspace_id: str, document_id: str):
    try:
        success = db.remove_document_from_workspace(workspace_id, document_id)
        if not success:
            # We don't error out if it's already removed, just return success or 404
            raise HTTPException(status_code=404, detail="Relationship not found.")
        return {"status": "success", "message": "Document removed from workspace."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to remove document from workspace.")


@app.post("/api/workspaces/{workspace_id}/compare")
def compare_workspace_documents(workspace_id: str, payload: CompareQuery):
    """
    Compares 2 to 5 documents attached to a research workspace.
    """
    doc_ids = payload.document_ids

    # 1. Selection count validation (2 to 5)
    if len(doc_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 papers to compare.")
    if len(doc_ids) > 5:
        raise HTTPException(status_code=400, detail="You can compare up to 5 papers at a time.")

    # 2. Workspace existence validation
    ws = db.get_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    # 3. Workspace document membership validation
    ws_docs = db.get_documents_for_workspace(workspace_id)
    ws_doc_ids = {d["id"] for d in ws_docs}

    for d_id in doc_ids:
        # Check document exists
        if not db.get_document_by_id(d_id):
            raise HTTPException(status_code=404, detail=f"Document {d_id} not found.")
        # Check document belongs to workspace
        if d_id not in ws_doc_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Document {d_id} does not belong to workspace {workspace_id}."
            )

    try:
        result = compare_service.compare_documents(workspace_id, doc_ids)
        return result
    except Exception as e:
        logger.error(f"Comparison API error: {e}")
        error_msg = str(e) if str(e) else "An unexpected error occurred during comparison."
        raise HTTPException(status_code=500, detail=error_msg)


# --- DOCUMENT ANALYSIS (per-document Summary / Insights / Sources) ---

@app.get("/api/documents/{document_id}/summary")
def get_document_summary(document_id: str):
    """
    Generate a grounded narrative summary of a single uploaded document.
    Result includes confidence label and the chunk ids used as context.
    """
    try:
        return document_analysis_service.summary(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Summary API error for {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the summary.",
        )


@app.get("/api/documents/{document_id}/insights")
def get_document_insights(document_id: str):
    """
    Extract structured insights (key concepts, methodology, findings,
    metrics, limitations, observations, future work) from a document.
    """
    try:
        return document_analysis_service.insights(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Insights API error for {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while extracting insights.",
        )


@app.get("/api/documents/{document_id}/sources")
def get_document_sources(document_id: str):
    """
    Return chunk-level source references for a document. No LLM call.
    """
    try:
        return document_analysis_service.sources(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Sources API error for {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while retrieving sources.",
        )


# ============================================================================
# WORKSPACE INTELLIGENCE — Notes, Brief, Project Plan, Experiments
# ============================================================================

# ---------- Notes ----------

class NoteIn(BaseModel):
    title: str
    content: str
    kind: str = "note"
    source_message_id: Optional[str] = None

class NoteUpdate(BaseModel):
    title: str
    content: str


@app.get("/api/workspaces/{workspace_id}/notes")
def list_workspace_notes(workspace_id: str, offset: int = 0, limit: int = 50):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    notes = notes_service.list(workspace_id)
    paginated = _paginate(notes, offset, limit)
    paginated["workspace_id"] = workspace_id
    return paginated


@app.post("/api/workspaces/{workspace_id}/notes")
def create_workspace_note(workspace_id: str, payload: NoteIn):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return notes_service.create(workspace_id, payload.title, payload.content,
                                     kind=payload.kind, source_message_id=payload.source_message_id)
    except Exception as e:
        logger.error(f"Note create failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create note.")


@app.put("/api/notes/{note_id}")
def update_note(note_id: str, payload: NoteUpdate):
    try:
        updated = notes_service.update(note_id, payload.title, payload.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update note.")
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found.")
    return updated


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str):
    if not notes_service.delete(note_id):
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"status": "success"}


# ---------- Research Brief ----------

@app.get("/api/workspaces/{workspace_id}/brief")
def get_research_brief(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
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


@app.put("/api/workspaces/{workspace_id}/brief")
def update_research_brief(workspace_id: str, payload: BriefUpdate):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    fields = payload.model_dump(exclude_none=True)
    return brief_service.update(workspace_id, fields)


@app.post("/api/workspaces/{workspace_id}/brief/auto-draft")
def auto_draft_brief(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return brief_service.auto_draft(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Auto-draft brief failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to auto-draft brief.")


# ---------- Project Plan ----------

@app.get("/api/workspaces/{workspace_id}/project-plan")
def get_project_plan(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
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


@app.put("/api/workspaces/{workspace_id}/project-plan")
def update_project_plan(workspace_id: str, payload: ProjectPlanUpdate):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return project_plan_service.update(workspace_id, payload.model_dump(exclude_none=True))


@app.post("/api/workspaces/{workspace_id}/project-plan/auto-generate")
def auto_generate_project_plan(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return project_plan_service.auto_generate(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Auto-gen project plan failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to auto-generate project plan.")


# ---------- Experiments ----------

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


@app.get("/api/workspaces/{workspace_id}/experiments")
def list_experiments(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return {"workspace_id": workspace_id, "experiments": experiments_service.list(workspace_id)}


@app.post("/api/workspaces/{workspace_id}/experiments")
def create_experiment(workspace_id: str, payload: ExperimentIn):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return experiments_service.create(workspace_id, payload.name,
                                          model=payload.model, dataset=payload.dataset,
                                          configuration=payload.configuration,
                                          metric=payload.metric, result=payload.result,
                                          experiment_date=payload.experiment_date,
                                          notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/experiments/{experiment_id}")
def update_experiment(experiment_id: str, payload: ExperimentUpdate):
    updated = experiments_service.update(experiment_id, **payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return updated


@app.delete("/api/experiments/{experiment_id}")
def delete_experiment(experiment_id: str):
    if not experiments_service.delete(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return {"status": "success"}


@app.get("/api/workspaces/{workspace_id}/experiments/analytics")
def experiments_analytics(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return experiments_service.analytics(workspace_id)


# ---------- Research Gap Analysis ----------

@app.post("/api/workspaces/{workspace_id}/research-gap")
def workspace_research_gap(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return research_gap_service.analyze(workspace_id)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Research gap failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform research-gap analysis.")


# ---------- Workspace Synthesis ----------

class SynthesisQuery(BaseModel):
    question: Optional[str] = None


@app.post("/api/workspaces/{workspace_id}/synthesis")
def workspace_synthesis(workspace_id: str, payload: SynthesisQuery):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    try:
        return synthesis_service.synthesize(workspace_id, payload.question)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to synthesize workspace.")


# ============================================================================
# CITATIONS
# ============================================================================

class CitationIn(BaseModel):
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    workspace_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: str = "manual"
    external_id: Optional[str] = None
    abstract: Optional[str] = None


@app.get("/api/citations")
def get_citations(workspace_id: Optional[str] = None):
    return {"citations": list_citations(workspace_id=workspace_id)}


@app.post("/api/citations")
def add_citation(payload: CitationIn):
    return create_citation(payload.model_dump(exclude_none=True))


@app.delete("/api/citations/{citation_id}")
def remove_citation(citation_id: str):
    if not delete_citation(citation_id):
        raise HTTPException(status_code=404, detail="Citation not found.")
    return {"status": "success"}


@app.post("/api/documents/{document_id}/citations/extract")
def extract_citations_from_document(document_id: str):
    """Heuristically extract citation candidates from a document."""
    try:
        candidates = extract_citation_candidates(document_id)
    except Exception as e:
        logger.error(f"Citation extract failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract citations.")
    return {"document_id": document_id, "candidates": candidates}


@app.get("/api/citations/format")
def format_citation_endpoint(id: str, style: str = "ieee"):
    from services.citations_service import list_citations as _list
    cite = None
    for c in _list(workspace_id=None):
        if c["id"] == id:
            cite = c
            break
    if not cite:
        raise HTTPException(status_code=404, detail="Citation not found.")
    return {"id": id, "style": style, "formatted": format_citation(cite, style)}


@app.post("/api/citations/bibliography")
def bibliography(payload: dict):
    """Format multiple citations in a chosen style. payload: {style, ids}."""
    style = (payload or {}).get("style", "ieee")
    ids = (payload or {}).get("ids", []) or []
    from services.citations_service import list_citations as _list
    items = []
    for c in _list(workspace_id=None):
        if c["id"] in ids:
            items.append(format_citation(c, style))
    return {"style": style, "bibliography": items, "count": len(items)}


# ============================================================================
# DISCOVERY — OpenAlex, Crossref, arXiv
# ============================================================================

class DiscoveryQuery(BaseModel):
    query: str
    limit_per_source: int = 8


@app.post("/api/discover/research")
def discover_research(payload: DiscoveryQuery):
    try:
        return search_research(payload.query, payload.limit_per_source)
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail="Discovery failed.")


# ---------- GitHub ----------

class GithubQuery(BaseModel):
    query: str
    limit: int = 10


@app.post("/api/discover/github")
def discover_github(payload: GithubQuery):
    try:
        return search_repositories(payload.query, payload.limit)
    except Exception as e:
        logger.error(f"GitHub search failed: {e}")
        raise HTTPException(status_code=500, detail="GitHub search failed.")


# ---------- Datasets ----------

class DatasetsQuery(BaseModel):
    query: str
    limit: int = 10


@app.post("/api/discover/datasets")
def discover_datasets(payload: DatasetsQuery):
    try:
        results = search_datasets(payload.query, payload.limit)
        return {"results": results, "available": bool(results) or None, "query": payload.query}
    except Exception as e:
        logger.error(f"Datasets search failed: {e}")
        raise HTTPException(status_code=500, detail="Dataset search failed.")


# ============================================================================
# RESEARCH STUDIO
# ============================================================================

# ============================================================================
# WORKSPACE TEMPLATES
# ============================================================================

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    brief_template: Optional[str] = ""
    plan_template: Optional[str] = ""


@app.get("/api/workspace-templates")
def list_workspace_templates():
    return {"templates": db.get_workspace_templates()}


@app.post("/api/workspace-templates")
def create_workspace_template_endpoint(payload: TemplateCreate):
    return db.create_workspace_template(
        payload.name, payload.description,
        payload.brief_template, payload.plan_template,
    )


@app.delete("/api/workspace-templates/{template_id}")
def delete_workspace_template_endpoint(template_id: str):
    if not db.delete_workspace_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"status": "success"}


@app.post("/api/workspaces/{workspace_id}/apply-template/{template_id}")
def apply_template_to_workspace(workspace_id: str, template_id: str):
    ws = db.get_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    tmpl = db.get_workspace_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found.")

    import json as _json
    brief_fields = {}
    plan_fields = {}

    if tmpl.get("brief_template"):
        try:
            brief_fields = _json.loads(tmpl["brief_template"])
        except Exception:
            brief_fields = {"topic": tmpl["brief_template"]}
    if tmpl.get("plan_template"):
        try:
            plan_fields = _json.loads(tmpl["plan_template"])
        except Exception:
            plan_fields = {"problem_statement": tmpl["plan_template"]}

    brief_result = None
    plan_result = None
    if brief_fields:
        brief_result = brief_service.update(workspace_id, brief_fields)
    if plan_fields:
        plan_result = project_plan_service.update(workspace_id, plan_fields)

    return {
        "status": "success",
        "brief": brief_result,
        "project_plan": plan_result,
    }


# ============================================================================
# DOCUMENT TAGS
# ============================================================================

@app.post("/api/documents/{document_id}/tags")
def add_document_tag(document_id: str, payload: dict):
    tag = (payload or {}).get("tag", "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty.")
    if not db.get_document_by_id(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    db.add_document_tag(document_id, tag)
    return {"status": "success", "tags": db.get_document_tags(document_id)}


@app.delete("/api/documents/{document_id}/tags/{tag}")
def remove_document_tag(document_id: str, tag: str):
    removed = db.remove_document_tag(document_id, tag)
    if not removed:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return {"status": "success", "tags": db.get_document_tags(document_id)}


@app.get("/api/documents/{document_id}/tags")
def list_document_tags(document_id: str):
    return {"tags": db.get_document_tags(document_id)}


@app.get("/api/tags")
def list_all_tags():
    return {"tags": db.get_all_tags()}


# ============================================================================
# STUDIO
# ============================================================================

@app.get("/api/studio/templates")
def studio_templates():
    return {"templates": list_templates()}


@app.get("/api/workspaces/{workspace_id}/studio")
def list_studio(workspace_id: str):
    if not db.get_workspace_by_id(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return {"workspace_id": workspace_id, "documents": studio_service.list(workspace_id)}


class StudioCreate(BaseModel):
    workspace_id: str
    template: str = "ieee"
    title: str = "Untitled"


@app.post("/api/studio")
def create_studio(payload: StudioCreate):
    if not db.get_workspace_by_id(payload.workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return studio_service.create(payload.workspace_id, payload.template, payload.title)


@app.get("/api/studio/{sid}")
def get_studio(sid: str):
    doc = studio_service.get(sid)
    if not doc:
        raise HTTPException(status_code=404, detail="Studio document not found.")
    return doc


class StudioUpdate(BaseModel):
    template: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None


@app.put("/api/studio/{sid}")
def update_studio(sid: str, payload: StudioUpdate):
    updated = studio_service.update(sid, **payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Studio document not found.")
    return updated


@app.delete("/api/studio/{sid}")
def delete_studio(sid: str):
    if not studio_service.delete(sid):
        raise HTTPException(status_code=404, detail="Studio document not found.")
    return {"status": "success"}


class StudioHelp(BaseModel):
    action: str
    instruction: str = ""


@app.post("/api/studio/{sid}/help")
def studio_help(sid: str, payload: StudioHelp):
    try:
        return studio_service.help_action(sid, payload.action, payload.instruction)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Studio help failed: {e}")
        raise HTTPException(status_code=500, detail="Studio help failed.")


# ============================================================================
# SETTINGS + PROVIDER STATUS
# ============================================================================

@app.get("/api/settings/providers")
def settings_providers():
    """Public provider status. Never includes keys."""
    from ai.llm_service import llm_service
    providers = []
    for p in llm_service.providers:
        providers.append({
            "name": getattr(p, "_label", p.name) or p.name,
            "model": getattr(p, "model", ""),
            "supports_vision": bool(p.supports_vision),
            "status": "configured",
            # primary marker: which provider is tried first by default
                "primary": (p is llm_service.providers[0] if llm_service.providers else False),
            })
    return {
        "configured": llm_service.is_configured,
        "providers": providers,
    }


@app.get("/api/settings")
def get_settings():
    """Returns user-configurable settings. Provider keys are NEVER included."""
    from ai.config import ai_config
    return {
        "ui": {
            "theme": db.get_setting("ui,theme", "light"),
        },
        "chat": {
            "default_mode": db.get_setting("chat,default_mode", "research"),
            "history_window": int(db.get_setting("chat,history_window", "16") or "16"),
        },
        "ai": {
            "primary_provider": db.get_setting("ai,primary_provider", ""),
            "provider_configured": ai_config.is_gemini_configured,
        },
    }


class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    default_mode: Optional[str] = None
    history_window: Optional[int] = None


@app.put("/api/settings")
def update_settings(payload: SettingsUpdate):
    if payload.theme is not None:
        db.set_setting("ui,theme", payload.theme)
    if payload.default_mode is not None:
        if payload.default_mode not in ("research", "project"):
            raise HTTPException(status_code=400, detail="default_mode must be 'research' or 'project'.")
        db.set_setting("chat,default_mode", payload.default_mode)
    if payload.history_window is not None:
        try:
            n = int(payload.history_window)
            if n < 1 or n > 100:
                raise ValueError()
            db.set_setting("chat,history_window", str(n))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="history_window must be 1..100.")
    return {"status": "success"}
