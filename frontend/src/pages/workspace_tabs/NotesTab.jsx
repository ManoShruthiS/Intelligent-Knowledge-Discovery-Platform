import React, { useState, useEffect } from 'react';
import { FileText, Plus, Trash2, Save, X, Edit, Loader2 } from 'lucide-react';
import { listNotes, createNote, updateNote, deleteNote } from '../../services/api';

const NOTE_KINDS = [
  { value: 'general', label: 'General' },
  { value: 'methodology', label: 'Methodology' },
  { value: 'finding', label: 'Finding' },
  { value: 'question', label: 'Question' },
  { value: 'limitation', label: 'Limitation' },
  { value: 'gap', label: 'Research Gap' },
];

function NotesTab({ workspaceId }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ title: '', content: '' });
  const [showNewForm, setShowNewForm] = useState(false);
  const [newForm, setNewForm] = useState({ title: '', content: '', kind: 'general' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchNotes();
  }, [workspaceId]);

  const fetchNotes = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listNotes(workspaceId);
      setNotes(data.notes || []);
    } catch (err) {
      setError(err.message || 'Failed to load notes.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newForm.title.trim()) return;
    setSaving(true);
    try {
      const created = await createNote(workspaceId, newForm);
      setNotes(prev => [created, ...prev]);
      setNewForm({ title: '', content: '', kind: 'general' });
      setShowNewForm(false);
    } catch (err) {
      setError(err.message || 'Failed to create note.');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (note) => {
    setEditingId(note.id);
    setEditForm({ title: note.title || '', content: note.content || '' });
  };

  const handleUpdate = async (noteId) => {
    setSaving(true);
    try {
      const updated = await updateNote(noteId, editForm);
      setNotes(prev => prev.map(n => n.id === noteId ? { ...n, ...updated } : n));
      setEditingId(null);
    } catch (err) {
      setError(err.message || 'Failed to update note.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noteId) => {
    if (!window.confirm('Delete this note?')) return;
    try {
      await deleteNote(noteId);
      setNotes(prev => prev.filter(n => n.id !== noteId));
    } catch (err) {
      setError(err.message || 'Failed to delete note.');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  };

  const getKindColor = (kind) => {
    const colors = {
      general: 'var(--c-666)',
      methodology: 'var(--c-333)',
      finding: 'var(--c-111)',
      question: 'var(--c-555)',
      limitation: 'var(--c-888)',
      gap: 'var(--c-444)',
    };
    return colors[kind] || 'var(--c-666)';
  };

  if (loading) {
    return (
      <div style={styles.centered}>
        <Loader2 size={28} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: '0.9rem', color: 'var(--c-666)' }}>Loading notes...</span>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Research Notes</h2>
          <p style={styles.subtitle}>Capture observations, questions, and insights as you read.</p>
        </div>
        <button style={styles.btnPrimary} onClick={() => setShowNewForm(!showNewForm)}>
          {showNewForm ? <X size={16} /> : <Plus size={16} />}
          {showNewForm ? 'Cancel' : 'New Note'}
        </button>
      </div>

      {error && (
        <div style={styles.errorBanner}>{error}</div>
      )}

      {showNewForm && (
        <div style={styles.newNoteForm}>
          <input
            style={styles.input}
            placeholder="Note title"
            value={newForm.title}
            onChange={(e) => setNewForm({ ...newForm, title: e.target.value })}
          />
          <textarea
            style={styles.textarea}
            placeholder="Write your note..."
            rows={4}
            value={newForm.content}
            onChange={(e) => setNewForm({ ...newForm, content: e.target.value })}
          />
          <div style={styles.formActions}>
            <select
              style={styles.select}
              value={newForm.kind}
              onChange={(e) => setNewForm({ ...newForm, kind: e.target.value })}
            >
              {NOTE_KINDS.map(k => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
            <button
              style={{ ...styles.btnPrimary, ...(saving ? styles.btnDisabled : {}) }}
              onClick={handleCreate}
              disabled={saving || !newForm.title.trim()}
            >
              <Save size={14} />
              {saving ? 'Saving...' : 'Save Note'}
            </button>
          </div>
        </div>
      )}

      {notes.length === 0 && !error && (
        <div style={styles.emptyState}>
          <FileText size={40} color="var(--c-ddd)" />
          <p>No notes yet. Click "New Note" to get started.</p>
        </div>
      )}

      {notes.map(note => (
        <div key={note.id} style={styles.noteCard}>
          {editingId === note.id ? (
            <div style={styles.editForm}>
              <input
                style={styles.input}
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              />
              <textarea
                style={styles.textarea}
                rows={6}
                value={editForm.content}
                onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
              />
              <div style={styles.formActions}>
                <button
                  style={styles.btnGhost}
                  onClick={() => setEditingId(null)}
                >
                  <X size={14} /> Cancel
                </button>
                <button
                  style={{ ...styles.btnPrimary, ...(saving ? styles.btnDisabled : {}) }}
                  onClick={() => handleUpdate(note.id)}
                  disabled={saving}
                >
                  <Save size={14} /> {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div style={styles.noteHeader}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: 0 }}>
                  <FileText size={16} color="var(--c-555)" />
                  <span style={styles.noteTitle}>{note.title}</span>
                  <span style={{ ...styles.badge, color: getKindColor(note.kind) }}>
                    {note.kind || 'general'}
                  </span>
                </div>
                <div style={styles.noteActions}>
                  <button
                    style={styles.iconBtn}
                    onClick={() => startEdit(note)}
                    title="Edit"
                  >
                    <Edit size={14} />
                  </button>
                  <button
                    style={{ ...styles.iconBtn, color: 'var(--c-888)' }}
                    onClick={() => handleDelete(note.id)}
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {note.content && (
                <p style={styles.noteContent}>
                  {note.content.length > 200 ? note.content.slice(0, 200) + '...' : note.content}
                </p>
              )}
              <div style={styles.noteMeta}>
                {formatDate(note.created_at)}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    padding: '1.5rem 2rem 3rem 2rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: 'var(--c-111)',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '0.9rem',
    color: 'var(--c-666)',
  },
  btnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.5rem 1rem',
    fontSize: '0.85rem',
    fontWeight: 500,
    border: '1px solid var(--c-111)',
    borderRadius: '6px',
    backgroundColor: 'var(--c-111)',
    color: '#fff',
    cursor: 'pointer',
  },
  btnGhost: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.4rem 0.8rem',
    fontSize: '0.85rem',
    fontWeight: 500,
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-333)',
    cursor: 'pointer',
  },
  btnDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  errorBanner: {
    padding: '0.75rem 1rem',
    fontSize: '0.85rem',
    color: 'var(--c-333)',
    backgroundColor: 'var(--c-f5f5f5)',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
  },
  centered: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4rem 2rem',
    gap: '0.75rem',
    color: 'var(--c-666)',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4rem 2rem',
    gap: '0.75rem',
    backgroundColor: '#fff',
    border: '1px solid var(--c-eee)',
    borderRadius: '8px',
    color: 'var(--c-888)',
    fontSize: '0.9rem',
  },
  newNoteForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
    padding: '1.25rem',
    backgroundColor: '#fff',
    border: '1px solid var(--c-ddd)',
    borderRadius: '8px',
  },
  input: {
    width: '100%',
    padding: '0.6rem 0.8rem',
    fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-111)',
    outline: 'none',
    boxSizing: 'border-box',
  },
  textarea: {
    width: '100%',
    padding: '0.6rem 0.8rem',
    fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-111)',
    outline: 'none',
    resize: 'vertical',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  },
  select: {
    padding: '0.5rem 0.75rem',
    fontSize: '0.85rem',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-333)',
    cursor: 'pointer',
    outline: 'none',
  },
  formActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    justifyContent: 'space-between',
  },
  noteCard: {
    padding: '1rem 1.25rem',
    backgroundColor: '#fff',
    border: '1px solid var(--c-eee)',
    borderRadius: '8px',
  },
  noteHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '0.75rem',
  },
  noteTitle: {
    fontSize: '0.95rem',
    fontWeight: 600,
    color: 'var(--c-111)',
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  badge: {
    fontSize: '0.7rem',
    fontWeight: 700,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    backgroundColor: 'var(--c-f5f5f5)',
    padding: '0.15rem 0.5rem',
    borderRadius: '4px',
    flexShrink: 0,
  },
  noteActions: {
    display: 'flex',
    gap: '0.25rem',
    flexShrink: 0,
  },
  iconBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    border: '1px solid var(--c-eee)',
    borderRadius: '4px',
    backgroundColor: '#fff',
    color: 'var(--c-555)',
    cursor: 'pointer',
    padding: 0,
  },
  noteContent: {
    fontSize: '0.85rem',
    color: 'var(--c-555)',
    lineHeight: 1.5,
    marginTop: '0.5rem',
    marginBottom: '0.25rem',
  },
  noteMeta: {
    fontSize: '0.75rem',
    color: 'var(--c-888)',
  },
  editForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
};

export default NotesTab;
