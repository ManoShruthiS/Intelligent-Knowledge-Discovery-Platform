import React, { useState } from 'react';
import { Search, FileText, Code, Database, PlayCircle, Filter } from 'lucide-react';
import Orbot from '../components/common/Orbot';
import './Discover.css';

function Discover() {
  const [activeTab, setActiveTab] = useState('All');

  const mockPapers = [
    { title: 'Multilingual Fake News Detection Using Transformers', author: 'NLP Research Group', year: 2025, type: 'Paper' },
    { title: 'Cross-lingual Misinformation Tracking', author: 'J. Smith et al.', year: 2024, type: 'Paper' },
  ];

  const mockRepos = [
    { title: 'multilingual-fake-news-detection', author: 'Python · Transformers · PyTorch', type: 'Repository' },
  ];

  const mockDatasets = [
    { title: 'Global Misinformation Dataset 2024', author: '1.2M rows · Multilingual', type: 'Dataset' },
  ];

  const mockLearning = [
    { title: 'Understanding Multilingual NLP', author: 'YouTube · 12 min', type: 'Learning' },
  ];

  return (
    <div className="discover-container">
      <div className="discover-header">
        <div className="discover-title-area">
          <h1>Discover</h1>
          <p>Find the best research, repositories, and learning resources.</p>
        </div>
        <div className="discover-orbot-mini">
           <Orbot size={80} state="searching" />
        </div>
      </div>

      <div className="discover-search-container">
        <div className="discover-search-input">
          <Search size={20} color="var(--c-888)" />
          <input type="text" placeholder="multilingual fake news detection" defaultValue="multilingual fake news detection" />
          <button className="search-btn"><Search size={16} color="#fff"/></button>
        </div>
      </div>

      <div className="discover-tabs">
        {['All', 'Papers', 'Repositories', 'Datasets', 'Learning', 'Topics'].map(tab => (
          <button 
            key={tab} 
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="discover-results">
        {(activeTab === 'All' || activeTab === 'Papers') && (
          <section className="results-section">
            <div className="section-header">
              <h3>Papers <span>(12)</span></h3>
              <button className="view-all">View all</button>
            </div>
            <div className="results-grid">
              {mockPapers.map((item, i) => (
                <div key={i} className="result-card">
                  <div className="card-top">
                    <h4>{item.title}</h4>
                    <span className="meta">{item.year} · NLP</span>
                  </div>
                  <div className="card-bottom">
                    <button className="btn-secondary">View</button>
                    <button className="btn-icon"><Filter size={16}/></button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {(activeTab === 'All' || activeTab === 'Repositories') && (
          <section className="results-section">
            <div className="section-header">
              <h3>Repositories <span>(8)</span></h3>
              <button className="view-all">View all</button>
            </div>
            <div className="results-grid">
              {mockRepos.map((item, i) => (
                <div key={i} className="result-card">
                  <div className="card-top">
                    <h4>{item.title}</h4>
                    <span className="meta">{item.author}</span>
                  </div>
                  <div className="card-bottom">
                    <Code size={20} color="var(--c-555)" />
                    <button className="btn-secondary">View</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
        
        {(activeTab === 'All' || activeTab === 'Learning') && (
          <section className="results-section">
            <div className="section-header">
              <h3>Learning <span>(5)</span></h3>
              <button className="view-all">View all</button>
            </div>
            <div className="results-grid">
              {mockLearning.map((item, i) => (
                <div key={i} className="result-card">
                  <div className="card-top">
                    <h4>{item.title}</h4>
                    <span className="meta">{item.author}</span>
                  </div>
                  <div className="card-bottom">
                    <PlayCircle size={20} color="var(--c-555)" />
                    <button className="btn-secondary">View</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {(activeTab === 'All' || activeTab === 'Topics') && (
          <section className="results-section">
            <div className="section-header">
              <h3>Topics</h3>
            </div>
            <div className="topics-flex">
              {['Transformers', 'NLP', 'Misinformation', 'Text Classification', 'Low-resource Languages'].map(topic => (
                <span key={topic} className="topic-tag">{topic}</span>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export default Discover;
