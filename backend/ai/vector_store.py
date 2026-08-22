import os
import json
import logging
import faiss
import numpy as np
from typing import List, Dict

import database.database as db
from ai.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# 384 is the embedding dimension for sentence-transformers/all-MiniLM-L6-v2
VECTOR_DIMENSION = 384
VECTOR_STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vector_store")
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "index.faiss")
MAPPING_PATH = os.path.join(VECTOR_STORE_DIR, "mapping.json")

class VectorStore:
    """
    Manages the FAISS index for semantic search and maintains the mapping
    between FAISS internal integer IDs and SQLite string chunk IDs.
    """
    
    def __init__(self):
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        self.index = None
        # dict mapping faiss int ID to chunk string ID
        self.mapping = {}
        # Keep track of next available FAISS integer ID
        self.next_id = 0
        self._load_or_create()

    def _load_or_create(self):
        """Loads existing index and mapping if they exist, otherwise creates new ones."""
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(MAPPING_PATH):
            try:
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                with open(MAPPING_PATH, 'r') as f:
                    # JSON keys are strings, convert back to int
                    loaded_mapping = json.load(f)
                    self.mapping = {int(k): v for k, v in loaded_mapping.items()}
                    self.next_id = max(self.mapping.keys()) + 1 if self.mapping else 0
            except Exception as e:
                logger.info(f"Failed to load vector store: {e}. Creating a new one.")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        """Initializes a fresh FAISS L2 index."""
        self.index = faiss.IndexFlatL2(VECTOR_DIMENSION)
        # Using IndexIDMap allows us to provide our own integer IDs rather than implicit sequential ones
        self.index = faiss.IndexIDMap(self.index)
        self.mapping = {}
        self.next_id = 0
        
    def _save(self):
        """Persists the FAISS index and mapping to disk."""
        faiss.write_index(self.index, FAISS_INDEX_PATH)
        with open(MAPPING_PATH, 'w') as f:
            json.dump(self.mapping, f)

    def add_embeddings(self, chunk_ids: List[str], embeddings: List[List[float]]) -> None:
        """Adds new embeddings to the index and saves it."""
        if not chunk_ids or not embeddings:
            return
            
        if len(chunk_ids) != len(embeddings):
            raise ValueError("Mismatched chunk_ids and embeddings count")

        # Prepare integer IDs
        ids = []
        for cid in chunk_ids:
            faiss_id = self.next_id
            ids.append(faiss_id)
            self.mapping[faiss_id] = cid
            self.next_id += 1
            
        # Convert to numpy array with required types
        vectors_np = np.array(embeddings).astype('float32')
        ids_np = np.array(ids).astype('int64')
        
        self.index.add_with_ids(vectors_np, ids_np)
        self._save()

    def rebuild_index(self):
        """
        Completely rebuilds the FAISS index from the SQLite database.
        This is crucial when documents are deleted to remove orphaned vectors safely.
        """
        logger.info("Rebuilding FAISS vector index from SQLite database...")
        self._create_new_index()
        
        chunks = db.get_all_chunks()
        if not chunks:
            self._save()
            logger.info("No chunks found. Vector index cleared.")
            return
            
        texts_to_embed = []
        chunk_ids_to_embed = []
        
        valid_chunk_ids = []
        valid_embeddings = []
        
        for chunk in chunks:
            if chunk.get('embedding'):
                try:
                    emb_list = json.loads(chunk['embedding'])
                    if len(emb_list) == VECTOR_DIMENSION:
                        valid_chunk_ids.append(chunk['id'])
                        valid_embeddings.append(emb_list)
                        continue
                except Exception as e:
                    logger.error(f"Error loading embedding for chunk {chunk['id']}: {e}")
            
            # If no embedding or failed, we need to regenerate
            texts_to_embed.append(chunk['text'])
            chunk_ids_to_embed.append(chunk['id'])
            
        if texts_to_embed:
            logger.info(f"Generating missing embeddings for {len(texts_to_embed)} chunks...")
            embedder = EmbeddingService()
            new_embeddings = embedder.embed_texts(texts_to_embed)
            valid_chunk_ids.extend(chunk_ids_to_embed)
            valid_embeddings.extend(new_embeddings)
            
        self.add_embeddings(valid_chunk_ids, valid_embeddings)
        logger.info(f"Successfully rebuilt FAISS vector index with {len(valid_chunk_ids)} chunks.")

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """
        Searches FAISS for the most similar chunks and returns the mapped SQLite IDs and scores.
        """
        if self.index.ntotal == 0:
            return []
            
        # FAISS expects a 2D array [batch_size, d]
        q_np = np.array([query_embedding]).astype('float32')
        
        # search returns squared L2 distances (smaller is more similar) and indices
        distances, indices = self.index.search(q_np, top_k)
        
        results = []
        # distances[0] and indices[0] because we only sent one query
        for dist, idx in zip(distances[0], indices[0]):
            # FAISS returns -1 if there are fewer than k vectors in the index
            if idx == -1:
                continue
                
            chunk_id = self.mapping.get(int(idx))
            if chunk_id:
                results.append({
                    "chunk_id": chunk_id,
                    "distance": float(dist)
                })
                
        return results

# Expose a singleton instance for the app
vector_store = VectorStore()
