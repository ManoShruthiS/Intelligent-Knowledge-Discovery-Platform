import React from 'react';
import { Target } from 'lucide-react';

function InsightsTab() {
  return (
    <div className="tab-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '40vh' }}>
      <div style={{ textAlign: 'center', color: 'var(--c-555)' }}>
        <Target size={48} style={{ margin: '0 auto 1rem', color: 'var(--c-888)' }} />
        <h2>AI Insights Coming Next</h2>
        <p>This feature will extract key findings, concepts, and relationships from the text.</p>
      </div>
    </div>
  );
}

export default InsightsTab;
