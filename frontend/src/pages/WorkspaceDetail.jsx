import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Search, Plus, Filter, MessageSquare, Trash2, X, Bot, Send, RotateCcw, Eraser, Download } from 'lucide-react';
import Orbot from '../components/common/Orbot';
import MarkdownMessage from '../components/common/MarkdownMessage';
import CompareTab from './workspace_tabs/CompareTab';
import NotesTab from './workspace_tabs/NotesTab';
import BriefTab from './workspace_tabs/BriefTab';
import ProjectPlanTab from './workspace_tabs/ProjectPlanTab';
import ExperimentsTab from './workspace_tabs/ExperimentsTab';
import CitationsTab from './workspace_tabs/CitationsTab';
import TemplatesTab from './workspace_tabs/TemplatesTab';
import WorkspaceIntelligenceTabs from '../components/workspace/WorkspaceIntelligenceTabs';
import { getWorkspace, removeDocumentFromWorkspace, addDocumentToWorkspace, getDocuments, askOrbot, getBrief, getProjectPlan, listNotes, listCitations } from '../services/api';
import './WorkspaceDetail.css';

function WorkspaceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Papers');
  
  const [workspace, setWorkspace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const [paperSearch, setPaperSearch] = useState('');

  // Add Document Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [allDocs, setAllDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  
  // Chat State
  const [query, setQuery] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState(() => {
    try {
      const raw = sessionStorage.getItem(`kno.workspace.${id}`);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  });
  const [chatMode, setChatMode] = useState('research');

  // Persist across tab switches.
  useEffect(() => {
    if (!id) return;
    try {
      sessionStorage.setItem(`kno.workspace.${id}`, JSON.stringify(chatHistory));
    } catch (_) {}
  }, [chatHistory, id]);

  const handleClearWorkspaceChat = () => {
    if (!window.confirm('Clear the conversation for this workspace?')) return;
    setChatHistory([]);
    if (id) {
      try { sessionStorage.removeItem(`kno.workspace.${id}`); } catch (_) {}
    }
  };

  useEffect(() => {
    fetchWorkspace();
  }, [id]);

  const fetchWorkspace = async () => {
    try {
      setLoading(true);
      const data = await getWorkspace(id);
      setWorkspace(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAddModal = async () => {
    setShowAddModal(true);
    setLoadingDocs(true);
    setActionError(null);
    try {
      const docs = await getDocuments();
      setAllDocs(docs);
    } catch (err) {
      setActionError(err.message || 'Failed to load documents.');
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleAddDocument = async (docId) => {
    setActionError(null);
    try {
      await addDocumentToWorkspace(id, docId);
      fetchWorkspace();
      setShowAddModal(false);
    } catch (err) {
      setActionError(err.message || 'Failed to add document to workspace.');
    }
  };

  const handleRemoveDocument = async (e, docId) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to remove this document from the workspace?")) return;
    setActionError(null);
    try {
      await removeDocumentFromWorkspace(id, docId);
      setWorkspace(prev => ({
        ...prev,
        documents: prev.documents.filter(d => d.id !== docId)
      }));
    } catch (err) {
      setActionError(err.message || 'Failed to remove document from workspace.');
    }
  };

  const sendChatQuestion = async (question, historyAtSend) => {
    const data = await askOrbot({
      message: question,
      mode: chatMode,
      history: historyAtSend,
      workspaceId: id,
      topK: 5,
    });
    setChatHistory(prev => [
      ...prev,
      {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || [],
        trace: data.trace || null,
        confidence: data.confidence || null,
      },
    ]);
  };

  const handleChatSend = async (text) => {
    const question = (text ?? query).trim();
    if (!question || isChatLoading) return;

    setChatHistory(prev => [...prev, { role: 'user', content: question }]);
    setQuery('');
    setIsChatLoading(true);

    const priorHistory = chatHistory;
    try {
      await sendChatQuestion(question, priorHistory);
    } catch (err) {
      setChatHistory(prev => [
        ...prev,
        { role: 'error', content: err.message || 'Unable to reach ORBOT.' },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleChatRetry = async (errorIdx) => {
    if (isChatLoading) return;
    let userIdx = errorIdx - 1;
    while (userIdx >= 0 && chatHistory[userIdx].role !== 'user') {
      userIdx -= 1;
    }
    if (userIdx < 0) return;
    const original = chatHistory[userIdx];
    const question = (original.content || '').trim();
    if (!question) return;

    setChatHistory(prev => prev.slice(0, userIdx + 1));
    setIsChatLoading(true);

    const priorHistory = chatHistory.slice(0, userIdx);
    try {
      await sendChatQuestion(question, priorHistory);
    } catch (err) {
      setChatHistory(prev => [
        ...prev,
        { role: 'error', content: err.message || 'Unable to reach ORBOT.' },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleChatKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSend();
    }
  };

  const handleExportWorkspace = async () => {
    try {
      const [brief, plan, notesRes, citationsRes] = await Promise.all([
        getBrief(id).catch(() => null),
        getProjectPlan(id).catch(() => null),
        listNotes(id).catch(() => ({ items: [] })),
        listCitations(id).catch(() => ({ citations: [] })),
      ]);

      const docs = workspace.documents || [];
      const notes = notesRes.items || notesRes || [];
      const citations = citationsRes.citations || citationsRes || [];

      let md = `# ${workspace.name}\n\n`;
      md += `**Description:** ${workspace.description || 'None'}\n\n`;
      md += `**Created:** ${new Date(workspace.created_at).toLocaleString()}\n\n`;
      md += `---\n\n`;

      md += `## Documents (${docs.length})\n\n`;
      if (docs.length === 0) {
        md += `_No documents in this workspace._\n\n`;
      } else {
        docs.forEach((d, i) => {
          md += `${i + 1}. **${d.filename}** (${d.file_type})\n`;
        });
        md += '\n';
      }

      if (brief) {
        md += `## Research Brief\n\n`;
        if (brief.topic) md += `**Topic:** ${brief.topic}\n\n`;
        if (brief.problem) md += `**Problem:** ${brief.problem}\n\n`;
        if (brief.research_question) md += `**Research Question:** ${brief.research_question}\n\n`;
        if (brief.objectives) md += `**Objectives:** ${brief.objectives}\n\n`;
        if (brief.key_findings) md += `**Key Findings:** ${brief.key_findings}\n\n`;
        if (brief.common_limitations) md += `**Limitations:** ${brief.common_limitations}\n\n`;
        if (brief.potential_gap) md += `**Potential Gap:** ${brief.potential_gap}\n\n`;
        if (brief.proposed_direction) md += `**Proposed Direction:** ${brief.proposed_direction}\n\n`;
        if (brief.open_questions) md += `**Open Questions:** ${brief.open_questions}\n\n`;
        md += '\n';
      }

      if (plan) {
        md += `## Project Plan\n\n`;
        if (plan.problem_statement) md += `**Problem Statement:** ${plan.problem_statement}\n\n`;
        if (plan.objectives) md += `**Objectives:** ${plan.objectives}\n\n`;
        if (plan.requirements) md += `**Requirements:** ${plan.requirements}\n\n`;
        if (plan.architecture) md += `**Architecture:** ${plan.architecture}\n\n`;
        if (plan.technology_stack) md += `**Technology Stack:** ${plan.technology_stack}\n\n`;
        if (plan.implementation_stages) md += `**Implementation Stages:** ${plan.implementation_stages}\n\n`;
        if (plan.testing_strategy) md += `**Testing Strategy:** ${plan.testing_strategy}\n\n`;
        if (plan.evaluation_metrics) md += `**Evaluation Metrics:** ${plan.evaluation_metrics}\n\n`;
        if (plan.deployment_plan) md += `**Deployment Plan:** ${plan.deployment_plan}\n\n`;
        md += '\n';
      }

      if (notes.length > 0) {
        md += `## Notes (${notes.length})\n\n`;
        notes.forEach((n, i) => {
          md += `### ${n.title}\n\n${n.content}\n\n`;
        });
      }

      if (citations.length > 0) {
        md += `## Citations (${citations.length})\n\n`;
        citations.forEach((c, i) => {
          const authors = c.authors ? c.authors : 'Unknown';
          const year = c.year ? c.year : 'n.d.';
          md += `${i + 1}. ${authors}. "${c.title}." ${c.venue || ''} (${year})`;
          if (c.doi) md += ` DOI: ${c.doi}`;
          if (c.url) md += ` [${c.url}]`;
          md += '\n';
        });
        md += '\n';
      }

      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${workspace.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_export.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(err.message || 'Failed to export workspace.');
    }
  };

  if (loading) return <div className="ws-detail-container"><div className="loading-state">Loading workspace...</div></div>;
  if (error) return <div className="ws-detail-container"><div className="error-state">{error}</div></div>;
  if (!workspace) return null;

  // Filter docs out that are already in workspace
  const workspaceDocIds = new Set(workspace.documents.map(d => d.id));
  const availableDocs = allDocs.filter(d => !workspaceDocIds.has(d.id));

  return (
    <div className="ws-detail-container">
      <button className="back-btn" onClick={() => navigate('/workspaces')}>
        <ArrowLeft size={16} />
        Back to Workspaces
      </button>

      <div className="ws-detail-header">
        <div className="ws-title-area">
          <h1>{workspace.name}</h1>
          <p>{workspace.description || 'Organize, analyze, and synthesize knowledge for this topic.'}</p>
        </div>
        <div className="ws-actions">
          <button className="btn-primary" onClick={handleExportWorkspace}>
            <Download size={18} /> Export Workspace
          </button>
          <button className="btn-primary" onClick={() => setActiveTab('Ask ORBOT')}>
            <MessageSquare size={18} /> Chat with Workspace
          </button>
        </div>
      </div>

      <div className="ws-tabs" role="tablist" aria-label="Workspace tabs">
        {['Overview', 'Papers', 'Compare', 'Ask ORBOT', 'Intelligence', 'Notes', 'Brief', 'Plan', 'Experiments', 'Citations', 'Templates'].map((tab, idx, arr) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`tabpanel-${tab.replace(/\s+/g, '-').toLowerCase()}`}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => { setActiveTab(tab); setActionError(null); }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') {
                e.preventDefault();
                const next = arr[(idx + 1) % arr.length];
                e.target.closest('[role="tablist"]').querySelectorAll('[role="tab"]')[(idx + 1) % arr.length].focus();
              } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                const prev = arr[(idx - 1 + arr.length) % arr.length];
                e.target.closest('[role="tablist"]').querySelectorAll('[role="tab"]')[(idx - 1 + arr.length) % arr.length].focus();
              }
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {actionError && (
        <div className="error-state" role="alert" style={{ margin: '0 0 1rem 0' }}>{actionError}</div>
      )}

      {activeTab === 'Overview' && (
        <div className="ws-synthesize-view">
           <div className="synthesize-empty" style={{textAlign: 'left', alignItems: 'flex-start', padding: '2rem'}}>
             <h2>Workspace Details</h2>
             <p><strong>Name:</strong> {workspace.name}</p>
             <p><strong>Description:</strong> {workspace.description || 'None'}</p>
             <p><strong>Created:</strong> {new Date(workspace.created_at).toLocaleString()}</p>
             <p><strong>Total Papers:</strong> {workspace.documents?.length || 0}</p>
           </div>
        </div>
      )}

      {activeTab === 'Compare' && (
        <CompareTab workspaceId={id} documents={workspace.documents || []} />
      )}

      {activeTab === 'Papers' && (
        <div className="ws-docs-view">
          <div className="docs-toolbar">
            <div className="search-box">
              <Search size={18} color="var(--c-888)" />
              <input type="text" placeholder="Search papers in workspace..." value={paperSearch} onChange={(e) => setPaperSearch(e.target.value)} />
            </div>
            <div className="toolbar-actions">
              <button className="btn-primary" onClick={handleOpenAddModal}><Plus size={16} /> Add Paper</button>
            </div>
          </div>

          <div className="docs-list">
            <div className="docs-list-header">
              <div className="col-name">Name</div>
              <div className="col-status">Status</div>
              <div className="col-date">Date added</div>
            </div>
            
            {workspace.documents?.length === 0 ? (
              <div className="empty-state" style={{minHeight: '200px'}}>
                <p>No papers attached to this workspace.</p>
              </div>
            ) : (
              workspace.documents.filter(doc => !paperSearch || doc.filename.toLowerCase().includes(paperSearch.toLowerCase())).map(doc => (
                <div key={doc.id} className="doc-list-item" onClick={() => navigate(`/documents/${doc.id}`)}>
                  <div className="col-name">
                    <FileText size={18} color="var(--c-555)" />
                    <span>{doc.filename}</span>
                  </div>
                  <div className="col-status">
                    <button className="btn-icon delete-btn" onClick={(e) => handleRemoveDocument(e, doc.id)} title="Remove from workspace">
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <div className="col-date">{new Date(doc.added_at).toLocaleDateString()}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === 'Intelligence' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <WorkspaceIntelligenceTabs workspaceId={id} />
        </div>
      )}

      {activeTab === 'Notes' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <NotesTab workspaceId={id} />
        </div>
      )}

      {activeTab === 'Brief' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <BriefTab workspaceId={id} />
        </div>
      )}

      {activeTab === 'Plan' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <ProjectPlanTab workspaceId={id} />
        </div>
      )}

      {activeTab === 'Experiments' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <ExperimentsTab workspaceId={id} />
        </div>
      )}

      {activeTab === 'Citations' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <CitationsTab workspaceId={id} documents={workspace.documents || []} />
        </div>
      )}

      {activeTab === 'Templates' && (
        <div style={{ flex: 1, padding: '1rem 2rem 2rem 2rem' }}>
          <TemplatesTab workspaceId={id} />
        </div>
      )}

      {activeTab === 'Ask ORBOT' && (
        <div className="ws-chat-view" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0 2rem 2rem 2rem' }}>
          {chatHistory.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleClearWorkspaceChat}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              >
                <Eraser size={12} /> Clear conversation
              </button>
            </div>
          )}
          <div className="chat-history" style={{ flex: 1, overflowY: 'auto', marginBottom: '1rem' }}>
            {chatHistory.length === 0 ? (
              <div className="ask-ai-empty" style={{ textAlign: 'center', marginTop: '4rem' }}>
                <Orbot size={80} state="idle" />
                <h2>Chat with this workspace</h2>
                <p>Ask questions about any of the papers in {workspace.name}</p>
              </div>
            ) : (
              chatHistory.map((msg, idx) => (
                <div key={idx} className={`chat-message ${msg.role}`} style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', padding: '1rem', borderRadius: '8px', backgroundColor: (msg.role === 'assistant' || msg.role === 'error') ? 'var(--c-fafafa)' : 'var(--c-white)', border: (msg.role === 'assistant' || msg.role === 'error') ? '1px solid var(--c-eee)' : 'none' }}>
                  <div className="message-icon">
                    {(msg.role === 'assistant' || msg.role === 'error') ? <Bot size={24} /> : <div style={{width:24, height:24, borderRadius:'50%', backgroundColor:'var(--c-111)'}}></div>}
                  </div>
                  <div className="message-content" style={{ flex: 1 }}>
                    {msg.role === 'assistant' ? (
                      <MarkdownMessage
                        content={msg.content}
                        trace={msg.trace}
                        confidence={msg.confidence}
                      />
                    ) : msg.role === 'error' ? (
                      <>
                        <div className="text" style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{msg.content}</div>
                        <div style={{ marginTop: '0.5rem' }}>
                          <button
                            type="button"
                            className="orbot-retry-btn"
                            onClick={() => handleChatRetry(idx)}
                            disabled={isChatLoading}
                          >
                            <RotateCcw size={14} /> Retry
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="text" style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{msg.content}</div>
                    )}
                    {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                      <div className="sources-container" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--c-eee)' }}>
                        <span style={{ fontSize: '0.8rem', color: 'var(--c-555)', fontWeight: 500, display: 'block', marginBottom: '0.5rem' }}>SOURCES</span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                          {msg.sources.map((source, sIdx) => (
                            <div key={sIdx} style={{ fontSize: '0.8rem', backgroundColor: 'var(--c-white)', border: '1px solid var(--c-ddd)', padding: '0.25rem 0.5rem', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '4px' }} title={`Similarity: ${source.similarity}`}>
                              <FileText size={12} />
                              {source.filename} {source.page_number ? `· Page ${source.page_number}` : ''}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isChatLoading && (
              <div className="chat-message assistant loading" style={{ display: 'flex', gap: '1rem', padding: '1rem' }}>
                <Orbot size={24} state="searching" />
                <div style={{ padding: '0.5rem' }}>
                  ORBOT is thinking...
                </div>
              </div>
            )}
          </div>

          <div className="chat-input-area" style={{ border: '1px solid var(--c-ddd)', borderRadius: '8px', padding: '0.5rem', display: 'flex', alignItems: 'center', backgroundColor: 'var(--c-white)' }}>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleChatKeyDown}
              placeholder={`Ask about the ${workspace.documents?.length || 0} papers in this workspace...`}
              style={{ flex: 1, border: 'none', resize: 'none', padding: '0.5rem', outline: 'none', fontFamily: 'inherit' }}
              rows={1}
            />
            <div className="chat-mode-toggle" role="tablist" aria-label="ORBOT mode">
              <button
                type="button"
                role="tab"
                aria-selected={chatMode === 'research'}
                className={`chat-mode-btn ${chatMode === 'research' ? 'active' : ''}`}
                onClick={() => setChatMode('research')}
              >
                Research
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={chatMode === 'project'}
                className={`chat-mode-btn ${chatMode === 'project' ? 'active' : ''}`}
                onClick={() => setChatMode('project')}
              >
                Project
              </button>
            </div>
            <button
              className="btn-icon"
              style={{ backgroundColor: 'var(--c-111)', color: 'white', borderRadius: '4px', padding: '0.5rem', marginLeft: '0.5rem' }}
              onClick={() => handleChatSend()}
              disabled={!query.trim() || isChatLoading}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      )}

      {/* Add Document Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ width: '600px', maxWidth: '90vw' }}>
            <div className="modal-header">
              <h2>Add Paper to Workspace</h2>
              <button className="btn-icon" onClick={() => setShowAddModal(false)} aria-label="Close add paper dialog"><X size={20} /></button>
            </div>
            <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              {loadingDocs ? (
                <div className="loading-state">Loading documents...</div>
              ) : availableDocs.length === 0 ? (
                <div className="empty-state">No more documents available to add. Upload new documents from the Library.</div>
              ) : (
                <div className="docs-list">
                  {availableDocs.map(doc => (
                    <div key={doc.id} className="doc-list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--c-eee)', padding: '1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <FileText size={18} color="var(--c-555)" />
                        <span style={{ fontWeight: 500 }}>{doc.filename}</span>
                      </div>
                      <button className="btn-primary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }} onClick={() => handleAddDocument(doc.id)}>
                        Add
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default WorkspaceDetail;
