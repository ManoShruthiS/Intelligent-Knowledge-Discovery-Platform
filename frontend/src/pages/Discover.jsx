import React, { useEffect, useState } from 'react';
import {
  Search, AlertCircle, ExternalLink, GitBranch, Database,
  RefreshCw, BookOpen, Star, GitFork, Calendar,
} from 'lucide-react';
import MarkdownMessage from '../components/common/MarkdownMessage';
import {
  discoverResearch, discoverGithub, discoverDatasets,
} from '../services/api';

const TABS = [
  { key: 'research', label: 'Research Papers', icon: BookOpen,
    helper: 'Searches OpenAlex + Crossref + arXiv in parallel.' },
  { key: 'github', label: 'GitHub', icon: GitBranch,
    helper: 'Search public repositories via the GitHub Search API. Optional GITHUB_TOKEN raises rate limit.' },
  { key: 'datasets', label: 'Datasets', icon: Database,
    helper: 'Search the HuggingFace Datasets public index.' },
];

function Discover() {
  const [tab, setTab] = useState('research');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [availability, setAvailability] = useState({});

  const runSearch = async (q = query) => {
    const trimmed = (q || '').trim();
    if (!trimmed) {
      setResults(null);
      setError('Enter a search query.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (tab === 'research') {
        const r = await discoverResearch(trimmed, 8);
        setResults(r.combined || []);
        setAvailability(r.availability || {});
      } else if (tab === 'github') {
        const r = await discoverGithub(trimmed, 12);
        setResults(r.results || []);
        setAvailability({
          github: r.available ? 'ok' : 'unavailable',
          error: r.error || null,
        });
      } else if (tab === 'datasets') {
        const r = await discoverDatasets(trimmed, 12);
        setResults(r.results || []);
      }
    } catch (e) {
      setError(e.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setResults(null);
    setError(null);
  }, [tab]);

  return (
    <div className="discover-container">
      <div className="discover-header">
        <div className="discover-title-area">
          <h1>Discover</h1>
          <p>Find papers, repositories, and datasets — all from free public sources.</p>
        </div>
        <div className="discover-orbot-mini" aria-hidden="true">
          <svg viewBox="0 0 100 100" width="64" height="64" fill="none">
            <ellipse cx="50" cy="50" rx="40" ry="15" stroke="#E5E5E5" strokeWidth="1" transform="rotate(20 50 50)" />
            <ellipse cx="50" cy="50" rx="40" ry="15" stroke="#E5E5E5" strokeWidth="1" transform="rotate(-40 50 50)" />
            <rect x="35" y="25" width="30" height="24" rx="12" fill="#FFFFFF" stroke="#333333" strokeWidth="2" />
            <rect x="38" y="28" width="24" height="14" rx="7" fill="#111111" />
            <circle cx="45" cy="35" r="2.5" fill="#FFFFFF" />
            <circle cx="55" cy="35" r="2.5" fill="#FFFFFF" />
          </svg>
        </div>
      </div>

      <div className="discover-tabs">
        {TABS.map(t => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              className={`discover-tab ${active ? 'active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              <Icon size={14} /> {t.label}
            </button>
          );
        })}
      </div>

      <div className="discover-search-row">
        <div className="discover-search-input">
          <Search size={18} color="var(--c-888)" />
          <input
            type="text"
            placeholder={tab === 'research'
              ? 'Search a topic, paper, author, or DOI…'
              : tab === 'github'
              ? 'Search repositories by name, topic, or language…'
              : 'Search datasets by name or tag…'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runSearch(); }}
          />
          <button
            type="button"
            className="discover-search-btn"
            disabled={loading}
            onClick={() => runSearch()}
          >
            {loading ? <RefreshCw size={14} className="spinning" color="#fff" /> : <Search size={14} color="#fff" />}
          </button>
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--c-777)', paddingTop: '0.5rem' }}>
          {TABS.find(t => t.key === tab)?.helper}
        </div>
      </div>

      {error && (
        <div className="wi-error" role="alert">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {/* Source availability chips for Research tab */}
      {tab === 'research' && availability && Object.keys(availability).length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          {['openalex', 'crossref', 'arxiv'].map(src => (
            <span key={src} className="wi-tag" title={availability[src] === 'ok' ? 'Available' : 'Currently unavailable'}>
              {src} · {availability[src] || 'unknown'}
            </span>
          ))}
        </div>
      )}
      {tab === 'github' && availability.github === 'unavailable' && (
        <div className="wi-error">
          GitHub is currently unavailable. {availability.error ? `(${availability.error})` : ''}
          To raise the rate limit, configure a <code>GITHUB_TOKEN</code> in <code>backend/.env</code>.
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
          <RefreshCw size={24} className="spinning" />
        </div>
      )}

      {!loading && results && results.length === 0 && (
        <div className="discover-empty-state">
          <p>No results. Try a different query.</p>
        </div>
      )}

      {!loading && results && results.length > 0 && (
        <div className="discover-results">
          {tab === 'research' && results.map((r, i) => <ResearchResult key={i} r={r} />)}
          {tab === 'github' && results.map((r, i) => <GithubResult key={i} r={r} />)}
          {tab === 'datasets' && results.map((r, i) => <DatasetResult key={i} r={r} />)}
        </div>
      )}

      {!loading && !results && !error && (
        <div className="discover-empty-state">
          {tab === 'research' && (
            <>
              <h3>Find papers to support your research</h3>
              <p>OpenAlex, Crossref, and arXiv are queried in parallel. Results are deduplicated.</p>
            </>
          )}
          {tab === 'github' && (
            <>
              <h3>Find implementations and tooling</h3>
              <p>Search public repositories by topic, language, or keyword.</p>
            </>
          )}
          {tab === 'datasets' && (
            <>
              <h3>Find datasets for your experiments</h3>
              <p>Search the HuggingFace Datasets index.</p>
            </>
          )}
        </div>
      )}

      <style>{`
        .discover-tabs {
          display: flex; gap: 0.4rem; margin-bottom: 1rem; flex-wrap: wrap;
          border-bottom: 1px solid var(--c-eee, #eee);
          padding-bottom: 0.5rem;
        }
        .discover-tab {
          display: inline-flex; align-items: center; gap: 0.4rem;
          padding: 0.4rem 0.75rem; font-size: 0.85rem;
          background: transparent; color: var(--c-555, #555);
          border: 1px solid transparent; border-radius: 6px;
          cursor: pointer;
        }
        .discover-tab:hover { background: var(--c-f5, #f5f5f5); color: var(--c-111, #111); }
        .discover-tab.active {
          background: var(--c-111, #111); color: white;
          border-color: var(--c-111, #111);
        }
        .discover-results {
          display: flex; flex-direction: column; gap: 0.75rem;
        }
        .discover-result-card {
          background: var(--c-white, #fff);
          border: 1px solid var(--c-eee, #eee);
          border-radius: 8px; padding: 1rem 1.25rem;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .discover-result-card:hover {
          border-color: var(--c-ccc, #ccc);
          box-shadow: 0 4px 14px rgba(0,0,0,0.04);
        }
        .discover-result-title {
          font-weight: 600; font-size: 1rem; color: var(--c-111, #111);
          margin-bottom: 0.25rem;
        }
        .discover-result-meta {
          font-size: 0.8rem; color: var(--c-555, #555);
          margin-bottom: 0.5rem;
        }
        .discover-result-abstract {
          font-size: 0.9rem; color: var(--c-333, #333);
          line-height: 1.55;
        }
        .discover-result-link {
          display: inline-flex; align-items: center; gap: 0.3rem;
          font-size: 0.8rem; color: var(--c-555, #555);
          text-decoration: none;
        }
        .discover-result-link:hover { color: var(--c-111, #111); }
      `}</style>
    </div>
  );
}

function ResearchResult({ r }) {
  const authors = (r.authors || []).slice(0, 6).join(', ');
  const moreAuthors = r.authors && r.authors.length > 6 ? ` +${r.authors.length - 6} more` : '';
  return (
    <div className="discover-result-card">
      <div className="discover-result-title">{r.title || 'Untitled'}</div>
      <div className="discover-result-meta">
        {authors}{moreAuthors}
        {r.year ? ` · ${r.year}` : ''}
        {r.venue ? ` · ${r.venue}` : ''}
        {' · '}<span style={{ textTransform: 'capitalize' }}>{r.source}</span>
        {r.cited_by_count != null ? ` · ${r.cited_by_count} citations` : ''}
        {r.open_access ? ' · Open Access' : ''}
      </div>
      {r.abstract && (
        <div className="discover-result-abstract" style={{
          display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical',
          overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {r.abstract}
        </div>
      )}
      <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {r.url && (
          <a href={r.url} target="_blank" rel="noopener noreferrer" className="discover-result-link">
            <ExternalLink size={12} /> Open source
          </a>
        )}
        {r.pdf_url && (
          <a href={r.pdf_url} target="_blank" rel="noopener noreferrer" className="discover-result-link">
            <ExternalLink size={12} /> PDF
          </a>
        )}
        {r.doi && (
          <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noopener noreferrer" className="discover-result-link">
            <ExternalLink size={12} /> DOI: {r.doi}
          </a>
        )}
      </div>
    </div>
  );
}

function GithubResult({ r }) {
  return (
    <div className="discover-result-card">
      <div className="discover-result-title">
        <a href={r.html_url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
          {r.full_name}
        </a>
      </div>
      <div className="discover-result-meta">
        {r.language && <span>{r.language}</span>}
        {r.license && <span> · {r.license}</span>}
        {r.stars != null && <>
          {' · '}<Star size={11} style={{ verticalAlign: 'middle' }} /> {r.stars.toLocaleString()}
        </>}
        {r.forks != null && <>
          {' · '}<GitFork size={11} style={{ verticalAlign: 'middle' }} /> {r.forks.toLocaleString()}
        </>}
        {r.updated_at && <>
          {' · '}<Calendar size={11} style={{ verticalAlign: 'middle' }} /> updated {new Date(r.updated_at).toLocaleDateString()}
        </>}
      </div>
      {r.description && (
        <div className="discover-result-abstract">{r.description}</div>
      )}
      {r.topics && r.topics.length > 0 && (
        <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
          {r.topics.slice(0, 8).map(t => (
            <span key={t} className="wi-tag" style={{ textTransform: 'none' }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function DatasetResult({ r }) {
  return (
    <div className="discover-result-card">
      <div className="discover-result-title">
        <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
          {r.id}
        </a>
      </div>
      <div className="discover-result-meta">
        {r.downloads != null && `Downloads: ${r.downloads.toLocaleString()}`}
        {r.likes != null && ` · Likes: ${r.likes}`}
        {r.last_modified && ` · Updated ${new Date(r.last_modified).toLocaleDateString()}`}
      </div>
      {r.tags && r.tags.length > 0 && (
        <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
          {r.tags.slice(0, 12).map(t => (
            <span key={t} className="wi-tag" style={{ textTransform: 'none' }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default Discover;