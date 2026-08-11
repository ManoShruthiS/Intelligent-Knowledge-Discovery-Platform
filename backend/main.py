from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from services.document_processor import process_document, UnsupportedFileTypeError, DocumentProcessingError
import database.database as db
from ai.chunker import DocumentChunker
from ai.vector_store import vector_store
from ai.embeddings import EmbeddingService

chunker = DocumentChunker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database when the application starts
    db.init_db()
    yield

app = FastAPI(title="Intelligent Knowledge Discovery Platform API", lifespan=lifespan)

# Configure CORS so the React frontend can communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from ai.config import ai_config

@app.get("/api/health")
def health_check():
    """Basic health check endpoint to verify the backend and configuration are running."""
    return {
        "status": "healthy", 
        "message": "Backend is running!",
        "ai_configuration": "configured" if ai_config.is_gemini_configured else "not configured"
    }

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a document upload (PDF, DOCX, TXT), extracts its text, 
    persists it to the database, and returns the document record.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")
        
    try:
        # Read the file content into memory
        content = await file.read()
        
        # Process the document to extract text and metadata
        result = process_document(content, file.filename)
        
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred during document processing.")

@app.get("/api/documents")
def get_documents():
    """Returns a list of all uploaded documents (metadata only)."""
    try:
        docs = db.get_documents()
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve documents.")

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
        print(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during search.")

class AskQuery(BaseModel):
    question: str
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    top_k: int = 5

@app.post("/api/ask")
def ask_question(payload: AskQuery):
    """
    Answers a user question grounded in retrieved document chunks.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
        
    try:
        response = rag_service.ask(
            question=payload.question,
            document_id=payload.document_id,
            workspace_id=payload.workspace_id,
            top_k=payload.top_k
        )
        return response
    except Exception as e:
        print(f"Ask API error: {e}")
        # Send a clean error message back to the frontend
        error_msg = str(e) if str(e) else "An unexpected error occurred."
        raise HTTPException(status_code=500, detail=error_msg)

# --- WORKSPACES API ---

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = ""

@app.post("/api/workspaces")
def create_workspace(payload: WorkspaceCreate):
    try:
        ws = db.create_workspace(payload.name, payload.description)
        return ws
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create workspace.")

@app.get("/api/workspaces")
def get_workspaces():
    try:
        return db.get_all_workspaces()
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
