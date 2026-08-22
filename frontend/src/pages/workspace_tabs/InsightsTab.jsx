import React, { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Target,
  RefreshCw,
  AlertCircle,
  FlaskConical,
  Database,
  Cpu,
  ListChecks,
  BarChart3,
  ShieldAlert,
  Eye,
  ArrowRight,
  FileText,
} from 'lucide-react';
import MarkdownMessage from '../../components/common/MarkdownMessage';
import { getDocumentInsights } from '../../services/api';

function InsightsTab() {
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
      const result = await getDocumentInsights(documentId);
      setData(result);
    } catch (e) {
      setError(e.message || 'Unable to extract insights.');
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
          Extracting insights from the document…
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
            <div style={{ fontWeight: 500 }}>Unable to extract insights</div>
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

  const { insights, document: docMeta, confidence } = data;
  const confidenceLabel =
    confidence === 'grounded'
      ? 'Grounded in the document'
      : confidence === 'partial'
      ? 'Partially grounded'
      : 'Unverified — limited context';

  const emptyMsg = 'Not reported in the supplied document.';

  return (
    <div className="tab-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h2 className="tab-section-title" style={{ margin: 0 }}>Insights</h2>
          <div style={{ marginTop: '0.4rem', color: 'var(--c-555)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <FileText size={14} />
            <span>{docMeta && docMeta.filename}</span>
            <span style={{ color: 'var(--c-ccc)' }}>·</span>
            <span>{confidenceLabel}</span>
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={load}
          title="Regenerate insights"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <RefreshCw size={14} /> Regenerate
        </button>
      </div>

      {/* Key Concepts */}
      <section className="tab-section">
        <h3 className="tab-section-title">
          <Target size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
          Key concepts
        </h3>
        {insights.key_concepts && insights.key_concepts.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {insights.key_concepts.map((c, i) => (
              <div key={i} className="info-card" style={{ padding: '0.75rem 1rem' }}>
                <div style={{ fontWeight: 500 }}>{c.concept}</div>
                {c.why_it_matters && (
                  <div style={{ color: 'var(--c-555)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                    {c.why_it_matters}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <Empty msg={emptyMsg} />
        )}
      </section>

      {/* Methodology */}
      <section className="tab-section">
        <h3 className="tab-section-title">
          <FlaskConical size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
          Methodology
        </h3>
        <div className="info-card" style={{ padding: '1rem' }}>
          <Subhead icon={<Cpu size={14} />} label="Approach" />
          <p style={{ margin: '0.25rem 0 1rem 0' }}>
            {insights.methodology?.approach || emptyMsg}
          </p>

          <Subhead icon={<Database size={14} />} label="Datasets" />
          {insights.methodology?.datasets && insights.methodology.datasets.length > 0 ? (
            <ul style={{ margin: '0.25rem 0 1rem 0' }}>
              {insights.methodology.datasets.map((d, i) => (
                <li key={i}>
                  <strong>{d.name}</strong>{d.role ? ` — ${d.role}` : ''}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: '0.25rem 0 1rem 0', color: 'var(--c-555)' }}>{emptyMsg}</p>
          )}

          <Subhead icon={<Cpu size={14} />} label="Models or algorithms" />
          {insights.methodology?.models_or_algorithms && insights.methodology.models_or_algorithms.length > 0 ? (
            <ul style={{ margin: '0.25rem 0 1rem 0' }}>
              {insights.methodology.models_or_algorithms.map((m, i) => (
                <li key={i}>
                  <strong>{m.name}</strong>{m.purpose ? ` — ${m.purpose}` : ''}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: '0.25rem 0 1rem 0', color: 'var(--c-555)' }}>{emptyMsg}</p>
          )}

          <Subhead icon={<BarChart3 size={14} />} label="Evaluation" />
          <p style={{ margin: '0.25rem 0 0 0' }}>
            {insights.methodology?.evaluation || emptyMsg}
          </p>
        </div>
      </section>

      {/* Key Findings */}
      <section className="tab-section">
        <h3 className="tab-section-title">
          <ListChecks size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
          Key findings
        </h3>
        {insights.key_findings && insights.key_findings.length > 0 ? (
          <ul className="info-card" style={{ padding: '1rem 1rem 1rem 2rem' }}>
            {insights.key_findings.map((f, i) => (
              <li key={i} style={{ marginBottom: '0.35rem' }}>{f}</li>
            ))}
          </ul>
        ) : (
          <Empty msg={emptyMsg} />
        )}
      </section>

      {/* Metrics */}
      {insights.metrics && insights.metrics.length > 0 && (
        <section className="tab-section">
          <h3 className="tab-section-title">
            <BarChart3 size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
            Metrics reported
          </h3>
          <div className="info-card" style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--c-f5)' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', fontSize: '0.85rem' }}>Metric</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', fontSize: '0.85rem' }}>Value</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', fontSize: '0.85rem' }}>Context</th>
                </tr>
              </thead>
              <tbody>
                {insights.metrics.map((m, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--c-eee)' }}>
                    <td style={{ padding: '0.5rem 0.75rem', fontWeight: 500 }}>{m.metric}</td>
                    <td style={{ padding: '0.5rem 0.75rem' }}>{m.value}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--c-555)' }}>{m.context}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Limitations */}
      <section className="tab-section">
        <h3 className="tab-section-title">
          <ShieldAlert size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
          Limitations
        </h3>
        {insights.limitations && insights.limitations.length > 0 ? (
          <ul className="info-card" style={{ padding: '1rem 1rem 1rem 2rem' }}>
            {insights.limitations.map((l, i) => (
              <li key={i} style={{ marginBottom: '0.35rem' }}>{l}</li>
            ))}
          </ul>
        ) : (
          <Empty msg={emptyMsg} />
        )}
      </section>

      {/* Important observations */}
      {insights.important_observations && insights.important_observations.length > 0 && (
        <section className="tab-section">
          <h3 className="tab-section-title">
            <Eye size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
            Important observations
          </h3>
          <ul className="info-card" style={{ padding: '1rem 1rem 1rem 2rem' }}>
            {insights.important_observations.map((o, i) => (
              <li key={i} style={{ marginBottom: '0.35rem' }}>{o}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Future work */}
      {insights.future_work && insights.future_work.length > 0 && (
        <section className="tab-section">
          <h3 className="tab-section-title">
            <ArrowRight size={16} style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
            Future work suggested by the authors
          </h3>
          <ul className="info-card" style={{ padding: '1rem 1rem 1rem 2rem' }}>
            {insights.future_work.map((w, i) => (
              <li key={i} style={{ marginBottom: '0.35rem' }}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Footer note */}
      <p style={{ marginTop: '1.5rem', color: 'var(--c-777)', fontSize: '0.8rem', fontStyle: 'italic' }}>
        Insights are extracted from the supplied document only. ORBOT does not introduce outside knowledge.
      </p>
    </div>
  );
}

function Subhead({ icon, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--c-555)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '0.5rem' }}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function Empty({ msg }) {
  return (
    <div className="info-card" style={{ padding: '1rem', color: 'var(--c-555)', fontStyle: 'italic' }}>
      {msg}
    </div>
  );
}

export default InsightsTab;
