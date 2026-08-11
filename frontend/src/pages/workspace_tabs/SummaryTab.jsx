import React from 'react';
import { Lightbulb } from 'lucide-react';

function SummaryTab() {
  return (
    <div className="tab-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '40vh' }}>
      <div style={{ textAlign: 'center', color: 'var(--c-555)' }}>
        <Lightbulb size={48} style={{ margin: '0 auto 1rem', color: 'var(--c-888)' }} />
        <h2>AI Summary Coming Next</h2>
        <p>This feature will automatically generate concise summaries of your document using AI.</p>
      </div>
    </div>
  );
}

export default SummaryTab;
