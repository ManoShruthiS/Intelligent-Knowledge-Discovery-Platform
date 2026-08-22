import React, { useEffect, useState } from 'react';
import { Clock, FileText, ChevronRight, RefreshCw, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getDocuments } from '../services/api';

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Recent() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setError(null);
      try {
        const r = await getDocuments();
        if (!cancelled) setDocs((r.documents || []).slice(0, 10));
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="documents-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Recent</h1>
          <p className="page-subtitle">Recently created documents.</p>
        </div>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--c-555, #555)', fontSize: '0.9rem', padding: '2rem 0', justifyContent: 'center' }}>
            <RefreshCw size={18} className="spinning" /> Loading documents...
          </div>
        )}

        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--c-error, #dc3545)', fontSize: '0.9rem', padding: '1rem', borderRadius: 6, border: '1px solid var(--c-error, #dc3545)', background: '#fff5f5' }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {!loading && !error && docs.length === 0 && (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--c-555, #555)', fontSize: '0.9rem' }}>
            <FileText size={32} color="var(--c-ccc, #ccc)" style={{ marginBottom: '0.75rem' }} />
            <p>No documents yet.</p>
          </div>
        )}

        {!loading && !error && docs.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {docs.map(doc => (
              <button key={doc.id} type="button" onClick={() => navigate(`/documents/${doc.id}`)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem',
                  padding: '0.75rem 1rem', borderRadius: 6,
                  border: '1px solid var(--c-eee, #eee)',
                  background: 'var(--c-white, #fff)',
                  cursor: 'pointer', textAlign: 'left', width: '100%',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--c-f5, #f5f5f5)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'var(--c-white, #fff)'; }}>
                <FileText size={18} color="var(--c-555, #555)" style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--c-111, #111)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.title || doc.filename || 'Untitled'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--c-555, #555)', marginTop: '0.15rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    {doc.document_type && <span>{doc.document_type}</span>}
                    {doc.created_at && <span>{new Date(doc.created_at).toLocaleDateString()}</span>}
                    <span>{formatSize(doc.size)}</span>
                  </div>
                </div>
                <ChevronRight size={16} color="var(--c-ccc, #ccc)" style={{ flexShrink: 0 }} />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Recent;
