import pytest
from fastapi.testclient import TestClient
from main import app
import database.database as db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()

def create_mock_doc(filename: str, text: str = "Sample content"):
    doc_data = {
        "filename": filename,
        "file_type": "application/pdf",
        "file_size": 1000,
        "page_count": 5,
        "character_count": len(text),
        "text": text
    }
    return db.create_document(doc_data)

def test_compare_minimum_and_maximum_validation():
    # Setup Workspace & Doc
    ws = db.create_workspace("Validation Workspace")
    ws_id = ws["id"]
    
    doc1 = create_mock_doc("paper1.pdf")
    db.add_document_to_workspace(ws_id, doc1["id"])

    # Test 3: Less than 2 papers -> HTTP 400
    resp = client.post(f"/api/workspaces/{ws_id}/compare", json={"document_ids": [doc1["id"]]})
    assert resp.status_code == 400
    assert "at least 2 papers" in resp.json()["detail"].lower()

    # Create 5 more docs
    doc_ids = [doc1["id"]]
    for i in range(2, 7):
        d = create_mock_doc(f"paper{i}.pdf")
        db.add_document_to_workspace(ws_id, d["id"])
        doc_ids.append(d["id"])

    # Test 4: More than 5 papers (6 papers) -> HTTP 400
    resp = client.post(f"/api/workspaces/{ws_id}/compare", json={"document_ids": doc_ids})
    assert resp.status_code == 400
    assert "up to 5 papers" in resp.json()["detail"].lower()

def test_compare_workspace_security():
    # Test 5: Workspace security guard
    ws_a = db.create_workspace("Workspace A")
    ws_b = db.create_workspace("Workspace B")

    doc_a1 = create_mock_doc("doc_a1.pdf")
    doc_a2 = create_mock_doc("doc_a2.pdf")
    doc_b1 = create_mock_doc("doc_b1.pdf")

    db.add_document_to_workspace(ws_a["id"], doc_a1["id"])
    db.add_document_to_workspace(ws_a["id"], doc_a2["id"])
    db.add_document_to_workspace(ws_b["id"], doc_b1["id"])

    # Attempt to compare doc_a1 and doc_b1 using Workspace A endpoint
    resp = client.post(f"/api/workspaces/{ws_a['id']}/compare", json={"document_ids": [doc_a1["id"], doc_b1["id"]]})
    assert resp.status_code == 400
    assert "does not belong to workspace" in resp.json()["detail"].lower()

def test_compare_existing_rag_and_workspace_crud_regression():
    # Test 8: Normal RAG ask endpoint is reachable (Gemini may be rate limited, so we check it returns 200 or rate-limited 500 only)
    resp = client.post("/api/ask", json={"question": "What is attention mechanism?"})
    # Accept 200 (success) or 500 with rate-limit message (Gemini quota)
    assert resp.status_code in [200, 500]
    if resp.status_code == 500:
        error = resp.json().get("detail", "")
        # The only acceptable 500 is a rate limit one from Gemini
        assert "rate" in error.lower() or "quota" in error.lower() or "traffic" in error.lower(), \
            f"Unexpected 500 error: {error}"

    # Test 9: Workspace CRUD works
    ws = db.create_workspace("Regression Workspace")
    assert ws["name"] == "Regression Workspace"
    ws_fetched = db.get_workspace_by_id(ws["id"])
    assert ws_fetched["id"] == ws["id"]
    deleted = db.delete_workspace(ws["id"])
    assert deleted is True
