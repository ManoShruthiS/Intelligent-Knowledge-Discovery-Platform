import React, { useState } from 'react';
import { Search, Compass, UploadCloud, FolderPlus, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Orbot from '../components/common/Orbot';
import UploadModal from '../components/common/UploadModal';
import './Home.css';

function Home() {
  const navigate = useNavigate();
  const [isUploadModalOpen, setUploadModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/discover?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <div className="home-container">
      <div className="home-hero">
        <div className="hero-orbot-wrapper">
          <Orbot size={180} state="floating" />
        </div>
        
        <div className="hero-content">
          <h1 className="hero-title">What are you researching?</h1>
          <p className="hero-subtitle">
            Discover research, understand papers, and connect ideas with your AI research companion.
          </p>

          <form className="hero-search-box" onSubmit={handleSearch}>
            <Search size={20} className="search-icon" strokeWidth={2} />
            <input 
              type="text" 
              placeholder="Search a topic, research question, paper, or concept..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" className="search-action-btn">
              <Search size={18} strokeWidth={2} color="#fff" />
            </button>
          </form>

          <div className="hero-actions">
            <button className="hero-action-card" onClick={() => navigate('/discover')}>
              <div className="action-icon">
                <Compass size={24} strokeWidth={1.5} />
              </div>
              <div className="action-text">
                <h3>Discover Research</h3>
                <p>Find papers, repositories, datasets, and learning resources.</p>
              </div>
            </button>

            <button className="hero-action-card" onClick={() => setUploadModalOpen(true)}>
              <div className="action-icon">
                <UploadCloud size={24} strokeWidth={1.5} />
              </div>
              <div className="action-text">
                <h3>Upload Papers</h3>
                <p>Analyze your own research documents.</p>
              </div>
            </button>

            <button className="hero-action-card" onClick={() => navigate('/workspaces')}>
              <div className="action-icon">
                <FolderPlus size={24} strokeWidth={1.5} />
              </div>
              <div className="action-text">
                <h3>Create Workspace</h3>
                <p>Organize papers around a research topic.</p>
              </div>
            </button>
          </div>
        </div>
      </div>

      <div className="home-recent">
        <div className="recent-header">
          <h2>Recent Workspaces</h2>
        </div>
        
        <div className="recent-list">
          <div className="recent-item" onClick={() => navigate('/workspaces/fake-news-detection')}>
            <div className="recent-item-icon">
              <FileText size={20} strokeWidth={1.5} />
            </div>
            <div className="recent-item-info">
              <h4>Fake News Detection</h4>
              <p>7 papers · Updated today</p>
            </div>
          </div>
          
          <div className="recent-item" onClick={() => navigate('/workspaces/nlp-research')}>
            <div className="recent-item-icon">
              <FileText size={20} strokeWidth={1.5} />
            </div>
            <div className="recent-item-info">
              <h4>NLP Research</h4>
              <p>4 papers · Updated yesterday</p>
            </div>
          </div>

          <div className="recent-item" onClick={() => navigate('/workspaces/medical-imaging')}>
            <div className="recent-item-icon">
              <FileText size={20} strokeWidth={1.5} />
            </div>
            <div className="recent-item-info">
              <h4>Medical Imaging</h4>
              <p>6 papers · Updated 3 days ago</p>
            </div>
          </div>
        </div>
      </div>

      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setUploadModalOpen(false)} 
      />
    </div>
  );
}

export default Home;
