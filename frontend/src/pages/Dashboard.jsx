
import React, { useState, useEffect, useContext, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileText, Folder, Compass, ArrowRight, MoreVertical, Eye, Trash2 } from 'lucide-react';
import { UploadContext } from '../components/layout/AppLayout';
import { listDocuments, deleteDocument, getWorkspaces } from '../services/api';
import TopBar from '../components/header/TopBar';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import './Dashboard.css';


const RECENT_ITEMS_LIMIT = 3;


function SkeletonListRow() {
  return (
    <div className="skeleton-list-row">
      <LoadingSkeleton
        width="32px"
        height="32px"
        style={{ borderRadius: '6px', flexShrink: 0 }}
      />
      <div className="skeleton-text-block">
        <LoadingSkeleton width="85%" height="0.95rem" />
        <LoadingSkeleton width="60%" height="0.8rem" />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { openUpload } = useContext(UploadContext);

  
  const [recentDocs, setRecentDocs] = useState([]);
  const [recentWorkspaces, setRecentWorkspaces] = useState([]);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [activeWorkspaceMenuId, setActiveWorkspaceMenuId] = useState(null);
  const [recentDocsError, setRecentDocsError] = useState(null);
  const [recentWorkspacesError, setRecentWorkspacesError] = useState(null);
  const [recentDocsLoading, setRecentDocsLoading] = useState(true);
  const [recentWorkspacesLoading, setRecentWorkspacesLoading] = useState(true);
  const [docToDelete, setDocToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  
  const refreshCounterRef = useRef(0);

  
  const loadDashboardData = useCallback(() => {
    
    const myRefreshId = ++refreshCounterRef.current;
    setRecentDocsError(null);
    setRecentWorkspacesError(null);
    setRecentDocsLoading(true);
    setRecentWorkspacesLoading(true);

    listDocuments({ limit: RECENT_ITEMS_LIMIT, offset: 0 })
      .then(data => {
        if (refreshCounterRef.current !== myRefreshId) return;
        const docs = Array.isArray(data) ? data : (data?.documents || data?.items || []);
        setRecentDocs(docs.slice(0, RECENT_ITEMS_LIMIT));
      })
      .catch(() => {
        if (refreshCounterRef.current !== myRefreshId) return;
        setRecentDocsError("Couldn't load recent documents.");
      })
      .finally(() => {
        if (refreshCounterRef.current === myRefreshId) {
          setRecentDocsLoading(false);
        }
      });

    getWorkspaces()
      .then(res => {
        if (refreshCounterRef.current !== myRefreshId) return;
        const list = Array.isArray(res) ? res : (res?.items || []);
        setRecentWorkspaces(list.slice(0, RECENT_ITEMS_LIMIT));
      })
      .catch(() => {
        if (refreshCounterRef.current !== myRefreshId) return;
        setRecentWorkspacesError("Couldn't load workspaces.");
      })
      .finally(() => {
        if (refreshCounterRef.current === myRefreshId) {
          setRecentWorkspacesLoading(false);
        }
      });
  }, []);

  
  const refreshWorkspacesSafely = useCallback(() => {
    const myRefreshId = ++refreshCounterRef.current;
    setRecentWorkspacesError(null);
    getWorkspaces()
      .then(res => {
        if (refreshCounterRef.current !== myRefreshId) return;
        const list = Array.isArray(res) ? res : (res?.items || []);
        setRecentWorkspaces(list.slice(0, RECENT_ITEMS_LIMIT));
      })
      .catch(() => {});
  }, []);

  
  useEffect(() => {
    loadDashboardData();

    const closeMenu = () => {
      setActiveMenuId(null);
      setActiveWorkspaceMenuId(null);
    };
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, [loadDashboardData]);

  
  useEffect(() => {
    if (!docToDelete) return undefined;
    const handleKey = (e) => {
      if (e.key === 'Escape' && !isDeleting) {
        setDocToDelete(null);
        setDeleteError(null);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [docToDelete, isDeleting]);

  
  const closeDeleteModal = () => {
    if (isDeleting) return;
    setDocToDelete(null);
    setDeleteError(null);
  };

  
  const handleConfirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteDocument(docToDelete.id);
      setRecentDocs(prev => prev.filter(d => d.id !== docToDelete.id));
      refreshWorkspacesSafely();
      setDocToDelete(null);
    } catch (err) {
      setDeleteError(err?.message || 'Failed to delete document.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="dashboard-169-root">
      {}
      <div className="dashboard-embedded-topbar">
        <TopBar onUploadClick={openUpload} />
      </div>

      {}
      <div className="dashboard-169-hero">
        <div className="hero-text-area">
          <h1 className="dashboard-headline">
            Welcome back, <span className="headline-gold">Friend</span>
          </h1>
          <p className="dashboard-subline">Let's continue where you left off.</p>
        </div>
      </div>

      {}
      <div className="dashboard-actions">
        {}
        <motion.div
          className="action-card action-upload"
          whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(0, 95, 115, 0.12)' }}
          onClick={openUpload}
        >
          <div className="action-card-content">
            <div className="action-icon-wrap icon-teal">
              <FileText size={22} strokeWidth={1.8} />
            </div>
            <div className="action-text">
              <h3>Upload Documents</h3>
              <p>Add documents to a workspace</p>
            </div>
            <div className="action-arrow-circle">
              <ArrowRight size={14} />
            </div>
          </div>
        </motion.div>

        {}
        <motion.div
          className="action-card action-workspace"
          whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(184, 148, 69, 0.12)' }}
          onClick={() => navigate('/workspaces')}
        >
          <div className="action-card-content">
            <div className="action-icon-wrap icon-gold">
              <Folder size={22} strokeWidth={1.8} />
            </div>
            <div className="action-text">
              <h3>Create Workspace</h3>
              <p>Organize your knowledge</p>
            </div>
            <div className="action-arrow-circle">
              <ArrowRight size={14} />
            </div>
          </div>
        </motion.div>

        {}
        <motion.div
          className="action-card action-discover"
          whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(10, 147, 150, 0.12)' }}
          onClick={() => navigate('/discover')}
        >
          <div className="action-card-content">
            <div className="action-icon-wrap icon-teal">
              <Compass size={22} strokeWidth={1.8} />
            </div>
            <div className="action-text">
              <h3>Discover</h3>
              <p>Find related information, resources and ideas</p>
            </div>
            <div className="action-arrow-circle">
              <ArrowRight size={14} />
            </div>
          </div>
        </motion.div>
      </div>

      {}
      <div className="dashboard-lists">
        {}
        <div className="list-panel">
          <div className="list-header">
            <div className="list-title">
              <Folder size={20} strokeWidth={1.5} className="list-title-icon" />
              <span>Recent Workspaces</span>
            </div>
            <button
              className="view-all-btn"
              onClick={() => navigate('/workspaces')}
              aria-label="View all workspaces"
              disabled={recentWorkspacesLoading}
            >
              View all <ArrowRight size={14} />
            </button>
          </div>
          <div className="list-content">
            {recentWorkspacesLoading ? (
              <>
                <SkeletonListRow />
                <SkeletonListRow />
                <SkeletonListRow />
              </>
            ) : recentWorkspacesError ? (
              <div className="list-error">
                <p>{recentWorkspacesError}</p>
                <button onClick={loadDashboardData}>Retry</button>
              </div>
            ) : recentWorkspaces.length > 0 ? (
              recentWorkspaces.map((ws, index) => (
                <div
                  key={ws.id ?? index}
                  className="list-item"
                  onClick={() => navigate(`/workspaces/${ws.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`/workspaces/${ws.id}`);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open workspace ${ws.name || ws.title}`}
                  style={{ position: 'relative', cursor: 'pointer' }}
                >
                  <div className="list-item-icon workspace-icon">
                    <Folder size={20} strokeWidth={1.5} />
                  </div>
                  <div className="list-item-info">
                    <h4>{ws.name || ws.title}</h4>
                  </div>
                  <button
                    className="more-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveWorkspaceMenuId(activeWorkspaceMenuId === ws.id ? null : ws.id);
                    }}
                    title="Workspace actions"
                    aria-label="Workspace actions"
                  >
                    <MoreVertical size={18} />
                  </button>

                  {activeWorkspaceMenuId === ws.id && (
                    <div
                      className="dashboard-row-menu"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button className="menu-action-item" onClick={() => { setActiveWorkspaceMenuId(null); navigate(`/workspaces/${ws.id}`); }}>
                        <Eye size={14} /> Open Workspace
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="empty-list-text">No workspaces yet.</p>
            )}
          </div>
        </div>

        {}
        <div className="list-panel">
          <div className="list-header">
            <div className="list-title">
              <FileText size={20} strokeWidth={1.5} className="list-title-icon" />
              <span>Recent Documents</span>
            </div>
            <button
              className="view-all-btn"
              onClick={() => navigate('/documents')}
              aria-label="View all documents"
              disabled={recentDocsLoading}
            >
              View all <ArrowRight size={14} />
            </button>
          </div>
          <div className="list-content">
            {recentDocsLoading ? (
              <>
                <SkeletonListRow />
                <SkeletonListRow />
                <SkeletonListRow />
              </>
            ) : recentDocsError ? (
              <div className="list-error">
                <p>{recentDocsError}</p>
                <button onClick={loadDashboardData}>Retry</button>
              </div>
            ) : recentDocs.length > 0 ? (
              recentDocs.map((doc, index) => (
                <div
                  key={doc.id ?? index}
                  className="list-item"
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`/documents/${doc.id}`);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open document ${doc.title || doc.filename}`}
                  style={{ position: 'relative' }}
                >
                  <div className="list-item-icon doc-icon">
                    <span>PDF</span>
                  </div>
                  <div className="list-item-info">
                    <h4>{doc.title || doc.filename}</h4>
                  </div>
                  <button
                    className="more-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveMenuId(activeMenuId === doc.id ? null : doc.id);
                    }}
                    title="Document actions"
                    aria-label="Document actions"
                  >
                    <MoreVertical size={18} />
                  </button>

                  {activeMenuId === doc.id && (
                    <div
                      className="dashboard-doc-menu"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button className="menu-action-item" onClick={() => { setActiveMenuId(null); navigate(`/documents/${doc.id}`); }}>
                        <Eye size={14} /> Open Document
                      </button>
                      <div className="menu-divider" />
                      <button
                        className="menu-action-item danger"
                        onClick={() => {
                          setActiveMenuId(null);
                          setDeleteError(null);
                          setDocToDelete(doc);
                        }}
                      >
                        <Trash2 size={14} /> Delete Document
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="empty-list-text">No documents uploaded yet.</p>
            )}
          </div>
        </div>
      </div>

      {}
      {docToDelete && (
        <div
          className="confirm-modal-overlay"
          onClick={closeDeleteModal}
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-confirm-title"
        >
          <div
            className="confirm-modal"
            onClick={(e) => e.stopPropagation()}
            role="document"
          >
            <h3 id="delete-confirm-title">Delete document?</h3>
            <p>
              This will permanently delete{' '}
              <strong>"{docToDelete.title || docToDelete.filename}"</strong>.
            </p>
            <p className="confirm-warning">This action cannot be undone.</p>
            {deleteError && (
              <div className="confirm-modal-error" role="alert">
                {deleteError}
              </div>
            )}
            <div className="confirm-modal-actions">
              <button
                className="btn-ghost"
                onClick={closeDeleteModal}
                disabled={isDeleting}
                autoFocus
              >
                Cancel
              </button>
              <button
                className="btn-danger"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}