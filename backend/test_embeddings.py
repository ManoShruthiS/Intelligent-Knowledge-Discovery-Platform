import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.embeddings import EmbeddingService
from ai.vector_store import vector_store
import database.database as db

def run_test():
    print("Initializing Database...")
    db.init_db()

    print("Rebuilding FAISS index from DB...")
    vector_store.rebuild_index()

    print(f"Vector Store contains {vector_store.index.ntotal} embeddings.")

    print("Initializing EmbeddingService...")
    embedder = EmbeddingService()

    query = "fake news detection"
    print(f"Embedding test query: '{query}'")
    query_emb = embedder.embed_text(query)

    print("Searching FAISS index...")
    results = vector_store.search(query_emb, top_k=3)
    
    if results:
        print(f"Found {len(results)} results:")
        for res in results:
            print(res)
    else:
        print("No results found. This is expected if the DB has no documents.")

if __name__ == "__main__":
    run_test()
