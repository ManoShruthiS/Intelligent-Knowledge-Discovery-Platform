import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useParams, useNavigate } from 'react-router-dom';
import { FileText, File, MoreHorizontal, Share, Loader2, AlertCircle } from 'lucide-react';
import { getDocument } from '../services/api';
import './DocumentWorkspace.css';

function DocumentWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDocument = async () => {
      try {
        setLoading(true);
        const data = await getDocument(id);
        setDocument(data);
      } catch (err) {
        setError(err.message || 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };
    fetchDocument();
  }, [id]);

  if (loading) {
    return (
      <div className="workspace-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Loader2 size={40} className="spinning" style={{ color: 'var(--c-555)' }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="workspace-container">
        <div style={{ padding: '3rem', textAlign: 'center' }}>
          <AlertCircle size={48} style={{ color: 'var(--c-333)', margin: '0 auto 1rem' }} />
          <h2>Unable to load document</h2>
          <p style={{ color: 'var(--c-555)', margin: '1rem 0' }}>{error}</p>
          <button className="btn-secondary" onClick={() => navigate('/documents')}>
            Back to Documents
          </button>
        </div>
      </div>
    );
  }

  if (!document) return null;

  const DocIcon = document.file_type === 'PDF' ? FileText : File;

  return (
    <div className="workspace-container">
      <div className="workspace-header">
        <div className="workspace-title-row">
          <div className="workspace-doc-info">
            <DocIcon size={24} className="doc-icon" />
            <h1 className="doc-title" title={document.filename}>{document.filename}</h1>
          </div>
          <div className="workspace-actions">
            <button className="btn-icon">
              <MoreHorizontal size={20} />
            </button>
            <button className="btn-share-mobile">
              <Share size={18} />
              Share
            </button>
          </div>
        </div>

        <nav className="workspace-tabs">
          <NavLink to="overview" className={({isActive}) => isActive ? "tab-item active" : "tab-item"}>
            Overview
          </NavLink>
          <NavLink to="summary" className={({isActive}) => isActive ? "tab-item active" : "tab-item"}>
            Summary
          </NavLink>
          <NavLink to="insights" className={({isActive}) => isActive ? "tab-item active" : "tab-item"}>
            Insights
          </NavLink>
          <NavLink to="ask-ai" className={({isActive}) => isActive ? "tab-item active" : "tab-item"}>
            Ask AI
          </NavLink>
          <NavLink to="sources" className={({isActive}) => isActive ? "tab-item active" : "tab-item"}>
            Sources
          </NavLink>
        </nav>
      </div>

      <div className="workspace-content">
        {/* Pass the document data to the child tabs via Outlet context */}
        <Outlet context={{ document }} />
      </div>
    </div>
  );
}

export default DocumentWorkspace;
