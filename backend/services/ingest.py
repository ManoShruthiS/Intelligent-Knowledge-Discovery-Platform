from __future__ import annotations
import logging
from typing import Optional
import database.database as db
from ai.chunker import DocumentChunker
from ai.embeddings import EmbeddingService
from ai.vector_store import vector_store
logger = logging.getLogger(__name__)
chunker = DocumentChunker()

class IngestStats(dict):

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None

def ingest_document(doc_id: str, process_result: dict, *, bm25_index=None, graphrag_service=None, contextual_retrieval_fn=None) -> IngestStats:
    stats = IngestStats(chunks=0, embeddings=0, faiss_added=0, bm25_added=0, graphrag_added=0, contextual_chunks=0, errors=[])
    pages = process_result.get('pages') or []
    if not pages:
        db.update_document_status(doc_id, 'ready')
        return stats
    chunks = chunker.chunk_document(process_result)
    if not chunks:
        db.update_document_status(doc_id, 'ready')
        return stats
    stats['chunks'] = len(chunks)
    embeddings: list = []
    try:
        embedder = EmbeddingService()
        texts = [c['text'] for c in chunks]
        embeddings = embedder.embed_texts(texts) or []
        for chunk, emb in zip(chunks, embeddings):
            chunk['embedding'] = emb
        stats['embeddings'] = len(embeddings)
    except Exception as e:
        logger.exception(f'Embedding generation failed for {doc_id}: {e}')
        stats['errors'].append(f'embeddings: {e}')
        texts = [c['text'] for c in chunks]
    try:
        db.create_chunks(doc_id, chunks)
        inserted = db.get_chunks_for_document(doc_id)
        chunk_ids = [c['id'] for c in inserted]
    except Exception as e:
        logger.exception(f'Chunk persistence failed for {doc_id}: {e}')
        stats['errors'].append(f'db.create_chunks: {e}')
        return stats
    if embeddings:
        try:
            vector_store.add_embeddings(chunk_ids, embeddings)
            stats['faiss_added'] = len(chunk_ids)
        except Exception as e:
            logger.exception(f'FAISS add failed for {doc_id}: {e}')
            stats['errors'].append(f'faiss: {e}')
    if bm25_index is not None:
        try:
            for cid, chunk_text in zip(chunk_ids, texts):
                bm25_index.add_chunk(cid, doc_id, chunk_text)
            stats['bm25_added'] = len(chunk_ids)
        except Exception as e:
            logger.warning(f'BM25 ingest skipped for {doc_id}: {e}')
            stats['errors'].append(f'bm25: {e}')
    if graphrag_service is not None:
        try:
            for cid, chunk_text in zip(chunk_ids, texts):
                graphrag_service.ingest_chunk(cid, doc_id, chunk_text)
            stats['graphrag_added'] = len(chunk_ids)
        except Exception as e:
            logger.warning(f'GraphRAG ingest skipped for {doc_id}: {e}')
            stats['errors'].append(f'graphrag: {e}')
    if callable(contextual_retrieval_fn):
        try:
            n = contextual_retrieval_fn(doc_id, inserted, max_chunks=50)
            stats['contextual_chunks'] = int(n or 0)
        except Exception as e:
            logger.warning(f'Contextual retrieval skipped for {doc_id}: {e}')
            stats['errors'].append(f'contextual: {e}')
    try:
        db.update_document_status(doc_id, 'ready')
    except Exception as e:
        logger.warning(f'Failed to update document status to ready for {doc_id}: {e}')
    return stats

def persist_upload(content: bytes, doc_id: str, original_filename: str) -> Optional[str]:
    import os
    UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads')
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    ext = os.path.splitext(original_filename)[1].lower()
    if not ext:
        return None
    safe_name = f'{doc_id}{ext}'
    path = os.path.join(UPLOADS_DIR, safe_name)
    try:
        with open(path, 'wb') as fh:
            fh.write(content)
        return path
    except Exception as e:
        logger.warning(f'Failed to persist upload {original_filename}: {e}')
        return None
