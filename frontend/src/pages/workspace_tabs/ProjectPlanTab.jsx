import React, { useState, useEffect } from 'react';
import { Layout, Save, Wand2, Loader2, AlertCircle, Check } from 'lucide-react';
import { getProjectPlan, updateProjectPlan, autoGenerateProjectPlan } from '../../services/api';
import './ProjectPlanTab.css';

const PLAN_FIELDS = [
  { key: 'problem_statement', label: 'Problem Statement' },
  { key: 'objectives', label: 'Objectives' },
  { key: 'requirements', label: 'Requirements' },
  { key: 'architecture', label: 'Architecture' },
  { key: 'technology_stack', label: 'Technology Stack' },
  { key: 'components', label: 'Components' },
  { key: 'data_flow', label: 'Data Flow' },
  { key: 'implementation_stages', label: 'Implementation Stages' },
  { key: 'testing_strategy', label: 'Testing Strategy' },
  { key: 'evaluation_metrics', label: 'Evaluation Metrics' },
  { key: 'deployment_plan', label: 'Deployment Plan' },
];

function ProjectPlanTab({ workspaceId }) {
  const [plan, setPlan] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    setLoading(true);
    getProjectPlan(workspaceId)
      .then(data => {
        if (cancelled) return;
        setPlan(data || {});
        setError(null);
      })
      .catch(err => {
        if (cancelled) return;
        setError(err.message || 'Failed to load project plan.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [workspaceId]);

  const handleChange = (key, value) => {
    setPlan(prev => ({ ...prev, [key]: value }));
    setSaveSuccess(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      const updated = await updateProjectPlan(workspaceId, plan);
      setPlan(updated || plan);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      setError(err.message || 'Failed to save project plan.');
    } finally {
      setSaving(false);
    }
  };

  const handleAutoGenerate = async () => {
    setGenerating(true);
    setError(null);
    setSaveSuccess(false);
    try {
      const generated = await autoGenerateProjectPlan(workspaceId);
      setPlan(generated || {});
    } catch (err) {
      setError(err.message || 'Failed to auto-generate project plan.');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="pp-tab-container">
        <div className="pp-loading-state">
          <Loader2 size={32} className="spin-icon" />
          <span>Loading project plan...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="pp-tab-container">
      <div className="pp-header">
        <div className="pp-header-text">
          <Layout size={20} />
          <h2>Project Plan</h2>
        </div>
        <div className="pp-header-actions">
          <button
            className="pp-btn pp-btn-secondary"
            onClick={handleAutoGenerate}
            disabled={generating || saving}
          >
            {generating ? (
              <><Loader2 size={16} className="spin-icon" /> Generating...</>
            ) : (
              <><Wand2 size={16} /> Auto-generate with ORBOT</>
            )}
          </button>
          <button
            className="pp-btn pp-btn-primary"
            onClick={handleSave}
            disabled={saving || generating}
          >
            {saving ? (
              <><Loader2 size={16} className="spin-icon" /> Saving...</>
            ) : (
              <><Save size={16} /> Save Plan</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="pp-error-state">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {saveSuccess && (
        <div className="pp-success-state">
          <Check size={16} />
          <span>Project plan saved successfully.</span>
        </div>
      )}

      <div className="pp-fields-grid">
        {PLAN_FIELDS.map(field => (
          <div key={field.key} className="pp-field-group">
            <label className="pp-field-label">{field.label}</label>
            <textarea
              className="pp-field-textarea"
              value={plan[field.key] || ''}
              onChange={e => handleChange(field.key, e.target.value)}
              placeholder={`Enter ${field.label.toLowerCase()}...`}
              rows={4}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default ProjectPlanTab;
