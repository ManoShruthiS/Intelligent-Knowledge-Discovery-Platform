import os
import json
import logging
import faiss
import numpy as np
from typing import List, Dict
import database.database as db
from ai.embeddings import EmbeddingService
logger = logging.getLogger(__name__)
VECTOR_DIMENSION = 384
VECTOR_STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vector_store')
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, 'index.faiss')
MAPPING_PATH = os.path.join(VECTOR_STORE_DIR, 'mapping.json')

class VectorStore:

    def __init__(self):
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        self.index = None
        self.mapping = {}
        self.next_id = 0
        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(MAPPING_PATH):
            try:
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                with open(MAPPING_PATH, 'r') as f:
                    loaded_mapping = json.load(f)
                    self.mapping = {int(k): v for k, v in loaded_mapping.items()}
                    self.next_id = max(self.mapping.keys()) + 1 if self.mapping else 0
            except Exception as e:
                logger.info(f'Failed to load vector store: {e}. Creating a new one.')
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        self.index = faiss.IndexFlatL2(VECTOR_DIMENSION)
        self.index = faiss.IndexIDMap(self.index)
        self.mapping = {}
        self.next_id = 0

    def _save(self):
        faiss.write_index(self.index, FAISS_INDEX_PATH)
        with open(MAPPING_PATH, 'w') as f:
            json.dump(self.mapping, f)

    def add_embeddings(self, chunk_ids: List[str], embeddings: List[List[float]]) -> None:
        if not chunk_ids or not embeddings:
            return
        if len(chunk_ids) != len(embeddings):
            raise ValueError('Mismatched chunk_ids and embeddings count')
        ids = []
        for cid in chunk_ids:
            faiss_id = self.next_id
            ids.append(faiss_id)
            self.mapping[faiss_id] = cid
            self.next_id += 1
        vectors_np = np.array(embeddings).astype('float32')
        ids_np = np.array(ids).astype('int64')
        self.index.add_with_ids(vectors_np, ids_np)
        self._save()

    def rebuild_index(self):
        logger.info('Rebuilding FAISS vector index from SQLite database...')
        self._create_new_index()
        chunks = db.get_all_chunks()
        if not chunks:
            self._save()
            logger.info('No chunks found. Vector index cleared.')
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
            texts_to_embed.append(chunk['text'])
            chunk_ids_to_embed.append(chunk['id'])
        if texts_to_embed:
            logger.info(f'Generating missing embeddings for {len(texts_to_embed)} chunks...')
            embedder = EmbeddingService()
            new_embeddings = embedder.embed_texts(texts_to_embed)
            valid_chunk_ids.extend(chunk_ids_to_embed)
            valid_embeddings.extend(new_embeddings)
        self.add_embeddings(valid_chunk_ids, valid_embeddings)
        logger.info(f'Successfully rebuilt FAISS vector index with {len(valid_chunk_ids)} chunks.')

    def search(self, query_embedding: List[float], top_k: int=5) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        q_np = np.array([query_embedding]).astype('float32')
        distances, indices = self.index.search(q_np, top_k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            chunk_id = self.mapping.get(int(idx))
            if chunk_id:
                results.append({'chunk_id': chunk_id, 'distance': float(dist)})
        return results
vector_store = VectorStore()
