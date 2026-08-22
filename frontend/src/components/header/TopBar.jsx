import React, { useState } from 'react';
import { Search, Bell, Menu, UploadCloud, FolderPlus } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import UploadModal from '../common/UploadModal';
import './TopBar.css';

function TopBar({ toggleSidebar }) {
  const location = useLocation();
  const navigate = useNavigate();
  const isDocumentPage = location.pathname.startsWith('/documents/');
  const [isUploadModalOpen, setUploadModalOpen] = useState(false);

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <button className="menu-btn" onClick={toggleSidebar} aria-label="Toggle navigation menu">
            <Menu size={20} />
          </button>
        </div>

        <div className="topbar-right">
          <button className="topbar-action-btn" onClick={() => setUploadModalOpen(true)} aria-label="Upload document">
            <UploadCloud size={18} strokeWidth={1.5} />
            Upload
          </button>
          
          <button className="topbar-action-btn" onClick={() => navigate('/workspaces')} aria-label="Go to workspaces">
            <FolderPlus size={18} strokeWidth={1.5} />
            Workspaces
          </button>

          {isDocumentPage && (
            <button className="btn-share">
              Share
            </button>
          )}
        </div>
      </header>

      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setUploadModalOpen(false)} 
      />
    </>
  );
}

export default TopBar;
