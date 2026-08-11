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
      <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
      <main className="main-content">
        <TopBar toggleSidebar={toggleSidebar} />
        <div className="scrollable-area">
          {children}
        </div>
      </main>
    </div>
  );
}

export default AppLayout;
