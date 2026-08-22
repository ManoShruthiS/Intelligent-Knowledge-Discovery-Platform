import React, { useState, useEffect } from 'react';
import { FileText, Save, Wand2, Loader2 } from 'lucide-react';
import { getBrief, updateBrief, autoDraftBrief } from '../../services/api';

const BRIEF_FIELDS = [
  { key: 'topic', label: 'Research Topic', type: 'input' },
  { key: 'problem', label: 'Problem Statement', type: 'textarea' },
  { key: 'research_question', label: 'Research Question', type: 'textarea' },
  { key: 'objectives', label: 'Objectives', type: 'textarea' },
  { key: 'papers_reviewed', label: 'Papers Reviewed', type: 'textarea' },
  { key: 'key_findings', label: 'Key Findings', type: 'textarea' },
  { key: 'common_limitations', label: 'Common Limitations', type: 'textarea' },
  { key: 'potential_gap', label: 'Potential Gap', type: 'textarea' },
  { key: 'proposed_direction', label: 'Proposed Direction', type: 'textarea' },
  { key: 'open_questions', label: 'Open Questions', type: 'textarea' },
  { key: 'current_stage', label: 'Current Stage', type: 'input' },
];

function BriefTab({ workspaceId }) {
  const [fields, setFields] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoDrafting, setAutoDrafting] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchBrief();
  }, [workspaceId]);

  const fetchBrief = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBrief(workspaceId);
      setFields(data || {});
    } catch (err) {
      setError(err.message || 'Failed to load brief.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, value) => {
    setFields(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateBrief(workspaceId, fields);
      setSaved(true);
    } catch (err) {
      setError(err.message || 'Failed to save brief.');
    } finally {
      setSaving(false);
    }
  };

  const handleAutoDraft = async () => {
    setAutoDrafting(true);
    setError(null);
    setSaved(false);
    try {
      const data = await autoDraftBrief(workspaceId);
      if (data) setFields(data);
      setSaved(true);
    } catch (err) {
      setError(err.message || 'Auto-draft failed.');
    } finally {
      setAutoDrafting(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.centered}>
        <Loader2 size={28} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: '0.9rem', color: 'var(--c-666)' }}>Loading brief...</span>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Research Brief</h2>
          <p style={styles.subtitle}>Define the scope and direction of your research project.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
          <button
            style={{ ...styles.btnSecondary, ...(autoDrafting ? styles.btnDisabled : {}) }}
            onClick={handleAutoDraft}
            disabled={autoDrafting || saving}
          >
            {autoDrafting ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Wand2 size={14} />}
            {autoDrafting ? 'Drafting...' : 'Auto-draft with ORBOT'}
          </button>
          <button
            style={{ ...styles.btnPrimary, ...(saving ? styles.btnDisabled : {}) }}
            onClick={handleSave}
            disabled={saving || autoDrafting}
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save Brief'}
          </button>
        </div>
      </div>

      {error && (
        <div style={styles.errorBanner}>{error}</div>
      )}

      {saved && !error && (
        <div style={styles.successBanner}>Brief saved successfully.</div>
      )}

      {autoDrafting && (
        <div style={styles.autoDraftNotice}>
          <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
          <span>ORBOT is reading your papers and drafting the brief...</span>
        </div>
      )}

      <div style={styles.fieldsGrid}>
        {BRIEF_FIELDS.map(field => (
          <div
            key={field.key}
            style={field.type === 'textarea' ? styles.fieldGroupWide : styles.fieldGroup}
          >
            <label style={styles.label}>{field.label}</label>
            {field.type === 'textarea' ? (
              <textarea
                style={styles.textarea}
                value={fields[field.key] || ''}
                onChange={(e) => handleChange(field.key, e.target.value)}
                rows={4}
              />
            ) : (
              <input
                style={styles.input}
                value={fields[field.key] || ''}
                onChange={(e) => handleChange(field.key, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    padding: '1.5rem 2rem 3rem 2rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: '0.75rem',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: 'var(--c-111)',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '0.9rem',
    color: 'var(--c-666)',
  },
  btnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.5rem 1rem',
    fontSize: '0.85rem',
    fontWeight: 500,
    border: '1px solid var(--c-111)',
    borderRadius: '6px',
    backgroundColor: 'var(--c-111)',
    color: '#fff',
    cursor: 'pointer',
  },
  btnSecondary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.5rem 1rem',
    fontSize: '0.85rem',
    fontWeight: 500,
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-333)',
    cursor: 'pointer',
  },
  btnDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  errorBanner: {
    padding: '0.75rem 1rem',
    fontSize: '0.85rem',
    color: 'var(--c-333)',
    backgroundColor: 'var(--c-f5f5f5)',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
  },
  successBanner: {
    padding: '0.75rem 1rem',
    fontSize: '0.85rem',
    color: 'var(--c-111)',
    backgroundColor: 'var(--c-fafafa)',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    fontWeight: 500,
  },
  autoDraftNotice: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.75rem 1rem',
    fontSize: '0.85rem',
    color: 'var(--c-444)',
    backgroundColor: 'var(--c-fafafa)',
    border: '1px solid var(--c-eee)',
    borderRadius: '6px',
  },
  centered: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4rem 2rem',
    gap: '0.75rem',
    color: 'var(--c-666)',
  },
  fieldsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
  },
  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
  },
  fieldGroupWide: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
    gridColumn: '1 / -1',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: 600,
    color: 'var(--c-444)',
    letterSpacing: '0.02em',
  },
  input: {
    width: '100%',
    padding: '0.6rem 0.8rem',
    fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-111)',
    outline: 'none',
    boxSizing: 'border-box',
  },
  textarea: {
    width: '100%',
    padding: '0.6rem 0.8rem',
    fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)',
    borderRadius: '6px',
    backgroundColor: '#fff',
    color: 'var(--c-111)',
    outline: 'none',
    resize: 'vertical',
    fontFamily: 'inherit',
    lineHeight: 1.5,
    boxSizing: 'border-box',
  },
};

export default BriefTab;
