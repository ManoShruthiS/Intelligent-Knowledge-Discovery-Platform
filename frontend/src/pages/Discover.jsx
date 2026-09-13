import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, ExternalLink, FileText, GitBranch, Database, Play, Loader2,
  X, Plus, Folder, Check, AlertCircle, Quote, AlertTriangle, RotateCw
} from 'lucide-react';
import * as api from '../services/api';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import './Discover.css';


const FILTERS = [
  { id: 'all',      label: 'All',          icon: null },
  { id: 'papers',   label: 'Papers',       icon: FileText },
  { id: 'github',   label: 'Repositories', icon: GitBranch },
  { id: 'datasets', label: 'Datasets',     icon: Database },
  { id: 'learning', label: 'Learning',     icon: Play },
];


const SECTION_ORDER = ['papers', 'github', 'datasets', 'learning'];



const TOPIC_CHIPS = [
  'Artificial Intelligence',
  'Machine Learning',
  'Computer Vision',
  'Natural Language Processing',
  'Generative AI',
  'Deep Learning',
  'Transformers',
];







const SOURCE_ERROR_MESSAGE = 'This source did not respond. Please try again.';





const mapPapers = (r) => {
  
  
  const authorStr = Array.isArray(r.authors) && r.authors.length ? r.authors.join(', ') : null;
  const metaParts = [];
  if (authorStr) metaParts.push(authorStr);
  if (r.venue) metaParts.push(r.venue);
  return {
    id: r.id || r.doi || `paper-${Math.random().toString(36).slice(2, 9)}`,
    type: 'papers',
    typeLabel: 'Research Paper',
    title: r.title || 'Untitled paper',
    authors: authorStr,
    year: r.year || null,
    source: r.source || r.venue || null,
    sourceLabel: r.source ? r.source.charAt(0).toUpperCase() + r.source.slice(1) : null,
    description: r.abstract || null,
    url: r.url || r.pdf_url || (r.doi ? `https://doi.org/${r.doi}` : null),
    tags: Array.isArray(r.keywords) ? r.keywords : [],
    meta: metaParts.join(' · ') || null,
    extra: { citedBy: r.cited_by_count, venue: r.venue, doi: r.doi, openAccess: r.open_access },
    citationPayload: {
      title: r.title || 'Untitled paper',
      authors: Array.isArray(r.authors) ? r.authors.join('; ') : null,
      year: r.year || null,
      venue: r.venue || r.source || null,
      doi: r.doi || null,
      url: r.url || (r.doi ? `https://doi.org/${r.doi}` : null),
      abstract: r.abstract || null,
      source_type: 'discover_papers',
    }
  };
};

const mapGithub = (r) => {
  
  const metaParts = [];
  if (r.owner) metaParts.push(r.owner);
  if (r.language) metaParts.push(r.language);
  if (r.stars != null) metaParts.push(`${r.stars} ★`);
  return {
    id: r.html_url || r.url || `repo-${Math.random().toString(36).slice(2, 9)}`,
    type: 'github',
    typeLabel: 'GitHub Repository',
    title: r.full_name || r.title || r.url || 'Untitled repository',
    authors: r.owner || r.author || null,
    
    
    year: null,
    source: 'GitHub',
    sourceLabel: 'GitHub',
    description: r.description || null,
    url: r.html_url || r.url || null,
    tags: Array.isArray(r.topics) ? r.topics : [],
    meta: metaParts.join(' · ') || null,
    extra: { language: r.language, stars: r.stars, forks: r.forks },
    citationPayload: {
      title: r.full_name || r.title || r.url || 'Untitled repository',
      authors: r.owner || null,
      year: null,
      venue: r.language || null,
      doi: null,
      url: r.html_url || r.url || null,
      abstract: r.description || null,
      source_type: 'discover_github',
    }
  };
};

const mapDatasets = (r) => {
  
  const metaParts = [];
  if (r.source) metaParts.push(r.source);
  if (r.downloads != null) metaParts.push(`${r.downloads} downloads`);
  return {
    id: r.url || r.id || `dataset-${Math.random().toString(36).slice(2, 9)}`,
    type: 'datasets',
    typeLabel: 'Dataset',
    title: r.id || r.title || r.url || 'Untitled dataset',
    authors: r.source || r.author || null,
    
    year: r.last_modified ? String(r.last_modified).slice(0, 4) : null,
    source: r.source || 'HuggingFace',
    sourceLabel: r.source ? r.source.charAt(0).toUpperCase() + r.source.slice(1) : 'Hugging Face',
    description: r.description || null,
    url: r.url || null,
    tags: Array.isArray(r.tags) ? r.tags : [],
    meta: metaParts.join(' · ') || null,
    extra: { downloads: r.downloads, likes: r.likes },
    citationPayload: {
      title: r.id || r.title || r.url || 'Untitled dataset',
      authors: r.source || null,
      year: null,
      venue: r.source || 'HuggingFace',
      doi: null,
      url: r.url || null,
      abstract: r.description || null,
      source_type: 'discover_datasets',
    }
  };
};

const mapLearning = (r) => {
  
  const metaParts = [];
  if (r.creator) metaParts.push(r.creator);
  if (r.duration) metaParts.push(r.duration);
  
  let year = null;
  if (r.published) {
    const s = String(r.published);
    if (/^\d{4}/.test(s)) year = s.slice(0, 4);
    else year = s;
  }
  return {
    id: r.id || r.url || `learn-${Math.random().toString(36).slice(2, 9)}`,
    type: 'learning',
    typeLabel: 'Learning Resource',
    title: r.title || 'Untitled resource',
    authors: r.creator || null,
    year,
    source: r.platform || r.source || null,
    sourceLabel: r.platform || r.source || null,
    description: r.description || null,
    url: r.url || null,
    tags: Array.isArray(r.tags) ? r.tags : [],
    meta: metaParts.join(' · ') || null,
    extra: { thumbnail: r.thumbnail, duration: r.duration },
    citationPayload: {
      title: r.title || 'Untitled resource',
      authors: r.creator || null,
      year: r.published || null,
      venue: r.platform || r.source || null,
      doi: null,
      url: r.url || null,
      abstract: r.description || null,
      source_type: 'discover_learning',
    }
  };
};


const TAB_META = {
  papers:   { mapper: mapPapers,   openLabel: 'Open Original',     sectionTitle: 'Papers' },
  github:   { mapper: mapGithub,   openLabel: 'Open Repository',   sectionTitle: 'Repositories' },
  datasets: { mapper: mapDatasets, openLabel: 'Open Dataset',      sectionTitle: 'Datasets' },
  learning: { mapper: mapLearning, openLabel: 'Watch on YouTube',  sectionTitle: 'Learning' },
};


const EMPTY_SOURCE = { results: [], loading: false, error: null, queried: false };


const INITIAL_VISIBLE_COUNT = 4;


function SkeletonCard() {
  return (
    <div className="discover-result-card discover-skeleton-card">
      <div className="discover-result-body">
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <LoadingSkeleton width="70px" height="0.85rem" />
          <LoadingSkeleton width="50px" height="0.85rem" />
        </div>
        <LoadingSkeleton width="92%" height="1.05rem" />
        <LoadingSkeleton width="60%" height="0.85rem" />
        <LoadingSkeleton width="100%" height="0.85rem" count={3} />
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem' }}>
          <LoadingSkeleton width="40px" height="1.2rem" />
          <LoadingSkeleton width="60px" height="1.2rem" />
          <LoadingSkeleton width="50px" height="1.2rem" />
        </div>
      </div>
    </div>
  );
}

export default function Discover() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState('all');
  const [query, setQuery] = useState('');

  
  const [sources, setSources] = useState({
    papers:   { ...EMPTY_SOURCE },
    github:   { ...EMPTY_SOURCE },
    datasets: { ...EMPTY_SOURCE },
    learning: { ...EMPTY_SOURCE },
  });
  const [hasSearched, setHasSearched] = useState(false);

  
  
  const [expandedSources, setExpandedSources] = useState(() => new Set());

  
  
  
  
  const [cardSavePopoverId, setCardSavePopoverId] = useState(null);
  const [cardSaveStates, setCardSaveStates] = useState({});

  
  
  
  
  
  const [drawerResult, setDrawerResult] = useState(null);

  
  const [workspaces, setWorkspaces] = useState([]);
  const [wsLoading, setWsLoading] = useState(false);
  const [wsPickerOpen, setWsPickerOpen] = useState(false);
  const [saveState, setSaveState] = useState({ status: 'idle', workspaceId: null, message: null });

  
  const updateSource = (key, patch) => {
    setSources((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  };

  
  const toggleExpand = (sourceKey) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(sourceKey)) {
        next.delete(sourceKey);
      } else {
        next.add(sourceKey);
      }
      return next;
    });
  };

  
  
  
  
  
  const handleSearch = async (overrideQuery = null) => {
    const trimmed = (overrideQuery ?? query).trim();
    
    if (!trimmed) {
      setSources({
        papers:   { ...EMPTY_SOURCE },
        github:   { ...EMPTY_SOURCE },
        datasets: { ...EMPTY_SOURCE },
        learning: { ...EMPTY_SOURCE },
      });
      setExpandedSources(new Set());
      setHasSearched(false);
      return;
    }

    setHasSearched(true);
    
    setExpandedSources(new Set());

    
    const toCall = activeFilter === 'all'
      ? SECTION_ORDER
      : [activeFilter];

    
    
    
    setSources((prev) => {
      const next = { ...prev };
      SECTION_ORDER.forEach((key) => {
        if (toCall.includes(key)) {
          next[key] = { results: [], loading: true, error: null, queried: true };
        } else {
          next[key] = { ...EMPTY_SOURCE };
        }
      });
      return next;
    });

    await Promise.allSettled(toCall.map((key) => fetchSource(key, trimmed, {
      yearFrom: null,
      yearTo: null,
    })));
  };

  
  
  
  const fetchSource = async (key, trimmedQuery, parsedYears = {}) => {
    try {
      let data;
      let results = [];
      if (key === 'papers') {
        data = await api.discoverResearch(trimmedQuery, 10, {
          sortBy: 'relevance',
          yearFrom: parsedYears.yearFrom ?? null,
          yearTo: parsedYears.yearTo ?? null,
          openAccessOnly: false,
          minCitations: 0,
        });
        results = (data.results || []).map(mapPapers);
      } else if (key === 'github') {
        data = await api.discoverGithub(trimmedQuery, 12, 'best-match');
        results = (data.results || []).map(mapGithub);
      } else if (key === 'datasets') {
        data = await api.discoverDatasets(trimmedQuery, 12);
        results = (data.results || []).map(mapDatasets);
      } else if (key === 'learning') {
        data = await api.discoverLearning(trimmedQuery, 12);
        results = (data.results || []).map(mapLearning);
      }
      
      if (data?.note) {
        updateSource(key, { results, loading: false, error: null, note: data.note });
        return;
      }
      updateSource(key, { results, loading: false, error: null });
    } catch (err) {
      
      console.error(`Discover ${key} failed:`, err);
      updateSource(key, {
        results: [],
        loading: false,
        error: SOURCE_ERROR_MESSAGE,
      });
    }
  };

  
  
  
  const handleRetrySource = (key) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    updateSource(key, { results: [], loading: true, error: null });
    fetchSource(key, trimmed);
  };

  
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  
  
  const handleFilterChange = (filterId) => {
    setActiveFilter(filterId);
  };

  
  const openDrawer = (result) => {
    setDrawerResult(result);
    setSaveState({ status: 'idle', workspaceId: null, message: null });
    setWsPickerOpen(false);
    if (workspaces.length === 0 && !wsLoading) {
      loadWorkspaces();
    }
  };

  
  const closeDrawer = () => {
    setDrawerResult(null);
    setWsPickerOpen(false);
    setSaveState({ status: 'idle', workspaceId: null, message: null });
  };

  
  useEffect(() => {
    if (!drawerResult) return;
    const handler = (e) => {
      if (e.key === 'Escape') closeDrawer();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    
  }, [drawerResult]);

  
  const loadWorkspaces = async () => {
    setWsLoading(true);
    try {
      const data = await api.getWorkspaces();
      const list = Array.isArray(data)
        ? data
        : (data?.items || data?.workspaces || []);
      setWorkspaces(list);
    } catch (err) {
      
      console.error('Failed to load workspaces:', err);
      setWorkspaces([]);
    } finally {
      setWsLoading(false);
    }
  };

  
  const handleSaveToWorkspace = async (workspaceId) => {
    if (!drawerResult?.citationPayload) return;
    setSaveState({ status: 'saving', workspaceId, message: null });
    setWsPickerOpen(false);
    try {
      await api.addCitation({
        workspace_id: workspaceId,
        ...drawerResult.citationPayload,
      });
      const ws = workspaces.find((w) => w.id === workspaceId);
      const wsName = ws?.name || ws?.title || 'workspace';
      setSaveState({
        status: 'saved',
        workspaceId,
        message: `Saved to "${wsName}".`,
      });
    } catch (err) {
      
      console.error('Save to workspace failed:', err);
      setSaveState({
        status: 'error',
        workspaceId,
        message: 'Could not save to this workspace. Please try again.',
      });
    }
  };

  
  
  
  const toggleCardSavePopover = (resultId) => {
    setCardSavePopoverId((prev) => (prev === resultId ? null : resultId));
    if (workspaces.length === 0 && !wsLoading) {
      loadWorkspaces();
    }
  };

  const closeCardSavePopover = () => setCardSavePopoverId(null);

  
  const handleCardSave = async (result, workspaceId) => {
    if (!result?.citationPayload) return;
    const id = result.id;
    setCardSaveStates((prev) => ({
      ...prev,
      [id]: { status: 'saving', workspaceId, message: null },
    }));
    setCardSavePopoverId(null);
    try {
      await api.addCitation({
        workspace_id: workspaceId,
        ...result.citationPayload,
      });
      const ws = workspaces.find((w) => w.id === workspaceId);
      const wsName = ws?.name || ws?.title || 'workspace';
      setCardSaveStates((prev) => ({
        ...prev,
        [id]: { status: 'saved', workspaceId, message: `Saved to "${wsName}".` },
      }));
      
      setTimeout(() => {
        setCardSaveStates((prev) => {
          if (!prev[id] || prev[id].status !== 'saved') return prev;
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }, 3000);
    } catch (err) {
      
      console.error('Card save failed:', err);
      setCardSaveStates((prev) => ({
        ...prev,
        [id]: { status: 'error', workspaceId, message: 'Could not save to this workspace.' },
      }));
    }
  };

  
  const sortedWorkspaces = useMemo(() => {
    return [...workspaces].sort((a, b) => {
      const an = (a.name || a.title || '').toLowerCase();
      const bn = (b.name || b.title || '').toLowerCase();
      return an.localeCompare(bn);
    });
  }, [workspaces]);

  
  const visibleSections = activeFilter === 'all' ? SECTION_ORDER : [activeFilter];

  
  const activeMeta = drawerResult ? (TAB_META[drawerResult.type] || TAB_META.papers) : null;

  

  
  
  const formatCount = (source) => {
    if (source.loading) return '…';
    if (source.error) return '—';
    return String(source.results.length);
  };

  
  const renderSection = (sourceKey) => {
    const source = sources[sourceKey];
    const meta = TAB_META[sourceKey];

    
    
    if (!source.queried) return null;
    const hasContent = source.loading || source.error || source.results.length > 0;
    if (!hasContent) return null;

    const isExpanded = expandedSources.has(sourceKey);
    const cardsToShow = isExpanded
      ? source.results
      : source.results.slice(0, INITIAL_VISIBLE_COUNT);
    const canExpand = source.results.length > INITIAL_VISIBLE_COUNT && !source.loading && !source.error;

    return (
      <section key={sourceKey} className="discover-source-section">
        <header className="discover-source-section-header">
          <div className="discover-source-section-title">
            <h3>{meta.sectionTitle}</h3>
            <span className="discover-source-section-count">
              {source.loading
                ? 'Searching…'
                : source.error
                ? 'Unavailable'
                : `${source.results.length} result${source.results.length === 1 ? '' : 's'}`}
            </span>
          </div>
          {canExpand && (
            <button
              className="discover-view-all-btn"
              onClick={() => toggleExpand(sourceKey)}
            >
              {isExpanded ? 'Show less' : 'View all →'}
            </button>
          )}
        </header>

        {}
        {source.loading && (
          <div className="discover-results-grid">
            {Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {

}
        {!source.loading && source.error && (
          <div className="discover-source-error" role="alert">
            <div className="discover-source-error-icon">
              <AlertTriangle size={16} />
            </div>
            <div className="discover-source-error-body">
              <div className="discover-source-error-title">
                Unable to load {meta.sectionTitle}
              </div>
              <div className="discover-source-error-message">{source.error}</div>
            </div>
            <button
              type="button"
              className="discover-source-error-retry"
              onClick={() => handleRetrySource(sourceKey)}
            >
              <RotateCw size={14} /> Retry
            </button>
          </div>
        )}

        {}
        {!source.loading && !source.error && source.note && (
          <div className="discover-info-note">{source.note}</div>
        )}

        {}
        {!source.loading && !source.error && source.results.length > 0 && (
          <div className="discover-results-grid">
            {cardsToShow.map((res) => (
              <ResultCard
                key={res.id}
                result={res}
                onOpen={openDrawer}
                isSavePopoverOpen={cardSavePopoverId === res.id}
                onToggleSavePopover={() => toggleCardSavePopover(res.id)}
                onCloseSavePopover={closeCardSavePopover}
                saveState={cardSaveStates[res.id]}
                onSave={(workspaceId) => handleCardSave(res, workspaceId)}
                workspaces={sortedWorkspaces}
                wsLoading={wsLoading}
                onCreateWorkspace={() => {
                  closeCardSavePopover();
                  navigate('/workspaces');
                }}
              />
            ))}
          </div>
        )}
      </section>
    );
  };

  

  return (
    <div className="discover-root">

      {}
      <div className="discover-header">
        <h1>DISCOVER</h1>
        <p>Explore knowledge, resources, and ideas beyond your documents.</p>
      </div>

      {}
      <section className="discover-hero">
        <h2>Explore something new.</h2>
        <p>Search across papers, code, datasets, and learning resources.</p>
      </section>

      {}
      <div className="discover-search-row">
        <div className="discover-search-input-wrapper">
          <Search size={20} className="discover-search-icon" />
          <input
            type="text"
            placeholder="Search a topic, paper, author, technology, or idea..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <button className="discover-btn-search" onClick={handleSearch} disabled={anyLoading(sources)}>
          {anyLoading(sources) ? <Loader2 size={18} className="spin" /> : 'Discover'}
        </button>
      </div>

      {}
      <div className="discover-filters-row" role="tablist" aria-label="Source filters">
        {FILTERS.map((f) => {
          const Icon = f.icon;
          return (
            <button
              key={f.id}
              className={`discover-filter-chip ${activeFilter === f.id ? 'active' : ''}`}
              onClick={() => handleFilterChange(f.id)}
              role="tab"
              aria-selected={activeFilter === f.id}
            >
              {Icon && (
                <span className="discover-filter-chip-icon">
                  <Icon size={16} strokeWidth={2} />
                </span>
              )}
              {f.label}
            </button>
          );
        })}
      </div>

      {}
      <div className="discover-results-area">

        {
}
        {!hasSearched && (
          <div className="discover-topics">
            <div className="discover-topics-title">Explore popular topics</div>
            <div className="discover-topics-chips">
              {TOPIC_CHIPS.map((topic) => (
                <button
                  key={topic}
                  type="button"
                  className="discover-topic-chip"
                  onClick={() => {
                    setQuery(topic);
                    handleSearch(topic);
                  }}
                >
                  {topic}
                </button>
              ))}
            </div>
          </div>
        )}

        {
}
        {hasSearched && SECTION_ORDER.some((k) => sources[k].queried) && (
          <div className="discover-results-overview" role="status" aria-live="polite">
            <div className="discover-overview-query">
              Results for <strong>&ldquo;{query}&rdquo;</strong>
            </div>
            <div className="discover-overview-chips">
              {SECTION_ORDER.map((key) => {
                const source = sources[key];
                if (!source.queried) return null;
                const meta = TAB_META[key];
                return (
                  <div key={key} className="discover-overview-chip">
                    <span className="discover-overview-chip-label">{meta.sectionTitle}</span>
                    <span className="discover-overview-chip-count">{formatCount(source)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {}
        {hasSearched && visibleSections.map(renderSection)}
      </div>

      {}
      {drawerResult && activeMeta && (
        <DetailDrawer
          result={drawerResult}
          openLabel={activeMeta.openLabel}
          onClose={closeDrawer}
          sortedWorkspaces={sortedWorkspaces}
          wsLoading={wsLoading}
          wsPickerOpen={wsPickerOpen}
          setWsPickerOpen={setWsPickerOpen}
          saveState={saveState}
          onSave={handleSaveToWorkspace}
          onCreateWorkspace={() => {
            closeDrawer();
            navigate('/workspaces');
          }}
        />
      )}
    </div>
  );
}


function anyLoading(sources) {
  return Object.values(sources).some((s) => s.loading);
}













function ResultCard({
  result, onOpen,
  isSavePopoverOpen, onToggleSavePopover, onCloseSavePopover,
  saveState, onSave, workspaces, wsLoading, onCreateWorkspace,
}) {
  
  const saveWrapRef = useRef(null);
  useEffect(() => {
    if (!isSavePopoverOpen) return undefined;
    const handler = (e) => {
      if (saveWrapRef.current && !saveWrapRef.current.contains(e.target)) {
        onCloseSavePopover();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isSavePopoverOpen, onCloseSavePopover]);

  
  const handleOpenClick = (e) => {
    e.stopPropagation();
    if (result.url) {
      window.open(result.url, '_blank', 'noopener,noreferrer');
    }
  };

  
  const handleSaveClick = (e) => {
    e.stopPropagation();
    onToggleSavePopover();
  };

  
  const handlePickWorkspace = (e, workspaceId) => {
    e.stopPropagation();
    onSave(workspaceId);
  };

  
  const handleCreateNew = (e) => {
    e.stopPropagation();
    onCloseSavePopover();
    onCreateWorkspace();
  };

  const saving = saveState?.status === 'saving';
  const saved = saveState?.status === 'saved';

  return (
    <div
      className="discover-result-card"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(result)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(result);
        }
      }}
    >
      {}
      {result.extra?.thumbnail && (
        <div className="discover-result-thumb">
          <img src={result.extra.thumbnail} alt="" loading="lazy" />
        </div>
      )}

      <div className="discover-result-body">
        {}
        <div className="discover-result-tagline">
          <span className="discover-result-type-tag">{result.typeLabel}</span>
          {result.sourceLabel && (
            <span className="discover-result-source-tag">{result.sourceLabel}</span>
          )}
        </div>

        <h4 className="discover-result-title">{result.title}</h4>

        {
}
        {result.meta && (
          <p className="discover-result-meta">{result.meta}</p>
        )}

        {result.description && (
          <p className="discover-result-desc">{result.description}</p>
        )}

        {}
        <div className="discover-result-bottom">
          <div className="discover-result-tags">
            {result.year && <span className="discover-result-year">{result.year}</span>}
            {result.tags && result.tags.slice(0, 4).map((tag) => (
              <span key={tag} className="discover-tag">{tag}</span>
            ))}
          </div>

          <div className="discover-result-actions">
            {result.url && (
              <button
                type="button"
                className="discover-btn-open"
                onClick={handleOpenClick}
                title={`Open ${result.typeLabel}`}
              >
                <ExternalLink size={14} /> Open
              </button>
            )}
            <div className="discover-card-save-wrap" ref={saveWrapRef}>
              <button
                type="button"
                className={`discover-btn-save ${saved ? 'saved' : ''} ${saving ? 'saving' : ''}`}
                onClick={handleSaveClick}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 size={14} className="spin" />
                ) : saved ? (
                  <Check size={14} />
                ) : (
                  <Folder size={14} />
                )}
                {saving ? 'Saving…' : saved ? 'Saved' : 'Save'}
              </button>
              {isSavePopoverOpen && (
                <div
                  className="discover-card-save-popover"
                  onClick={(e) => e.stopPropagation()}
                  role="menu"
                >
                  <div className="discover-card-save-popover-title">Save to workspace</div>
                  {wsLoading ? (
                    <div className="discover-card-save-loading">
                      <Loader2 size={14} className="spin" /> Loading…
                    </div>
                  ) : workspaces.length === 0 ? (
                    <div className="discover-card-save-empty">
                      <p>You don't have any workspaces yet.</p>
                      <button type="button" onClick={handleCreateNew}>
                        <Plus size={12} /> Create a workspace
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="discover-card-save-list">
                        {workspaces.map((ws) => (
                          <button
                            key={ws.id}
                            type="button"
                            className="discover-card-save-item"
                            onClick={(e) => handlePickWorkspace(e, ws.id)}
                            role="menuitem"
                          >
                            <Folder size={12} />
                            <span>{ws.name || ws.title || 'Untitled workspace'}</span>
                          </button>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="discover-card-save-new"
                        onClick={handleCreateNew}
                      >
                        <Plus size={12} /> New workspace
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}



function DetailDrawer({
  result, openLabel, onClose,
  sortedWorkspaces, wsLoading, wsPickerOpen, setWsPickerOpen,
  saveState, onSave, onCreateWorkspace,
}) {
  const {
    title, authors, year, source, description, url, tags, typeLabel, extra, citationPayload
  } = result;

  
  const authorList = authors
    ? authors.split(/;|,\s*(?=[A-Z])/).map((a) => a.trim()).filter(Boolean)
    : [];

  const longDescription = description || 'No description provided for this resource.';

  const headerIcon = typeLabel === 'Research Paper'
    ? <FileText size={20} />
    : typeLabel === 'GitHub Repository'
    ? <GitBranch size={20} />
    : typeLabel === 'Dataset'
    ? <Database size={20} />
    : <Play size={20} />;

  return (
    <div className="discover-drawer-overlay" onClick={onClose}>
      <aside
        className="discover-drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title || 'Result details'}
      >
        <header className="discover-drawer-header">
          <div className="discover-drawer-header-left">
            <div className="discover-drawer-type-icon">{headerIcon}</div>
            <div className="discover-drawer-type-label">{typeLabel}</div>
          </div>
          <button className="discover-drawer-close" onClick={onClose} aria-label="Close drawer">
            <X size={18} />
          </button>
        </header>

        {extra?.thumbnail ? (
          <a
            className="discover-drawer-thumb"
            href={url || '#'}
            target="_blank"
            rel="noopener noreferrer"
          >
            <img src={extra.thumbnail} alt="" />
          </a>
        ) : (
          <div className="discover-drawer-banner">
            <Quote size={28} />
          </div>
        )}

        <div className="discover-drawer-body">
          <h2 className="discover-drawer-title">{title}</h2>

          <div className="discover-drawer-meta">
            {authors && (
              <div className="discover-drawer-authors">{authors}</div>
            )}
            <div className="discover-drawer-meta-pills">
              {source && <span className="discover-result-source-tag">{source}</span>}
              {year && <span className="discover-result-year">{year}</span>}
              {extra?.citedBy != null && (
                <span className="discover-result-year">{extra.citedBy} citations</span>
              )}
              {extra?.stars != null && (
                <span className="discover-result-year">{extra.stars} ★</span>
              )}
              {extra?.downloads != null && (
                <span className="discover-result-year">{extra.downloads} downloads</span>
              )}
              {extra?.duration && (
                <span className="discover-result-year">{extra.duration}</span>
              )}
            </div>
          </div>

          {authorList.length > 1 && (
            <div className="discover-drawer-author-chips">
              {authorList.map((a, i) => (
                <span key={`${a}-${i}`} className="discover-drawer-author-chip">{a}</span>
              ))}
            </div>
          )}

          <section className="discover-drawer-section">
            <h3>{typeLabel === 'Research Paper' ? 'Abstract' : 'Description'}</h3>
            <p>{longDescription}</p>
          </section>

          {extra?.venue && (
            <section className="discover-drawer-section">
              <h3>Venue</h3>
              <p>{extra.venue}</p>
            </section>
          )}
          {extra?.doi && (
            <section className="discover-drawer-section">
              <h3>DOI</h3>
              <p className="discover-drawer-mono">{extra.doi}</p>
            </section>
          )}
          {extra?.language && (
            <section className="discover-drawer-section">
              <h3>Language</h3>
              <p>{extra.language}</p>
            </section>
          )}

          {tags && tags.length > 0 && (
            <section className="discover-drawer-section">
              <h3>Tags</h3>
              <div className="discover-result-tags">
                {tags.map((tag) => (
                  <span key={tag} className="discover-tag">{tag}</span>
                ))}
              </div>
            </section>
          )}

          <section className="discover-drawer-section discover-drawer-actions">
            <div className="discover-drawer-save">
              <h3>Save to workspace</h3>
              <div className="discover-drawer-save-controls">
                <button
                  className="discover-drawer-save-btn"
                  onClick={() => setWsPickerOpen((v) => !v)}
                  disabled={wsLoading || saveState.status === 'saving'}
                >
                  {saveState.status === 'saving' ? (
                    <Loader2 size={16} className="spin" />
                  ) : saveState.status === 'saved' ? (
                    <Check size={16} />
                  ) : (
                    <Folder size={16} />
                  )}
                  {saveState.status === 'saved'
                    ? 'Saved'
                    : saveState.status === 'saving'
                    ? 'Saving…'
                    : 'Choose a workspace'}
                </button>
                {url && (
                  <button
                    className="discover-drawer-open-btn"
                    onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}
                  >
                    <ExternalLink size={16} /> {openLabel}
                  </button>
                )}
              </div>

              {wsPickerOpen && (
                <div className="discover-ws-picker">
                  {wsLoading ? (
                    <div className="discover-ws-picker-loading">
                      <Loader2 size={16} className="spin" /> Loading workspaces…
                    </div>
                  ) : sortedWorkspaces.length === 0 ? (
                    <div className="discover-ws-picker-empty">
                      <p>You don't have any workspaces yet.</p>
                      <button className="discover-ws-picker-create" onClick={onCreateWorkspace}>
                        <Plus size={14} /> Create a workspace
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="discover-ws-picker-list">
                        {sortedWorkspaces.map((ws) => (
                          <button
                            key={ws.id}
                            className="discover-ws-picker-item"
                            onClick={() => onSave(ws.id)}
                          >
                            <Folder size={14} />
                            <span>{ws.name || ws.title || 'Untitled workspace'}</span>
                          </button>
                        ))}
                      </div>
                      <button className="discover-ws-picker-create" onClick={onCreateWorkspace}>
                        <Plus size={14} /> New workspace
                      </button>
                    </>
                  )}
                </div>
              )}

              {saveState.message && (
                <div className={`discover-drawer-save-msg ${saveState.status}`}>
                  {saveState.status === 'error' && <AlertCircle size={14} />}
                  {saveState.status === 'saved' && <Check size={14} />}
                  <span>{saveState.message}</span>
                </div>
              )}
            </div>
          </section>

          {citationPayload && (
            <section className="discover-drawer-section discover-drawer-bibtex">
              <h3>Citation preview</h3>
              <div className="discover-drawer-cite-row">
                <span className="discover-drawer-cite-key">@article</span>
                <span className="discover-drawer-cite-text">
                  {citationPayload.authors || 'Unknown authors'}
                  {citationPayload.year ? ` (${citationPayload.year}).` : '.'}{' '}
                  <em>{citationPayload.title}</em>
                  {citationPayload.venue ? `. ${citationPayload.venue}.` : ''}
                  {citationPayload.doi ? ` doi:${citationPayload.doi}.` : citationPayload.url ? ` ${citationPayload.url}` : ''}
                </span>
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
