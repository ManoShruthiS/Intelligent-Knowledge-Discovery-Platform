import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Paperclip, ChevronDown, Bot, User, Loader2, Camera, X, FileText, Image as ImageIcon, Trash2 } from 'lucide-react';
import Orbot from '../components/common/Orbot';
import MarkdownMessage from '../components/common/MarkdownMessage';
import { askOrbot, uploadDocument, getProvidersStatus } from '../services/api';
import './Home.css';

function Home() {
  // Chat state
  const [searchQuery, setSearchQuery] = useState('');
  const [messages, setMessages] = useState(() => {
    try {
      const raw = sessionStorage.getItem('kno.home.messages');
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  });
  const [isLoading, setIsLoading] = useState(false);

  // Persist conversation across tab switches and refreshes.
  useEffect(() => {
    try {
      sessionStorage.setItem('kno.home.messages', JSON.stringify(messages));
    } catch (_) {
      // sessionStorage may be unavailable; fail silently.
    }
  }, [messages]);

  // Allow the user to clear the conversation manually.
  const handleClearConversation = () => {
    if (!window.confirm('Clear the current conversation?')) return;
    setMessages([]);
    try {
      sessionStorage.removeItem('kno.home.messages');
    } catch (_) {}
  };
  
  // Attachments state: Array of objects { type: 'file'|'photo', file?: File, dataUrl?: string, name: string, id: string }
  const [attachments, setAttachments] = useState([]);

  // Dropdown states
  const [activeDropdown, setActiveDropdown] = useState(null); // 'mode', 'context', 'model', 'attach'
  const [selectedMode, setSelectedMode] = useState('Research');
  const [selectedModel, setSelectedModel] = useState('Gemini 2.5 Flash');
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    getProvidersStatus()
      .then(data => {
        const providers = Array.isArray(data) ? data : (data?.providers || []);
        const models = providers
          .filter(p => p.active !== false)
          .map(p => ({
            id: p.id || p.provider || p.name,
            label: p.model || p.name || 'Unknown Model',
            provider: p.provider || p.name || 'Unknown',
          }));
        if (models.length > 0) {
          setAvailableModels(models);
          setSelectedModel(models[0].label);
        }
      })
      .catch(() => {});
  }, []);

  // Camera Overlay State
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const messagesEndRef = useRef(null);
  const composerRef = useRef(null);
  const fileInputRef = useRef(null);

  const toggleDropdown = (name) => {
    setActiveDropdown(activeDropdown === name ? null : name);
  };

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (composerRef.current && !composerRef.current.contains(event.target)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Handle File Selection
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newAttachments = Array.from(e.target.files).map(file => ({
        type: 'file',
        file: file,
        name: file.name,
        id: Math.random().toString(36).substr(2, 9)
      }));
      setAttachments(prev => [...prev, ...newAttachments]);
    }
    // Reset input
    e.target.value = '';
    setActiveDropdown(null);
  };



  // Handle Camera Start
  const startCamera = async () => {
    setActiveDropdown(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      alert("Couldn't access your camera. Please check permissions.");
    }
  };

  // Handle Camera Capture
  const capturePhoto = () => {
    if (videoRef.current) {
      const canvas = document.createElement('canvas');
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/png');
      
      setAttachments(prev => [...prev, {
        type: 'photo',
        dataUrl,
        name: `Photo-${new Date().toLocaleTimeString().replace(/:/g, '-')}.png`,
        id: Math.random().toString(36).substr(2, 9)
      }]);
      stopCamera();
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    setIsCameraActive(false);
  };

  // Make sure camera stops on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  const removeAttachment = (id) => {
    setAttachments(prev => prev.filter(att => att.id !== id));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((!searchQuery.trim() && attachments.length === 0) || isLoading) return;

    const userQuery = searchQuery.trim() || 'Analyze the attached information.';
    setSearchQuery('');
    setActiveDropdown(null);

    // Snapshot current attachments before clearing
    const currentAttachments = [...attachments];
    const filesToUpload = currentAttachments.filter(a => a.type === 'file');
    const photoAttachments = currentAttachments.filter(a => a.type === 'photo');

    // Clear composer attachments immediately
    setAttachments([]);

    // Add user message to UI with attachments preview
    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: userQuery,
        attachments: currentAttachments,
      },
    ]);
    setIsLoading(true);

    try {
      // 1. Upload file attachments. Track all uploaded document IDs.
      const uploadedDocIds = [];
      const failedUploads = [];
      for (const att of filesToUpload) {
        try {
          const result = await uploadDocument(att.file);
          uploadedDocIds.push(result.id);
        } catch (err) {
          failedUploads.push({ name: att.name, message: err.message });
        }
      }

      // If we have file attachments and they all failed, surface the error.
      if (filesToUpload.length > 0 && uploadedDocIds.length === 0 && failedUploads.length > 0) {
        const msg = failedUploads.map(f => `${f.name}: ${f.message}`).join('; ');
        setMessages(prev => [
          ...prev,
          {
            role: 'orbot',
            content: `I couldn't process the attached file(s). ${msg}`,
          },
        ]);
        setIsLoading(false);
        return;
      }

      // 2. Build the attachments payload for /api/ask.
      //    - file attachments reference the uploaded documents by id
      //    - photo attachments carry the dataUrl so Gemini vision can read them inline
      const askAttachments = [
        ...uploadedDocIds.map(id => ({ type: 'document', name: id, documentId: id })),
        ...failedUploads.map(f => ({ type: 'file', name: f.name, error: f.message })),
        ...photoAttachments.map(p => ({
          type: 'photo',
          name: p.name,
          dataUrl: p.dataUrl,
        })),
      ];

      // 3. Pull conversation history (skip the user turn we just added — it's the new message).
      const historyForBackend = messages
        .map(m => ({
          role: m.role === 'orbot' ? 'orbot' : 'user',
          content: m.content || '',
        }))
        .filter(m => m.content && m.content.trim());

      // 4. Call ORBOT.
      const data = await askOrbot({
        message: userQuery,
        mode: (selectedMode || 'Research').toLowerCase(),
        history: historyForBackend,
        attachments: askAttachments,
        documentId: uploadedDocIds.length === 1 ? uploadedDocIds[0] : null,
        topK: 5,
      });

      const orbotMsg = {
        role: 'orbot',
        content: data.answer,
        sources: data.sources || [],
        trace: data.trace || null,
        confidence: data.confidence || null,
      };

      // 5. If some file uploads failed but ORBOT still answered, append a footer note.
      if (failedUploads.length > 0) {
        const failedNames = failedUploads.map(f => f.name).join(', ');
        orbotMsg.content += `\n\n_Note: I could not process: ${failedNames}._`;
      }

      setMessages(prev => [...prev, orbotMsg]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: 'error',
          content: error.message || 'An error occurred while communicating with ORBOT.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setSearchQuery(suggestion);
  };

  // Retry: find the user message immediately preceding the failed/error message
  // and resubmit it. Removes the error bubble on success.
  const handleRetry = async (errorIdx) => {
    if (isLoading) return;
    let userMsgIdx = errorIdx - 1;
    while (userMsgIdx >= 0 && messages[userMsgIdx].role !== 'user') {
      userMsgIdx -= 1;
    }
    if (userMsgIdx < 0) return;

    const originalUser = messages[userMsgIdx];
    const userQuery = (originalUser.content || '').trim();
    if (!userQuery) return;

    // Remove the error bubble and any ORBOT reply after the user message
    setMessages(prev => prev.slice(0, userMsgIdx + 1));
    setIsLoading(true);

    // Reconstruct minimal history (everything before the user message we are retrying)
    const historyForBackend = messages
      .slice(0, userMsgIdx)
      .map(m => ({ role: m.role === 'orbot' ? 'orbot' : 'user', content: m.content || '' }))
      .filter(m => m.content && m.content.trim());

    try {
      const data = await askOrbot({
        message: userQuery,
        mode: (selectedMode || 'Research').toLowerCase(),
        history: historyForBackend,
        attachments: originalUser.attachments,
        topK: 5,
      });
      setMessages(prev => [
        ...prev,
        {
          role: 'orbot',
          content: data.answer,
          sources: data.sources || [],
          trace: data.trace,
          confidence: data.confidence,
        },
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'error', content: error.message || 'Unable to reach ORBOT.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className={`home-container ${hasMessages ? 'chat-active' : ''}`}>
      
      {/* CAMERA OVERLAY */}
      {isCameraActive && (
        <div className="camera-overlay">
          <div className="camera-container">
            <video ref={videoRef} autoPlay playsInline className="camera-video" />
            <div className="camera-controls">
              <button className="camera-btn cancel" onClick={stopCamera}>Cancel</button>
              <button className="camera-btn capture" onClick={capturePhoto}>
                <div className="capture-inner"></div>
              </button>
            </div>
          </div>
        </div>
      )}



      {/* 
        STATE 1: EMPTY STATE 
      */}
      {!hasMessages && (
        <div className="home-hero-minimal">
          <div className="hero-orbot-wrapper">
            <Orbot size={64} state="floating" />
          </div>
          <h1 className="hero-greeting">What are you exploring?</h1>
        </div>
      )}

      {/* 
        STATE 2: CHAT STATE 
      */}
      {hasMessages && (
        <div className="home-chat-history">
          <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0.5rem 1rem 0' }}>
            <button
              type="button"
              className="orbot-retry-btn"
              onClick={handleClearConversation}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
            >
              <Trash2 size={12} /> Clear conversation
            </button>
          </div>
          <div className="chat-messages-container">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-message-row ${msg.role}`}>
                {msg.role === 'orbot' && (
                  <div className="message-avatar orbot">
                    <Bot size={18} />
                  </div>
                )}
                
                <div className="chat-bubble-wrapper">
                  {/* Render User Attachments in Chat History */}
                  {msg.role === 'user' && msg.attachments && msg.attachments.length > 0 && (
                    <div className="chat-message-attachments">
                      {msg.attachments.map(att => (
                        <div key={att.id} className="history-attachment-chip">
                          {att.type === 'file' ? (
                            <><FileText size={16} /> <span className="att-name">{att.name}</span></>
                          ) : (
                            <div className="history-img-wrapper">
                              <img src={att.dataUrl} alt="attachment" />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className={`chat-bubble ${msg.role}`}>
                    {msg.role === 'orbot' ? (
                      <MarkdownMessage
                        content={msg.content}
                        trace={msg.trace}
                        confidence={msg.confidence}
                      />
                    ) : (
                      <div className="message-content">{msg.content}</div>
                    )}

                    {msg.role === 'orbot' && msg.sources && msg.sources.length > 0 && (
                      <div className="message-sources">
                        <div className="sources-label">Sources:</div>
                        <div className="sources-list">
                          {msg.sources.map((src, i) => (
                            <div key={i} className="source-chip" title={src.filename}>
                              {src.filename} (p. {src.page_number})
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {msg.role === 'error' && (
                      <div className="message-actions">
                        <button
                          type="button"
                          className="orbot-retry-btn"
                          onClick={() => handleRetry(idx)}
                        >
                          Retry
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {msg.role === 'user' && (
                  <div className="message-avatar user">
                    <User size={18} />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="chat-message-row orbot">
                <div className="message-avatar orbot">
                  <Bot size={18} />
                </div>
                <div className="chat-bubble loading">
                  <Loader2 size={18} className="spinning" />
                  <span style={{ marginLeft: '0.5rem' }}>
                    {selectedMode === 'Project'
                      ? 'ORBOT is working through the problem...'
                      : 'ORBOT is analyzing the research...'}
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {/* 
        THE COMPOSER (Shared between states)
      */}
      <div className="home-composer-wrapper">
        <form className="hero-composer" onSubmit={handleSubmit} ref={composerRef}>
          
          {/* Hidden File Input */}
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            onChange={handleFileChange}
            multiple
            accept=".pdf,.docx,.txt,.csv,.png,.jpg,.jpeg"
          />

          {/* Attachments Preview Area inside Composer */}
          {attachments.length > 0 && (
            <div className="composer-attachments">
              {attachments.map(att => (
                <div key={att.id} className="attachment-chip">
                  {att.type === 'file' ? (
                    <div className="att-file-info">
                      <FileText size={14} className="att-icon" />
                      <span className="att-name">{att.name}</span>
                    </div>
                  ) : (
                    <div className="att-img-preview">
                      <img src={att.dataUrl} alt={att.name} />
                    </div>
                  )}
                  <button type="button" className="att-remove-btn" onClick={() => removeAttachment(att.id)}>
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <input 
            type="text" 
            placeholder="Ask ORBOT anything about your research or project..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`composer-input ${attachments.length > 0 ? 'has-attachments' : ''}`}
            autoFocus
          />

          <div className="composer-toolbar">
            <div className="toolbar-left">
              
              {/* Attach Dropdown */}
              <div className="toolbar-item">
                <button 
                  type="button" 
                  className="toolbar-btn icon-only"
                  onClick={() => toggleDropdown('attach')}
                  title="Attach"
                >
                  <Paperclip size={16} />
                </button>
                {activeDropdown === 'attach' && (
                  <div className="toolbar-dropdown attach-dropdown with-icons">
                    <div className="dropdown-item" onClick={() => { setActiveDropdown(null); fileInputRef.current.click(); }}>
                      <Paperclip size={14} className="dropdown-icon" />
                      Upload Files
                    </div>
                    <div className="dropdown-item" onClick={startCamera}>
                      <Camera size={14} className="dropdown-icon" />
                      Take photo
                    </div>
                  </div>
                )}
              </div>

              {/* Mode Dropdown */}
              <div className="toolbar-item">
                <button 
                  type="button" 
                  className={`toolbar-btn ${activeDropdown === 'mode' ? 'active' : ''}`}
                  onClick={() => toggleDropdown('mode')}
                >
                  {selectedMode} <ChevronDown size={14} />
                </button>
                {activeDropdown === 'mode' && (
                  <div className="toolbar-dropdown">
                    <div className={`dropdown-item ${selectedMode === 'Research' ? 'selected' : ''}`} onClick={() => { setSelectedMode('Research'); setActiveDropdown(null); }}>
                      Research
                    </div>
                    <div className={`dropdown-item ${selectedMode === 'Project' ? 'selected' : ''}`} onClick={() => { setSelectedMode('Project'); setActiveDropdown(null); }}>
                      Project
                    </div>
                  </div>
                )}
              </div>



              {/* Model Dropdown */}
              <div className="toolbar-item">
                <button 
                  type="button" 
                  className={`toolbar-btn ${activeDropdown === 'model' ? 'active' : ''}`}
                  onClick={() => toggleDropdown('model')}
                >
                  {selectedModel} <ChevronDown size={14} />
                </button>
                {activeDropdown === 'model' && (
                  <div className="toolbar-dropdown">
                    <div className="dropdown-label">MODEL</div>
                    {availableModels.length > 0 ? availableModels.map(model => (
                      <div
                        key={model.id}
                        className={`dropdown-item ${selectedModel === model.label ? 'selected' : ''}`}
                        onClick={() => { setSelectedModel(model.label); setActiveDropdown(null); }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          {model.label}
                          <span className="dropdown-subtext">{model.provider}</span>
                        </div>
                      </div>
                    )) : (
                      <div className={`dropdown-item selected`}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          Gemini 2.5 Flash
                          <span className="dropdown-subtext">Fast · Recommended</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

            </div>

            <div className="toolbar-right">
              <button 
                type="submit" 
                className={`composer-send-btn ${(searchQuery.trim() || attachments.length > 0) && !isLoading ? 'active' : ''}`}
                disabled={(!searchQuery.trim() && attachments.length === 0) || isLoading}
              >
                <ArrowUp size={18} strokeWidth={2.5} color="#fff" />
              </button>
            </div>
          </div>
        </form>

        {/* Suggestion Chips - Only visible in empty state */}
        {!hasMessages && (
          <div className="hero-suggestions">
            <button className="suggestion-chip" onClick={() => handleSuggestionClick("Explain a research paper")} type="button">
              Explain a research paper
            </button>
            <button className="suggestion-chip" onClick={() => handleSuggestionClick("Compare research findings")} type="button">
              Compare research findings
            </button>
            <button className="suggestion-chip" onClick={() => handleSuggestionClick("Explore a research topic")} type="button">
              Explore a research topic
            </button>
            <button className="suggestion-chip" onClick={() => handleSuggestionClick("Help me plan a project")} type="button">
              Help me plan a project
            </button>
          </div>
        )}
      </div>

    </div>
  );
}

export default Home;
