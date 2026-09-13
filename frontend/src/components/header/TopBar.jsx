import React, { useState, useRef, useEffect } from 'react';
import { Award, CheckCircle } from 'lucide-react';
import './TopBar.css';

export default function TopBar() {
  
  const [isOpen, setIsOpen] = useState(false);
  
  const dropdownRef = useRef(null);

  
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-actions" ref={dropdownRef}>
        {}
        <button
          className={`topbar-profile ${isOpen ? 'active' : ''}`}
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-label="User menu"
        >
          <div className="topbar-avatar">M</div>
        </button>

        {isOpen && (
          <div className="topbar-dropdown-menu">
            {}
            <div className="topbar-dropdown-header">
              <div className="topbar-dropdown-avatar">M</div>
              <div className="topbar-dropdown-user-info">
                <div className="topbar-dropdown-fullname">Mano Shruthi S</div>
                <div className="topbar-dropdown-batch">G6 GenAI</div>
              </div>
            </div>
            <div className="topbar-dropdown-divider"></div>
            {}
            <div className="topbar-dropdown-item active-user">
              <CheckCircle size={15} className="item-icon" />
              <span>Project Developer</span>
            </div>
            <div className="topbar-dropdown-item">
              <Award size={15} className="item-icon" />
              <span>Sure Trust Intern</span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
