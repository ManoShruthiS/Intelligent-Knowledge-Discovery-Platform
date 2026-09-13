import React, { useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import Sidebar from '../sidebar/Sidebar';
import TopBar from '../header/TopBar';
import UploadModal from '../common/UploadModal';


export const UploadContext = React.createContext({
  openUpload: () => {},
  closeUpload: () => {},
  uploadWorkspaceId: null,
});

function AppLayout({ children }) {
  
  const [isUploadOpen, setUploadOpen] = useState(false);
  const [uploadWorkspaceId, setUploadWorkspaceId] = useState(null);
  const location = useLocation();
  
  const isDashboard = location.pathname === '/';

  
  const openUpload = useCallback((workspaceId = null) => {
    setUploadWorkspaceId(typeof workspaceId === 'string' ? workspaceId : null);
    setUploadOpen(true);
  }, []);

  
  const closeUpload = useCallback(() => {
    setUploadOpen(false);
    setUploadWorkspaceId(null);
  }, []);

  return (
    <UploadContext.Provider value={{ openUpload, closeUpload, uploadWorkspaceId }}>
      <div className="app-container">
        {}
        <a href="#main-content" className="sr-only">Skip to main content</a>

        {}
        <Sidebar />

        {}
        <main className="main-content" id="main-content">
          {!isDashboard && <TopBar onUploadClick={openUpload} />}
          <div className={`scrollable-area ${isDashboard ? 'scrollable-area-dashboard' : ''}`}>
            {children}
          </div>
        </main>

        {}
        <UploadModal
          isOpen={isUploadOpen}
          onClose={closeUpload}
          workspaceId={uploadWorkspaceId}
        />
      </div>
    </UploadContext.Provider>
  );
}

export default AppLayout;
