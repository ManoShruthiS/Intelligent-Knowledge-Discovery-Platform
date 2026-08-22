import React, { useState, useEffect } from 'react';
import { LayoutTemplate, Plus, Trash2, Loader2, ChevronRight } from 'lucide-react';
import { listWorkspaceTemplates, createWorkspaceTemplate, deleteWorkspaceTemplate, applyWorkspaceTemplate } from '../../services/api';

function TemplatesTab({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [applyingId, setApplyingId] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [form, setForm] = useState({ name: '', description: '', brief_template: '', plan_template: '' });
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const data = await listWorkspaceTemplates();
      setTemplates(data.templates || []);
    } catch (err) {
      setError(err.message || 'Failed to load templates.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      await createWorkspaceTemplate(form);
      setForm({ name: '', description: '', brief_template: '', plan_template: '' });
      setShowForm(false);
      setSuccess('Template created.');
      await fetchTemplates();
    } catch (err) {
      setError(err.message || 'Failed to create template.');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete template "${name}"?`)) return;
    try {
      await deleteWorkspaceTemplate(id);
      setTemplates(prev => prev.filter(t => t.id !== id));
    } catch (err) {
      setError(err.message || 'Failed to delete template.');
    }
  };

  const handleApply = async (templateId, templateName) => {
    if (!window.confirm(`Apply template "${templateName}" to this workspace? This will populate the Brief and Project Plan.`)) return;
    setApplyingId(templateId);
    setError(null);
    setSuccess(null);
    try {
      await applyWorkspaceTemplate(workspaceId, templateId);
      setSuccess(`Template "${templateName}" applied successfully.`);
    } catch (err) {
      setError(err.message || 'Failed to apply template.');
    } finally {
      setApplyingId(null);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Workspace Templates</h2>
          <p style={styles.subtitle}>Create reusable templates for research briefs and project plans.</p>
        </div>
        <button
          style={{ ...styles.btnPrimary, ...(creating ? styles.btnDisabled : {}) }}
          onClick={() => setShowForm(!showForm)}
        >
          <Plus size={14} />
          {showForm ? 'Cancel' : 'New Template'}
        </button>
      </div>

      {error && <div style={styles.errorBanner}>{error}</div>}
      {success && <div style={styles.successBanner}>{success}</div>}

      {showForm && (
        <div style={styles.formCard}>
          <h3 style={styles.formTitle}>Create Template</h3>
          <div style={styles.formGrid}>
            <div style={styles.fieldGroup}>
              <label style={styles.label}>Name *</label>
              <input
                style={styles.input}
                value={form.name}
                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. Machine Learning Research"
              />
            </div>
            <div style={styles.fieldGroup}>
              <label style={styles.label}>Description</label>
              <input
                style={styles.input}
                value={form.description}
                onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of this template"
              />
            </div>
            <div style={styles.fieldGroupWide}>
              <label style={styles.label}>Brief Template (JSON or plain text)</label>
              <textarea
                style={styles.textarea}
                value={form.brief_template}
                onChange={e => setForm(prev => ({ ...prev, brief_template: e.target.value }))}
                placeholder='{"topic": "...", "objectives": "..."} or plain text'
                rows={4}
              />
            </div>
            <div style={styles.fieldGroupWide}>
              <label style={styles.label}>Plan Template (JSON or plain text)</label>
              <textarea
                style={styles.textarea}
                value={form.plan_template}
                onChange={e => setForm(prev => ({ ...prev, plan_template: e.target.value }))}
                placeholder='{"problem_statement": "...", "architecture": "..."} or plain text'
                rows={4}
              />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button
              style={{ ...styles.btnPrimary, ...(creating || !form.name.trim() ? styles.btnDisabled : {}) }}
              onClick={handleCreate}
              disabled={creating || !form.name.trim()}
            >
              {creating ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Plus size={14} />}
              {creating ? 'Creating...' : 'Create Template'}
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div style={styles.centered}>
          <Loader2 size={28} style={{ animation: 'spin 1s linear infinite' }} />
        </div>
      )}

      {!loading && templates.length === 0 && (
        <div style={styles.empty}>
          <LayoutTemplate size={48} style={{ color: 'var(--c-888)', marginBottom: '1rem' }} />
          <h3>No templates yet</h3>
          <p style={{ color: 'var(--c-555)' }}>Create a template to standardize research briefs and project plans.</p>
        </div>
      )}

      {!loading && templates.length > 0 && (
        <div style={styles.list}>
          {templates.map(t => (
            <div key={t.id} style={styles.card}>
              <div style={styles.cardBody}>
                <h3 style={styles.cardTitle}>{t.name}</h3>
                {t.description && <p style={styles.cardDesc}>{t.description}</p>}
                <div style={styles.cardMeta}>
                  {t.brief_template && <span style={styles.badge}>Brief</span>}
                  {t.plan_template && <span style={styles.badge}>Plan</span>}
                </div>
              </div>
              <div style={styles.cardActions}>
                <button
                  style={{ ...styles.btnSmall, ...(applyingId === t.id ? styles.btnDisabled : {}) }}
                  onClick={() => handleApply(t.id, t.name)}
                  disabled={applyingId === t.id}
                >
                  {applyingId === t.id
                    ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                    : <ChevronRight size={12} />}
                  {applyingId === t.id ? 'Applying...' : 'Apply'}
                </button>
                <button
                  style={{ ...styles.btnIconDelete }}
                  onClick={() => handleDelete(t.id, t.name)}
                  title="Delete template"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex', flexDirection: 'column', gap: '1rem',
    padding: '1.5rem 2rem 3rem 2rem',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    flexWrap: 'wrap', gap: '0.75rem',
  },
  title: { fontSize: '1.25rem', fontWeight: 600, color: 'var(--c-111)', marginBottom: '0.25rem' },
  subtitle: { fontSize: '0.9rem', color: 'var(--c-666)' },
  btnPrimary: {
    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
    padding: '0.5rem 1rem', fontSize: '0.85rem', fontWeight: 500,
    border: '1px solid var(--c-111)', borderRadius: '6px',
    backgroundColor: 'var(--c-111)', color: '#fff', cursor: 'pointer',
  },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  errorBanner: {
    padding: '0.75rem 1rem', fontSize: '0.85rem', color: 'var(--c-333)',
    backgroundColor: 'var(--c-f5f5f5)', border: '1px solid var(--c-ddd)', borderRadius: '6px',
  },
  successBanner: {
    padding: '0.75rem 1rem', fontSize: '0.85rem', color: 'var(--c-111)',
    backgroundColor: 'var(--c-fafafa)', border: '1px solid var(--c-ddd)',
    borderRadius: '6px', fontWeight: 500,
  },
  formCard: {
    padding: '1.5rem', border: '1px solid var(--c-ddd)', borderRadius: '8px',
    backgroundColor: '#fff',
  },
  formTitle: { fontSize: '1rem', fontWeight: 600, color: 'var(--c-111)', marginBottom: '1rem' },
  formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' },
  fieldGroup: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
  fieldGroupWide: { display: 'flex', flexDirection: 'column', gap: '0.35rem', gridColumn: '1 / -1' },
  label: { fontSize: '0.8rem', fontWeight: 600, color: 'var(--c-444)', letterSpacing: '0.02em' },
  input: {
    width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)', borderRadius: '6px',
    backgroundColor: '#fff', color: 'var(--c-111)', outline: 'none', boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.9rem',
    border: '1px solid var(--c-ddd)', borderRadius: '6px',
    backgroundColor: '#fff', color: 'var(--c-111)', outline: 'none',
    resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5, boxSizing: 'border-box',
  },
  centered: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: '4rem 2rem', color: 'var(--c-666)',
  },
  empty: {
    textAlign: 'center', padding: '4rem 2rem',
    border: '1px dashed var(--c-ccc)', borderRadius: '8px',
  },
  list: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  card: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '1rem 1.25rem', border: '1px solid var(--c-ddd)',
    borderRadius: '8px', backgroundColor: '#fff',
  },
  cardBody: { flex: 1, minWidth: 0 },
  cardTitle: { fontSize: '0.95rem', fontWeight: 600, color: 'var(--c-111)', marginBottom: '0.25rem' },
  cardDesc: { fontSize: '0.85rem', color: 'var(--c-555)', marginBottom: '0.5rem' },
  cardMeta: { display: 'flex', gap: '0.5rem' },
  badge: {
    fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '4px',
    backgroundColor: 'var(--c-f5)', color: 'var(--c-555)', fontWeight: 500,
  },
  cardActions: { display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, marginLeft: '1rem' },
  btnSmall: {
    display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
    padding: '0.4rem 0.8rem', fontSize: '0.8rem', fontWeight: 500,
    border: '1px solid var(--c-ddd)', borderRadius: '6px',
    backgroundColor: '#fff', color: 'var(--c-333)', cursor: 'pointer',
  },
  btnIconDelete: {
    color: 'var(--c-888)', padding: '0.25rem', borderRadius: '4px',
    border: 'none', background: 'none', cursor: 'pointer',
  },
};

export default TemplatesTab;
