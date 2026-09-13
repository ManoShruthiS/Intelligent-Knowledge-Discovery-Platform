import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional
DB_FILE = 'knowledge.db'

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys = ON;')
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=5000')
    except Exception:
        pass
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS documents (\n            id TEXT PRIMARY KEY,\n            filename TEXT NOT NULL,\n            title TEXT,\n            file_type TEXT NOT NULL,\n            file_size INTEGER NOT NULL,\n            page_count INTEGER,\n            character_count INTEGER NOT NULL,\n            extracted_text TEXT NOT NULL,\n            status TEXT DEFAULT 'processing',\n            author TEXT,\n            year INTEGER,\n            starred BOOLEAN DEFAULT 0,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL\n        )\n    ")
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS document_chunks (\n            id TEXT PRIMARY KEY,\n            document_id TEXT NOT NULL,\n            chunk_index INTEGER NOT NULL,\n            text TEXT NOT NULL,\n            page_number INTEGER,\n            char_start INTEGER,\n            char_end INTEGER,\n            bboxes_json TEXT,\n            page_width REAL,\n            page_height REAL,\n            embedding TEXT,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS workspaces (\n            id TEXT PRIMARY KEY,\n            name TEXT NOT NULL,\n            description TEXT,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS workspace_documents (\n            workspace_id TEXT NOT NULL,\n            document_id TEXT NOT NULL,\n            created_at TIMESTAMP NOT NULL,\n            PRIMARY KEY (workspace_id, document_id),\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,\n            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS notes (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT NOT NULL,\n            kind TEXT NOT NULL DEFAULT 'note',\n            title TEXT NOT NULL,\n            content TEXT NOT NULL,\n            source_message_id TEXT,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_ws ON notes(workspace_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS research_briefs (\n            workspace_id TEXT PRIMARY KEY,\n            topic TEXT,\n            problem TEXT,\n            research_question TEXT,\n            objectives TEXT,\n            papers_reviewed TEXT,\n            key_findings TEXT,\n            common_limitations TEXT,\n            potential_gap TEXT,\n            proposed_direction TEXT,\n            open_questions TEXT,\n            current_stage TEXT,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS project_plans (\n            workspace_id TEXT PRIMARY KEY,\n            problem_statement TEXT,\n            objectives TEXT,\n            requirements TEXT,\n            architecture TEXT,\n            technology_stack TEXT,\n            components TEXT,\n            data_flow TEXT,\n            implementation_stages TEXT,\n            testing_strategy TEXT,\n            evaluation_metrics TEXT,\n            deployment_plan TEXT,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS experiments (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT NOT NULL,\n            name TEXT NOT NULL,\n            model TEXT,\n            dataset TEXT,\n            configuration TEXT,\n            metric TEXT,\n            result TEXT,\n            experiment_date TEXT,\n            notes TEXT,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_experiments_ws ON experiments(workspace_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS citations (\n            id TEXT PRIMARY KEY,\n            document_id TEXT,\n            workspace_id TEXT,\n            source_type TEXT NOT NULL,\n            external_id TEXT,\n            title TEXT NOT NULL,\n            authors TEXT,\n            year INTEGER,\n            venue TEXT,\n            doi TEXT,\n            url TEXT,\n            abstract TEXT,\n            created_at TIMESTAMP NOT NULL\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citations_doc ON citations(document_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citations_ws ON citations(workspace_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS studio_documents (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT NOT NULL,\n            template TEXT NOT NULL,\n            title TEXT NOT NULL,\n            content TEXT NOT NULL,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_studio_ws ON studio_documents(workspace_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS workspace_templates (\n            id TEXT PRIMARY KEY,\n            name TEXT NOT NULL,\n            description TEXT,\n            brief_template TEXT,\n            plan_template TEXT,\n            created_at TIMESTAMP NOT NULL\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS document_tags (\n            document_id TEXT NOT NULL,\n            tag TEXT NOT NULL,\n            PRIMARY KEY (document_id, tag),\n            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_tags_tag ON document_tags(tag)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS settings (\n            key TEXT PRIMARY KEY,\n            value TEXT\n        )\n    ')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS workspace_resources (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT NOT NULL,\n            resource_type TEXT NOT NULL,\n            title TEXT NOT NULL,\n            url TEXT,\n            description TEXT,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_workspace_resources_ws ON workspace_resources(workspace_id)')
    try:
        cursor.execute('ALTER TABLE documents ADD COLUMN title TEXT')
    except Exception:
        pass
    for _col, _decl in (('abstract', 'TEXT'), ('keywords', 'TEXT'), ('insights', 'TEXT'), ('metadata_status', "TEXT DEFAULT 'pending'"), ('metadata_provider', 'TEXT'), ('metadata_updated_at', 'TIMESTAMP')):
        try:
            cursor.execute(f'ALTER TABLE documents ADD COLUMN {_col} {_decl}')
        except Exception:
            pass
    for _col, _decl in (('char_start', 'INTEGER'), ('char_end', 'INTEGER'), ('bboxes_json', 'TEXT'), ('page_width', 'REAL'), ('page_height', 'REAL')):
        try:
            cursor.execute(f'ALTER TABLE document_chunks ADD COLUMN {_col} {_decl}')
        except Exception:
            pass
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS document_versions (\n            id TEXT PRIMARY KEY,\n            document_id TEXT NOT NULL,\n            version_number INTEGER NOT NULL,\n            title TEXT,\n            content TEXT,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_versions ON document_versions(document_id)')
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS document_analysis_cache (\n            document_id TEXT NOT NULL,\n            analysis_kind TEXT NOT NULL,\n            document_type TEXT NOT NULL DEFAULT 'general',\n            content_json TEXT NOT NULL,\n            content_text TEXT,\n            content_hash TEXT,\n            model TEXT,\n            generated_at TIMESTAMP NOT NULL,\n            PRIMARY KEY (document_id, analysis_kind),\n            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_analysis ON document_analysis_cache(document_id)')
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS conversations (\n            id TEXT PRIMARY KEY,\n            user_id TEXT,\n            scope TEXT NOT NULL DEFAULT 'home',\n            workspace_id TEXT,\n            title TEXT NOT NULL DEFAULT 'New conversation',\n            mode TEXT NOT NULL DEFAULT 'research',\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_workspace ON conversations(workspace_id, updated_at DESC)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS conversation_messages (\n            id TEXT PRIMARY KEY,\n            conversation_id TEXT NOT NULL,\n            role TEXT NOT NULL,\n            content TEXT NOT NULL,\n            message_index INTEGER NOT NULL,\n            sources_json TEXT,\n            trace TEXT,\n            confidence TEXT,\n            metadata_json TEXT,\n            suggested_followups_json TEXT,\n            insufficient_evidence INTEGER DEFAULT 0,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_msg_conv ON conversation_messages(conversation_id, message_index)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_msg_created ON conversation_messages(conversation_id, created_at)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS citation_references (\n            id TEXT PRIMARY KEY,\n            external_id TEXT,\n            source TEXT,\n            title TEXT NOT NULL,\n            authors TEXT,\n            year INTEGER,\n            venue TEXT,\n            doi TEXT,\n            arxiv_id TEXT,\n            url TEXT,\n            abstract TEXT,\n            citations_count INTEGER DEFAULT 0,\n            imported_document_id TEXT,\n            metadata_json TEXT,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (imported_document_id) REFERENCES documents(id) ON DELETE SET NULL\n        )\n    ')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_citation_refs_doi ON citation_references(doi) WHERE doi IS NOT NULL')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_citation_refs_arxiv ON citation_references(arxiv_id) WHERE arxiv_id IS NOT NULL')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citation_refs_imported ON citation_references(imported_document_id)')
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS citation_edges (\n            id TEXT PRIMARY KEY,\n            source_document_id TEXT,\n            target_reference_id TEXT,\n            relationship TEXT NOT NULL DEFAULT 'cites',\n            context TEXT,\n            page_number INTEGER,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE CASCADE,\n            FOREIGN KEY (target_reference_id) REFERENCES citation_references(id) ON DELETE CASCADE\n        )\n    ")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citation_edges_src ON citation_edges(source_document_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citation_edges_tgt ON citation_edges(target_reference_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS literature_reviews (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT NOT NULL,\n            title TEXT NOT NULL,\n            topic TEXT,\n            document_ids TEXT NOT NULL,\n            structure TEXT NOT NULL,\n            draft_text TEXT,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lit_reviews_ws ON literature_reviews(workspace_id)')
    cursor.execute("\n        CREATE TABLE IF NOT EXISTS quiz_decks (\n            id TEXT PRIMARY KEY,\n            workspace_id TEXT,\n            document_id TEXT,\n            title TEXT NOT NULL,\n            topic TEXT,\n            difficulty TEXT NOT NULL DEFAULT 'mixed',\n            question_count INTEGER NOT NULL DEFAULT 0,\n            created_at TIMESTAMP NOT NULL,\n            updated_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,\n            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE\n        )\n    ")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_quiz_decks_ws ON quiz_decks(workspace_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_quiz_decks_doc ON quiz_decks(document_id)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS quiz_questions (\n            id TEXT PRIMARY KEY,\n            deck_id TEXT NOT NULL,\n            kind TEXT NOT NULL,\n            prompt TEXT NOT NULL,\n            answer TEXT NOT NULL,\n            options_json TEXT,\n            explanation TEXT,\n            source_chunk_id TEXT,\n            source_quote TEXT,\n            position INTEGER NOT NULL DEFAULT 0,\n            created_at TIMESTAMP NOT NULL,\n            FOREIGN KEY (deck_id) REFERENCES quiz_decks(id) ON DELETE CASCADE,\n            FOREIGN KEY (source_chunk_id) REFERENCES document_chunks(id) ON DELETE SET NULL\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_quiz_questions_deck ON quiz_questions(deck_id, position)')
    cursor.execute('\n        CREATE TABLE IF NOT EXISTS quiz_attempts (\n            id TEXT PRIMARY KEY,\n            question_id TEXT NOT NULL,\n            user_answer TEXT NOT NULL,\n            is_correct INTEGER NOT NULL,\n            confidence REAL,\n            reviewed_at TIMESTAMP NOT NULL,\n            next_review_at TIMESTAMP,\n            ease_factor REAL DEFAULT 2.5,\n            interval_days INTEGER DEFAULT 1,\n            repetitions INTEGER DEFAULT 0,\n            FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE\n        )\n    ')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_quiz_attempts_q ON quiz_attempts(question_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_quiz_attempts_next ON quiz_attempts(next_review_at)')
    # Per-user isolation: add client_id columns if they don't exist yet
    for _tbl in ('documents', 'workspaces'):
        try:
            cursor.execute(f'ALTER TABLE {_tbl} ADD COLUMN client_id TEXT')
        except Exception:
            pass  # column already exists
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_workspaces_client ON workspaces(client_id)')
    except Exception:
        pass
    conn.commit()
    conn.close()

def create_document(doc_data: dict, client_id: Optional[str] = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    doc_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute(
        '''
        INSERT INTO documents (
            id, filename, title, file_type, file_size, page_count, character_count,
            extracted_text, status, author, year, starred, created_at, updated_at, client_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            doc_id,
            doc_data['filename'],
            doc_data.get('title', doc_data['filename']),
            doc_data['file_type'],
            doc_data['file_size'],
            doc_data.get('page_count'),
            doc_data['character_count'],
            doc_data['text'],
            doc_data.get('status', 'processing'),
            doc_data.get('author'),
            doc_data.get('year'),
            doc_data.get('starred', False),
            now,
            now,
            client_id or 'anonymous',
        )
    )
    conn.commit()
    conn.close()
    return {
        'id': doc_id,
        'filename': doc_data['filename'],
        'file_type': doc_data['file_type'],
        'file_size': doc_data['file_size'],
        'page_count': doc_data.get('page_count'),
        'character_count': doc_data['character_count'],
        'status': doc_data.get('status', 'processing'),
        'author': doc_data.get('author'),
        'year': doc_data.get('year'),
        'starred': doc_data.get('starred', False),
        'created_at': now,
        'client_id': client_id or 'anonymous',
    }

def update_document_status(doc_id: str, status: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE documents SET status = ?, updated_at = ? WHERE id = ?', (status, datetime.utcnow().isoformat(), doc_id))
    conn.commit()
    conn.close()

def update_document_starred(doc_id: str, starred: bool) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE documents SET starred = ?, updated_at = ? WHERE id = ?', (starred, datetime.utcnow().isoformat(), doc_id))
    conn.commit()
    conn.close()

def update_document_metadata(doc_id: str, title: Optional[str]=None, author: Optional[str]=None, year: Optional[int]=None, abstract: Optional[str]=None, keywords: Optional[list]=None, insights: Optional[str]=None, provider: Optional[str]=None) -> None:
    import json as _json
    conn = get_connection()
    cursor = conn.cursor()
    sets = []
    vals = []
    if title is not None:
        sets.append('title = ?')
        vals.append(title)
    if author is not None:
        sets.append('author = ?')
        vals.append(author)
    if year is not None:
        sets.append('year = ?')
        vals.append(int(year))
    if abstract is not None:
        sets.append('abstract = ?')
        vals.append(abstract)
    if keywords is not None:
        sets.append('keywords = ?')
        vals.append(_json.dumps(list(keywords)))
    if insights is not None:
        sets.append('insights = ?')
        vals.append(insights)
    if provider is not None:
        sets.append('metadata_provider = ?')
        vals.append(provider)
    if not sets:
        conn.close()
        return
    now = datetime.utcnow().isoformat()
    sets.append('metadata_updated_at = ?')
    vals.append(now)
    sets.append('updated_at = ?')
    vals.append(now)
    vals.append(doc_id)
    cursor.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()

def update_document_metadata_status(doc_id: str, status: str, provider: Optional[str]=None) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    if provider:
        cursor.execute('UPDATE documents SET metadata_status = ?, metadata_provider = ?, metadata_updated_at = ?, updated_at = ? WHERE id = ?', (status, provider, now, now, doc_id))
    else:
        cursor.execute('UPDATE documents SET metadata_status = ?, metadata_updated_at = ?, updated_at = ? WHERE id = ?', (status, now, now, doc_id))
    conn.commit()
    conn.close()

def get_document_metadata_status(doc_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT metadata_status, metadata_provider, metadata_updated_at, title, author, year, abstract, keywords, insights FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    import json as _json
    d = dict(row)
    if d.get('keywords'):
        try:
            d['keywords'] = _json.loads(d['keywords'])
        except Exception:
            d['keywords'] = []
    else:
        d['keywords'] = []
    return d

def get_documents(client_id: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if client_id and client_id != 'anonymous':
        # Return documents belonging to this client OR legacy docs with no client_id
        cursor.execute(
            '''
            SELECT id, filename, title, file_type, file_size, page_count, character_count,
                   status, author, year, starred, created_at, updated_at,
                   metadata_status, abstract, keywords, insights
            FROM documents
            WHERE client_id = ? OR client_id IS NULL OR client_id = 'anonymous'
            ORDER BY created_at DESC
            ''',
            (client_id,)
        )
    else:
        cursor.execute(
            '''
            SELECT id, filename, title, file_type, file_size, page_count, character_count,
                   status, author, year, starred, created_at, updated_at,
                   metadata_status, abstract, keywords, insights
            FROM documents
            ORDER BY created_at DESC
            '''
        )
    rows = cursor.fetchall()
    conn.close()
    out = []
    for row in rows:
        d = dict(row)
        if d.get('keywords'):
            try:
                import json as _json
                d['keywords'] = _json.loads(d['keywords'])
            except Exception:
                d['keywords'] = []
        else:
            d['keywords'] = []
        out.append(d)
    return out

def get_document_by_id(doc_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def delete_document(doc_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM document_chunks WHERE document_id = ?', (doc_id,))
    cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_document(doc_id: str, **fields) -> Optional[dict]:
    allowed = {'filename', 'title', 'extracted_text', 'character_count', 'page_count'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_document_by_id(doc_id)
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ', '.join((f'{k} = ?' for k in updates))
    values = list(updates.values())
    cursor.execute(f'UPDATE documents SET {set_clause}, updated_at = ? WHERE id = ?', values + [datetime.utcnow().isoformat(), doc_id])
    conn.commit()
    conn.close()
    return get_document_by_id(doc_id)

def get_workspace_documents(ws_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT d.id, d.filename, d.title, d.file_type, d.file_size, d.page_count,\n               d.character_count, d.created_at, d.updated_at\n        FROM documents d\n        JOIN workspace_documents wd ON d.id = wd.document_id\n        WHERE wd.workspace_id = ?\n        ORDER BY d.created_at DESC\n    ', (ws_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
import json

def create_chunks(document_id: str, chunks_data: List[Dict]) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM document_chunks WHERE document_id = ?', (document_id,))
    now = datetime.utcnow().isoformat()
    rows = []
    for chunk in chunks_data:
        embedding_str = json.dumps(chunk['embedding']) if 'embedding' in chunk and chunk['embedding'] else None
        rows.append((str(uuid.uuid4()), document_id, chunk['chunk_index'], chunk['text'], chunk.get('page_number'), chunk.get('char_start'), chunk.get('char_end'), chunk.get('bboxes_json'), chunk.get('page_width'), chunk.get('page_height'), embedding_str, now))
    cursor.executemany('\n        INSERT INTO document_chunks (\n            id, document_id, chunk_index, text, page_number,\n            char_start, char_end, bboxes_json, page_width, page_height,\n            embedding, created_at\n        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ', rows)
    conn.commit()
    conn.close()

def get_chunks_for_document(document_id: str) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id, chunk_index, text, page_number, char_start, char_end,\n               bboxes_json, page_width, page_height, created_at\n        FROM document_chunks\n        WHERE document_id = ?\n        ORDER BY chunk_index ASC\n    ', (document_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_chunks() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id, text, embedding\n        FROM document_chunks \n        ORDER BY id ASC\n    ')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chunks_by_ids(chunk_ids: List[str]) -> List[Dict]:
    if not chunk_ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(chunk_ids))
    cursor.execute(f'\n        SELECT id, document_id, chunk_index, text, page_number,\n               char_start, char_end, bboxes_json, page_width, page_height,\n               created_at\n        FROM document_chunks\n        WHERE id IN ({placeholders})\n    ', chunk_ids)
    rows = cursor.fetchall()
    conn.close()
    result_dict = {row['id']: dict(row) for row in rows}
    ordered_results = []
    for cid in chunk_ids:
        if cid in result_dict:
            ordered_results.append(result_dict[cid])
    return ordered_results

def create_workspace(name: str, description: str = '', client_id: Optional[str] = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    ws_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute(
        '''
        INSERT INTO workspaces (id, name, description, created_at, updated_at, client_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (ws_id, name, description, now, now, client_id or 'anonymous')
    )
    conn.commit()
    conn.close()
    return {
        'id': ws_id,
        'name': name,
        'description': description,
        'created_at': now,
        'updated_at': now,
        'client_id': client_id or 'anonymous',
    }

def get_all_workspaces(client_id: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if client_id and client_id != 'anonymous':
        cursor.execute(
            '''
            SELECT * FROM workspaces
            WHERE client_id = ? OR client_id IS NULL OR client_id = 'anonymous'
            ORDER BY updated_at DESC
            ''',
            (client_id,)
        )
    else:
        cursor.execute('SELECT * FROM workspaces ORDER BY updated_at DESC')
    rows = cursor.fetchall()
    workspaces = [dict(row) for row in rows]
    ws_ids = tuple(ws['id'] for ws in workspaces)
    if ws_ids:
        placeholders = ','.join('?' * len(ws_ids))
        cursor.execute(
            f'SELECT workspace_id, document_id FROM workspace_documents WHERE workspace_id IN ({placeholders})',
            ws_ids
        )
        wd_rows = cursor.fetchall()
    else:
        wd_rows = []
    conn.close()
    ws_docs = {}
    for r in wd_rows:
        ws_docs.setdefault(r['workspace_id'], []).append(r['document_id'])
    for ws in workspaces:
        ws['document_ids'] = ws_docs.get(ws['id'], [])
    return workspaces

def get_workspace_by_id(ws_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM workspaces WHERE id = ?', (ws_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_workspace(ws_id: str, name: str, description: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        UPDATE workspaces \n        SET name = ?, description = ?, updated_at = ?\n        WHERE id = ?\n    ', (name, description, now, ws_id))
    if cursor.rowcount == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_workspace_by_id(ws_id)

def delete_workspace(ws_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM workspace_documents WHERE workspace_id = ?', (ws_id,))
    cursor.execute('DELETE FROM workspace_resources WHERE workspace_id = ?', (ws_id,))
    cursor.execute('DELETE FROM notes WHERE workspace_id = ?', (ws_id,))
    cursor.execute('DELETE FROM citations WHERE workspace_id = ?', (ws_id,))
    cursor.execute('DELETE FROM workspaces WHERE id = ?', (ws_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_document_to_workspace(ws_id: str, doc_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cursor.execute('\n            INSERT INTO workspace_documents (workspace_id, document_id, created_at)\n            VALUES (?, ?, ?)\n        ', (ws_id, doc_id, now))
        cursor.execute('\n            UPDATE workspaces SET updated_at = ? WHERE id = ?\n        ', (now, ws_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_document_from_workspace(ws_id: str, doc_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        DELETE FROM workspace_documents \n        WHERE workspace_id = ? AND document_id = ?\n    ', (ws_id, doc_id))
    deleted = cursor.rowcount > 0
    if deleted:
        now = datetime.utcnow().isoformat()
        cursor.execute('\n            UPDATE workspaces SET updated_at = ? WHERE id = ?\n        ', (now, ws_id))
    conn.commit()
    conn.close()
    return deleted

def get_documents_for_workspace(ws_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT d.id, d.filename, d.file_type, d.file_size, d.page_count, d.character_count, d.created_at, wd.created_at as added_at\n        FROM documents d\n        JOIN workspace_documents wd ON d.id = wd.document_id\n        WHERE wd.workspace_id = ?\n        ORDER BY wd.created_at DESC\n    ', (ws_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_workspaces_for_document(doc_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT w.* \n        FROM workspaces w\n        JOIN workspace_documents wd ON w.id = wd.workspace_id\n        WHERE wd.document_id = ?\n        ORDER BY w.updated_at DESC\n    ', (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def create_note(workspace_id: str, title: str, content: str, kind: str='note', source_message_id: Optional[str]=None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO notes (id, workspace_id, kind, title, content, source_message_id, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n    ', (note_id, workspace_id, kind, title, content, source_message_id, now, now))
    cursor.execute('UPDATE workspaces SET updated_at = ? WHERE id = ?', (now, workspace_id))
    conn.commit()
    conn.close()
    return {'id': note_id, 'workspace_id': workspace_id, 'kind': kind, 'title': title, 'content': content, 'source_message_id': source_message_id, 'created_at': now, 'updated_at': now}

def list_notes(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id, workspace_id, kind, title, content, source_message_id, created_at, updated_at\n        FROM notes WHERE workspace_id = ? ORDER BY updated_at DESC\n    ', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_note(note_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_note(note_id: str, title: str, content: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        UPDATE notes SET title = ?, content = ?, updated_at = ?\n        WHERE id = ?\n    ', (title, content, now, note_id))
    if cursor.rowcount == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_note(note_id)

def delete_note(note_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_research_brief(workspace_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM research_briefs WHERE workspace_id = ?', (workspace_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_research_brief(workspace_id: str, fields: Dict) -> dict:
    allowed = ['topic', 'problem', 'research_question', 'objectives', 'papers_reviewed', 'key_findings', 'common_limitations', 'potential_gap', 'proposed_direction', 'open_questions', 'current_stage']
    existing = get_research_brief(workspace_id) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if k in allowed}}
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        INSERT INTO research_briefs (workspace_id, topic, problem, research_question, objectives,\n            papers_reviewed, key_findings, common_limitations, potential_gap,\n            proposed_direction, open_questions, current_stage, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ON CONFLICT(workspace_id) DO UPDATE SET\n            topic = excluded.topic,\n            problem = excluded.problem,\n            research_question = excluded.research_question,\n            objectives = excluded.objectives,\n            papers_reviewed = excluded.papers_reviewed,\n            key_findings = excluded.key_findings,\n            common_limitations = excluded.common_limitations,\n            potential_gap = excluded.potential_gap,\n            proposed_direction = excluded.proposed_direction,\n            open_questions = excluded.open_questions,\n            current_stage = excluded.current_stage,\n            updated_at = excluded.updated_at\n    ', (workspace_id, merged.get('topic'), merged.get('problem'), merged.get('research_question'), merged.get('objectives'), merged.get('papers_reviewed'), merged.get('key_findings'), merged.get('common_limitations'), merged.get('potential_gap'), merged.get('proposed_direction'), merged.get('open_questions'), merged.get('current_stage'), now))
    cursor.execute('UPDATE workspaces SET updated_at = ? WHERE id = ?', (now, workspace_id))
    conn.commit()
    conn.close()
    return get_research_brief(workspace_id)

def get_project_plan(workspace_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM project_plans WHERE workspace_id = ?', (workspace_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_project_plan(workspace_id: str, fields: Dict) -> dict:
    allowed = ['problem_statement', 'objectives', 'requirements', 'architecture', 'technology_stack', 'components', 'data_flow', 'implementation_stages', 'testing_strategy', 'evaluation_metrics', 'deployment_plan']
    existing = get_project_plan(workspace_id) or {}
    merged = {**existing, **{k: v for k, v in fields.items() if k in allowed}}
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        INSERT INTO project_plans (workspace_id, problem_statement, objectives, requirements,\n            architecture, technology_stack, components, data_flow, implementation_stages,\n            testing_strategy, evaluation_metrics, deployment_plan, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ON CONFLICT(workspace_id) DO UPDATE SET\n            problem_statement = excluded.problem_statement,\n            objectives = excluded.objectives,\n            requirements = excluded.requirements,\n            architecture = excluded.architecture,\n            technology_stack = excluded.technology_stack,\n            components = excluded.components,\n            data_flow = excluded.data_flow,\n            implementation_stages = excluded.implementation_stages,\n            testing_strategy = excluded.testing_strategy,\n            evaluation_metrics = excluded.evaluation_metrics,\n            deployment_plan = excluded.deployment_plan,\n            updated_at = excluded.updated_at\n    ', (workspace_id, merged.get('problem_statement'), merged.get('objectives'), merged.get('requirements'), merged.get('architecture'), merged.get('technology_stack'), merged.get('components'), merged.get('data_flow'), merged.get('implementation_stages'), merged.get('testing_strategy'), merged.get('evaluation_metrics'), merged.get('deployment_plan'), now))
    cursor.execute('UPDATE workspaces SET updated_at = ? WHERE id = ?', (now, workspace_id))
    conn.commit()
    conn.close()
    return get_project_plan(workspace_id)

def create_experiment(workspace_id: str, name: str, **fields) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    exp_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO experiments (id, workspace_id, name, model, dataset, configuration,\n            metric, result, experiment_date, notes, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ', (exp_id, workspace_id, name, fields.get('model'), fields.get('dataset'), fields.get('configuration'), fields.get('metric'), fields.get('result'), fields.get('experiment_date'), fields.get('notes'), now, now))
    cursor.execute('UPDATE workspaces SET updated_at = ? WHERE id = ?', (now, workspace_id))
    conn.commit()
    conn.close()
    return get_experiment(exp_id)

def list_experiments(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM experiments WHERE workspace_id = ? ORDER BY created_at DESC', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_experiment(exp_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM experiments WHERE id = ?', (exp_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_experiment(exp_id: str, **fields) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    sets, vals = ([], [])
    for key in ('name', 'model', 'dataset', 'configuration', 'metric', 'result', 'experiment_date', 'notes'):
        if key in fields:
            sets.append(f'{key} = ?')
            vals.append(fields[key])
    if not sets:
        conn.close()
        return get_experiment(exp_id)
    sets.append('updated_at = ?')
    vals.append(now)
    vals.append(exp_id)
    cursor.execute(f"UPDATE experiments SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_experiment(exp_id)

def delete_experiment(exp_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM experiments WHERE id = ?', (exp_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def create_citation(**fields) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cite_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO citations (id, document_id, workspace_id, source_type, external_id,\n            title, authors, year, venue, doi, url, abstract, created_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ', (cite_id, fields.get('document_id'), fields.get('workspace_id'), fields.get('source_type', 'manual'), fields.get('external_id'), fields.get('title', 'Untitled'), fields.get('authors'), fields.get('year'), fields.get('venue'), fields.get('doi'), fields.get('url'), fields.get('abstract'), now))
    conn.commit()
    conn.close()
    return get_citation(cite_id)

def get_citation(cite_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM citations WHERE id = ?', (cite_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_citations(workspace_id: Optional[str]=None) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if workspace_id:
        cursor.execute('SELECT * FROM citations WHERE workspace_id = ? ORDER BY year DESC, created_at DESC', (workspace_id,))
    else:
        cursor.execute('SELECT * FROM citations ORDER BY created_at DESC LIMIT 200')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_citation(cite_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM citations WHERE id = ?', (cite_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def create_studio_doc(workspace_id: str, template: str, title: str, content: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO studio_documents (id, workspace_id, template, title, content, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?)\n    ', (sid, workspace_id, template, title, content, now, now))
    conn.commit()
    conn.close()
    return get_studio_doc(sid)

def get_studio_doc(sid: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM studio_documents WHERE id = ?', (sid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_studio_docs(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM studio_documents WHERE workspace_id = ? ORDER BY updated_at DESC', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_studio_doc(sid: str, **fields) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    sets, vals = ([], [])
    for key in ('template', 'title', 'content'):
        if key in fields:
            sets.append(f'{key} = ?')
            vals.append(fields[key])
    if not sets:
        conn.close()
        return get_studio_doc(sid)
    sets.append('updated_at = ?')
    vals.append(now)
    vals.append(sid)
    cursor.execute(f"UPDATE studio_documents SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_studio_doc(sid)

def delete_studio_doc(sid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM studio_documents WHERE id = ?', (sid,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_setting(key: str, default: Optional[str]=None) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO settings (key, value) VALUES (?, ?)\n        ON CONFLICT(key) DO UPDATE SET value = excluded.value\n    ', (key, value))
    conn.commit()
    conn.close()

def create_document_version(doc_id: str, title: str, content: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(version_number) as max_ver FROM document_versions WHERE document_id = ?', (doc_id,))
    row = cursor.fetchone()
    next_ver = (dict(row)['max_ver'] or 0) + 1 if row else 1
    version_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO document_versions (id, document_id, version_number, title, content, created_at)\n        VALUES (?, ?, ?, ?, ?, ?)\n    ', (version_id, doc_id, next_ver, title, content, now))
    conn.commit()
    conn.close()
    return {'id': version_id, 'document_id': doc_id, 'version_number': next_ver, 'title': title, 'content': content, 'created_at': now}

def get_document_versions(doc_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id, document_id, version_number, title, created_at\n        FROM document_versions\n        WHERE document_id = ?\n        ORDER BY version_number DESC\n    ', (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_document_version(version_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM document_versions WHERE id = ?', (version_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_workspace_template(name: str, description: str='', brief_template: str='', plan_template: str='') -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    tid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO workspace_templates (id, name, description, brief_template, plan_template, created_at)\n        VALUES (?, ?, ?, ?, ?, ?)\n    ', (tid, name, description, brief_template, plan_template, now))
    conn.commit()
    conn.close()
    return {'id': tid, 'name': name, 'description': description, 'brief_template': brief_template, 'plan_template': plan_template, 'created_at': now}

def get_workspace_templates() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM workspace_templates ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_workspace_template(tid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM workspace_templates WHERE id = ?', (tid,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_workspace_template_by_id(tid: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM workspace_templates WHERE id = ?', (tid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_document_tag(doc_id: str, tag: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO document_tags (document_id, tag) VALUES (?, ?)', (doc_id, tag.strip().lower()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_document_tag(doc_id: str, tag: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM document_tags WHERE document_id = ? AND tag = ?', (doc_id, tag.strip().lower()))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_document_tags(doc_id: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT tag FROM document_tags WHERE document_id = ? ORDER BY tag', (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r['tag'] for r in rows]

def get_documents_by_tag(tag: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT document_id FROM document_tags WHERE tag = ?', (tag.strip().lower(),))
    rows = cursor.fetchall()
    conn.close()
    return [r['document_id'] for r in rows]

def get_all_tags() -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT tag FROM document_tags ORDER BY tag')
    rows = cursor.fetchall()
    conn.close()
    return [r['tag'] for r in rows]

def get_document_analysis(document_id: str, kind: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM document_analysis_cache WHERE document_id = ? AND analysis_kind = ?', (document_id, kind))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_document_analysis(document_id: str, kind: str, document_type: str, content: dict, content_text: Optional[str]=None, content_hash: Optional[str]=None, model: Optional[str]=None) -> dict:
    import json as _json
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO document_analysis_cache\n            (document_id, analysis_kind, document_type, content_json, content_text, content_hash, model, generated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n        ON CONFLICT(document_id, analysis_kind) DO UPDATE SET\n            document_type = excluded.document_type,\n            content_json  = excluded.content_json,\n            content_text  = excluded.content_text,\n            content_hash  = excluded.content_hash,\n            model         = excluded.model,\n            generated_at  = excluded.generated_at\n        ', (document_id, kind, document_type, _json.dumps(content, ensure_ascii=False), content_text, content_hash, model, now))
    conn.commit()
    conn.close()
    return get_document_analysis(document_id, kind)

def delete_document_analysis(document_id: str, kind: Optional[str]=None) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    if kind:
        cursor.execute('DELETE FROM document_analysis_cache WHERE document_id = ? AND analysis_kind = ?', (document_id, kind))
    else:
        cursor.execute('DELETE FROM document_analysis_cache WHERE document_id = ?', (document_id,))
    conn.commit()
    conn.close()

def get_analysis_content_hash(doc: dict) -> str:
    import hashlib
    if hasattr(doc, 'keys'):
        doc = dict(doc)
    base = (doc.get('extracted_text') or '') + '|' + (doc.get('file_type') or '')
    return hashlib.sha256(base.encode('utf-8')).hexdigest()
import json as _json

def _user_id_for(provided_user_id: Optional[str]) -> str:
    if provided_user_id and isinstance(provided_user_id, str) and provided_user_id.strip():
        return provided_user_id.strip()
    return 'anonymous'

def create_conversation(*, user_id: Optional[str]=None, scope: str='home', workspace_id: Optional[str]=None, title: Optional[str]=None, mode: str='research') -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    resolved_user = _user_id_for(user_id)
    initial_title = (title or 'New conversation').strip()[:120] or 'New conversation'
    cursor.execute('\n        INSERT INTO conversations (id, user_id, scope, workspace_id, title, mode, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n    ', (cid, resolved_user, scope, workspace_id, initial_title, mode, now, now))
    conn.commit()
    conn.close()
    return get_conversation(cid)

def get_conversation(conversation_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_conversations(*, user_id: Optional[str]=None, scope: Optional[str]=None, workspace_id: Optional[str]=None, limit: int=100) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    resolved_user = _user_id_for(user_id)
    base_query = '\n        SELECT c.*,\n               (SELECT content FROM conversation_messages\n                  WHERE conversation_id = c.id\n                  ORDER BY message_index DESC LIMIT 1) AS last_message_preview\n        FROM conversations c\n        WHERE c.user_id = ?\n    '
    params: List = [resolved_user]
    if scope:
        base_query += ' AND c.scope = ?'
        params.append(scope)
    if workspace_id:
        base_query += ' AND c.workspace_id = ?'
        params.append(workspace_id)
    base_query += ' ORDER BY c.updated_at DESC LIMIT ?'
    params.append(int(limit))
    cursor.execute(base_query, params)
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        preview = (d.get('last_message_preview') or '').strip()
        if len(preview) > 80:
            preview = preview[:77] + '...'
        d['last_message_preview'] = preview
        results.append(d)
    return results

def update_conversation(conversation_id: str, *, title: Optional[str]=None, mode: Optional[str]=None) -> Optional[dict]:
    existing = get_conversation(conversation_id)
    if not existing:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    sets = ['updated_at = ?']
    params: List = [now]
    if title is not None:
        sets.append('title = ?')
        params.append(title.strip()[:120] or 'Untitled')
    if mode is not None:
        sets.append('mode = ?')
        params.append(mode)
    params.append(conversation_id)
    cursor.execute(f"UPDATE conversations SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return get_conversation(conversation_id)

def touch_conversation(conversation_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (datetime.utcnow().isoformat(), conversation_id))
    conn.commit()
    conn.close()

def delete_conversation(conversation_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def delete_workspace_conversations(workspace_id: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE workspace_id = ?', (workspace_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def append_message(conversation_id: str, *, role: str, content: str, sources: Optional[List[dict]]=None, trace: Optional[str]=None, confidence: Optional[str]=None, metadata: Optional[dict]=None, suggested_followups: Optional[List[str]]=None, insufficient_evidence: bool=False) -> dict:
    if role not in ('user', 'orbot'):
        raise ValueError(f"role must be 'user' or 'orbot' (got: {role!r})")
    if content is None:
        raise ValueError('content is required')
    conn = get_connection()
    cursor = conn.cursor()
    mid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('SELECT COALESCE(MAX(message_index), -1) AS max_idx FROM conversation_messages WHERE conversation_id = ?', (conversation_id,))
    row = cursor.fetchone()
    next_idx = int(row['max_idx']) + 1
    cursor.execute('\n        INSERT INTO conversation_messages\n            (id, conversation_id, role, content, message_index,\n             sources_json, trace, confidence, metadata_json,\n             suggested_followups_json, insufficient_evidence, created_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ', (mid, conversation_id, role, content, next_idx, _json.dumps(sources) if sources is not None else None, trace, confidence, _json.dumps(metadata) if metadata is not None else None, _json.dumps(suggested_followups) if suggested_followups is not None else None, 1 if insufficient_evidence else 0, now))
    cursor.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (now, conversation_id))
    cursor.execute('SELECT title FROM conversations WHERE id = ?', (conversation_id,))
    row = cursor.fetchone()
    title = dict(row)['title'] if row else None
    if (not title or title.strip() in ('', 'New conversation')) and role == 'user':
        auto_title = (content or '').strip().splitlines()[0][:80] if content else 'New conversation'
        if not auto_title:
            auto_title = 'New conversation'
        cursor.execute('UPDATE conversations SET title = ? WHERE id = ?', (auto_title, conversation_id))
    conn.commit()
    conn.close()
    return get_message(mid)

def get_message(message_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM conversation_messages WHERE id = ?', (message_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_message(row) if row else None

def list_messages(conversation_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT * FROM conversation_messages\n        WHERE conversation_id = ?\n        ORDER BY message_index ASC\n    ', (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_message(r) for r in rows]

def list_messages_as_history(conversation_id: str, max_messages: int=16) -> List[Dict]:
    messages = list_messages(conversation_id)
    if max_messages and len(messages) > max_messages:
        messages = messages[-max_messages:]
    return [{'role': 'user' if m['role'] == 'user' else 'orbot', 'content': m['content']} for m in messages]

def update_message(message_id: str, *, content: Optional[str]=None) -> Optional[dict]:
    existing = get_message(message_id)
    if not existing:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    if content is not None:
        cursor.execute('UPDATE conversation_messages SET content = ? WHERE id = ?', (content, message_id))
        conn.commit()
    conn.close()
    return get_message(message_id)

def delete_messages_after(conversation_id: str, after_index: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversation_messages WHERE conversation_id = ? AND message_index > ?', (conversation_id, after_index))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def _row_to_message(row) -> dict:
    d = dict(row)
    for key in ('sources_json', 'metadata_json', 'suggested_followups_json'):
        raw = d.get(key)
        if raw is None or raw == '':
            d[key] = None
        else:
            try:
                d[key] = _json.loads(raw)
            except Exception:
                d[key] = None
    d['insufficient_evidence'] = bool(d.get('insufficient_evidence'))
    return d

def _row_to_reference(row) -> dict:
    d = dict(row)
    raw = d.get('metadata_json')
    if raw:
        try:
            d['metadata'] = _json.loads(raw)
        except Exception:
            d['metadata'] = None
    else:
        d['metadata'] = None
    return d

def upsert_citation_reference(payload: dict) -> dict:
    ref_id = payload.get('id') or str(uuid.uuid4())
    doi = payload.get('doi')
    arxiv = payload.get('arxiv_id')
    metadata_json = _json.dumps(payload.get('metadata') or {}) if payload.get('metadata') is not None else None
    conn = get_connection()
    cursor = conn.cursor()
    existing_id = None
    if doi:
        cursor.execute('SELECT id FROM citation_references WHERE doi = ?', (doi,))
        row = cursor.fetchone()
        if row:
            existing_id = row['id']
    if not existing_id and arxiv:
        cursor.execute('SELECT id FROM citation_references WHERE arxiv_id = ?', (arxiv,))
        row = cursor.fetchone()
        if row:
            existing_id = row['id']
    if existing_id:
        ref_id = existing_id
        cursor.execute('\n            UPDATE citation_references SET\n                title = COALESCE(?, title),\n                authors = COALESCE(?, authors),\n                year = COALESCE(?, year),\n                venue = COALESCE(?, venue),\n                doi = COALESCE(?, doi),\n                arxiv_id = COALESCE(?, arxiv_id),\n                url = COALESCE(?, url),\n                abstract = COALESCE(?, abstract),\n                citations_count = COALESCE(?, citations_count),\n                imported_document_id = COALESCE(?, imported_document_id),\n                metadata_json = COALESCE(?, metadata_json),\n                source = COALESCE(?, source)\n            WHERE id = ?\n            ', (payload.get('title'), payload.get('authors'), payload.get('year'), payload.get('venue'), payload.get('doi'), payload.get('arxiv_id'), payload.get('url'), payload.get('abstract'), payload.get('citations_count'), payload.get('imported_document_id'), metadata_json, payload.get('source'), ref_id))
    else:
        cursor.execute('\n            INSERT INTO citation_references (\n                id, source, title, authors, year, venue, doi, arxiv_id, url,\n                abstract, citations_count, imported_document_id, metadata_json,\n                external_id, created_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ', (ref_id, payload.get('source') or 'manual', payload.get('title') or 'Untitled', payload.get('authors'), payload.get('year'), payload.get('venue'), payload.get('doi'), payload.get('arxiv_id'), payload.get('url'), payload.get('abstract'), payload.get('citations_count') or 0, payload.get('imported_document_id'), metadata_json, payload.get('external_id'), datetime.utcnow()))
    conn.commit()
    conn.close()
    return get_citation_reference(ref_id)

def get_citation_reference(ref_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM citation_references WHERE id = ?', (ref_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_reference(row) if row else None

def find_citation_reference(*, doi: Optional[str]=None, arxiv_id: Optional[str]=None) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if doi:
        cursor.execute('SELECT * FROM citation_references WHERE doi = ?', (doi,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return _row_to_reference(row)
    if arxiv_id:
        cursor.execute('SELECT * FROM citation_references WHERE arxiv_id = ?', (arxiv_id,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return _row_to_reference(row)
    conn.close()
    return None

def list_citation_references_for_document(document_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT DISTINCT r.* FROM citation_references r\n        JOIN citation_edges e ON e.target_reference_id = r.id\n        WHERE e.source_document_id = ?\n        ORDER BY r.year DESC NULLS LAST, r.title ASC\n        ', (document_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_reference(r) for r in rows]

def list_all_citation_references() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM citation_references ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_reference(r) for r in rows]

def create_citation_edge(source_document_id: str, target_reference_id: str, relationship: str='cites', context: Optional[str]=None, page_number: Optional[int]=None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id FROM citation_edges\n        WHERE source_document_id = ? AND target_reference_id = ? AND relationship = ?\n        ', (source_document_id, target_reference_id, relationship))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return get_citation_graph_for_document(source_document_id)
    edge_id = str(uuid.uuid4())
    cursor.execute('\n        INSERT INTO citation_edges (id, source_document_id, target_reference_id,\n                                    relationship, context, page_number, created_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?)\n        ', (edge_id, source_document_id, target_reference_id, relationship, context, page_number, datetime.utcnow()))
    conn.commit()
    conn.close()
    return get_citation_graph_for_document(source_document_id)

def get_citation_graph_for_document(document_id: str) -> dict:
    doc = get_document_by_id(document_id)
    if not doc:
        return {'nodes': [], 'edges': [], 'document': None}
    refs = list_citation_references_for_document(document_id)
    nodes = [{'id': f'doc:{document_id}', 'kind': 'document', 'label': doc.get('title') or doc.get('filename') or 'Document', 'filename': doc.get('filename'), 'year': doc.get('year'), 'author': doc.get('author')}]
    edges = []
    for r in refs:
        ref_node_id = f"ref:{r['id']}"
        nodes.append({'id': ref_node_id, 'kind': 'reference', 'label': r.get('title') or 'Untitled', 'doi': r.get('doi'), 'arxiv_id': r.get('arxiv_id'), 'year': r.get('year'), 'authors': r.get('authors'), 'venue': r.get('venue'), 'citations_count': r.get('citations_count'), 'imported_document_id': r.get('imported_document_id'), 'url': r.get('url'), 'external_id': r.get('external_id'), 'abstract': r.get('abstract')})
        edges.append({'source': f'doc:{document_id}', 'target': ref_node_id, 'relationship': 'cites'})
        if r.get('imported_document_id'):
            imported = get_document_by_id(r['imported_document_id'])
            if imported:
                imported_node_id = f"doc:{r['imported_document_id']}"
                if not any((n['id'] == imported_node_id for n in nodes)):
                    nodes.append({'id': imported_node_id, 'kind': 'document', 'label': imported.get('title') or imported.get('filename') or 'Document', 'filename': imported.get('filename'), 'year': imported.get('year'), 'author': imported.get('author')})
                edges.append({'source': imported_node_id, 'target': ref_node_id, 'relationship': 'is_reference_for'})
    return {'nodes': nodes, 'edges': edges, 'document': doc}

def delete_citation_edges_for_document(document_id: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM citation_edges WHERE source_document_id = ?', (document_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def mark_reference_imported(reference_id: str, document_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE citation_references SET imported_document_id = ? WHERE id = ?', (document_id, reference_id))
    conn.commit()
    conn.close()
    return get_citation_reference(reference_id)

def _row_to_review(row) -> dict:
    d = dict(row)
    raw = d.get('structure')
    if raw:
        try:
            d['structure'] = _json.loads(raw)
        except Exception:
            d['structure'] = None
    raw_ids = d.get('document_ids')
    if raw_ids:
        try:
            d['document_ids'] = _json.loads(raw_ids)
        except Exception:
            d['document_ids'] = []
    else:
        d['document_ids'] = []
    return d

def create_literature_review(workspace_id: str, title: str, topic: Optional[str], document_ids: List[str], structure: dict, draft_text: Optional[str]=None) -> dict:
    review_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        INSERT INTO literature_reviews (id, workspace_id, title, topic, document_ids,\n                                         structure, draft_text, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ', (review_id, workspace_id, title, topic, _json.dumps(document_ids or []), _json.dumps(structure or {}), draft_text, datetime.utcnow(), datetime.utcnow()))
    conn.commit()
    conn.close()
    return get_literature_review(review_id)

def get_literature_review(review_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM literature_reviews WHERE id = ?', (review_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_review(row) if row else None

def list_literature_reviews(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM literature_reviews WHERE workspace_id = ? ORDER BY updated_at DESC', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_review(r) for r in rows]

def update_literature_review(review_id: str, **fields) -> Optional[dict]:
    fields = dict(fields)
    if 'document_ids' in fields:
        fields['document_ids'] = _json.dumps(fields['document_ids'])
    if 'structure' in fields:
        fields['structure'] = _json.dumps(fields['structure'])
    fields['updated_at'] = datetime.utcnow()
    if not fields:
        return get_literature_review(review_id)
    placeholders = ', '.join((f'{k} = ?' for k in fields.keys()))
    values = list(fields.values()) + [review_id]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE literature_reviews SET {placeholders} WHERE id = ?', values)
    conn.commit()
    conn.close()
    return get_literature_review(review_id)

def delete_literature_review(review_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM literature_reviews WHERE id = ?', (review_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def _row_to_deck(row) -> dict:
    return dict(row)

def _row_to_question(row) -> dict:
    d = dict(row)
    raw = d.get('options_json')
    if raw:
        try:
            d['options'] = _json.loads(raw)
        except Exception:
            d['options'] = None
    else:
        d['options'] = None
    return d

def create_quiz_deck(workspace_id: Optional[str], document_id: Optional[str], title: str, topic: Optional[str], difficulty: str='mixed') -> dict:
    deck_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('\n        INSERT INTO quiz_decks (id, workspace_id, document_id, title, topic,\n                                difficulty, question_count, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)\n        ', (deck_id, workspace_id, document_id, title, topic, difficulty, datetime.utcnow(), datetime.utcnow()))
    conn.commit()
    conn.close()
    return get_quiz_deck(deck_id)

def get_quiz_deck(deck_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM quiz_decks WHERE id = ?', (deck_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_deck(row) if row else None

def list_quiz_decks(workspace_id: Optional[str]=None, document_id: Optional[str]=None) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if workspace_id:
        cursor.execute('SELECT * FROM quiz_decks WHERE workspace_id = ? ORDER BY updated_at DESC', (workspace_id,))
    elif document_id:
        cursor.execute('SELECT * FROM quiz_decks WHERE document_id = ? ORDER BY updated_at DESC', (document_id,))
    else:
        cursor.execute('SELECT * FROM quiz_decks ORDER BY updated_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_deck(r) for r in rows]

def delete_quiz_deck(deck_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quiz_decks WHERE id = ?', (deck_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def add_quiz_questions(deck_id: str, questions: List[dict]) -> List[dict]:
    if not questions:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    base_index = cursor.execute('SELECT COALESCE(MAX(position), -1) + 1 AS next FROM quiz_questions WHERE deck_id = ?', (deck_id,)).fetchone()['next']
    inserted_ids = []
    for i, q in enumerate(questions):
        qid = str(uuid.uuid4())
        options_json = _json.dumps(q.get('options')) if q.get('options') is not None else None
        cursor.execute('\n            INSERT INTO quiz_questions (id, deck_id, kind, prompt, answer, options_json,\n                                        explanation, source_chunk_id, source_quote,\n                                        position, created_at)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ', (qid, deck_id, q.get('kind') or 'short_answer', q.get('prompt') or '', q.get('answer') or '', options_json, q.get('explanation'), q.get('source_chunk_id'), q.get('source_quote'), base_index + i, datetime.utcnow()))
        inserted_ids.append(qid)
    cursor.execute('UPDATE quiz_decks SET question_count = (SELECT COUNT(*) FROM quiz_questions WHERE deck_id = ?), updated_at = ? WHERE id = ?', (deck_id, datetime.utcnow(), deck_id))
    conn.commit()
    conn.close()
    return get_quiz_questions(deck_id)

def get_quiz_questions(deck_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM quiz_questions WHERE deck_id = ? ORDER BY position ASC', (deck_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_question(r) for r in rows]

def get_quiz_question(question_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM quiz_questions WHERE id = ?', (question_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_question(row) if row else None

def delete_quiz_question(question_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quiz_questions WHERE id = ?', (question_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def record_quiz_attempt(question_id: str, user_answer: str, is_correct: bool, confidence: Optional[float]=None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM quiz_attempts WHERE question_id = ? ORDER BY reviewed_at DESC LIMIT 1', (question_id,))
    prev = cursor.fetchone()
    prev_ease = prev['ease_factor'] if prev else 2.5
    prev_interval = prev['interval_days'] if prev else 0
    prev_reps = prev['repetitions'] if prev else 0
    if is_correct:
        reps = prev_reps + 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3
        else:
            interval = max(1, int(round(prev_interval * prev_ease)))
        ease = max(1.3, prev_ease + 0.1 - (5.0 - (confidence or 3.0)) * (0.08 + (5.0 - (confidence or 3.0)) * 0.02))
    else:
        reps = 0
        interval = 1
        ease = max(1.3, prev_ease - 0.2)
    next_review = datetime.utcnow().timestamp() + interval * 86400
    next_review_dt = datetime.utcfromtimestamp(next_review)
    attempt_id = str(uuid.uuid4())
    cursor.execute('\n        INSERT INTO quiz_attempts (id, question_id, user_answer, is_correct, confidence,\n                                    reviewed_at, next_review_at, ease_factor, interval_days,\n                                    repetitions)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ', (attempt_id, question_id, user_answer, 1 if is_correct else 0, confidence, datetime.utcnow(), next_review_dt, ease, interval, reps))
    conn.commit()
    conn.close()
    return {'attempt_id': attempt_id, 'next_review_at': next_review_dt.isoformat() + 'Z', 'ease_factor': ease, 'interval_days': interval, 'repetitions': reps}

def latest_attempt_for_question(question_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM quiz_attempts WHERE question_id = ? ORDER BY reviewed_at DESC LIMIT 1', (question_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def due_quiz_questions(deck_id: str, now: Optional[datetime]=None) -> List[dict]:
    questions = get_quiz_questions(deck_id)
    now = now or datetime.utcnow()
    due = []
    for q in questions:
        latest = latest_attempt_for_question(q['id'])
        if not latest:
            due.append(q)
            continue
        next_review = latest.get('next_review_at')
        if not next_review:
            due.append(q)
            continue
        try:
            if isinstance(next_review, str):
                next_dt = datetime.fromisoformat(next_review.replace('Z', ''))
            else:
                next_dt = next_review
            if next_dt <= now:
                due.append(q)
        except Exception:
            due.append(q)
    return due

def deck_progress(deck_id: str) -> dict:
    questions = get_quiz_questions(deck_id)
    total = len(questions)
    if total == 0:
        return {'total': 0, 'answered': 0, 'correct': 0, 'accuracy': 0.0, 'due_now': 0}
    correct = 0
    answered = 0
    due_count = 0
    now = datetime.utcnow()
    for q in questions:
        latest = latest_attempt_for_question(q['id'])
        if latest:
            answered += 1
            if latest.get('is_correct'):
                correct += 1
        next_review = latest.get('next_review_at') if latest else None
        if not next_review:
            due_count += 1
            continue
        try:
            next_dt = datetime.fromisoformat(next_review.replace('Z', '')) if isinstance(next_review, str) else next_review
            if next_dt <= now:
                due_count += 1
        except Exception:
            due_count += 1
    accuracy = round(correct / answered * 100, 1) if answered else 0.0
    return {'total': total, 'answered': answered, 'correct': correct, 'accuracy': accuracy, 'due_now': due_count}

def create_note(workspace_id: str, title: str, content: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("\n        INSERT INTO notes (id, workspace_id, kind, title, content, created_at, updated_at)\n        VALUES (?, ?, 'note', ?, ?, ?, ?)\n    ", (note_id, workspace_id, title, content, now, now))
    conn.commit()
    conn.close()
    return {'id': note_id, 'workspace_id': workspace_id, 'title': title, 'content': content, 'created_at': now}

def get_workspace_notes(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM notes WHERE workspace_id = ? ORDER BY created_at DESC', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_note(note_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_note(note_id: str, title: str, content: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?\n    ', (title, content, now, note_id))
    conn.commit()
    conn.close()
    return {'id': note_id, 'title': title, 'content': content, 'updated_at': now}

def create_resource(workspace_id: str, resource_type: str, title: str, url: str, description: str='') -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    resource_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute('\n        INSERT INTO workspace_resources (id, workspace_id, resource_type, title, url, description, created_at, updated_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n    ', (resource_id, workspace_id, resource_type, title, url, description, now, now))
    conn.commit()
    conn.close()
    return {'id': resource_id, 'workspace_id': workspace_id, 'resource_type': resource_type, 'title': title, 'url': url, 'description': description, 'created_at': now}

def get_workspace_resources(workspace_id: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM workspace_resources WHERE workspace_id = ? ORDER BY created_at DESC', (workspace_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_resource(resource_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM workspace_resources WHERE id = ?', (resource_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
