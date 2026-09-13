import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Home, FileText, Folder, Compass } from 'lucide-react';
import './Sidebar.css';

const NAV_ITEMS = [
  { to: '/', icon: Home, label: 'Dashboard', end: true },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/workspaces', icon: Folder, label: 'Workspaces' },
  { to: '/discover', icon: Compass, label: 'Discover' },
];

export default function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="sidebar">
      {}
      <div className="sidebar-brand" onClick={() => navigate('/')}>
        <span className="brand-kno">KNO</span>
        <span className="brand-tagline">Knowledge<br />Discovery</span>
        <div className="brand-divider" />
      </div>

      {}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={`${item.to}-${item.label}`}
            to={item.to}
            end={item.end}
            className="sidebar-nav-link"
          >
            {({ isActive }) => (
              <motion.div
                className={`sidebar-nav-item${isActive && item.label === 'Dashboard' ? ' sidebar-nav-item--active' : ''}`}
                whileHover={{ x: 2 }}
              >
                <item.icon size={20} strokeWidth={1.5} className="sidebar-nav-icon" />
                <span className="sidebar-nav-label">{item.label}</span>
              </motion.div>
            )}
          </NavLink>
        ))}
      </nav>

    </aside>
  );
}
