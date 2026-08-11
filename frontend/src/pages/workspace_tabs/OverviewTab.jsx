import React from 'react';
import { useOutletContext } from 'react-router-dom';

function OverviewTab() {
  const { document } = useOutletContext();

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="tab-container">
      <section className="tab-section">
        <h2 className="tab-section-title">Document Metadata</h2>
        <div className="info-card" style={{ display: 'flex', gap: '3rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)', marginBottom: '0.25rem' }}>Type</div>
            <div style={{ fontWeight: 500 }}>{document.file_type}</div>
          </div>
          {document.page_count && (
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)', marginBottom: '0.25rem' }}>Pages</div>
              <div style={{ fontWeight: 500 }}>{document.page_count}</div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)', marginBottom: '0.25rem' }}>Size</div>
            <div style={{ fontWeight: 500 }}>{(document.file_size / 1024).toFixed(1)} KB</div>
          </div>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)', marginBottom: '0.25rem' }}>Characters</div>
            <div style={{ fontWeight: 500 }}>{document.character_count.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)', marginBottom: '0.25rem' }}>Uploaded</div>
            <div style={{ fontWeight: 500 }}>{formatDate(document.created_at)}</div>
          </div>
        </div>
      </section>

      <section className="tab-section">
        <h2 className="tab-section-title">Extracted Text</h2>
        <div className="info-card" style={{ 
            maxHeight: '600px', 
            overflowY: 'auto', 
            whiteSpace: 'pre-wrap', 
            fontFamily: 'var(--font-mono)', 
            fontSize: 'var(--text-sm)',
            lineHeight: 1.6 
          }}>
          {document.extracted_text}
        </div>
      </section>
    </div>
  );
}

export default OverviewTab;
