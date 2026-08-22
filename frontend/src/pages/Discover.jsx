import React, { useEffect, useState, useRef } from 'react';
import {
  Search, AlertCircle, ExternalLink, GitBranch, Database,
  RefreshCw, BookOpen, Star, GitFork, Calendar, Bookmark,
  BookmarkCheck, SlidersHorizontal, X, ChevronRight, Zap,
  TrendingUp, Play, FileText, Video,
} from 'lucide-react';
import {
  discoverResearch, discoverGithub, discoverDatasets,
} from '../services/api';
import './Discover.css';

const TABS = [
  { key: 'research', label: 'Research Papers', icon: BookOpen },
  { key: 'github',   label: 'GitHub Repositories', icon: GitBranch },
  { key: 'datasets', label: 'Datasets', icon: Database },
  { key: 'learning', label: 'Learning Resources', icon: Play },
];

const TRENDING_TOPICS = [
  { label: 'Large Language Models', count: '12,456 papers' },
  { label: 'Machine Learning',      count: '45,231 papers' },
  { label: 'Deep Learning',         count: '38,521 papers' },
  { label: 'Neural Networks',       count: '22,134 papers' },
  { label: 'Natural Language Processing', count: '18,773 papers' },
];

const LEARNING_RESOURCES = [
  { title: 'Transformers from Scratch', type: 'video', duration: '2h 15m', source: 'YouTube', url: 'https://youtube.com/watch?v=U0s0f995w14', description: 'A step-by-step implementation of the Transformer architecture.' },
  { title: 'Stanford CS224N: NLP with Deep Learning', type: 'course', duration: '20 lectures', source: 'Stanford', url: 'http://web.stanford.edu/class/cs224n/', description: 'Graduate course on deep learning approaches to NLP.' },
  { title: 'Illustrated BERT, ELMo, and co.', type: 'article', duration: '30 min read', source: 'Jay Alammar Blog', url: 'https://jalammar.github.io/illustrated-bert/', description: 'Visual guide to language models with detailed diagrams.' },
  { title: 'Attention Is All You Need - Paper Explained', type: 'video', duration: '45 min', source: 'Yannic Kilcher', url: 'https://youtube.com/watch?v=iDulhoQ2pro', description: 'In-depth explanation of the Transformer paper by Vaswani et al.' },
  { title: 'Fast.ai Practical Deep Learning', type: 'course', duration: '9 lessons', source: 'fast.ai', url: 'https://course.fast.ai/', description: 'Top-down approach to deep learning, practical and accessible.' },
  { title: 'The Annotated Transformer', type: 'article', duration: '45 min read', source: 'Harvard NLP', url: 'https://nlp.seas.harvard.edu/annotated-transformer/', description: 'Line-by-line implementation of "Attention Is All You Need".' },
];

const SOURCE_LOGOS = {
  arxiv: { label: 'arXiv', color: '#B31B1B' },
  openalex: { label: 'OpenAlex', color: '#4A90D9' },
  crossref: { label: 'Crossref', color: '#FF6B35' },
};

function SourceBadge({ source }) {
  const s = SOURCE_LOGOS[source?.toLowerCase()] || { label: source, color: '#888' };
  return (
    <span className="discover-source-badge" style={{ borderColor: s.color + '40', color: s.color }}>
      {s.label}
    </span>
  );
}

function Discover() {
  const [tab, setTab]           = useState('research');
  const [query, setQuery]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [results, setResults]   = useState(null);
  const [availability, setAvailability] = useState({});
  const [bookmarks, setBookmarks] = useState(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters]   = useState({
    yearFrom: 1900,
    yearTo: 2024,
    docTypes: { journal: true, conference: true, preprint: true, book: false, dissertation: false },
    openAccess: false,
    minCitations: 0,
  });
  const [stats, setStats]       = useState(null);
  const searchStartRef          = useRef(null);

  const runSearch = async (q = query) => {
    const trimmed = (q || '').trim();
    if (!trimmed) { setError('Enter a search query.'); return; }
    setLoading(true);
    setError(null);
    setStats(null);
    searchStartRef.current = Date.now();
    try {
      if (tab === 'research') {
        const r = await discoverResearch(trimmed, 10);
        const elapsed = ((Date.now() - searchStartRef.current) / 1000).toFixed(1);
        const combined = r.combined || [];
        // Apply filters
        const filtered = combined.filter(item => {
          if (item.year && (item.year < filters.yearFrom || item.year > filters.yearTo)) return false;
          if (filters.minCitations > 0 && (item.cited_by_count || 0) < filters.minCitations) return false;
          if (filters.openAccess && !item.open_access) return false;
          return true;
        });
        // Deduplicate by title similarity
        const seen = new Set();
        const deduped = filtered.filter(item => {
          const key = (item.title || '').toLowerCase().trim().slice(0, 60);
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        const sources = new Set(combined.map(c => c.source)).size;
        setResults(deduped);
        setAvailability(r.availability || {});
        setStats({
          total: combined.length,
          displayed: deduped.length,
          sources,
          elapsed,
          dedup: Math.round((1 - deduped.length / Math.max(combined.length, 1)) * 100),
        });
      } else if (tab === 'github') {
        const r = await discoverGithub(trimmed, 12);
        setResults(r.results || []);
        setAvailability({ github: r.available ? 'ok' : 'unavailable', error: r.error || null });
      } else if (tab === 'datasets') {
        const r = await discoverDatasets(trimmed, 12);
        setResults(r.results || []);
      } else if (tab === 'learning') {
        // Filter learning resources by query
        const q2 = trimmed.toLowerCase();
        setResults(LEARNING_RESOURCES.filter(r =>
          r.title.toLowerCase().includes(q2) ||
          r.description.toLowerCase().includes(q2) ||
          r.source.toLowerCase().includes(q2)
        ));
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
    setStats(null);
  }, [tab]);

  const toggleBookmark = (id) => {
    setBookmarks(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="discover-page">
      {/* ── Main content column ── */}
      <div className="discover-main">
        {/* Header */}
        <div className="discover-header">
          <div>
            <h1 className="discover-title">
              Discover Research <Zap size={22} className="discover-title-icon" />
            </h1>
            <p className="discover-subtitle">
              Find papers, repositories, datasets, and learning resources from trusted public sources.
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="discover-tabs">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                type="button"
                className={`discover-tab ${tab === t.key ? 'active' : ''}`}
                onClick={() => setTab(t.key)}
                id={`discover-tab-${t.key}`}
              >
                <Icon size={14} />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Search bar */}
        <div className="discover-search-row">
          <div className="discover-search-wrap">
            <Search size={16} className="discover-search-icon" />
            <input
              id="discover-search-input"
              type="text"
              className="discover-search-input"
              placeholder={
                tab === 'research'  ? 'Search a topic, paper, author, or DOI…' :
                tab === 'github'    ? 'Search repositories by name, topic, or language…' :
                tab === 'datasets'  ? 'Search datasets by name or tag…' :
                                     'Search for tutorials, courses, or topics…'
              }
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') runSearch(); }}
            />
            <button
              id="discover-search-btn"
              type="button"
              className="discover-search-btn"
              disabled={loading}
              onClick={() => runSearch()}
            >
              {loading ? <RefreshCw size={14} className="spinning" /> : <><Search size={13} /> Search</>}
            </button>
          </div>
        </div>

        {/* Filter bar (research only) */}
        {tab === 'research' && (
          <div className="discover-filter-bar">
            <span className="discover-filter-chip">All Sources ▾</span>
            <span className="discover-filter-chip">Any Year ▾</span>
            <span className="discover-filter-chip">Sort: Relevance ▾</span>
            <button
              type="button"
              className="discover-filter-chip discover-filter-more"
              onClick={() => setShowFilters(!showFilters)}
            >
              <SlidersHorizontal size={13} /> More Filters
            </button>
            <button type="button" className="discover-save-search">
              <Bookmark size={13} /> Save Search
            </button>
          </div>
        )}

        {/* Stats bar */}
        {stats && (
          <div className="discover-stats-bar">
            <div className="discover-stat">
              <FileText size={16} />
              <span className="discover-stat-num">{stats.total.toLocaleString()}</span>
              <span className="discover-stat-label">Papers Found</span>
            </div>
            <div className="discover-stat">
              <Search size={16} />
              <span className="discover-stat-num">{stats.sources}</span>
              <span className="discover-stat-label">Sources Searched</span>
            </div>
            <div className="discover-stat">
              <RefreshCw size={16} />
              <span className="discover-stat-num">{stats.elapsed}s</span>
              <span className="discover-stat-label">Search Time</span>
            </div>
            <div className="discover-stat">
              <Zap size={16} />
              <span className="discover-stat-num">{100 - (stats.dedup || 0)}%</span>
              <span className="discover-stat-label">Deduplicated</span>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="wi-error" role="alert">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* GitHub unavailable */}
        {tab === 'github' && availability.github === 'unavailable' && (
          <div className="wi-error">
            GitHub is currently unavailable. Configure a <code>GITHUB_TOKEN</code> in <code>backend/.env</code> to raise the rate limit.
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="discover-loading-state">
            <RefreshCw size={28} className="spinning" />
            <span>Searching across sources…</span>
          </div>
        )}

        {/* Empty */}
        {!loading && results && results.length === 0 && (
          <div className="discover-empty-state">
            <Search size={40} strokeWidth={1.5} />
            <h3>No results found</h3>
            <p>Try a different search term or adjust your filters.</p>
          </div>
        )}

        {/* Results */}
        {!loading && results && results.length > 0 && (
          <>
            {tab === 'research' && (
              <div className="discover-results-section">
                <div className="discover-results-header">
                  <h2>Top Research Papers</h2>
                  <p>Results from OpenAlex, Crossref, and arXiv</p>
                </div>
                <div className="discover-results-list">
                  {results.map((r, i) => (
                    <ResearchCard
                      key={i}
                      r={r}
                      bookmarked={bookmarks.has(r.doi || r.url || r.title)}
                      onBookmark={() => toggleBookmark(r.doi || r.url || r.title)}
                    />
                  ))}
                </div>
              </div>
            )}
            {tab === 'github' && (
              <div className="discover-results-list">
                {results.map((r, i) => <GithubCard key={i} r={r} />)}
              </div>
            )}
            {tab === 'datasets' && (
              <div className="discover-results-list">
                {results.map((r, i) => <DatasetCard key={i} r={r} />)}
              </div>
            )}
            {tab === 'learning' && (
              <div className="discover-results-list">
                {results.map((r, i) => <LearningCard key={i} r={r} />)}
              </div>
            )}
          </>
        )}

        {/* Empty state (initial) */}
        {!loading && !results && !error && (
          <div className="discover-empty-state">
            <BookOpen size={44} strokeWidth={1.2} />
            <h3>
              {tab === 'research'  ? 'Find papers to support your research' :
               tab === 'github'    ? 'Find implementations and tooling' :
               tab === 'datasets'  ? 'Find datasets for your experiments' :
                                    'Find tutorials and courses'}
            </h3>
            <p>
              {tab === 'research'  ? 'OpenAlex, Crossref, and arXiv queried in parallel. Results are deduplicated by title.' :
               tab === 'github'    ? 'Search public repositories by topic, language, or keyword.' :
               tab === 'datasets'  ? 'Search the HuggingFace Datasets public index.' :
                                    'Curated videos, courses, and articles from top educators.'}
            </p>
            {tab === 'learning' && (
              <button
                type="button"
                className="discover-search-btn"
                style={{ marginTop: '0.5rem', padding: '0.6rem 1.5rem' }}
                onClick={() => { setResults(LEARNING_RESOURCES); }}
              >
                Browse All Resources
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Right sidebar ── */}
      <aside className="discover-sidebar">
        {/* Refine panel */}
        <div className="discover-sidebar-card">
          <h3 className="discover-sidebar-title">Refine Your Search</h3>

          <div className="discover-filter-group">
            <label className="discover-filter-label">Year Range</label>
            <div className="discover-year-range">
              <input
                type="range"
                min="1900"
                max="2024"
                value={filters.yearTo}
                className="discover-range-input"
                onChange={e => setFilters(f => ({ ...f, yearTo: +e.target.value }))}
              />
              <div className="discover-year-labels">
                <span>{filters.yearFrom}</span>
                <span>{filters.yearTo}</span>
              </div>
            </div>
          </div>

          <div className="discover-filter-group">
            <label className="discover-filter-label">Document Type</label>
            {[
              ['journal',      'Journal Articles'],
              ['conference',   'Conference Papers'],
              ['preprint',     'Preprints'],
              ['book',         'Books'],
              ['dissertation', 'Dissertations'],
            ].map(([key, label]) => (
              <label key={key} className="discover-checkbox-row">
                <input
                  type="checkbox"
                  checked={filters.docTypes[key]}
                  onChange={e =>
                    setFilters(f => ({
                      ...f,
                      docTypes: { ...f.docTypes, [key]: e.target.checked },
                    }))
                  }
                />
                {label}
              </label>
            ))}
          </div>

          <div className="discover-filter-group discover-toggle-row">
            <label className="discover-filter-label">Open Access Only</label>
            <button
              type="button"
              id="discover-open-access-toggle"
              className={`discover-toggle ${filters.openAccess ? 'on' : ''}`}
              onClick={() => setFilters(f => ({ ...f, openAccess: !f.openAccess }))}
            />
          </div>

          <div className="discover-filter-group">
            <label className="discover-filter-label">
              Minimum Citations&nbsp;
              <span style={{ color: 'var(--c-888)', fontWeight: 400 }}>({filters.minCitations})</span>
            </label>
            <input
              type="range"
              min="0"
              max="5000"
              step="10"
              value={filters.minCitations}
              className="discover-range-input"
              onChange={e => setFilters(f => ({ ...f, minCitations: +e.target.value }))}
            />
          </div>

          <button
            type="button"
            id="discover-clear-filters-btn"
            className="discover-clear-filters"
            onClick={() =>
              setFilters({
                yearFrom: 1900, yearTo: 2024,
                docTypes: { journal: true, conference: true, preprint: true, book: false, dissertation: false },
                openAccess: false,
                minCitations: 0,
              })
            }
          >
            <RefreshCw size={13} /> Clear Filters
          </button>
        </div>

        {/* Trending Topics */}
        <div className="discover-sidebar-card">
          <h3 className="discover-sidebar-title">
            <TrendingUp size={14} /> Trending Topics
          </h3>
          <div className="discover-trending-list">
            {TRENDING_TOPICS.map(({ label, count }) => (
              <button
                key={label}
                type="button"
                className="discover-trending-item"
                onClick={() => { setQuery(label); runSearch(label); }}
              >
                <div>
                  <span className="discover-trending-label">{label}</span>
                  <span className="discover-trending-count">{count}</span>
                </div>
                <ChevronRight size={14} className="discover-trending-arrow" />
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

/* ── Research Card ── */
function ResearchCard({ r, bookmarked, onBookmark }) {
  const authors     = (r.authors || []).slice(0, 3).join(', ');
  const moreAuthors = (r.authors || []).length > 3 ? ` et al.` : '';
  const keywords    = (r.keywords || []).slice(0, 4);
  const moreKw      = (r.keywords || []).length > 4 ? `+${(r.keywords || []).length - 4}` : null;

  // Determine sources for badge row
  const src = r.source ? [r.source] : [];

  return (
    <div className="discover-result-card">
      <div className="discover-rc-body">
        <div className="discover-rc-thumb">
          <FileText size={28} strokeWidth={1} className="discover-rc-thumb-icon" />
        </div>
        <div className="discover-rc-content">
          <div className="discover-rc-top">
            <h3 className="discover-rc-title">{r.title || 'Untitled'}</h3>
            <button
              type="button"
              className={`discover-bookmark-btn ${bookmarked ? 'active' : ''}`}
              onClick={onBookmark}
              title={bookmarked ? 'Remove bookmark' : 'Bookmark'}
            >
              {bookmarked ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
            </button>
          </div>

          <div className="discover-rc-meta">
            {authors && <span>{authors}{moreAuthors}</span>}
            {r.venue && <span> · {r.venue}</span>}
            {r.year && <span className="discover-rc-year"> · {r.year}</span>}
          </div>

          {r.abstract && (
            <p className="discover-rc-abstract">{r.abstract}</p>
          )}

          {keywords.length > 0 && (
            <div className="discover-rc-tags">
              {keywords.map(kw => (
                <span key={kw} className="discover-tag">{kw}</span>
              ))}
              {moreKw && <span className="discover-tag discover-tag-more">+{moreKw.slice(1)}</span>}
            </div>
          )}

          <div className="discover-rc-footer">
            <div className="discover-rc-sources">
              {src.map(s => <SourceBadge key={s} source={s} />)}
            </div>
            <div className="discover-rc-right">
              {r.cited_by_count != null && (
                <span className="discover-rc-citations">
                  ¶ {r.cited_by_count.toLocaleString()} Citations
                </span>
              )}
              {r.year && <span className="discover-rc-yr">{r.year}</span>}
              <a
                href={r.url || r.pdf_url || (r.doi && `https://doi.org/${r.doi}`) || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="discover-view-btn"
              >
                View Details <ChevronRight size={13} />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── GitHub Card ── */
function GithubCard({ r }) {
  return (
    <div className="discover-result-card">
      <div className="discover-rc-content" style={{ padding: '1rem 1.25rem' }}>
        <div className="discover-rc-top">
          <h3 className="discover-rc-title">
            <a href={r.html_url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
              {r.full_name}
            </a>
          </h3>
        </div>
        <div className="discover-rc-meta">
          {r.language && <span>{r.language}</span>}
          {r.license && <span> · {r.license}</span>}
          {r.stars != null && <><span> · </span><Star size={11} style={{ verticalAlign: 'middle' }} /> {r.stars.toLocaleString()}</>}
          {r.forks != null && <><span> · </span><GitFork size={11} style={{ verticalAlign: 'middle' }} /> {r.forks.toLocaleString()}</>}
          {r.updated_at && <><span> · </span><Calendar size={11} style={{ verticalAlign: 'middle' }} /> {new Date(r.updated_at).toLocaleDateString()}</>}
        </div>
        {r.description && <p className="discover-rc-abstract">{r.description}</p>}
        {r.topics?.length > 0 && (
          <div className="discover-rc-tags">
            {r.topics.slice(0, 8).map(t => <span key={t} className="discover-tag">{t}</span>)}
          </div>
        )}
        <div className="discover-rc-footer" style={{ justifyContent: 'flex-end', marginTop: '0.75rem' }}>
          <a href={r.html_url} target="_blank" rel="noopener noreferrer" className="discover-view-btn">
            View Repo <ChevronRight size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}

/* ── Dataset Card ── */
function DatasetCard({ r }) {
  return (
    <div className="discover-result-card">
      <div className="discover-rc-content" style={{ padding: '1rem 1.25rem' }}>
        <div className="discover-rc-top">
          <h3 className="discover-rc-title">
            <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
              {r.id}
            </a>
          </h3>
        </div>
        <div className="discover-rc-meta">
          {r.downloads != null && <span>Downloads: {r.downloads.toLocaleString()}</span>}
          {r.likes != null && <span> · Likes: {r.likes}</span>}
          {r.last_modified && <span> · Updated {new Date(r.last_modified).toLocaleDateString()}</span>}
        </div>
        {r.tags?.length > 0 && (
          <div className="discover-rc-tags">
            {r.tags.slice(0, 10).map(t => <span key={t} className="discover-tag">{t}</span>)}
          </div>
        )}
        <div className="discover-rc-footer" style={{ justifyContent: 'flex-end', marginTop: '0.75rem' }}>
          <a href={r.url} target="_blank" rel="noopener noreferrer" className="discover-view-btn">
            View Dataset <ChevronRight size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}

/* ── Learning Card ── */
function LearningCard({ r }) {
  const typeIcon = r.type === 'video' ? <Play size={14} /> : r.type === 'course' ? <BookOpen size={14} /> : <FileText size={14} />;
  return (
    <div className="discover-result-card">
      <div className="discover-rc-content" style={{ padding: '1rem 1.25rem' }}>
        <div className="discover-rc-top">
          <h3 className="discover-rc-title">{r.title}</h3>
          <span className={`discover-learning-type discover-learning-type-${r.type}`}>
            {typeIcon} {r.type}
          </span>
        </div>
        <div className="discover-rc-meta">
          <span>{r.source}</span>
          {r.duration && <span> · {r.duration}</span>}
        </div>
        <p className="discover-rc-abstract">{r.description}</p>
        <div className="discover-rc-footer" style={{ justifyContent: 'flex-end', marginTop: '0.75rem' }}>
          <a href={r.url} target="_blank" rel="noopener noreferrer" className="discover-view-btn">
            Start Learning <ChevronRight size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}

export default Discover;