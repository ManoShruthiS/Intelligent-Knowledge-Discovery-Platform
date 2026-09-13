import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileText, ArrowRight, Home, Compass, Briefcase, BookOpen } from 'lucide-react';
import { getDocuments } from '../../services/api';
import './CommandPalette.css';

const NAV_ITEMS = [
  { label: 'Home', path: '/', icon: Home },
  { label: 'Discover', path: '/discover', icon: Compass },
  { label: 'Documents', path: '/documents', icon: FileText },
  { label: 'Workspaces', path: '/workspaces', icon: Briefcase },
];

function CommandPalette({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [recentDocs, setRecentDocs] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
      getDocuments()
        .then(docs => {
          const sorted = [...docs].sort((a, b) => {
            const da = a.created_at || a.uploaded_at || '';
            const db = b.created_at || b.uploaded_at || '';
            return db.localeCompare(da);
          });
          setRecentDocs(sorted.slice(0, 5));
        })
        .catch(() => setRecentDocs([]));
    }
  }, [isOpen]);

  const filteredNav = NAV_ITEMS.filter(item =>
    item.label.toLowerCase().includes(query.toLowerCase())
  );

  const filteredDocs = recentDocs.filter(doc =>
    (doc.filename || doc.name || '').toLowerCase().includes(query.toLowerCase())
  );

  const allItems = [
    ...filteredNav.map(item => ({ type: 'nav', ...item })),
    ...filteredDocs.map(doc => ({ type: 'doc', id: doc.id, label: doc.filename || doc.name || 'Untitled' })),
  ];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (listRef.current) {
      const selected = listRef.current.querySelector('.cp-selected');
      if (selected) selected.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  const handleSelect = useCallback((item) => {
    if (item.type === 'nav') {
      navigate(item.path);
    } else if (item.type === 'doc') {
      navigate(`/documents/${item.id}`);
    }
    onClose();
  }, [navigate, onClose]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, allItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (allItems[selectedIndex]) handleSelect(allItems[selectedIndex]);
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [allItems, selectedIndex, handleSelect, onClose]);

  if (!isOpen) return null;

  return (
    <div className="cp-overlay" onClick={onClose}>
      <div className="cp-modal" onClick={e => e.stopPropagation()}>
        <div className="cp-search-row">
          <Search size={18} className="cp-search-icon" />
          <input
            ref={inputRef}
            type="text"
            className="cp-search-input"
            placeholder="Type a command or search..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <kbd className="cp-kbd">Esc</kbd>
        </div>
        <div className="cp-divider" />
        <div className="cp-results" ref={listRef}>
          {filteredNav.length > 0 && (
            <div className="cp-section-label">Navigation</div>
          )}
          {filteredNav.map((item, i) => {
            const globalIdx = allItems.indexOf(allItems.find(x => x.type === 'nav' && x.path === item.path));
            const Icon = item.icon;
            return (
              <div
                key={item.path}
                className={`cp-item ${globalIdx === selectedIndex ? 'cp-selected' : ''}`}
                onClick={() => handleSelect({ type: 'nav', ...item })}
                onMouseEnter={() => setSelectedIndex(globalIdx)}
              >
                <Icon size={16} className="cp-item-icon" />
                <span className="cp-item-label">{item.label}</span>
                <ArrowRight size={14} className="cp-item-arrow" />
              </div>
            );
          })}
          {filteredDocs.length > 0 && (
            <div className="cp-section-label">Recent Documents</div>
          )}
          {filteredDocs.map((doc) => {
            const globalIdx = allItems.indexOf(allItems.find(x => x.type === 'doc' && x.id === doc.id));
            return (
              <div
                key={doc.id}
                className={`cp-item ${globalIdx === selectedIndex ? 'cp-selected' : ''}`}
                onClick={() => handleSelect({ type: 'doc', id: doc.id })}
                onMouseEnter={() => setSelectedIndex(globalIdx)}
              >
                <FileText size={16} className="cp-item-icon" />
                <span className="cp-item-label">{doc.filename || doc.name || 'Untitled'}</span>
                <ArrowRight size={14} className="cp-item-arrow" />
              </div>
            );
          })}
          {allItems.length === 0 && (
            <div className="cp-empty">No results found</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
