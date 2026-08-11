import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Search, Plus, Filter, MessageSquare, Trash2, X, Bot, Send } from 'lucide-react';
import Orbot from '../components/common/Orbot';
import { getWorkspace, removeDocumentFromWorkspace, addDocumentToWorkspace, getDocuments, askWorkspace } from '../services/api';
import './WorkspaceDetail.css';

function WorkspaceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Papers');
  
  const [workspace, setWorkspace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Add Document Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [allDocs, setAllDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  
  // Chat State
  const [query, setQuery] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [chatError, setChatError] = useState('');

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
    try {
      const docs = await getDocuments();
      setAllDocs(docs);
    } catch (err) {
      alert("Failed to load documents: " + err.message);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleAddDocument = async (docId) => {
    try {
      await addDocumentToWorkspace(id, docId);
      // Refresh workspace docs
      fetchWorkspace();
      setShowAddModal(false);
    } catch (err) {
      alert("Failed to add document: " + err.message);
    }
  };

  const handleRemoveDocument = async (e, docId) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to remove this document from the workspace?")) {
      try {
        await removeDocumentFromWorkspace(id, docId);
        setWorkspace(prev => ({
          ...prev,
          documents: prev.documents.filter(d => d.id !== docId)
        }));
      } catch (err) {
        alert("Failed to remove document: " + err.message);
      }
    }
  };

  const handleChatSend = async (text) => {
    const question = text || query;
    if (!question.trim()) return;

    const newMessage = { role: 'user', content: question };
    setChatHistory(prev => [...prev, newMessage]);
    setQuery('');
    setIsChatLoading(true);
    setChatError('');

    try {
      const data = await askWorkspace(id, question);
      const aiMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || []
      };
      setChatHistory(prev => [...prev, aiMessage]);
    } catch (err) {
      setChatError(err.message);
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
          <button className="btn-primary" onClick={() => setActiveTab('Ask ORBOT')}>
            <MessageSquare size={18} /> Chat with Workspace
          </button>
        </div>
      </div>

      <div className="ws-tabs">
        {['Overview', 'Papers', 'Ask ORBOT'].map(tab => (
          <button 
            key={tab} 
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

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

      {activeTab === 'Papers' && (
        <div className="ws-docs-view">
          <div className="docs-toolbar">
            <div className="search-box">
              <Search size={18} color="var(--c-888)" />
              <input type="text" placeholder="Search papers in workspace..." />
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
              workspace.documents.map(doc => (
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

      {activeTab === 'Ask ORBOT' && (
        <div className="ws-chat-view" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0 2rem 2rem 2rem' }}>
          <div className="chat-history" style={{ flex: 1, overflowY: 'auto', marginBottom: '1rem' }}>
            {chatHistory.length === 0 ? (
              <div className="ask-ai-empty" style={{ textAlign: 'center', marginTop: '4rem' }}>
                <Orbot size={80} state="idle" />
                <h2>Chat with this workspace</h2>
                <p>Ask questions about any of the papers in {workspace.name}</p>
              </div>
            ) : (
              chatHistory.map((msg, idx) => (
                <div key={idx} className={`chat-message ${msg.role}`} style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', padding: '1rem', borderRadius: '8px', backgroundColor: msg.role === 'assistant' ? 'var(--c-fafafa)' : 'var(--c-white)', border: msg.role === 'assistant' ? '1px solid var(--c-eee)' : 'none' }}>
                  <div className="message-icon">
                    {msg.role === 'assistant' ? <Bot size={24} /> : <div style={{width:24, height:24, borderRadius:'50%', backgroundColor:'var(--c-111)'}}></div>}
                  </div>
                  <div className="message-content" style={{ flex: 1 }}>
                    <div className="text" style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{msg.content}</div>
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
                <div style={{ padding: '0.5rem' }}>Thinking...</div>
              </div>
            )}
            {chatError && <div className="error-state">{chatError}</div>}
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
              <button className="btn-icon" onClick={() => setShowAddModal(false)}><X size={20} /></button>
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
