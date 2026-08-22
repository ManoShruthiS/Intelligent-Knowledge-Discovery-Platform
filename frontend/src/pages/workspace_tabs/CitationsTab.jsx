import React, { useState, useEffect, useCallback } from 'react';
import { BookOpen, Plus, Trash2, Copy, FileText, ExternalLink } from 'lucide-react';
import { listCitations, addCitation, deleteCitation, bibliography, extractCitations } from '../../services/api';
import './CitationsTab.css';

const STYLES = ['IEEE', 'APA', 'MLA', 'Chicago', 'Harvard'];

const EMPTY_FORM = {
  title: '',
  authors: '',
  year: '',
  venue: '',
  doi: '',
  url: '',
  abstract: '',
  source_type: 'paper',
};

function CitationsTab({ workspaceId, documents }) {
  const [citations, setCitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState('IEEE');
  const [bibliographyText, setBibliographyText] = useState('');
  const [bibliographyLoading, setBibliographyLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);

  const loadCitations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCitations(workspaceId);
      setCitations(data.citations || data || []);
    } catch (err) {
      setError(err.message || 'Failed to load citations.');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadCitations();
  }, [loadCitations]);

  const handleFormChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleAddCitation = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      await addCitation({ workspace_id: workspaceId, ...formData });
      setFormData(EMPTY_FORM);
      setShowNew(false);
      await loadCitations();
    } catch (err) {
      setError(err.message || 'Failed to add citation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (citationId) => {
    if (!window.confirm('Delete this citation?')) return;

    setError(null);
    try {
      await deleteCitation(citationId);
      setCitations(prev => prev.filter(c => c.id !== citationId));
    } catch (err) {
      setError(err.message || 'Failed to delete citation.');
    }
  };

  const handleGenerateBibliography = async () => {
    if (citations.length === 0) return;

    setBibliographyLoading(true);
    setError(null);
    try {
      const ids = citations.map(c => c.id);
      const result = await bibliography(selectedStyle.toLowerCase(), ids);
      setBibliographyText(result.bibliography || result.text || result || '');
    } catch (err) {
      setError(err.message || 'Failed to generate bibliography.');
    } finally {
      setBibliographyLoading(false);
    }
  };

  const handleCopyBibliography = async () => {
    try {
      await navigator.clipboard.writeText(bibliographyText);
    } catch {
      // Fallback: select text
    }
  };

  const handleExtractFromDocument = async (documentId) => {
    if (!documentId) return;

    setExtracting(true);
    setError(null);
    try {
      await extractCitations(documentId);
      await loadCitations();
    } catch (err) {
      setError(err.message || 'Failed to extract citations.');
    } finally {
      setExtracting(false);
    }
  };

  return (
    <div className="citations-tab-container">
      <div className="citations-header">
        <div>
          <h2>Citations</h2>
          <p className="citations-subtitle">Manage your reference library. Add, extract, and format citations for your bibliography.</p>
        </div>
        <div className="citations-toolbar">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowNew(prev => !prev)}
          >
            <Plus size={16} />
            {showNew ? 'Cancel' : 'Add Citation'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="error-state">
          <span>{error}</span>
        </div>
      )}

      {/* Extract from Document */}
      {documents && documents.length > 0 && (
        <div className="extract-section">
          <FileText size={16} color="var(--c-555)" />
          <label>Extract from Document</label>
          <select
            className="extract-select"
            value=""
            onChange={(e) => {
              if (e.target.value) handleExtractFromDocument(e.target.value);
              e.target.value = '';
            }}
            disabled={extracting}
          >
            <option value="" disabled>
              {extracting ? 'Extracting...' : 'Select a document'}
            </option>
            {documents.map(doc => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* New Citation Form */}
      {showNew && (
        <form className="new-citation-form" onSubmit={handleAddCitation}>
          <div className="form-row">
            <div className="form-group">
              <label>Title *</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => handleFormChange('title', e.target.value)}
                placeholder="Paper or book title"
                required
              />
            </div>
            <div className="form-group">
              <label>Source Type</label>
              <select
                value={formData.source_type}
                onChange={(e) => handleFormChange('source_type', e.target.value)}
              >
                <option value="paper">Paper</option>
                <option value="book">Book</option>
                <option value="website">Website</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Authors</label>
              <input
                type="text"
                value={formData.authors}
                onChange={(e) => handleFormChange('authors', e.target.value)}
                placeholder="e.g. Smith, J. and Doe, A."
              />
            </div>
            <div className="form-group">
              <label>Year</label>
              <input
                type="number"
                value={formData.year}
                onChange={(e) => handleFormChange('year', e.target.value)}
                placeholder="2024"
                min="0"
                max="2099"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Venue</label>
              <input
                type="text"
                value={formData.venue}
                onChange={(e) => handleFormChange('venue', e.target.value)}
                placeholder="Journal or conference name"
              />
            </div>
            <div className="form-group">
              <label>DOI</label>
              <input
                type="text"
                value={formData.doi}
                onChange={(e) => handleFormChange('doi', e.target.value)}
                placeholder="10.xxxx/xxxxx"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>URL</label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => handleFormChange('url', e.target.value)}
                placeholder="https://..."
              />
            </div>
          </div>

          <div className="form-group">
            <label>Abstract</label>
            <textarea
              value={formData.abstract}
              onChange={(e) => handleFormChange('abstract', e.target.value)}
              placeholder="Brief summary or abstract..."
              rows={3}
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting || !formData.title.trim()}>
              {submitting ? 'Adding...' : 'Add Citation'}
            </button>
          </div>
        </form>
      )}

      {/* Citation List */}
      {loading ? (
        <div className="citations-loading">
          <BookOpen size={28} color="var(--c-555)" className="spinning" />
          <p>Loading citations...</p>
        </div>
      ) : citations.length === 0 ? (
        <div className="citations-empty">
          <BookOpen size={36} color="var(--c-ccc, #ccc)" />
          <p>No citations yet. Add one manually or extract from a document.</p>
        </div>
      ) : (
        <div className="citations-list-section">
          <div className="citations-count">{citations.length} citation{citations.length !== 1 ? 's' : ''}</div>
          {citations.map(cit => (
            <div key={cit.id} className="citation-card">
              <div className="citation-card-top">
                <div className="citation-title">{cit.title}</div>
                <button
                  type="button"
                  className="citation-delete-btn"
                  onClick={() => handleDelete(cit.id)}
                  title="Delete citation"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="citation-meta-row">
                {cit.authors && <span className="citation-authors">{cit.authors}</span>}
                {cit.year && <span className="citation-year">{cit.year}</span>}
                {cit.venue && <span className="citation-venue">{cit.venue}</span>}
                {cit.source_type && (
                  <span className="source-type-badge">{cit.source_type}</span>
                )}
              </div>
              <div className="citation-meta-row">
                {cit.doi && (
                  <a
                    className="citation-doi-link"
                    href={`https://doi.org/${cit.doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {cit.doi} <ExternalLink size={12} />
                  </a>
                )}
                {cit.url && !cit.doi && (
                  <a
                    className="citation-doi-link"
                    href={cit.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {cit.url} <ExternalLink size={12} />
                  </a>
                )}
              </div>
              {cit.abstract && (
                <div className="citation-abstract">{cit.abstract}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Bibliography Generator */}
      {!loading && citations.length > 0 && (
        <div className="bibliography-section">
          <div className="bibliography-header">
            <h3>BIBLIOGRAPHY</h3>
            <div className="bibliography-controls">
              <select
                className="style-select"
                value={selectedStyle}
                onChange={(e) => setSelectedStyle(e.target.value)}
              >
                {STYLES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button
                type="button"
                className="btn-primary"
                onClick={handleGenerateBibliography}
                disabled={bibliographyLoading}
              >
                <BookOpen size={14} />
                {bibliographyLoading ? 'Generating...' : 'Generate Bibliography'}
              </button>
            </div>
          </div>

          {bibliographyText && (
            <div className="bibliography-result">
              {bibliographyText}
              <div style={{ marginTop: '0.75rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleCopyBibliography}
                  style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
                >
                  <Copy size={12} /> Copy
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default CitationsTab;
