import pytest
from fastapi.testclient import TestClient
from main import app
import database.database as db
import uuid
import json

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()

def test_workspace_crud():
    # 1. Create Workspace
    payload = {"name": "Test Workspace", "description": "A description"}
    resp = client.post("/api/workspaces", json=payload)
    assert resp.status_code == 200
    ws = resp.json()
    ws_id = ws["id"]
    assert ws["name"] == "Test Workspace"
    
    # 2. Get Workspace
    resp = client.get(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Workspace"
    assert "documents" in resp.json()
    
    # 3. Update Workspace
    payload_update = {"name": "Updated Workspace", "description": "New description"}
    resp = client.put(f"/api/workspaces/{ws_id}", json=payload_update)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Workspace"
    
    # 4. List Workspaces
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    
    # Create a mock document to test relationships
    doc_data = {
        "filename": "test.pdf",
        "file_type": "application/pdf",
        "file_size": 100,
        "page_count": 1,
        "character_count": 100,
        "text": "test"
    }
    doc_record = db.create_document(doc_data)
    doc_id = doc_record["id"]
    
    # 5. Add Document
    resp = client.post(f"/api/workspaces/{ws_id}/documents/{doc_id}")
    assert resp.status_code == 200
    
    # 6. Verify Document Added
    resp = client.get(f"/api/workspaces/{ws_id}")
    assert len(resp.json()["documents"]) == 1
    
    # 7. Remove Document
    resp = client.delete(f"/api/workspaces/{ws_id}/documents/{doc_id}")
    assert resp.status_code == 200
    
    # 8. Delete Workspace
    resp = client.delete(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 200
    
    resp = client.get(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 404
