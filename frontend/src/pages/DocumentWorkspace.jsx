import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useParams, useNavigate } from 'react-router-dom';
import { FileText, File, MoreHorizontal, Share, Loader2, AlertCircle, Download, History, Save } from 'lucide-react';
import { getDocument, getDocumentVersions, createDocumentVersion } from '../services/api';
import './DocumentWorkspace.css';

function DocumentWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [versions, setVersions] = useState([]);

  useEffect(() => {
    const fetchDocument = async () => {
      try {
        setLoading(true);
        const data = await getDocument(id);
        setDocument(data);
        fetchVersions();
      } catch (err) {
        setError(err.message || 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };
    fetchDocument();
  }, [id]);

  const fetchVersions = async () => {
    try {
      const res = await getDocumentVersions(id);
      setVersions(res.versions || []);
    } catch {}
  };

  const handleExport = () => {
    if (!document) return;
    let md = `# ${document.title || document.filename}\n\n`;
    md += `**Type:** ${document.file_type}\n`;
    md += `**Size:** ${(document.file_size / 1024).toFixed(1)} KB\n`;
    if (document.page_count) md += `**Pages:** ${document.page_count}\n`;
    md += `**Characters:** ${document.character_count?.toLocaleString() || 'N/A'}\n`;
    md += `**Created:** ${new Date(document.created_at).toLocaleString()}\n`;
    md += `\n---\n\n`;
    md += `## Extracted Text\n\n`;
    md += document.extracted_text || '_No extracted text available._\n';

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(document.title || document.filename).replace(/[^a-z0-9]/gi, '_').toLowerCase()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCreateVersion = async () => {
    try {
      await createDocumentVersion(id);
      fetchVersions();
    } catch (err) {
      alert('Failed to create version snapshot.');
    }
  };

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
            <button className="btn-icon" onClick={handleExport} title="Export as Markdown">
              <Download size={20} />
            </button>
            <button className="btn-icon" onClick={handleCreateVersion} title="Save version snapshot">
              <Save size={20} />
            </button>
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
        <Outlet context={{ document, versions }} />
      </div>
    </div>
  );
}

export default DocumentWorkspace;
