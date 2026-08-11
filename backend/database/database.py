import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional

DB_FILE = "knowledge.db"

def get_connection():
    """Returns a connection to the SQLite database, with row factory set to dict-like rows."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the database schema if it does not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER,
            character_count INTEGER NOT NULL,
            extracted_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            page_number INTEGER,
            embedding TEXT,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_documents (
            workspace_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (workspace_id, document_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def create_document(doc_data: dict) -> dict:
    """Inserts a new document record into the database and returns the created record."""
    conn = get_connection()
    cursor = conn.cursor()
    
    doc_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO documents (
            id, filename, file_type, file_size, page_count, character_count, extracted_text, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        doc_data['filename'],
        doc_data['file_type'],
        doc_data['file_size'],
        doc_data.get('page_count'),
        doc_data['character_count'],
        doc_data['text'],
        now,
        now
    ))
    conn.commit()
    conn.close()
    
    return {
        "id": doc_id,
        "filename": doc_data['filename'],
        "file_type": doc_data['file_type'],
        "file_size": doc_data['file_size'],
        "page_count": doc_data.get('page_count'),
        "character_count": doc_data['character_count'],
        "created_at": now
    }

def get_documents() -> List[dict]:
    """Retrieves all documents, ordered by newest first, omitting extracted_text."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, file_type, file_size, page_count, character_count, created_at, updated_at 
        FROM documents 
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_document_by_id(doc_id: str) -> Optional[dict]:
    """Retrieves a specific document including its extracted_text."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def delete_document(doc_id: str) -> bool:
    """Deletes a document by ID. Returns True if deleted, False if not found."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

import json

def create_chunks(document_id: str, chunks_data: List[Dict]) -> None:
    """Inserts multiple chunks for a document. Deletes any existing chunks for this document first to avoid duplicates."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # First, clear any existing chunks for this document
    cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
    
    now = datetime.utcnow().isoformat()
    
    # Prepare data for executemany
    rows = []
    for chunk in chunks_data:
        embedding_str = json.dumps(chunk['embedding']) if 'embedding' in chunk and chunk['embedding'] else None
        
        rows.append((
            str(uuid.uuid4()),
            document_id,
            chunk['chunk_index'],
            chunk['text'],
            chunk.get('page_number'),
            embedding_str,
            now
        ))
        
    cursor.executemany("""
        INSERT INTO document_chunks (
            id, document_id, chunk_index, text, page_number, embedding, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    
    conn.commit()
    conn.close()

def get_chunks_for_document(document_id: str) -> List[Dict]:
    """Retrieves all chunks for a specific document."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, chunk_index, text, page_number, created_at 
        FROM document_chunks 
        WHERE document_id = ? 
        ORDER BY chunk_index ASC
    """, (document_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_chunks() -> List[Dict]:
    """Retrieves all chunks across all documents. Used for rebuilding the FAISS index."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, text, embedding
        FROM document_chunks 
        ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chunks_by_ids(chunk_ids: List[str]) -> List[Dict]:
    """Retrieves specific chunks by their IDs."""
    if not chunk_ids:
        return []
        
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create the parameterized query placeholder (?, ?, ?)
    placeholders = ','.join(['?'] * len(chunk_ids))
    
    cursor.execute(f"""
        SELECT id, document_id, chunk_index, text, page_number, created_at 
        FROM document_chunks 
        WHERE id IN ({placeholders})
    """, chunk_ids)
    
    rows = cursor.fetchall()
    conn.close()
    
    # We should return them in the same order as chunk_ids to maintain FAISS ranking
    result_dict = {row['id']: dict(row) for row in rows}
    
    ordered_results = []
    for cid in chunk_ids:
        if cid in result_dict:
            ordered_results.append(result_dict[cid])
            
    return ordered_results

def create_workspace(name: str, description: str = "") -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    ws_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO workspaces (id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ws_id, name, description, now, now))
    conn.commit()
    conn.close()
    
    return {
        "id": ws_id,
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now
    }

def get_all_workspaces() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspaces ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_workspace_by_id(ws_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_workspace(ws_id: str, name: str, description: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        UPDATE workspaces 
        SET name = ?, description = ?, updated_at = ?
        WHERE id = ?
    """, (name, description, now, ws_id))
    
    if cursor.rowcount == 0:
        conn.close()
        return None
        
    conn.commit()
    conn.close()
    return get_workspace_by_id(ws_id)

def delete_workspace(ws_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_document_to_workspace(ws_id: str, doc_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cursor.execute("""
            INSERT INTO workspace_documents (workspace_id, document_id, created_at)
            VALUES (?, ?, ?)
        """, (ws_id, doc_id, now))
        
        # Also update the workspace's updated_at
        cursor.execute("""
            UPDATE workspaces SET updated_at = ? WHERE id = ?
        """, (now, ws_id))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Either foreign key constraint failed (doc or ws doesn't exist)
        # or duplicate entry (primary key violation)
        return False
    finally:
        conn.close()

def remove_document_from_workspace(ws_id: str, doc_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM workspace_documents 
        WHERE workspace_id = ? AND document_id = ?
    """, (ws_id, doc_id))
    deleted = cursor.rowcount > 0
    
    if deleted:
        now = datetime.utcnow().isoformat()
        cursor.execute("""
            UPDATE workspaces SET updated_at = ? WHERE id = ?
        """, (now, ws_id))
        
    conn.commit()
    conn.close()
    return deleted

def get_documents_for_workspace(ws_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.filename, d.file_type, d.file_size, d.page_count, d.character_count, d.created_at, wd.created_at as added_at
        FROM documents d
        JOIN workspace_documents wd ON d.id = wd.document_id
        WHERE wd.workspace_id = ?
        ORDER BY wd.created_at DESC
    """, (ws_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_workspaces_for_document(doc_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.* 
        FROM workspaces w
        JOIN workspace_documents wd ON w.id = wd.workspace_id
        WHERE wd.document_id = ?
        ORDER BY w.updated_at DESC
    """, (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
