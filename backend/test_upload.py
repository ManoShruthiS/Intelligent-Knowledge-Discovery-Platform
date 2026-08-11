from fastapi.testclient import TestClient
from main import app
from docx import Document
import fitz
import io
import os

client = TestClient(app)

def test_api():
    print("Testing health endpoint...")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    print("Health check passed.")

    print("Testing TXT upload...")
    resp = client.post("/api/documents/upload", files={"file": ("test.txt", b"Hello World TXT", "text/plain")})
    assert resp.status_code == 200
    txt_data = resp.json()
    assert txt_data["file_type"] == "TXT"
    assert "text" not in txt_data  # Should only return metadata now
    assert "id" in txt_data
    doc_id = txt_data["id"]
    print("TXT upload passed.")

    print("Testing GET /api/documents...")
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    print("GET documents passed.")

    print(f"Testing GET /api/documents/{doc_id}...")
    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    doc_data = resp.json()
    assert doc_data["id"] == doc_id
    assert doc_data["extracted_text"] == "Hello World TXT"
    print("GET individual document passed.")

    print(f"Testing GET /api/documents/{doc_id}/chunks...")
    resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    chunks = resp.json()
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Hello World TXT"
    assert chunks[0]["page_number"] is None
    print("GET chunks passed.")

    print(f"Testing chunk generation for large document...")
    large_text = "Word " * 2000 # Will generate roughly 10000 characters
    resp = client.post("/api/documents/upload", files={"file": ("large.txt", large_text.encode("utf-8"), "text/plain")})
    assert resp.status_code == 200
    large_doc_id = resp.json()["id"]
    
    resp_chunks = client.get(f"/api/documents/{large_doc_id}/chunks")
    large_chunks = resp_chunks.json()
    # 10000 chars split into max 4000 chunks means at least 3 chunks
    assert len(large_chunks) >= 3
    # Check overlap roughly by ensuring chunk count and text reconstruction properties
    assert any(len(c["text"]) > 3000 for c in large_chunks)
    print("Large document chunking passed.")

    print("Testing global semantic search...")
    # Search for something related to the large text "Word" or "Hello World"
    search_payload = {
        "query": "Hello",
        "top_k": 2
    }
    resp = client.post("/api/search", json=search_payload)
    assert resp.status_code == 200
    search_results = resp.json()
    assert len(search_results) > 0
    assert any("Hello" in res["text"] for res in search_results)
    print("Global search passed.")
    
    print("Testing document-specific semantic search...")
    search_payload_doc = {
        "query": "Word",
        "document_id": large_doc_id,
        "top_k": 3
    }
    resp = client.post("/api/search", json=search_payload_doc)
    assert resp.status_code == 200
    search_results_doc = resp.json()
    assert len(search_results_doc) > 0
    # Ensure all results belong to large_doc_id
    assert all(res["document_id"] == large_doc_id for res in search_results_doc)
    print("Document-specific search passed.")

    print(f"Testing DELETE /api/documents/{doc_id}...")
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    print("DELETE document passed.")

    print(f"Testing GET deleted document chunks (should be 404)...")
    resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 404
    print("Deleted chunks 404 passed.")
    
    print("Testing search after deletion (should not return deleted doc)...")
    resp = client.post("/api/search", json={"query": "Hello", "top_k": 5})
    assert resp.status_code == 200
    post_delete_results = resp.json()
    assert not any(res["document_id"] == doc_id for res in post_delete_results)
    print("Search after deletion passed.")

    client.delete(f"/api/documents/{large_doc_id}")

    print("Testing empty file...")
    resp = client.post("/api/documents/upload", files={"file": ("empty.txt", b"", "text/plain")})
    assert resp.status_code == 422 
    print("Empty file passed.")

    print("Testing unsupported file...")
    resp = client.post("/api/documents/upload", files={"file": ("image.png", b"fake image", "image/png")})
    assert resp.status_code == 400
    print("Unsupported file passed.")
    
    print("All tests passed successfully!")

if __name__ == "__main__":
    # Must use TestClient inside an event loop or we need to wrap it if using lifespan.
    # FastAPI TestClient automatically triggers startup/shutdown events.
    with TestClient(app) as client:
        # We need to use `client` inside this context block to trigger the lifespan (db init)
        # However, redefining it globally didn't trigger lifespan, let's just override it here
        globals()['client'] = client
        test_api()
