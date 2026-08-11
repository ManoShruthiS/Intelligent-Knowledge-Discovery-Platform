import React from 'react';

function Settings() {
  return (
    <div className="documents-container" style={{ maxWidth: '600px' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Manage your preferences.</p>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', marginTop: '1rem' }}>
        <section>
          <h3 style={{ borderBottom: 'var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Appearance</h3>
          <p style={{ color: 'var(--c-555)' }}>Appearance settings will be available here.</p>
        </section>
        <section>
          <h3 style={{ borderBottom: 'var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>AI Preferences</h3>
          <p style={{ color: 'var(--c-555)' }}>AI configuration settings will be available here.</p>
        </section>
        <section>
          <h3 style={{ borderBottom: 'var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Document Settings</h3>
          <p style={{ color: 'var(--c-555)' }}>Parsing and extraction settings will be available here.</p>
        </section>
        <section>
          <h3 style={{ borderBottom: 'var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Account</h3>
          <p style={{ color: 'var(--c-555)' }}>Account management settings will be available here.</p>
        </section>
      </div>
    </div>
  );
}

export default Settings;
