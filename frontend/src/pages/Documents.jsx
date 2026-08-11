import React, { useEffect, useState } from 'react';
import { FileText, File, Trash2, Plus, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getDocuments, deleteDocument } from '../services/api';
import './Documents.css';

function Documents() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDocuments();
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

  const handleDocumentClick = (id) => {
    navigate(`/documents/${id}`);
  };

  const handleDelete = async (e, id, name) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      try {
        await deleteDocument(id);
        // Remove from UI
        setDocuments(documents.filter(doc => doc.id !== id));
      } catch (err) {
        alert(err.message || 'Failed to delete the document.');
      }
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
        <div className="documents-grid">
          {documents.map((doc) => {
            const Icon = doc.file_type === 'PDF' ? FileText : File;
            return (
              <div key={doc.id} className="document-card" onClick={() => handleDocumentClick(doc.id)}>
                <div className="document-card-header">
                  <div className="document-icon-wrapper">
                    <Icon size={24} strokeWidth={1.5} />
                  </div>
                  <button 
                    className="btn-icon delete-btn" 
                    title="Delete document"
                    onClick={(e) => handleDelete(e, doc.id, doc.filename)}
                  >
                    <Trash2 size={18} />
                  </button>
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
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default Documents;
