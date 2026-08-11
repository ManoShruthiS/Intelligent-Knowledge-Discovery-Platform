import React from 'react';

function Recent() {
  return (
    <div className="documents-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Recent</h1>
          <p className="page-subtitle">Recently accessed documents and conversations.</p>
        </div>
      </div>
      <div style={{ marginTop: '2rem', color: 'var(--c-555)' }}>
        No recent activity to display.
      </div>
    </div>
  );
}

export default Recent;
