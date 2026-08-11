from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def test_rag():
    print("Testing health endpoint...")
    resp = client.get("/api/health")
    assert resp.status_code == 200

    print("Uploading test document A...")
    doc_a_text = (
        "The primary objective of Project Alpha is to study the effects of prolonged spaceflight on human bone density. "
        "It was found that bone density decreases by 1% per month in microgravity. "
        "The main contribution of this paper is the introduction of a novel exercise regimen to mitigate these effects."
    )
    resp = client.post("/api/documents/upload", files={"file": ("doc_a.txt", doc_a_text.encode("utf-8"), "text/plain")})
    assert resp.status_code == 200
    doc_a_id = resp.json()["id"]

    print("Uploading test document B...")
    doc_b_text = (
        "Project Beta focuses on discovering new exoplanets using transit photometry. "
        "The primary dataset used was from the Kepler Space Telescope."
    )
    resp = client.post("/api/documents/upload", files={"file": ("doc_b.txt", doc_b_text.encode("utf-8"), "text/plain")})
    assert resp.status_code == 200
    doc_b_id = resp.json()["id"]

    # Debug search first
    search_payload = {
        "query": "What is the main contribution of Project Alpha?",
        "top_k": 5
    }
    search_resp = client.post("/api/search", json=search_payload)
    print("DEBUG Search results:", search_resp.json())

    # Test 1: Basic RAG
    print("Testing basic RAG (global)...")
    payload = {
        "question": "What is the main contribution of Project Alpha?",
        "top_k": 5
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
    if len(data["sources"]) == 0:
        print("DEBUG Basic RAG data:", data)
    assert len(data["sources"]) > 0
    assert any(doc_a_id == s["document_id"] for s in data["sources"])
    print("Basic RAG passed. Answer:", data["answer"][:100], "...")

    # Test 2: Unknown question (hallucination check)
    print("Testing unknown question...")
    payload = {
        "question": "What is the recipe for chocolate chip cookies?",
        "top_k": 5
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "reliable" in data["answer"].lower() or "couldn't find" in data["answer"].lower()
    print("Unknown question passed.")

    # Test 3: Document-specific search
    print("Testing document-specific search...")
    payload = {
        "question": "What dataset was used?",
        "document_id": doc_b_id,
        "top_k": 5
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "Kepler" in data["answer"]
    assert all(s["document_id"] == doc_b_id for s in data["sources"])
    print("Document-specific search passed.")

    # Test 4: Delete documents
    client.delete(f"/api/documents/{doc_a_id}")
    client.delete(f"/api/documents/{doc_b_id}")
    print("Deleted test documents.")
    print("All RAG tests passed successfully!")

if __name__ == "__main__":
    with TestClient(app) as client:
        globals()['client'] = client
        test_rag()
