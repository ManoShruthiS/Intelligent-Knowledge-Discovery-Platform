import React from 'react';
import { Link } from 'lucide-react';

function SourcesTab() {
  return (
    <div className="tab-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '40vh' }}>
      <div style={{ textAlign: 'center', color: 'var(--c-555)' }}>
        <Link size={48} style={{ margin: '0 auto 1rem', color: 'var(--c-888)' }} />
        <h2>Source Tracking Coming Next</h2>
        <p>This feature will show exact citations and quotes for AI-generated answers.</p>
      </div>
    </div>
  );
}

export default SourcesTab;
