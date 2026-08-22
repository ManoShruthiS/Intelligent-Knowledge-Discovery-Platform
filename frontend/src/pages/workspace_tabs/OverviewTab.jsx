import React from 'react';
import { useOutletContext } from 'react-router-dom';
import { History } from 'lucide-react';

function OverviewTab() {
  const { document, versions } = useOutletContext();

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

      {versions && versions.length > 0 && (
        <section className="tab-section">
          <h2 className="tab-section-title"><History size={16} style={{ marginRight: '0.5rem', verticalAlign: 'middle' }} />Version History</h2>
          <div className="info-card">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
              {versions.map((v, idx) => (
                <div key={v.id} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.75rem 0',
                  borderBottom: idx < versions.length - 1 ? '1px solid var(--c-e5)' : 'none',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      backgroundColor: idx === 0 ? 'var(--c-000)' : 'var(--c-e5)',
                      color: idx === 0 ? 'var(--c-fff)' : 'var(--c-555)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      flexShrink: 0,
                    }}>
                      v{v.version_number}
                    </div>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: 'var(--text-sm)' }}>{v.title || 'Untitled'}</div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-555)' }}>
                        {formatDate(v.created_at)}
                        {idx === 0 && <span style={{ marginLeft: '0.5rem', color: 'var(--c-000)', fontWeight: 500 }}>Latest</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

export default OverviewTab;
