import React, { useState, useEffect } from 'react';
import { FileText, Check, AlertCircle, FileCheck, Layers, Scale } from 'lucide-react';
import Orbot from '../../components/common/Orbot';
import { compareWorkspacePapers } from '../../services/api';
import './CompareTab.css';

const LOADING_STAGES = [
  "Reading selected papers...",
  "Comparing methodologies...",
  "Connecting the findings..."
];

function CompareTab({ workspaceId, documents }) {
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingStageIdx, setLoadingStageIdx] = useState(0);
  const [error, setError] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [viewMode, setViewMode] = useState('sections'); // 'sections' | 'table'

  // Loading stage animation timer
  useEffect(() => {
    let interval;
    if (loading) {
      setLoadingStageIdx(0);
      interval = setInterval(() => {
        setLoadingStageIdx(prev => (prev + 1) % LOADING_STAGES.length);
      }, 2500);
    }
    return () => clearInterval(interval);
  }, [loading]);

  const toggleDocument = (docId) => {
    if (selectedDocIds.includes(docId)) {
      setSelectedDocIds(selectedDocIds.filter(id => id !== docId));
    } else {
      if (selectedDocIds.length >= 5) {
        return; // Prevent selecting more than 5
      }
      setSelectedDocIds([...selectedDocIds, docId]);
    }
  };

  const handleCompare = async () => {
    if (selectedDocIds.length < 2 || selectedDocIds.length > 5) return;

    setLoading(true);
    setError(null);
    setComparisonResult(null);

    try {
      const data = await compareWorkspacePapers(workspaceId, selectedDocIds);
      setComparisonResult(data);
    } catch (err) {
      setError(err.message || 'Failed to compare papers.');
    } finally {
      setLoading(false);
    }
  };

  const isSelectionValid = selectedDocIds.length >= 2 && selectedDocIds.length <= 5;

  const categories = [
    { key: 'research_objective', label: 'Research Objective' },
    { key: 'methodology', label: 'Methodology' },
    { key: 'dataset', label: 'Dataset & Setup' },
    { key: 'results', label: 'Results & Evaluation' },
    { key: 'limitations', label: 'Limitations' }
  ];

  return (
    <div className="compare-tab-container">
      <div className="compare-header">
        <div>
          <h2>Compare Papers</h2>
          <p className="compare-subtitle">Select 2–5 papers to compare their research objectives, methodology, datasets, and findings.</p>
        </div>
        
        {comparisonResult && (
          <div className="view-mode-toggle">
            <button 
              className={`toggle-btn ${viewMode === 'sections' ? 'active' : ''}`}
              onClick={() => setViewMode('sections')}
            >
              <Layers size={14} /> Sectional
            </button>
            <button 
              className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
            >
              <Scale size={14} /> Compact Table
            </button>
          </div>
        )}
      </div>

      {/* Selection Area */}
      <div className="paper-selection-section">
        <div className="selection-toolbar">
          <span className="selection-count">
            Selected: <strong>{selectedDocIds.length}</strong> / 5
          </span>
          {selectedDocIds.length < 2 && (
            <span className="selection-warning">
              <AlertCircle size={14} /> Select at least 2 papers to compare
            </span>
          )}
          {selectedDocIds.length === 5 && (
            <span className="selection-info">
              Maximum 5 papers reached
            </span>
          )}
        </div>

        {documents.length === 0 ? (
          <div className="empty-papers-msg">
            No papers attached to this workspace yet. Add papers first to compare.
          </div>
        ) : (
          <div className="papers-selection-grid">
            {documents.map(doc => {
              const isSelected = selectedDocIds.includes(doc.id);
              const isDisabled = !isSelected && selectedDocIds.length >= 5;
              return (
                <div 
                  key={doc.id} 
                  className={`paper-select-card ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
                  onClick={() => !isDisabled && toggleDocument(doc.id)}
                >
                  <div className="checkbox-box">
                    {isSelected && <Check size={14} strokeWidth={3} />}
                  </div>
                  <div className="paper-card-details">
                    <div className="paper-card-title">
                      <FileText size={16} color="var(--c-555)" />
                      <span>{doc.filename}</span>
                    </div>
                    <div className="paper-card-meta">
                      <span>{doc.file_type ? doc.file_type.toUpperCase() : 'PDF'}</span>
                      {doc.page_count ? <span> · {doc.page_count} pages</span> : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="action-row">
          <button 
            className="btn-primary compare-btn"
            disabled={!isSelectionValid || loading}
            onClick={handleCompare}
          >
            <FileCheck size={18} />
            {loading ? 'Analyzing...' : 'Compare Selected Papers'}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="compare-loading-state">
          <Orbot size={64} state="searching" />
          <div className="loading-stage-text">
            {LOADING_STAGES[loadingStageIdx]}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="error-state" style={{ margin: '1.5rem 0' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Comparison Results */}
      {comparisonResult && !loading && (
        <div className="comparison-results-wrapper">

          {/* ORBOT Synthesis Section */}
          <div className="orbot-synthesis-card">
            <div className="synthesis-header">
              <Orbot size={36} state="idle" />
              <h3>ORBOT'S SYNTHESIS</h3>
            </div>

            <div className="synthesis-grid">
              <div className="synthesis-block">
                <span className="synthesis-label">BIGGEST DIFFERENCE</span>
                <p>{comparisonResult.overall_synthesis?.biggest_difference || 'Not provided'}</p>
              </div>
              <div className="synthesis-block">
                <span className="synthesis-label">COMMON GROUND</span>
                <p>{comparisonResult.overall_synthesis?.common_ground || 'Not provided'}</p>
              </div>
            </div>
          </div>

          {/* Sectional View */}
          {viewMode === 'sections' && (
            <div className="sectional-view">
              {categories.map(cat => {
                const aspectData = comparisonResult.comparison?.[cat.key] || [];
                return (
                  <div key={cat.key} className="comparison-category-block">
                    <h3 className="category-title">{cat.label}</h3>
                    <div className="category-papers-grid">
                      {aspectData.map((item, idx) => (
                        <div key={idx} className="category-paper-card">
                          <div className="paper-name-badge">
                            <FileText size={14} />
                            <span>{item.filename}</span>
                          </div>
                          <p className="paper-aspect-summary">{item.summary}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Compact Table View */}
          {viewMode === 'table' && (
            <div className="table-view-container">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Dimension</th>
                    {selectedDocIds.map(docId => {
                      const doc = documents.find(d => d.id === docId);
                      return <th key={docId}>{doc?.filename || 'Paper'}</th>;
                    })}
                  </tr>
                </thead>
                <tbody>
                  {categories.map(cat => {
                    const aspectData = comparisonResult.comparison?.[cat.key] || [];
                    return (
                      <tr key={cat.key}>
                        <td className="dimension-col">{cat.label}</td>
                        {selectedDocIds.map(docId => {
                          const item = aspectData.find(i => i.document_id === docId);
                          return (
                            <td key={docId} className="summary-col">
                              {item ? item.summary : 'Not reported'}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Sources Section */}
          {comparisonResult.sources && comparisonResult.sources.length > 0 && (
            <div className="comparison-sources-footer">
              <span className="sources-title">REFERRED SOURCES</span>
              <div className="sources-chips-grid">
                {comparisonResult.sources.map((src, idx) => (
                  <div key={idx} className="source-chip-item" title={`Similarity distance: ${src.similarity}`}>
                    <FileText size={12} />
                    <span>{src.filename}</span>
                    {src.page_number ? <span className="page-tag">Page {src.page_number}</span> : null}
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

export default CompareTab;
