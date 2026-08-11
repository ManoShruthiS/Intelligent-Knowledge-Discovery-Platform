import React from 'react';
import { Search, Bell, Menu } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import './TopBar.css';

function TopBar({ toggleSidebar }) {
  const location = useLocation();
  const isDocumentPage = location.pathname.startsWith('/documents/');

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="menu-btn" onClick={toggleSidebar}>
          <Menu size={20} />
        </button>
        
        {!isDocumentPage && (
          <div className="search-container">
            <Search size={16} className="search-icon" />
            <input type="text" placeholder="Search documents..." className="search-input" />
          </div>
        )}
      </div>

      <div className="topbar-right">
        {isDocumentPage && (
          <button className="btn-share">
            Share
          </button>
        )}
        <button className="icon-btn">
          <Bell size={20} />
        </button>
        <div className="profile-avatar">U</div>
      </div>
    </header>
  );
}

export default TopBar;
