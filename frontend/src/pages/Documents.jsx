import React, { useEffect, useState, useContext } from 'react';
import { 
  FileText, File, Plus, Loader2, FolderPlus,
  MoreVertical, CheckCircle2, Check
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  getDocuments, deleteDocument,
  getWorkspaces, addDocumentToWorkspace, createWorkspace
} from '../services/api';
import DocumentPreview from '../components/common/DocumentPreview';
import { UploadContext } from '../components/layout/AppLayout';
import './Documents.css';

function Documents() {
  const navigate = useNavigate();
  const { openUpload } = useContext(UploadContext);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [previewDocId, setPreviewDocId] = useState(null);

  
  const [activeMenuId, setActiveMenuId] = useState(null);

  
  const [wsModalDoc, setWsModalDoc] = useState(null);
  const [availableWorkspaces, setAvailableWorkspaces] = useState([]);
  const [loadingWs, setLoadingWs] = useState(false);
  const [addingWsId, setAddingWsId] = useState(null);
  const [addedWsSuccess, setAddedWsSuccess] = useState({});
  const [wsError, setWsError] = useState(null);
  
  
  const [showInlineWsCreate, setShowInlineWsCreate] = useState(false);
  const [newWsName, setNewWsName] = useState('');
  const [creatingInlineWs, setCreatingInlineWs] = useState(false);

  
  const [docToDelete, setDocToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    fetchDocuments();
    
    
    const handleClickOutside = () => setActiveMenuId(null);
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  useEffect(() => {
    if (!actionError) return undefined;
    const t = setTimeout(() => setActionError(null), 3500);
    return () => clearTimeout(t);
  }, [actionError]);



  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const [docsData, wsData] = await Promise.all([
        getDocuments(),
        getWorkspaces().catch(() => []) 
      ]);
      const list = Array.isArray(docsData) ? docsData : (docsData?.documents || docsData?.items || []);
      setDocuments(list);
      
      const wsList = Array.isArray(wsData) ? wsData : (wsData?.workspaces || wsData?.items || []);
      setAvailableWorkspaces(wsList);
      
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  };



  const handleDocumentClick = (doc) => {
    navigate(`/documents/${doc.id}`);
  };

  
  const openAddToWorkspaceModal = async (e, doc) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setWsModalDoc(doc);
    setWsError(null);
    setShowInlineWsCreate(false);
    setNewWsName('');
    
    try {
      setLoadingWs(true);
      const wsData = await getWorkspaces();
      const wsList = Array.isArray(wsData) ? wsData : (wsData?.workspaces || wsData?.items || []);
      setAvailableWorkspaces(wsList);

      
      const initialAddedState = {};
      wsList.forEach(ws => {
        const docIds = (ws.documents || ws.document_ids || []).map(d => typeof d === 'object' ? d.id : d);
        if (docIds.includes(doc.id)) {
          initialAddedState[ws.id] = true;
        }
      });
      setAddedWsSuccess(initialAddedState);
    } catch (err) {
      setWsError('Failed to load workspaces.');
    } finally {
      setLoadingWs(false);
    }
  };

  
  const handleAssignToWorkspace = async (workspaceId) => {
    if (!wsModalDoc) return;
    setAddingWsId(workspaceId);
    setWsError(null);
    try {
      await addDocumentToWorkspace(workspaceId, wsModalDoc.id);
      setAddedWsSuccess(prev => ({ ...prev, [workspaceId]: true }));
    } catch (err) {
      setWsError(err.message || 'Failed to add document to workspace.');
    } finally {
      setAddingWsId(null);
    }
  };

  
  const handleCreateInlineWorkspace = async (e) => {
    e.preventDefault();
    if (!newWsName.trim() || !wsModalDoc) return;
    
    setCreatingInlineWs(true);
    setWsError(null);
    try {
      const created = await createWorkspace(newWsName.trim());
      const newWsId = created.id || created.workspace_id;
      
      setAvailableWorkspaces(prev => [created, ...prev]);
      
      await addDocumentToWorkspace(newWsId, wsModalDoc.id);
      setAddedWsSuccess(prev => ({ ...prev, [newWsId]: true }));
      setShowInlineWsCreate(false);
      setNewWsName('');
    } catch (err) {
      setWsError(err.message || 'Failed to create workspace.');
    } finally {
      setCreatingInlineWs(false);
    }
  };

  const openDeleteConfirm = (e, doc) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setDeleteError(null);
    setDocToDelete({ id: doc.id, name: doc.title || doc.filename });
  };

  const handleConfirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteDocument(docToDelete.id);
      setDocuments(prev => (Array.isArray(prev) ? prev : []).filter(doc => doc.id !== docToDelete.id));
      setDocToDelete(null);
    } catch (err) {
      setDeleteError(err?.message || 'Failed to delete the document.');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'Added recently';
    const date = new Date(isoString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Added today';
    if (diffDays === 1) return 'Added yesterday';
    if (diffDays < 7) return `Added ${diffDays} days ago`;
    return `Added ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
  };

  const docList = Array.isArray(documents) ? documents : [];
  const docCount = docList.length;

  return (
    <div className="doc-page">
      {}
      <div className="doc-header">
        <div className="doc-header-text">
          <h1 className="doc-title">Documents</h1>
          <p className="doc-subtitle">Manage and explore your documents.</p>
        </div>
        <button className="doc-btn-primary" onClick={openUpload}>
          <Plus size={16} />
          Add document
        </button>
      </div>

      {actionError && (
        <div className="doc-action-error" role="alert">{actionError}</div>
      )}

      {}
      <div className="doc-count-meta">
        {docCount} {docCount === 1 ? 'document' : 'documents'}
      </div>

      {}
      <div className="doc-content">
        {loading ? (
          <div className="doc-loading"><Loader2 size={32} className="spinning" /></div>
        ) : error ? (
          <div className="doc-error">{error}</div>
        ) : docList.length === 0 ? (
          <div className="doc-empty">
            <File size={44} />
            <h3>No documents found</h3>
            <p>Add a new document to get started.</p>
          </div>
        ) : (
          <div className="doc-grid">
            {docList.map(doc => {
              const ext = (doc.file_type || doc.filename?.split('.').pop() || 'pdf').toLowerCase();
              const isReady = doc.status === 'ready' || doc.status === 'indexed' || doc.status === 'completed' || !doc.status;
              const fileTypeLabel = ext.toUpperCase();
              const pageText = doc.page_count ? `${doc.page_count} pages` : (ext === 'pdf' ? '15 pages' : '1 page');

              
              const getFileIconConfig = (type) => {
                switch (type) {
                  case 'pdf':
                    return { Icon: FileText, className: 'icon-pdf' };
                  case 'doc':
                  case 'docx':
                    return { Icon: FileText, className: 'icon-word' };
                  case 'txt':
                  case 'md':
                    return { Icon: FileText, className: 'icon-txt' };
                  case 'csv':
                  case 'xlsx':
                  case 'xls':
                    return { Icon: FileText, className: 'icon-excel' };
                  default:
                    return { Icon: File, className: 'icon-default' };
                }
              };

              const { Icon, className: iconClass } = getFileIconConfig(ext);

              const docWorkspaces = availableWorkspaces.filter(ws => {
                const docIds = (ws.documents || ws.document_ids || []).map(d => typeof d === 'object' ? d.id : d);
                return docIds.includes(doc.id);
              });

              return (
                <div key={doc.id} className="doc-card" onClick={() => handleDocumentClick(doc)}>
                  <div className="doc-card-header">
                    <div className={`doc-card-icon ${iconClass}`}>
                      <Icon size={22} />
                    </div>
                    <div className="doc-card-actions">
                      <div className="doc-menu-container">
                        <button 
                          className="doc-btn-icon" 
                          onClick={(e) => { e.stopPropagation(); setActiveMenuId(activeMenuId === doc.id ? null : doc.id); }}
                          title="More options"
                        >
                          <MoreVertical size={17} />
                        </button>
                        {activeMenuId === doc.id && (
                          <div className="doc-dropdown-menu">
                            <button onClick={(e) => { e.stopPropagation(); setActiveMenuId(null); navigate(`/documents/${doc.id}`); }}>Open</button>
                            <button onClick={(e) => { e.stopPropagation(); setActiveMenuId(null); setPreviewDocId(doc.id); }}>Preview</button>
                            <button onClick={(e) => openAddToWorkspaceModal(e, doc)}>Add to Workspace</button>
                            <div className="doc-menu-divider"></div>
                            <button className="danger" onClick={(e) => openDeleteConfirm(e, doc)}>Delete</button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="doc-card-body">
                    <h3 className="doc-card-title" title={doc.title || doc.filename}>{doc.title || doc.filename}</h3>
                    
                    <div className="doc-card-details">
                      {fileTypeLabel} • {pageText}
                    </div>
                    {docWorkspaces.length > 0 && (
                      <div className="doc-card-workspaces" style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                        {docWorkspaces.map(ws => (
                          <span key={ws.id} style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', backgroundColor: '#e2f0f9', color: '#10567e', borderRadius: '4px', fontWeight: '500' }}>
                            {ws.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {previewDocId && (
        <DocumentPreview documentId={previewDocId} onClose={() => setPreviewDocId(null)} />
      )}

      {}
      {wsModalDoc && (
        <div className="doc-modal-overlay" onClick={() => setWsModalDoc(null)}>
          <div className="doc-modal ws-assign-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Add to Workspace</h3>
            <p className="ws-modal-subtitle">
              Select a workspace to add <strong>"{wsModalDoc.title || wsModalDoc.filename}"</strong>
            </p>

            {wsError && <div className="doc-modal-error">{wsError}</div>}

            {loadingWs ? (
              <div className="ws-modal-loading"><Loader2 size={24} className="spinning" /> Loading workspaces...</div>
            ) : availableWorkspaces.length === 0 && !showInlineWsCreate ? (
              <div className="ws-modal-empty">
                <FolderPlus size={36} color="#64748B" />
                <p>No workspaces available yet.</p>
                <button className="doc-btn-primary" onClick={() => setShowInlineWsCreate(true)}>
                  <Plus size={16} /> Create New Workspace
                </button>
              </div>
            ) : (
              <div className="ws-modal-list">
                {availableWorkspaces.map(ws => {
                  const isAdded = addedWsSuccess[ws.id];
                  const isAdding = addingWsId === ws.id;

                  return (
                    <div key={ws.id} className="ws-modal-item">
                      <div className="ws-modal-item-info">
                        <h4>{ws.name}</h4>
                        {ws.description && <p>{ws.description}</p>}
                      </div>
                      <button 
                        className={`ws-assign-btn ${isAdded ? 'added' : ''}`}
                        onClick={() => handleAssignToWorkspace(ws.id)}
                        disabled={isAdding || isAdded}
                      >
                        {isAdding ? (
                          <Loader2 size={14} className="spinning" />
                        ) : isAdded ? (
                          <>
                            <Check size={14} /> Added
                          </>
                        ) : (
                          'Add'
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {}
            {showInlineWsCreate ? (
              <form className="ws-inline-form" onSubmit={handleCreateInlineWorkspace}>
                <input 
                  type="text" 
                  placeholder="Enter workspace name..." 
                  value={newWsName} 
                  onChange={(e) => setNewWsName(e.target.value)}
                  autoFocus
                  required 
                />
                <div className="ws-inline-form-actions">
                  <button type="button" className="doc-btn-secondary" onClick={() => setShowInlineWsCreate(false)} disabled={creatingInlineWs}>
                    Cancel
                  </button>
                  <button type="submit" className="doc-btn-primary" disabled={creatingInlineWs || !newWsName.trim()}>
                    {creatingInlineWs ? 'Creating & Adding...' : 'Create & Add'}
                  </button>
                </div>
              </form>
            ) : availableWorkspaces.length > 0 && (
              <button className="ws-add-new-btn" onClick={() => setShowInlineWsCreate(true)}>
                <Plus size={16} /> Create a new workspace
              </button>
            )}

            <div className="doc-modal-actions">
              <button className="doc-btn-secondary" onClick={() => setWsModalDoc(null)}>Done</button>
            </div>
          </div>
        </div>
      )}

      {}
      {docToDelete && (
        <div className="doc-modal-overlay" onClick={() => !isDeleting && setDocToDelete(null)}>
          <div className="doc-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete document?</h3>
            <p>This will permanently delete <strong>"{docToDelete.name}"</strong>.</p>
            <p className="doc-modal-warning">This action cannot be undone.</p>
            {deleteError && <div className="doc-modal-error">{deleteError}</div>}
            <div className="doc-modal-actions">
              <button className="doc-btn-secondary" onClick={() => setDocToDelete(null)} disabled={isDeleting}>Cancel</button>
              <button className="doc-btn-danger" onClick={handleConfirmDelete} disabled={isDeleting}>
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Documents;


