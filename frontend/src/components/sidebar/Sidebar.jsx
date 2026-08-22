import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { 
  Home, 
  Search,
  Library,
  FolderKanban,
  Clock, 
  Settings, 
  X,
  User
} from 'lucide-react';
import './Sidebar.css';
import Orbot from '../common/Orbot';

function Sidebar({ isOpen, toggleSidebar }) {
  const navigate = useNavigate();

  const handleNewClick = () => {
    navigate('/');
    if (isOpen) toggleSidebar();
  };

  const closeOnMobile = () => {
    if (isOpen && window.innerWidth <= 768) {
      toggleSidebar();
    }
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div className="sidebar-overlay" onClick={toggleSidebar}></div>
      )}
      
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
            <div className="brand-logo" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Orbot size={28} state="chatting" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', marginLeft: '8px' }}>
               <span className="brand-name" style={{ fontSize: '1.25rem', fontWeight: 700, lineHeight: 1 }}>KNO</span>
               <span style={{ fontSize: '0.65rem', color: 'var(--c-555)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Knowledge Discovery</span>
            </div>
          </div>
          <button className="mobile-close" onClick={toggleSidebar}>
            <X size={20} strokeWidth={1.5} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <NavLink to="/" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'} end onClick={closeOnMobile} aria-label="Home">
              <Home size={18} strokeWidth={1.5} />
              Home
            </NavLink>
            <NavLink to="/discover" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'} onClick={closeOnMobile} aria-label="Discover">
              <Search size={18} strokeWidth={1.5} />
              Discover
            </NavLink>
            <NavLink to="/documents" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'} onClick={closeOnMobile} aria-label="Library">
              <Library size={18} strokeWidth={1.5} />
              Library
            </NavLink>
            <NavLink to="/workspaces" className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'} onClick={closeOnMobile} aria-label="Workspaces">
              <FolderKanban size={18} strokeWidth={1.5} />
              Workspaces
            </NavLink>
          </div>

          <div className="nav-section">
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-profile-block">
            <div className="profile-info-left" onClick={() => navigate('/settings')}>
              <div className="profile-avatar-circle">
                <User size={20} strokeWidth={1.5} />
              </div>
              <div className="profile-text">
                <span className="profile-name">Mahi</span>
              </div>
            </div>
            <button className="profile-settings-btn" onClick={() => { navigate('/settings'); closeOnMobile(); }}>
              <Settings size={18} strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
