import React, { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { RefreshCw, AlertCircle, FileText } from 'lucide-react';
import MarkdownMessage from '../../components/common/MarkdownMessage';
import { getDocumentSummary } from '../../services/api';

function SummaryTab() {
  // DocumentWorkspace passes { document } via Outlet context.
  const { document } = useOutletContext() || {};
  const documentId = document && document.id ? document.id : null;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = async () => {
    if (!documentId) {
      setError('Document context unavailable.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getDocumentSummary(documentId);
      setData(result);
    } catch (e) {
      setError(e.message || 'Unable to generate summary.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  if (loading) {
    return (
      <div className="tab-container" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '40vh' }}>
        <RefreshCw size={28} className="spinning" style={{ color: 'var(--c-555)' }} />
        <p style={{ marginTop: '1rem', color: 'var(--c-555)' }}>
          Reading and summarizing the document…
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
            <div style={{ fontWeight: 500 }}>Unable to generate summary</div>
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

  const { summary, document: docMeta, confidence, sources } = data;
  const confidenceLabel =
    confidence === 'grounded'
      ? 'Grounded in the document'
      : confidence === 'partial'
      ? 'Partially grounded'
      : 'Unverified — limited context';

  return (
    <div className="tab-container">
      <section className="tab-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <h2 className="tab-section-title" style={{ margin: 0 }}>Summary</h2>
          <button
            type="button"
            className="btn-secondary"
            onClick={load}
            title="Regenerate summary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <RefreshCw size={14} /> Regenerate
          </button>
        </div>
        <div className="info-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--c-555)', fontSize: '0.85rem', flexWrap: 'wrap' }}>
            <FileText size={14} />
            <span>{docMeta && docMeta.filename}</span>
            <span style={{ color: 'var(--c-ccc)' }}>·</span>
            <span style={{ color: 'var(--c-555)' }}>{confidenceLabel}</span>
            {sources && (
              <>
                <span style={{ color: 'var(--c-ccc)' }}>·</span>
                <span style={{ color: 'var(--c-555)' }}>
                  {sources.length} section{sources.length !== 1 ? 's' : ''} used
                </span>
              </>
            )}
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <MarkdownMessage content={summary || 'No summary content was generated.'} />
          </div>
        </div>
      </section>
    </div>
  );
}

export default SummaryTab;
