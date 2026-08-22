import React, { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Send, FileText, Bot, RotateCcw, Trash2 } from 'lucide-react';
import Orbot from '../../components/common/Orbot';
import MarkdownMessage from '../../components/common/MarkdownMessage';
import { askOrbot } from '../../services/api';
import './AskAITab.css';

function AskAITab() {
  // DocumentWorkspace passes { document } via Outlet context.
  const { document } = useOutletContext() || {};
  const documentId = document && document.id ? document.id : null;

  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [mode, setMode] = useState('research');

  const suggestedPrompts = [
    "What are the main findings?",
    "Explain the methodology simply.",
    "What limitations does this paper mention?",
    "What is the main contribution?",
    "What dataset was used?"
  ];

  const sendQuestion = async (question, historyAtSend) => {
    const data = await askOrbot({
      message: question,
      mode,
      history: historyAtSend,
      documentId,
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

  const handleSend = async (text) => {
    const question = (text || query).trim();
    if (!question || isLoading) return;

    setChatHistory(prev => [...prev, { role: 'user', content: question }]);
    setQuery('');
    setIsLoading(true);

    const historyAtSend = chatHistory;
    try {
      await sendQuestion(question, historyAtSend);
    } catch (err) {
      setChatHistory(prev => [
        ...prev,
        { role: 'error', content: err.message || 'Unable to reach ORBOT.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Retry the user message immediately preceding the error bubble.
  const handleRetry = async (errorIdx) => {
    if (isLoading) return;
    let userIdx = errorIdx - 1;
    while (userIdx >= 0 && chatHistory[userIdx].role !== 'user') {
      userIdx -= 1;
    }
    if (userIdx < 0) return;
    const original = chatHistory[userIdx];
    const question = (original.content || '').trim();
    if (!question) return;

    // Drop the error bubble and any messages after the user message we are retrying
    setChatHistory(prev => prev.slice(0, userIdx + 1));
    setIsLoading(true);

    const historyAtSend = chatHistory.slice(0, userIdx);
    try {
      await sendQuestion(question, historyAtSend);
    } catch (err) {
      setChatHistory(prev => [
        ...prev,
        { role: 'error', content: err.message || 'Unable to reach ORBOT.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearConversation = () => {
    if (!window.confirm('Clear the conversation?')) return;
    setChatHistory([]);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="ask-ai-container">
      {chatHistory.length === 0 ? (
        <div className="ask-ai-empty">
          <Orbot size={80} state="idle" />
          <h2>Ask me about your research.</h2>
          
          <div className="suggested-prompts">
            {suggestedPrompts.map((prompt, idx) => (
              <button 
                key={idx} 
                className="prompt-chip"
                onClick={() => handleSend(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="chat-history">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClearConversation}
              title="Clear conversation"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
            >
              <Trash2 size={12} /> Clear
            </button>
          </div>
          {chatHistory.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              <div className="message-content">
                {(msg.role === 'assistant' || msg.role === 'error') && (
                  <div className="assistant-icon">
                    <Bot size={20} />
                  </div>
                )}

                <div className="message-body">
                  {msg.role === 'assistant' ? (
                    <MarkdownMessage
                      content={msg.content}
                      trace={msg.trace}
                      confidence={msg.confidence}
                    />
                  ) : msg.role === 'error' ? (
                    <>
                      <div className="text">{msg.content}</div>
                      <div className="message-actions">
                        <button
                          type="button"
                          className="orbot-retry-btn"
                          onClick={() => handleRetry(idx)}
                          disabled={isLoading}
                        >
                          <RotateCcw size={14} /> Retry
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="text">{msg.content}</div>
                  )}

                  {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                    <div className="sources-container">
                      <span className="sources-label">Sources</span>
                      <div className="sources-list">
                        {msg.sources.map((source, sIdx) => (
                          <div key={sIdx} className="source-chip" title={`Similarity: ${source.similarity}`}>
                            <FileText size={12} />
                            {source.filename} {source.page_number ? `· Page ${source.page_number}` : ''}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="chat-message assistant loading">
              <div className="message-content">
                <div className="assistant-icon">
                  <Orbot size={24} state="searching" />
                </div>
                <div className="message-body">
                  <div className="text typing-indicator">
                    {mode === 'project'
                      ? 'ORBOT is working through the problem...'
                      : 'ORBOT is analyzing the research...'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={document && document.filename
              ? `Ask about ${document.filename}...`
              : "Ask a question..."}
            rows={1}
          />
          <div className="input-mode-toggle" role="tablist" aria-label="ORBOT mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'research'}
              className={`mode-btn ${mode === 'research' ? 'active' : ''}`}
              onClick={() => setMode('research')}
            >
              Research
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'project'}
              className={`mode-btn ${mode === 'project' ? 'active' : ''}`}
              onClick={() => setMode('project')}
            >
              Project
            </button>
          </div>
          <button
            className="send-btn"
            onClick={() => handleSend()}
            disabled={!query.trim() || isLoading}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default AskAITab;
