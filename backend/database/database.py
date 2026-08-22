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
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    """Initializes the database schema if it does not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            title TEXT,
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

    # ------ New tables (Notes, Brief, Experiments, Project Plans, Citations, Discoveries) ------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'note',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_message_id TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_ws ON notes(workspace_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_briefs (
            workspace_id TEXT PRIMARY KEY,
            topic TEXT,
            problem TEXT,
            research_question TEXT,
            objectives TEXT,
            papers_reviewed TEXT,
            key_findings TEXT,
            common_limitations TEXT,
            potential_gap TEXT,
            proposed_direction TEXT,
            open_questions TEXT,
            current_stage TEXT,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_plans (
            workspace_id TEXT PRIMARY KEY,
            problem_statement TEXT,
            objectives TEXT,
            requirements TEXT,
            architecture TEXT,
            technology_stack TEXT,
            components TEXT,
            data_flow TEXT,
            implementation_stages TEXT,
            testing_strategy TEXT,
            evaluation_metrics TEXT,
            deployment_plan TEXT,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            name TEXT NOT NULL,
            model TEXT,
            dataset TEXT,
            configuration TEXT,
            metric TEXT,
            result TEXT,
            experiment_date TEXT,
            notes TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiments_ws ON experiments(workspace_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            workspace_id TEXT,
            source_type TEXT NOT NULL,
            external_id TEXT,
            title TEXT NOT NULL,
            authors TEXT,
            year INTEGER,
            venue TEXT,
            doi TEXT,
            url TEXT,
            abstract TEXT,
            created_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_doc ON citations(document_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_ws ON citations(workspace_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS studio_documents (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            template TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_studio_ws ON studio_documents(workspace_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            brief_template TEXT,
            plan_template TEXT,
            created_at TIMESTAMP NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_tags (
            document_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (document_id, tag),
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_tags_tag ON document_tags(tag)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Migration: add title column to documents table if missing
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN title TEXT")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions ON document_versions(document_id)")

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
            id, filename, title, file_type, file_size, page_count, character_count, extracted_text, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        doc_data['filename'],
        doc_data.get('title', doc_data['filename']),
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

def update_document(doc_id: str, **fields) -> Optional[dict]:
    """Updates document fields. Returns updated document or None."""
    allowed = {'filename', 'title', 'extracted_text', 'character_count', 'page_count'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_document_by_id(doc_id)
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    cursor.execute(f"UPDATE documents SET {set_clause}, updated_at = ? WHERE id = ?",
                   values + [datetime.utcnow().isoformat(), doc_id])
    conn.commit()
    conn.close()
    return get_document_by_id(doc_id)

def get_workspace_documents(ws_id: str) -> List[dict]:
    """Returns documents belonging to a workspace."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.filename, d.title, d.file_type, d.file_size, d.page_count,
               d.character_count, d.created_at, d.updated_at
        FROM documents d
        JOIN workspace_documents wd ON d.id = wd.document_id
        WHERE wd.workspace_id = ?
        ORDER BY d.created_at DESC
    """, (ws_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

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


# ===================== Notes =====================

def create_note(workspace_id: str, title: str, content: str, kind: str = "note",
                source_message_id: Optional[str] = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO notes (id, workspace_id, kind, title, content, source_message_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (note_id, workspace_id, kind, title, content, source_message_id, now, now))
    cursor.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
    conn.commit()
    conn.close()
    return {
        "id": note_id, "workspace_id": workspace_id, "kind": kind,
        "title": title, "content": content, "source_message_id": source_message_id,
        "created_at": now, "updated_at": now,
    }


def list_notes(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, workspace_id, kind, title, content, source_message_id, created_at, updated_at
        FROM notes WHERE workspace_id = ? ORDER BY updated_at DESC
    """, (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_note(note_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_note(note_id: str, title: str, content: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        UPDATE notes SET title = ?, content = ?, updated_at = ?
        WHERE id = ?
    """, (title, content, now, note_id))
    if cursor.rowcount == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_note(note_id)


def delete_note(note_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ===================== Research Brief =====================

def get_research_brief(workspace_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_briefs WHERE workspace_id = ?", (workspace_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_research_brief(workspace_id: str, fields: Dict) -> dict:
    """
    fields: dict with any subset of brief keys. Missing keys preserve existing values.
    """
    allowed = [
        "topic", "problem", "research_question", "objectives", "papers_reviewed",
        "key_findings", "common_limitations", "potential_gap",
        "proposed_direction", "open_questions", "current_stage",
    ]
    existing = get_research_brief(workspace_id) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if k in allowed}}
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO research_briefs (workspace_id, topic, problem, research_question, objectives,
            papers_reviewed, key_findings, common_limitations, potential_gap,
            proposed_direction, open_questions, current_stage, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id) DO UPDATE SET
            topic = excluded.topic,
            problem = excluded.problem,
            research_question = excluded.research_question,
            objectives = excluded.objectives,
            papers_reviewed = excluded.papers_reviewed,
            key_findings = excluded.key_findings,
            common_limitations = excluded.common_limitations,
            potential_gap = excluded.potential_gap,
            proposed_direction = excluded.proposed_direction,
            open_questions = excluded.open_questions,
            current_stage = excluded.current_stage,
            updated_at = excluded.updated_at
    """, (
        workspace_id,
        merged.get("topic"), merged.get("problem"), merged.get("research_question"),
        merged.get("objectives"), merged.get("papers_reviewed"),
        merged.get("key_findings"), merged.get("common_limitations"),
        merged.get("potential_gap"), merged.get("proposed_direction"),
        merged.get("open_questions"), merged.get("current_stage"), now,
    ))
    cursor.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
    conn.commit()
    conn.close()
    return get_research_brief(workspace_id)


# ===================== Project Plans =====================

def get_project_plan(workspace_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM project_plans WHERE workspace_id = ?", (workspace_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_project_plan(workspace_id: str, fields: Dict) -> dict:
    allowed = [
        "problem_statement", "objectives", "requirements", "architecture",
        "technology_stack", "components", "data_flow", "implementation_stages",
        "testing_strategy", "evaluation_metrics", "deployment_plan",
    ]
    existing = get_project_plan(workspace_id) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if k in allowed}}
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO project_plans (workspace_id, problem_statement, objectives, requirements,
            architecture, technology_stack, components, data_flow, implementation_stages,
            testing_strategy, evaluation_metrics, deployment_plan, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id) DO UPDATE SET
            problem_statement = excluded.problem_statement,
            objectives = excluded.objectives,
            requirements = excluded.requirements,
            architecture = excluded.architecture,
            technology_stack = excluded.technology_stack,
            components = excluded.components,
            data_flow = excluded.data_flow,
            implementation_stages = excluded.implementation_stages,
            testing_strategy = excluded.testing_strategy,
            evaluation_metrics = excluded.evaluation_metrics,
            deployment_plan = excluded.deployment_plan,
            updated_at = excluded.updated_at
    """, (
        workspace_id,
        merged.get("problem_statement"), merged.get("objectives"), merged.get("requirements"),
        merged.get("architecture"), merged.get("technology_stack"),
        merged.get("components"), merged.get("data_flow"),
        merged.get("implementation_stages"), merged.get("testing_strategy"),
        merged.get("evaluation_metrics"), merged.get("deployment_plan"), now,
    ))
    cursor.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
    conn.commit()
    conn.close()
    return get_project_plan(workspace_id)


# ===================== Experiments =====================

def create_experiment(workspace_id: str, name: str, **fields) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    exp_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO experiments (id, workspace_id, name, model, dataset, configuration,
            metric, result, experiment_date, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, workspace_id, name,
        fields.get("model"), fields.get("dataset"), fields.get("configuration"),
        fields.get("metric"), fields.get("result"), fields.get("experiment_date"),
        fields.get("notes"), now, now,
    ))
    cursor.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
    conn.commit()
    conn.close()
    return get_experiment(exp_id)


def list_experiments(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM experiments WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_experiment(exp_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_experiment(exp_id: str, **fields) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    sets, vals = [], []
    for key in ("name", "model", "dataset", "configuration", "metric", "result", "experiment_date", "notes"):
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(fields[key])
    if not sets:
        conn.close()
        return get_experiment(exp_id)
    sets.append("updated_at = ?")
    vals.append(now)
    vals.append(exp_id)
    cursor.execute(f"UPDATE experiments SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_experiment(exp_id)


def delete_experiment(exp_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ===================== Citations =====================

def create_citation(**fields) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cite_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO citations (id, document_id, workspace_id, source_type, external_id,
            title, authors, year, venue, doi, url, abstract, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cite_id,
        fields.get("document_id"), fields.get("workspace_id"),
        fields.get("source_type", "manual"),
        fields.get("external_id"),
        fields.get("title", "Untitled"),
        fields.get("authors"),
        fields.get("year"),
        fields.get("venue"),
        fields.get("doi"),
        fields.get("url"),
        fields.get("abstract"),
        now,
    ))
    conn.commit()
    conn.close()
    return get_citation(cite_id)


def get_citation(cite_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM citations WHERE id = ?", (cite_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_citations(workspace_id: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if workspace_id:
        cursor.execute("SELECT * FROM citations WHERE workspace_id = ? ORDER BY year DESC, created_at DESC", (workspace_id,))
    else:
        cursor.execute("SELECT * FROM citations ORDER BY created_at DESC LIMIT 200")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_citation(cite_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM citations WHERE id = ?", (cite_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ===================== Studio Documents =====================

def create_studio_doc(workspace_id: str, template: str, title: str, content: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO studio_documents (id, workspace_id, template, title, content, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (sid, workspace_id, template, title, content, now, now))
    conn.commit()
    conn.close()
    return get_studio_doc(sid)


def get_studio_doc(sid: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM studio_documents WHERE id = ?", (sid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_studio_docs(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM studio_documents WHERE workspace_id = ? ORDER BY updated_at DESC", (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_studio_doc(sid: str, **fields) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    sets, vals = [], []
    for key in ("template", "title", "content"):
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(fields[key])
    if not sets:
        conn.close()
        return get_studio_doc(sid)
    sets.append("updated_at = ?")
    vals.append(now)
    vals.append(sid)
    cursor.execute(f"UPDATE studio_documents SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_studio_doc(sid)


def delete_studio_doc(sid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM studio_documents WHERE id = ?", (sid,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ===================== Settings (key-value) =====================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()


# ===================== Document Versions =====================

def create_document_version(doc_id: str, title: str, content: str) -> dict:
    """Create a snapshot version of a document."""
    conn = get_connection()
    cursor = conn.cursor()
    # Get current max version number
    cursor.execute(
        "SELECT MAX(version_number) as max_ver FROM document_versions WHERE document_id = ?",
        (doc_id,),
    )
    row = cursor.fetchone()
    next_ver = (dict(row)["max_ver"] or 0) + 1 if row else 1

    version_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO document_versions (id, document_id, version_number, title, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (version_id, doc_id, next_ver, title, content, now))
    conn.commit()
    conn.close()
    return {
        "id": version_id,
        "document_id": doc_id,
        "version_number": next_ver,
        "title": title,
        "content": content,
        "created_at": now,
    }


def get_document_versions(doc_id: str) -> List[dict]:
    """List all versions for a document (newest first)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, document_id, version_number, title, created_at
        FROM document_versions
        WHERE document_id = ?
        ORDER BY version_number DESC
    """, (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document_version(version_id: str) -> Optional[dict]:
    """Get a specific version by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM document_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ===================== Workspace Templates =====================

def create_workspace_template(name: str, description: str = "",
                              brief_template: str = "",
                              plan_template: str = "") -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    tid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO workspace_templates (id, name, description, brief_template, plan_template, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (tid, name, description, brief_template, plan_template, now))
    conn.commit()
    conn.close()
    return {"id": tid, "name": name, "description": description,
            "brief_template": brief_template, "plan_template": plan_template,
            "created_at": now}


def get_workspace_templates() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspace_templates ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_workspace_template(tid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workspace_templates WHERE id = ?", (tid,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_workspace_template_by_id(tid: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspace_templates WHERE id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ===================== Document Tags =====================

def add_document_tag(doc_id: str, tag: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO document_tags (document_id, tag) VALUES (?, ?)",
                       (doc_id, tag.strip().lower()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_document_tag(doc_id: str, tag: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM document_tags WHERE document_id = ? AND tag = ?",
                   (doc_id, tag.strip().lower()))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_document_tags(doc_id: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tag FROM document_tags WHERE document_id = ? ORDER BY tag", (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r["tag"] for r in rows]


def get_documents_by_tag(tag: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT document_id FROM document_tags WHERE tag = ?", (tag.strip().lower(),))
    rows = cursor.fetchall()
    conn.close()
    return [r["document_id"] for r in rows]


def get_all_tags() -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tag FROM document_tags ORDER BY tag")
    rows = cursor.fetchall()
    conn.close()
    return [r["tag"] for r in rows]
