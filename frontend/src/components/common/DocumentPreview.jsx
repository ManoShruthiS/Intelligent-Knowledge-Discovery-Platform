import React, { useEffect, useState } from 'react';
import { X, FileText, Calendar, Hash, FileType, Loader2, AlertCircle } from 'lucide-react';
import { getDocument } from '../../services/api';
import './DocumentPreview.css';

const DocumentPreview = ({ documentId, onClose }) => {
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!documentId) return;

    let cancelled = false;

    const fetchDocument = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getDocument(documentId);
        if (!cancelled) setDocument(data);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load document.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchDocument();
    return () => { cancelled = true; };
  }, [documentId]);

  if (!documentId) return null;

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  const formatSize = (bytes) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="doc-preview-overlay" onClick={handleBackdropClick}>
      <div className="doc-preview-card" onClick={(e) => e.stopPropagation()}>
        <button className="doc-preview-close" onClick={onClose}>
          <X size={20} strokeWidth={1.5} />
        </button>

        {loading && (
          <div className="doc-preview-state">
            <Loader2 size={32} className="spinning" strokeWidth={1.5} />
            <p>Loading document...</p>
          </div>
        )}

        {error && (
          <div className="doc-preview-state">
            <AlertCircle size={32} strokeWidth={1.5} />
            <p>{error}</p>
          </div>
        )}

        {document && (
          <>
            <div className="doc-preview-header">
              <div className="doc-preview-icon">
                <FileText size={24} strokeWidth={1.5} />
              </div>
              <h2 className="doc-preview-title">{document.filename}</h2>
            </div>

            <div className="doc-preview-meta-grid">
              <div className="doc-preview-meta-item">
                <FileType size={14} strokeWidth={1.5} />
                <span className="doc-preview-meta-label">Type</span>
                <span className="doc-preview-meta-value">{document.file_type || '—'}</span>
              </div>
              <div className="doc-preview-meta-item">
                <Hash size={14} strokeWidth={1.5} />
                <span className="doc-preview-meta-label">Size</span>
                <span className="doc-preview-meta-value">{formatSize(document.file_size)}</span>
              </div>
              {document.page_count != null && (
                <div className="doc-preview-meta-item">
                  <Hash size={14} strokeWidth={1.5} />
                  <span className="doc-preview-meta-label">Pages</span>
                  <span className="doc-preview-meta-value">{document.page_count}</span>
                </div>
              )}
              {document.character_count != null && (
                <div className="doc-preview-meta-item">
                  <Hash size={14} strokeWidth={1.5} />
                  <span className="doc-preview-meta-label">Characters</span>
                  <span className="doc-preview-meta-value">{document.character_count.toLocaleString()}</span>
                </div>
              )}
              <div className="doc-preview-meta-item">
                <Calendar size={14} strokeWidth={1.5} />
                <span className="doc-preview-meta-label">Created</span>
                <span className="doc-preview-meta-value">{formatDate(document.created_at)}</span>
              </div>
            </div>

            {document.extracted_text && (
              <div className="doc-preview-text-area">
                <h3 className="doc-preview-text-heading">Extracted Text</h3>
                <div className="doc-preview-text-content">
                  {document.extracted_text}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default DocumentPreview;
