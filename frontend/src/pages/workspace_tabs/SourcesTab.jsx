import React, { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Link, RefreshCw, AlertCircle, FileText, Search } from 'lucide-react';
import { getDocumentSources } from '../../services/api';

function SourcesTab() {
  const { document } = useOutletContext() || {};
  const documentId = document && document.id ? document.id : null;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('');

  const load = async () => {
    if (!documentId) {
      setError('Document context unavailable.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getDocumentSources(documentId);
      setData(result);
    } catch (e) {
      setError(e.message || 'Unable to retrieve sources.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  const visibleSources = useMemo(() => {
    if (!data || !data.sources) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return data.sources;
    return data.sources.filter(s =>
      (s.text || '').toLowerCase().includes(q) ||
      (s.page_number != null && String(s.page_number).includes(q))
    );
  }, [data, filter]);

  if (loading) {
    return (
      <div className="tab-container" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '40vh' }}>
        <RefreshCw size={28} className="spinning" style={{ color: 'var(--c-555)' }} />
        <p style={{ marginTop: '1rem', color: 'var(--c-555)' }}>
          Loading source references…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-container" style={{ padding: '2rem' }}>
        <div className="error-state" role="alert" style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
          <AlertCircle size={20} />
          <div>
            <div style={{ fontWeight: 500 }}>Unable to retrieve sources</div>
            <div style={{ color: 'var(--c-555)', marginTop: '0.25rem' }}>{error}</div>
            <button type="button" className="btn-secondary" style={{ marginTop: '0.75rem' }} onClick={load}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="tab-container">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 className="tab-section-title" style={{ margin: 0 }}>Source references</h2>
          <div style={{ marginTop: '0.4rem', color: 'var(--c-555)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={14} />
            <span>{data.document && data.document.filename}</span>
            <span style={{ color: 'var(--c-ccc)' }}>·</span>
            <span>{data.total_chunks} chunk{data.total_chunks !== 1 ? 's' : ''}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '0.6rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--c-777)' }} />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter sources…"
              style={{
                padding: '0.4rem 0.75rem 0.4rem 2rem',
                border: '1px solid var(--c-ddd)',
                borderRadius: '6px',
                fontSize: '0.85rem',
                minWidth: '200px',
                background: 'var(--c-white)',
              }}
            />
          </div>
        </div>
      </div>

      <p style={{ color: 'var(--c-555)', fontSize: '0.85rem', marginBottom: '1rem' }}>
        Each entry is a chunk of the document ORBOT indexed when you uploaded it. Citations in ORBOT answers refer to these chunks.
      </p>

      {visibleSources.length === 0 && (
        <div className="info-card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--c-555)' }}>
          No sources match your filter.
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {visibleSources.map((src) => (
          <div key={src.chunk_id} className="info-card" style={{ padding: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <Link size={14} style={{ color: 'var(--c-777)' }} />
              <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>
                Chunk {src.chunk_index}
              </span>
              {src.page_number != null && (
                <>
                  <span style={{ color: 'var(--c-ccc)' }}>·</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--c-555)' }}>
                    Page {src.page_number}
                  </span>
                </>
              )}
              <span style={{ color: 'var(--c-ccc)' }}>·</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--c-777)' }}>
                {src.char_count} chars
              </span>
            </div>
            <div
              style={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)',
                fontSize: '0.85rem',
                color: 'var(--c-333)',
                background: 'var(--c-fafafa)',
                padding: '0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--c-eee)',
                maxHeight: '220px',
                overflowY: 'auto',
                lineHeight: 1.55,
              }}
            >
              {src.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SourcesTab;