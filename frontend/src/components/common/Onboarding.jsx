import React, { useState, useEffect } from 'react';
import { Search, Bot, FileText, FolderOpen } from 'lucide-react';
import './Onboarding.css';

const features = [
  {
    icon: Search,
    title: 'Research Discovery',
    description: 'Search across academic papers, datasets, and repositories to find relevant research.',
  },
  {
    icon: Bot,
    title: 'ORBOT Chat',
    description: 'Ask questions and get AI-powered answers grounded in your documents.',
  },
  {
    icon: FileText,
    title: 'Document Analysis',
    description: 'Upload and analyze documents with automatic text extraction and insights.',
  },
  {
    icon: FolderOpen,
    title: 'Workspace Management',
    description: 'Organize documents into workspaces and collaborate on research projects.',
  },
];

const Onboarding = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const hasOnboarded = localStorage.getItem('kno.onboarded');
    if (!hasOnboarded) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem('kno.onboarded', 'true');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="onboarding-overlay" onClick={dismiss}>
      <div className="onboarding-card" onClick={(e) => e.stopPropagation()}>
        <h1 className="onboarding-title">Welcome to KNO</h1>
        <p className="onboarding-subtitle">Intelligent Knowledge Discovery Platform</p>

        <div className="onboarding-features">
          {features.map(({ icon: Icon, title, description }) => (
            <div key={title} className="onboarding-feature-card">
              <div className="onboarding-feature-icon">
                <Icon size={22} strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="onboarding-feature-title">{title}</h3>
                <p className="onboarding-feature-desc">{description}</p>
              </div>
            </div>
          ))}
        </div>

        <button className="onboarding-btn" onClick={dismiss}>
          Get Started
        </button>
        <button className="onboarding-skip" onClick={dismiss}>
          Skip
        </button>
      </div>
    </div>
  );
};

export default Onboarding;
