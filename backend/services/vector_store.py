import faiss
import numpy as np
import logging
import json
from typing import List, Tuple
from database.database import get_all_chunks

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        # We need to map FAISS's integer IDs back to our string chunk_ids
        self.id_map: List[str] = []
        logger.info(f"Initialized FAISS IndexFlatL2 with dimension {dimension}")
        self._load_from_db()

    def _load_from_db(self):
        """Loads embeddings from the SQLite database into FAISS on startup."""
        logger.info("Loading existing embeddings from database into FAISS...")
        chunks = get_all_chunks()
        
        chunk_ids = []
        embeddings = []
        
        for chunk in chunks:
            if chunk.get('embedding'):
                try:
                    # Deserialize JSON embedding
                    emb_list = json.loads(chunk['embedding'])
                    if len(emb_list) == self.dimension:
                        chunk_ids.append(chunk['id'])
                        embeddings.append(emb_list)
                    else:
                        logger.warning(f"Embedding dimension mismatch for chunk {chunk['id']}")
                except Exception as e:
                    logger.error(f"Failed to load embedding for chunk {chunk['id']}: {e}")
        
        if embeddings:
            self.add_embeddings(chunk_ids, embeddings)
            logger.info(f"Successfully loaded {len(embeddings)} embeddings into FAISS.")
        else:
            logger.info("No embeddings found in database to load.")

    def add_embeddings(self, chunk_ids: List[str], embeddings: List[List[float]]):
        """
        Adds multiple embeddings to the FAISS index.
        chunk_ids: list of string IDs corresponding to the embeddings.
        embeddings: list of list of floats (the vectors).
        """
        if not embeddings or not chunk_ids:
            return
            
        if len(embeddings) != len(chunk_ids):
            raise ValueError("Length of chunk_ids and embeddings must match.")
            
        # Convert to numpy float32 array as required by FAISS
        embeddings_np = np.array(embeddings, dtype=np.float32)
        
        # Add to FAISS
        self.index.add(embeddings_np)
        
        # Store mapping
        self.id_map.extend(chunk_ids)
        logger.debug(f"Added {len(embeddings)} embeddings to vector store. Total: {self.index.ntotal}")

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Searches the FAISS index for the most similar vectors.
        Returns a list of tuples: (chunk_id, distance).
        """
        if self.index.ntotal == 0:
            return []
            
        query_np = np.array([query_embedding], dtype=np.float32)
        
        # search returns squared L2 distances and indices
        distances, indices = self.index.search(query_np, min(top_k, self.index.ntotal))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.id_map):
                chunk_id = self.id_map[idx]
                results.append((chunk_id, float(dist)))
                
        return results

# Instantiate a global instance to be used across the application
vector_store = VectorStore()
