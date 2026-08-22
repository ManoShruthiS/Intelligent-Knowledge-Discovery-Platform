import React, { useState } from 'react';
import { BookOpen, GitBranch, Database, RefreshCw, Search, AlertCircle, ExternalLink, Plus, Trash2 } from 'lucide-react';
import {
  discoverResearch, discoverGithub, discoverDatasets,
  addCitation, deleteCitation,
} from '../../services/api';

const TABS = [
  { key: 'research', label: 'Research Papers', icon: BookOpen },
  { key: 'github', label: 'GitHub', icon: GitBranch },
  { key: 'datasets', label: 'Datasets', icon: Database },
];

function WorkspaceIntelligenceTabs({ workspaceId }) {
  const [tab, setTab] = useState('research');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const runSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) { setError('Enter a search query.'); return; }
    setLoading(true); setError(null); setResults(null);
    try {
      if (tab === 'research') {
        const r = await discoverResearch(trimmed, 8);
        setResults(r.combined || []);
      } else if (tab === 'github') {
        const r = await discoverGithub(trimmed, 12);
        setResults(r.results || []);
        if (!r.available) setError(`GitHub unavailable: ${r.error || 'no token configured'}`);
      } else if (tab === 'datasets') {
        const r = await discoverDatasets(trimmed, 12);
        setResults(r.results || []);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Intelligence</h2>
        <span style={{ fontSize: '0.75rem', color: 'var(--c-777)' }}>
          {workspaceId ? 'Workspace-scoped discovery' : 'Global discovery'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1rem' }}>
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.key} type="button" onClick={() => { setTab(t.key); setResults(null); setError(null); }}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                padding: '0.4rem 0.75rem', fontSize: '0.82rem',
                background: tab === t.key ? 'var(--c-111, #111)' : 'transparent',
                color: tab === t.key ? 'white' : 'var(--c-555, #555)',
                border: '1px solid ' + (tab === t.key ? 'var(--c-111, #111)' : 'transparent'),
                borderRadius: 6, cursor: 'pointer',
              }}>
              <Icon size={13} /> {t.label}
            </button>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder={tab === 'research' ? 'Search papers, topics, DOIs...' : tab === 'github' ? 'Search repos...' : 'Search datasets...'}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runSearch()}
          style={{ flex: 1, padding: '0.5rem 0.75rem', border: '1px solid var(--c-ddd, #ddd)', borderRadius: 6, fontSize: '0.9rem' }}
        />
        <button type="button" className="btn-primary" onClick={runSearch} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', padding: '0.5rem 0.75rem', fontSize: '0.85rem' }}>
          {loading ? <RefreshCw size={14} className="spinning" /> : <Search size={14} />} Search
        </button>
      </div>

      {error && <div className="wi-error" role="alert"><AlertCircle size={14} /> {error}</div>}

      {results && results.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--c-555)' }}>No results found.</div>
      )}

      {results && results.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '60vh', overflow: 'auto' }}>
          {results.map((r, i) => (
            <div key={i} style={{
              padding: '0.75rem 1rem', background: 'var(--c-white, #fff)',
              border: '1px solid var(--c-eee, #eee)', borderRadius: 8,
            }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.25rem' }}>
                {r.title || r.full_name || r.id || 'Untitled'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--c-555, #555)', marginBottom: '0.35rem' }}>
                {tab === 'research' && <>
                  {(r.authors || []).slice(0, 3).join(', ')}
                  {r.year ? ` (${r.year})` : ''}
                  {r.source ? ` · ${r.source}` : ''}
                </>}
                {tab === 'github' && <>
                  {r.language || 'N/A'}{r.stars != null ? ` · ${r.stars} stars` : ''}
                </>}
                {tab === 'datasets' && <>
                  {r.downloads != null ? `Downloads: ${r.downloads.toLocaleString()}` : ''}
                  {r.tags?.length ? ` · ${r.tags.slice(0, 5).join(', ')}` : ''}
                </>}
              </div>
              {r.abstract && (
                <div style={{ fontSize: '0.8rem', color: 'var(--c-333, #333)', lineHeight: 1.5, marginBottom: '0.35rem',
                  display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {r.abstract}
                </div>
              )}
              {r.description && (
                <div style={{ fontSize: '0.8rem', color: 'var(--c-333, #333)', lineHeight: 1.5, marginBottom: '0.35rem' }}>
                  {r.description}
                </div>
              )}
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                {r.url && (
                  <a href={r.url} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: '0.75rem', color: 'var(--c-555, #555)', textDecoration: 'none' }}>
                    <ExternalLink size={11} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} /> Open
                  </a>
                )}
                {r.doi && (
                  <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: '0.75rem', color: 'var(--c-555, #555)', textDecoration: 'none' }}>
                    <ExternalLink size={11} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} /> DOI
                  </a>
                )}
                {r.html_url && (
                  <a href={r.html_url} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: '0.75rem', color: 'var(--c-555, #555)', textDecoration: 'none' }}>
                    <ExternalLink size={11} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} /> GitHub
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!results && !loading && !error && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--c-555)', fontSize: '0.9rem' }}>
          <p>Search to find papers, repos, or datasets. Results come from free public sources only.</p>
        </div>
      )}
    </div>
  );
}

export default WorkspaceIntelligenceTabs;