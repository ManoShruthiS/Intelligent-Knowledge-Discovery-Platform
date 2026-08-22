import React, { useState } from 'react';
import Sidebar from '../sidebar/Sidebar';
import TopBar from '../header/TopBar';

function AppLayout({ children }) {
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="app-container">
      <a
        href="#main-content"
        style={{
          position: 'absolute',
          left: '-9999px',
          top: 'auto',
          width: '1px',
          height: '1px',
          overflow: 'hidden',
          zIndex: 9999,
        }}
        onFocus={(e) => {
          e.target.style.position = 'fixed';
          e.target.style.left = '1rem';
          e.target.style.top = '1rem';
          e.target.style.width = 'auto';
          e.target.style.height = 'auto';
          e.target.style.padding = '0.75rem 1.5rem';
          e.target.style.backgroundColor = 'var(--c-000)';
          e.target.style.color = 'var(--c-fff)';
          e.target.style.borderRadius = '8px';
          e.target.style.fontSize = '0.9rem';
          e.target.style.fontWeight = '500';
          e.target.style.textDecoration = 'none';
          e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
        }}
        onBlur={(e) => {
          e.target.style.position = 'absolute';
          e.target.style.left = '-9999px';
          e.target.style.width = '1px';
          e.target.style.height = '1px';
          e.target.style.padding = '0';
          e.target.style.boxShadow = 'none';
        }}
      >
        Skip to main content
      </a>
      <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
      <main className="main-content" id="main-content">
        <TopBar toggleSidebar={toggleSidebar} />
        <div className="scrollable-area">
          {children}
        </div>
      </main>
    </div>
  );
}

export default AppLayout;
