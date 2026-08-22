import React, { useState, useEffect, useCallback } from 'react';
import { FlaskConical, Plus, Trash2, Save, X, Edit, BarChart3, Loader2, AlertCircle } from 'lucide-react';
import {
  listExperiments,
  createExperiment,
  updateExperiment,
  deleteExperiment,
  getExperimentAnalytics,
} from '../../services/api';
import './ExperimentsTab.css';

const EMPTY_FORM = {
  name: '',
  model: '',
  dataset: '',
  configuration: '',
  metric: '',
  result: '',
  experiment_date: '',
  notes: '',
};

function ExperimentsTab({ workspaceId }) {
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  const fetchExperiments = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const data = await listExperiments(workspaceId);
      setExperiments(data || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load experiments.');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const fetchAnalytics = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const data = await getExperimentAnalytics(workspaceId);
      setAnalytics(data);
    } catch {
      setAnalytics(null);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchExperiments();
    fetchAnalytics();
  }, [fetchExperiments, fetchAnalytics]);

  const handleChange = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const openNewForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowNew(true);
  };

  const openEditForm = (exp) => {
    setForm({
      name: exp.name || '',
      model: exp.model || '',
      dataset: exp.dataset || '',
      configuration: exp.configuration || '',
      metric: exp.metric || '',
      result: exp.result || '',
      experiment_date: exp.experiment_date || '',
      notes: exp.notes || '',
    });
    setEditingId(exp.id);
    setShowNew(true);
  };

  const closeForm = () => {
    setShowNew(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      if (editingId) {
        await updateExperiment(editingId, form);
      } else {
        await createExperiment(workspaceId, form);
      }
      closeForm();
      await fetchExperiments();
      await fetchAnalytics();
    } catch (err) {
      setError(err.message || 'Failed to save experiment.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    setSubmitting(true);
    setError(null);
    try {
      await deleteExperiment(id);
      setDeleteConfirmId(null);
      await fetchExperiments();
      await fetchAnalytics();
    } catch (err) {
      setError(err.message || 'Failed to delete experiment.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="exp-tab-container">
        <div className="exp-loading-state">
          <Loader2 size={32} className="spin-icon" />
          <span>Loading experiments...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="exp-tab-container">
      <div className="exp-header">
        <div className="exp-header-text">
          <FlaskConical size={20} />
          <h2>Experiments</h2>
        </div>
        {!showNew && (
          <button className="exp-btn exp-btn-primary" onClick={openNewForm}>
            <Plus size={16} /> New Experiment
          </button>
        )}
      </div>

      {error && (
        <div className="exp-error-state">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Inline form */}
      {showNew && (
        <div className="exp-form-card">
          <div className="exp-form-header">
            <h3>{editingId ? 'Edit Experiment' : 'New Experiment'}</h3>
            <button className="exp-btn exp-btn-ghost" onClick={closeForm} disabled={submitting}>
              <X size={16} />
            </button>
          </div>
          <div className="exp-form-grid">
            {[
              { key: 'name', label: 'Name', type: 'text', required: true },
              { key: 'model', label: 'Model', type: 'text' },
              { key: 'dataset', label: 'Dataset', type: 'text' },
              { key: 'configuration', label: 'Configuration', type: 'text' },
              { key: 'metric', label: 'Metric', type: 'text' },
              { key: 'result', label: 'Result', type: 'text' },
              { key: 'experiment_date', label: 'Date', type: 'date' },
            ].map(field => (
              <div key={field.key} className="exp-form-field">
                <label>{field.label}{field.required && ' *'}</label>
                <input
                  type={field.type}
                  value={form[field.key] || ''}
                  onChange={e => handleChange(field.key, e.target.value)}
                  required={field.required}
                />
              </div>
            ))}
            <div className="exp-form-field exp-form-field-wide">
              <label>Notes</label>
              <textarea
                value={form.notes || ''}
                onChange={e => handleChange('notes', e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <div className="exp-form-actions">
            <button className="exp-btn exp-btn-secondary" onClick={closeForm} disabled={submitting}>
              Cancel
            </button>
            <button className="exp-btn exp-btn-primary" onClick={handleSubmit} disabled={submitting || !form.name.trim()}>
              {submitting ? (
                <><Loader2 size={14} className="spin-icon" /> Saving...</>
              ) : (
                <><Save size={14} /> {editingId ? 'Update' : 'Create'}</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Experiments list */}
      {experiments.length === 0 && !showNew ? (
        <div className="exp-empty-state">
          <FlaskConical size={40} strokeWidth={1.2} />
          <p>No experiments yet. Create your first experiment to start tracking.</p>
        </div>
      ) : (
        <div className="exp-table-wrapper">
          <table className="exp-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Model</th>
                <th>Dataset</th>
                <th>Metric</th>
                <th>Result</th>
                <th>Date</th>
                <th className="exp-actions-col"></th>
              </tr>
            </thead>
            <tbody>
              {experiments.map(exp => (
                <tr key={exp.id}>
                  <td className="exp-td-name">{exp.name}</td>
                  <td>{exp.model || '—'}</td>
                  <td>{exp.dataset || '—'}</td>
                  <td>{exp.metric || '—'}</td>
                  <td className="exp-td-result">{exp.result || '—'}</td>
                  <td className="exp-td-date">{exp.experiment_date || '—'}</td>
                  <td className="exp-td-actions">
                    <button
                      className="exp-btn-icon"
                      title="Edit"
                      onClick={() => openEditForm(exp)}
                      disabled={submitting}
                    >
                      <Edit size={14} />
                    </button>
                    {deleteConfirmId === exp.id ? (
                      <span className="exp-delete-confirm">
                        <button
                          className="exp-btn-icon exp-btn-danger"
                          title="Confirm delete"
                          onClick={() => handleDelete(exp.id)}
                          disabled={submitting}
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          className="exp-btn-icon"
                          title="Cancel"
                          onClick={() => setDeleteConfirmId(null)}
                          disabled={submitting}
                        >
                          <X size={14} />
                        </button>
                      </span>
                    ) : (
                      <button
                        className="exp-btn-icon"
                        title="Delete"
                        onClick={() => setDeleteConfirmId(exp.id)}
                        disabled={submitting}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Analytics */}
      {analytics && (
        <div className="exp-analytics-section">
          <div className="exp-analytics-header">
            <BarChart3 size={16} />
            <h3>Analytics</h3>
          </div>
          <div className="exp-analytics-grid">
            {analytics.total_experiments !== undefined && (
              <div className="exp-stat-card">
                <span className="exp-stat-value">{analytics.total_experiments}</span>
                <span className="exp-stat-label">Total Experiments</span>
              </div>
            )}
            {analytics.unique_models !== undefined && (
              <div className="exp-stat-card">
                <span className="exp-stat-value">{analytics.unique_models}</span>
                <span className="exp-stat-label">Unique Models</span>
              </div>
            )}
            {analytics.unique_datasets !== undefined && (
              <div className="exp-stat-card">
                <span className="exp-stat-value">{analytics.unique_datasets}</span>
                <span className="exp-stat-label">Datasets Used</span>
              </div>
            )}
            {analytics.latest_experiment_date && (
              <div className="exp-stat-card">
                <span className="exp-stat-value">{analytics.latest_experiment_date}</span>
                <span className="exp-stat-label">Latest Run</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ExperimentsTab;
