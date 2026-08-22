import React, { useEffect, useState } from 'react';
import { FileText, File, Trash2, Plus, Loader2, Eye, Tag, X, CheckSquare, Square } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  getDocuments, deleteDocument,
  getDocumentTags, addDocumentTag, removeDocumentTag, getAllTags,
  getWorkspaces, addDocumentToWorkspace,
} from '../services/api';
import DocumentPreview from '../components/common/DocumentPreview';
import './Documents.css';

function Documents() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [previewDocId, setPreviewDocId] = useState(null);
  const [docTags, setDocTags] = useState({});
  const [allTags, setAllTags] = useState([]);
  const [tagFilter, setTagFilter] = useState(null);
  const [tagInputs, setTagInputs] = useState({});

  const [selectedIds, setSelectedIds] = useState(new Set());
  const [workspaces, setWorkspaces] = useState([]);
  const [showWorkspaceDropdown, setShowWorkspaceDropdown] = useState(false);

  useEffect(() => {
    fetchDocuments();
    fetchAllTags();
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const data = await getDocuments();
      setDocuments(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  };

  const fetchAllTags = async () => {
    try {
      const data = await getAllTags();
      setAllTags(data.tags || []);
    } catch (_) {}
  };

  const fetchDocTags = async (docId) => {
    try {
      const data = await getDocumentTags(docId);
      setDocTags(prev => ({ ...prev, [docId]: data.tags || [] }));
    } catch (_) {}
  };

  const handleAddTag = async (docId, tag) => {
    if (!tag.trim()) return;
    try {
      await addDocumentTag(docId, tag.trim());
      await fetchDocTags(docId);
      fetchAllTags();
      setTagInputs(prev => ({ ...prev, [docId]: '' }));
    } catch (err) {
      setError(err.message || 'Failed to add tag.');
    }
  };

  const handleRemoveTag = async (docId, tag) => {
    try {
      await removeDocumentTag(docId, tag);
      await fetchDocTags(docId);
      fetchAllTags();
    } catch (err) {
      setError(err.message || 'Failed to remove tag.');
    }
  };

  const handleDocumentClick = (id) => {
    navigate(`/documents/${id}`);
  };

  const handleDelete = async (e, id, name) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      try {
        await deleteDocument(id);
        setDocuments(documents.filter(doc => doc.id !== id));
        setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
      } catch (err) {
        alert(err.message || 'Failed to delete the document.');
      }
    }
  };

  const toggleSelect = (e, id) => {
    e.stopPropagation();
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map(d => d.id)));
    }
  };

  const clearSelection = () => setSelectedIds(new Set());

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedIds.size} selected document(s)? This cannot be undone.`)) return;
    const ids = [...selectedIds];
    let failed = 0;
    for (const id of ids) {
      try {
        await deleteDocument(id);
      } catch {
        failed++;
      }
    }
    setDocuments(prev => prev.filter(d => !selectedIds.has(d.id)));
    setSelectedIds(new Set());
    if (failed > 0) alert(`Failed to delete ${failed} document(s).`);
  };

  const handleBulkAddToWorkspace = async (workspaceId) => {
    setShowWorkspaceDropdown(false);
    const ids = [...selectedIds];
    let added = 0;
    for (const id of ids) {
      try {
        await addDocumentToWorkspace(workspaceId, id);
        added++;
      } catch {}
    }
    alert(`Added ${added} document(s) to workspace.`);
    clearSelection();
  };

  const openWorkspaceDropdown = async () => {
    try {
      const res = await getWorkspaces();
      setWorkspaces(res.items || res || []);
      setShowWorkspaceDropdown(true);
    } catch {
      alert('Failed to load workspaces.');
    }
  };

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  };

  const allSelected = documents.length > 0 && selectedIds.size === documents.length;

  return (
    <div className="documents-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-subtitle">Manage and view your uploaded documents.</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/')}>
          <Plus size={16} />
          Upload document
        </button>
      </div>

      {selectedIds.size > 0 && (
        <div className="bulk-action-bar">
          <div className="bulk-left">
            <button className="btn-icon" onClick={toggleSelectAll} title={allSelected ? 'Deselect all' : 'Select all'}>
              {allSelected ? <CheckSquare size={18} /> : <Square size={18} />}
            </button>
            <span className="bulk-count">{selectedIds.size} selected</span>
          </div>
          <div className="bulk-actions">
            <button className="btn-secondary" onClick={openWorkspaceDropdown} style={{ fontSize: '0.85rem' }}>
              Add to Workspace
            </button>
            {showWorkspaceDropdown && (
              <div className="workspace-dropdown">
                <div className="dropdown-header">
                  <span>Select workspace</span>
                  <button className="btn-icon" onClick={() => setShowWorkspaceDropdown(false)}><X size={14} /></button>
                </div>
                {workspaces.length === 0 ? (
                  <div className="dropdown-empty">No workspaces found</div>
                ) : (
                  workspaces.map(ws => (
                    <button key={ws.id} className="dropdown-item" onClick={() => handleBulkAddToWorkspace(ws.id)}>
                      {ws.name}
                    </button>
                  ))
                )}
              </div>
            )}
            <button className="btn-secondary" onClick={clearSelection} style={{ fontSize: '0.85rem' }}>
              Clear Selection
            </button>
            <button className="btn-primary" onClick={handleBulkDelete} style={{ backgroundColor: '#c0392b', fontSize: '0.85rem' }}>
              <Trash2 size={14} /> Delete Selected
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem 0' }}>
          <Loader2 size={32} className="spinning" />
        </div>
      )}

      {error && (
        <div style={{ padding: '2rem', backgroundColor: 'var(--c-f5)', borderRadius: '8px', color: 'var(--c-333)' }}>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && documents.length === 0 && (
        <div style={{ textAlign: 'center', padding: '4rem 2rem', border: '1px dashed var(--c-ccc)', borderRadius: '8px' }}>
          <File size={48} style={{ color: 'var(--c-888)', marginBottom: '1rem' }} />
          <h3>No documents yet</h3>
          <p style={{ color: 'var(--c-555)', marginBottom: '1.5rem' }}>Upload your first document to get started.</p>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Upload document
          </button>
        </div>
      )}

      {!loading && documents.length > 0 && (
        <div>
          {allTags.length > 0 && (
            <div className="tag-filter-bar">
              <span className="tag-filter-label"><Tag size={14} /> Filter by tag:</span>
              <button
                className={`tag-filter-chip ${!tagFilter ? 'active' : ''}`}
                onClick={() => setTagFilter(null)}
              >All</button>
              {allTags.map(tag => (
                <button
                  key={tag}
                  className={`tag-filter-chip ${tagFilter === tag ? 'active' : ''}`}
                  onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
                >{tag}</button>
              ))}
            </div>
          )}
          <div className="documents-grid">
            {documents
              .filter(doc => !tagFilter || (docTags[doc.id] || []).includes(tagFilter))
              .map((doc) => {
                const Icon = doc.file_type === 'PDF' ? FileText : File;
                const tags = docTags[doc.id] || [];
                const isSelected = selectedIds.has(doc.id);
                return (
                  <div key={doc.id} className={`document-card ${isSelected ? 'selected' : ''}`} onClick={() => handleDocumentClick(doc.id)}>
                    <div className="document-card-header">
                      <div className="document-icon-wrapper">
                        <Icon size={24} strokeWidth={1.5} />
                      </div>
                      <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                        <button
                          className="btn-icon"
                          title={isSelected ? 'Deselect' : 'Select'}
                          aria-label={`Select ${doc.filename}`}
                          onClick={(e) => toggleSelect(e, doc.id)}
                        >
                          {isSelected ? <CheckSquare size={18} color="var(--c-000)" /> : <Square size={18} />}
                        </button>
                        <button
                          className="btn-icon"
                          title="Preview document"
                          aria-label={`Preview ${doc.filename}`}
                          onClick={(e) => { e.stopPropagation(); setPreviewDocId(doc.id); }}
                        >
                          <Eye size={18} />
                        </button>
                        <button
                          className="btn-icon delete-btn"
                          title="Delete document"
                          aria-label={`Delete ${doc.filename}`}
                          onClick={(e) => handleDelete(e, doc.id, doc.filename)}
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                    <div className="document-card-body">
                      <h3 className="document-name" title={doc.filename}>{doc.filename}</h3>
                      <div className="document-meta">
                        <span className="document-type">{doc.file_type}</span>
                        <span className="document-date">{formatDate(doc.created_at)}</span>
                      </div>
                      <div className="document-meta" style={{ marginTop: '4px' }}>
                        <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                        {doc.page_count && <span>• {doc.page_count} Pages</span>}
                      </div>
                      <div className="document-tags-area">
                        {tags.length > 0 && (
                          <div className="document-tags">
                            {tags.map(tag => (
                              <span key={tag} className="document-tag">
                                {tag}
                                <button
                                  className="tag-remove-btn"
                                  onClick={(e) => { e.stopPropagation(); handleRemoveTag(doc.id, tag); }}
                                  title={`Remove tag "${tag}"`}
                                ><X size={10} /></button>
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="tag-input-row" onClick={e => e.stopPropagation()}>
                          <input
                            className="tag-input"
                            placeholder="Add tag..."
                            value={tagInputs[doc.id] || ''}
                            onChange={e => setTagInputs(prev => ({ ...prev, [doc.id]: e.target.value }))}
                            onKeyDown={e => {
                              if (e.key === 'Enter') {
                                handleAddTag(doc.id, tagInputs[doc.id] || '');
                              }
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      <DocumentPreview
        documentId={previewDocId}
        onClose={() => setPreviewDocId(null)}
      />
    </div>
  );
}

export default Documents;
