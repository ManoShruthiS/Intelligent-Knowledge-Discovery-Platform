import React, { useEffect, useState } from 'react';
import { FileText, Plus, Trash2, Download, RefreshCw, AlertCircle, X, Sparkles } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { listWorkspaceDocuments, deleteDocument, updateDocument, createDocument, studioHelp } from '../services/api';
import MarkdownMessage from '../components/common/MarkdownMessage';

const TEMPLATES = {
  research_brief: {
    title: 'Research Brief',
    content: '# Research Brief\n\n## Research Question\n\n## Background\n\n## Key Findings\n\n## Implications\n\n## References\n',
  },
  literature_review: {
    title: 'Literature Review',
    content: '# Literature Review\n\n## Scope\n\n## Thematic Analysis\n\n### Theme 1\n\n### Theme 2\n\n## Gaps in Current Research\n\n## Conclusion\n',
  },
  project_spec: {
    title: 'Project Specification',
    content: '# Project Specification\n\n## Overview\n\n## Objectives\n\n## Architecture\n\n## Data Model\n\n## API Design\n\n## Timeline\n',
  },
};

function Studio({ workspaceId: propWorkspaceId }) {
  const { id: routeId } = useParams();
  const wsId = propWorkspaceId || routeId;
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeDoc, setActiveDoc] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newTemplate, setNewTemplate] = useState('research_brief');
  const [showHelp, setShowHelp] = useState(false);
  const [helpAction, setHelpAction] = useState('Summarize');
  const [helpInstruction, setHelpInstruction] = useState('');
  const [helpResult, setHelpResult] = useState('');
  const [helpLoading, setHelpLoading] = useState(false);

  const loadDocs = async () => {
    if (!wsId) return;
    setLoading(true); setError(null);
    try {
      const r = await listWorkspaceDocuments(wsId);
      setDocs(r.documents || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDocs(); }, [wsId]);

  const openDoc = (doc) => {
    setActiveDoc(doc);
    setEditContent(doc.content || '');
    setEditTitle(doc.title || '');
  };

  const saveDoc = async () => {
    if (!activeDoc) return;
    setSaving(true); setError(null);
    try {
      if (activeDoc._isNew) {
        const r = await createDocument(wsId, {
          title: editTitle, content: editContent,
          document_type: activeDoc.document_type,
        });
        const saved = r.document || r;
        setDocs(prev => prev.map(d => d.id === activeDoc.id ? saved : d));
        setActiveDoc(saved);
      } else {
        await updateDocument(activeDoc.id, { title: editTitle, content: editContent });
        setDocs(prev => prev.map(d =>
          d.id === activeDoc.id ? { ...d, title: editTitle, content: editContent } : d
        ));
        setActiveDoc(prev => ({ ...prev, title: editTitle, content: editContent }));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const removeDoc = async (docId) => {
    if (!window.confirm('Delete this document permanently?')) return;
    try {
      await deleteDocument(docId);
      setDocs(prev => prev.filter(d => d.id !== docId));
      if (activeDoc?.id === docId) setActiveDoc(null);
    } catch (e) {
      setError(e.message);
    }
  };

  const insertNewDoc = () => {
    const tpl = TEMPLATES[newTemplate];
    const title = newTitle.trim() || tpl.title;
    const newDoc = {
      id: `new-${Date.now()}`, title, content: tpl.content,
      document_type: newTemplate, created_at: new Date().toISOString(), _isNew: true,
    };
    setDocs(prev => [newDoc, ...prev]);
    setActiveDoc(newDoc);
    setEditContent(tpl.content);
    setEditTitle(title);
    setShowNew(false); setNewTitle('');
  };

  const downloadDoc = (doc) => {
    const blob = new Blob([doc.content || ''], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${doc.title || 'document'}.md`;
    a.click(); URL.revokeObjectURL(url);
  };

  const submitHelp = async () => {
    if (!activeDoc) return;
    setHelpLoading(true); setHelpResult(''); setError(null);
    try {
      const r = await studioHelp(activeDoc.id, helpAction, helpInstruction);
      setHelpResult(r.result || r.message || JSON.stringify(r));
    } catch (e) {
      setError(e.message);
    } finally {
      setHelpLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '1rem', height: '100%', minHeight: 0 }}>
      <div style={{
        width: '260px', minWidth: '220px', flexShrink: 0,
        border: '1px solid var(--c-eee, #eee)', borderRadius: 8,
        background: 'var(--c-white, #fff)', display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0.75rem 1rem', borderBottom: '1px solid var(--c-eee, #eee)',
        }}>
          <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
            <FileText size={14} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
            Documents ({docs.length})
          </span>
          <button type="button" onClick={() => setShowNew(true)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--c-111, #111)', padding: 4 }}
            title="New document">
            <Plus size={16} />
          </button>
        </div>
        {showNew && (
          <div style={{ borderBottom: '1px solid var(--c-eee, #eee)' }}>
            <div style={{ padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <input type="text" placeholder="Title (optional)" value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                style={{ padding: '0.35rem 0.5rem', border: '1px solid var(--c-ddd, #ddd)', borderRadius: 4, fontSize: '0.85rem' }} />
              <select value={newTemplate} onChange={(e) => setNewTemplate(e.target.value)}
                style={{ padding: '0.35rem 0.5rem', border: '1px solid var(--c-ddd, #ddd)', borderRadius: 4, fontSize: '0.85rem' }}>
                {Object.entries(TEMPLATES).map(([k, v]) => (<option key={k} value={k}>{v.title}</option>))}
              </select>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button type="button" className="btn-primary"
                  style={{ flex: 1, padding: '0.4rem', fontSize: '0.8rem' }} onClick={insertNewDoc}>Create</button>
                <button type="button" className="btn-secondary"
                  style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem' }} onClick={() => setShowNew(false)}>
                  <X size={12} />
                </button>
              </div>
            </div>
          </div>
        )}
        <div style={{ flex: 1, overflow: 'auto', padding: '0.25rem 0' }}>
          {loading && <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--c-555)', fontSize: '0.85rem' }}><RefreshCw size={16} className="spinning" /></div>}
          {!loading && docs.length === 0 && <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--c-555)', fontSize: '0.85rem' }}>No documents yet. Create one from a template.</div>}
          {docs.map(doc => (
            <button key={doc.id} type="button" onClick={() => openDoc(doc)} style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%', textAlign: 'left',
              padding: '0.5rem 0.75rem', fontSize: '0.85rem',
              background: activeDoc?.id === doc.id ? 'var(--c-f5, #f5f5f5)' : 'transparent',
              border: 'none', cursor: 'pointer',
              borderLeft: activeDoc?.id === doc.id ? '3px solid var(--c-111, #111)' : '3px solid transparent',
              color: 'var(--c-111, #111)',
            }}>
              <FileText size={13} color="var(--c-555, #555)" />
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.title}</span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {error && <div className="wi-error" role="alert" style={{ marginBottom: '0.5rem', flexShrink: 0 }}><AlertCircle size={14} /> {error}</div>}
        {!activeDoc ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--c-555, #555)', fontSize: '0.95rem', textAlign: 'center' }}>
            <div><FileText size={32} color="var(--c-ccc, #ccc)" style={{ marginBottom: '0.75rem' }} />
              <p>Select a document to edit, or create a new one from a template.</p></div>
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0', borderBottom: '1px solid var(--c-eee, #eee)', marginBottom: '0.75rem', flexShrink: 0, flexWrap: 'wrap' }}>
              <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                style={{ flex: 1, minWidth: 200, padding: '0.4rem 0.6rem', border: '1px solid var(--c-ddd, #ddd)', borderRadius: 4, fontSize: '0.95rem', fontWeight: 600 }} />
              <button type="button" className="btn-primary" onClick={saveDoc} disabled={saving}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}>
                {saving && <RefreshCw size={12} className="spinning" />} Save
              </button>
              <button type="button" className="btn-secondary" onClick={() => downloadDoc(activeDoc)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}>
                <Download size={12} /> Export
              </button>
              <button type="button" className="btn-secondary" onClick={() => removeDoc(activeDoc.id)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', padding: '0.4rem 0.6rem', color: 'var(--c-error, #dc3545)' }}>
                <Trash2 size={12} />
              </button>
              <button type="button" className="btn-secondary" onClick={() => setShowHelp(!showHelp)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}>
                <Sparkles size={12} /> AI Help
              </button>
            </div>
            {showHelp && (
              <div style={{
                border: '1px solid var(--c-eee, #eee)', borderRadius: 6,
                padding: '0.75rem 1rem', marginBottom: '0.75rem', background: 'var(--c-fa, #fafafa)',
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                  {['Summarize', 'Rewrite', 'Expand', 'Fix Grammar'].map(action => (
                    <button key={action} type="button"
                      onClick={() => setHelpAction(action)}
                      style={{
                        padding: '0.3rem 0.6rem', fontSize: '0.78rem', borderRadius: 4,
                        border: helpAction === action ? '1px solid var(--c-111, #111)' : '1px solid var(--c-ddd, #ddd)',
                        background: helpAction === action ? 'var(--c-111, #111)' : 'var(--c-white, #fff)',
                        color: helpAction === action ? 'var(--c-white, #fff)' : 'var(--c-555, #555)',
                        cursor: 'pointer',
                      }}>
                      {action}
                    </button>
                  ))}
                </div>
                <textarea placeholder="Optional instruction for AI..." value={helpInstruction}
                  onChange={(e) => setHelpInstruction(e.target.value)}
                  style={{
                    width: '100%', resize: 'none', fontSize: '0.85rem', padding: '0.4rem 0.5rem',
                    border: '1px solid var(--c-ddd, #ddd)', borderRadius: 4, minHeight: 50,
                    fontFamily: 'inherit', marginBottom: '0.5rem', boxSizing: 'border-box',
                  }} />
                <button type="button" className="btn-primary" onClick={submitHelp} disabled={helpLoading}
                  style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                  {helpLoading && <RefreshCw size={12} className="spinning" />} Get Help
                </button>
                {helpResult && (
                  <div style={{
                    marginTop: '0.75rem', padding: '0.75rem', borderRadius: 6,
                    border: '1px solid var(--c-eee, #eee)', background: 'var(--c-white, #fff)',
                    maxHeight: 250, overflow: 'auto',
                  }}>
                    <MarkdownMessage content={helpResult} />
                  </div>
                )}
              </div>
            )}
            <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)}
              style={{ flex: 1, width: '100%', resize: 'none', fontFamily: 'var(--font-mono), ui-monospace, monospace', fontSize: '0.9rem', lineHeight: 1.7, padding: '0.75rem 1rem', border: '1px solid var(--c-eee, #eee)', borderRadius: 6, background: 'var(--c-white, #fff)', color: 'var(--c-111, #111)' }}
              placeholder="Write in Markdown..." />
          </div>
        )}
      </div>
    </div>
  );
}

export default Studio;