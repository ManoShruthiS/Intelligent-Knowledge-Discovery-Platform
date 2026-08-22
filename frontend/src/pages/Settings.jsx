import React, { useEffect, useState } from 'react';
import { Settings as SettingsIcon, CheckCircle2, AlertCircle, RefreshCw, Cpu, MessageSquare, FileText, Shield } from 'lucide-react';
import { getSettings, updateSettings, getProvidersStatus } from '../services/api';

function Settings() {
  const [settings, setSettings] = useState(null);
  const [providers, setProviders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true); setError(null); setSuccess(null);
    try {
      const [s, p] = await Promise.all([getSettings(), getProvidersStatus()]);
      setSettings(s); setProviders(p);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const savedTheme = localStorage.getItem('kno-theme');
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  const save = async (patch) => {
    setSaving(true); setError(null); setSuccess(null);
    try {
      await updateSettings(patch);
      setSuccess('Settings saved.');
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--c-555)' }}>
        <RefreshCw size={20} className="spinning" /> Loading settings…
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '800px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
        <SettingsIcon size={20} />
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Settings</h1>
      </div>
      <p style={{ color: 'var(--c-555)', marginBottom: '1.5rem' }}>
        Manage your AI providers, chat behaviour, and document preferences. API keys are
        configured on the backend and are never shown here.
      </p>

      {error && (
        <div className="wi-error" role="alert" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}
      {success && (
        <div className="wi-error" role="status" style={{
          display: 'flex', gap: '0.5rem', alignItems: 'center',
          background: '#f0f9f4', borderColor: '#bce5c6', color: '#1e6e3a',
        }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}

      {/* Provider status */}
      <section style={sectionStyle}>
        <SectionHeader icon={<Cpu size={16} />} title="AI Providers" />
        <p style={helpText}>
          KNO uses the configured backend providers in this order. The router falls back to the next
          provider when the current one fails. To change providers or models, edit <code>backend/.env</code>.
        </p>
        {providers ? (
          providers.providers.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
              {providers.providers.map((p, i) => (
                <div key={i} style={rowStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={badgeStyle}>{i === 0 ? 'PRIMARY' : 'FALLBACK'}</span>
                    <strong>{p.name}</strong>
                    <span style={{ color: 'var(--c-555)', fontSize: '0.85rem' }}>·</span>
                    <span style={{ color: 'var(--c-555)', fontSize: '0.85rem' }}>{p.model}</span>
                    {p.supports_vision && <span className="wi-tag" style={{ marginLeft: '0.5rem' }}>vision</span>}
                  </div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--c-777)' }}>configured</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--c-555)', marginTop: '0.75rem' }}>
              No providers configured. Add at least one of <code>GEMINI_API_KEY</code>,
              <code>GROQ_API_KEY</code>, or <code>OPENAI_API_KEY</code> to <code>backend/.env</code>
              and restart the backend.
            </p>
          )
        ) : null}
      </section>

      {/* Chat preferences */}
      <section style={sectionStyle}>
        <SectionHeader icon={<MessageSquare size={16} />} title="Chat Preferences" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.75rem' }}>
          <Field
            label="Default ORBOT mode"
            help="Used as the initial mode for new conversations in Home and Workspace chat."
          >
            <select
              value={settings?.chat?.default_mode || 'research'}
              onChange={(e) => save({ default_mode: e.target.value })}
              disabled={saving}
              style={inputStyle}
            >
              <option value="research">Research</option>
              <option value="project">Project</option>
            </select>
          </Field>
          <Field
            label="Conversation memory window"
            help="Maximum number of recent messages sent to ORBOT for context. Keep modest to control cost."
          >
            <input
              type="number"
              min="1"
              max="100"
              value={settings?.chat?.history_window || 16}
              onChange={(e) => save({ history_window: parseInt(e.target.value, 10) })}
              disabled={saving}
              style={inputStyle}
            />
          </Field>
        </div>
      </section>

      {/* Document preferences */}
      <section style={sectionStyle}>
        <SectionHeader icon={<FileText size={16} />} title="Document Preferences" />
        <p style={helpText}>
          Supported formats: PDF, DOCX, TXT, MD, CSV, XLSX, JSON, code files (Python, JS, Java,
          Go, Rust, …), Jupyter notebooks, and images (PNG, JPG, WEBP, GIF, BMP). Maximum file
          size is 25 MB per upload. Configuration of which extensions are accepted is server-side.
        </p>
      </section>

      {/* Security & Privacy */}
      <section style={sectionStyle}>
        <SectionHeader icon={<Shield size={16} />} title="Security & Privacy" />
        <ul style={{ color: 'var(--c-555)', fontSize: '0.9rem', lineHeight: 1.6, marginTop: '0.5rem', paddingLeft: '1.25rem' }}>
          <li>Your documents, notes, briefs, experiments, and citations live in a local SQLite database (<code>backend/knowledge.db</code>) plus a local FAISS vector index.</li>
          <li>API keys for Gemini, Groq, and OpenAI are read from <code>backend/.env</code> on the server. They are never returned through any API or rendered in this UI.</li>
          <li>Cross-Origin Resource Sharing (CORS) is restricted to <code>localhost:5173/5174/5175/3000</code> by default; override via <code>CORS_ALLOWED_ORIGINS</code> in <code>backend/.env</code>.</li>
          <li>ORBOT does not train on your data. Your documents are sent only to the configured AI provider(s) to generate answers.</li>
        </ul>
      </section>

      {/* Appearance */}
      <section style={sectionStyle}>
        <SectionHeader icon={<SettingsIcon size={16} />} title="Appearance" />
        <Field label="Theme" help="KNO is monochrome by design.">
          <select
            value={settings?.ui?.theme || 'light'}
            onChange={(e) => {
              const theme = e.target.value;
              save({ theme });
              if (theme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('kno-theme', 'dark');
              } else {
                document.documentElement.removeAttribute('data-theme');
                localStorage.setItem('kno-theme', 'light');
              }
            }}
            disabled={saving}
            style={inputStyle}
          >
            <option value="light">Light (default)</option>
            <option value="dark">Dark</option>
          </select>
        </Field>
      </section>
    </div>
  );
}

function SectionHeader({ icon, title }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
      {icon}
      <h2 style={{ margin: 0, fontSize: '1.05rem' }}>{title}</h2>
    </div>
  );
}

function Field({ label, help, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      <span style={{ fontSize: '0.85rem', color: 'var(--c-555)', fontWeight: 500 }}>{label}</span>
      {children}
      {help && <span style={{ fontSize: '0.75rem', color: 'var(--c-777)' }}>{help}</span>}
    </label>
  );
}

const sectionStyle = {
  background: 'var(--c-white, #fff)',
  border: '1px solid var(--c-eee, #eee)',
  borderRadius: 8, padding: '1rem 1.25rem', marginBottom: '1rem',
};
const helpText = { color: 'var(--c-555)', fontSize: '0.85rem', marginTop: '0.25rem', lineHeight: 1.5 };
const rowStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '0.5rem 0.75rem', background: 'var(--c-fafafa, #fafafa)',
  border: '1px solid var(--c-eee, #eee)', borderRadius: 6,
};
const badgeStyle = {
  fontSize: '0.65rem', letterSpacing: '0.05em', textTransform: 'uppercase',
  background: 'var(--c-111, #111)', color: 'white', padding: '0.15rem 0.5rem',
  borderRadius: 999, fontWeight: 600,
};
const inputStyle = {
  padding: '0.5rem 0.75rem', border: '1px solid var(--c-ddd, #ddd)',
  borderRadius: 6, fontFamily: 'inherit', fontSize: '0.9rem',
  background: 'var(--c-white, #fff)', color: 'var(--c-111, #111)',
  maxWidth: 280,
};

export default Settings;