import React, { useState } from 'react';
import { Send, FileText, Bot } from 'lucide-react';
import Orbot from '../../components/common/Orbot';
import './AskAITab.css';

function AskAITab({ documentId }) {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [error, setError] = useState('');

  const suggestedPrompts = [
    "What are the main findings?",
    "Explain the methodology simply.",
    "What limitations does this paper mention?",
    "What is the main contribution?",
    "What dataset was used?"
  ];

  const handleSend = async (text) => {
    const question = text || query;
    if (!question.trim()) return;

    // Add user message
    const newMessage = { role: 'user', content: question };
    setChatHistory(prev => [...prev, newMessage]);
    setQuery('');
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question,
          document_id: documentId,
          top_k: 5
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to get a response from AI.');
      }

      const data = await response.json();
      
      const aiMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || []
      };
      
      setChatHistory(prev => [...prev, aiMessage]);

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
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
          {chatHistory.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              <div className="message-content">
                {msg.role === 'assistant' && (
                  <div className="assistant-icon">
                    <Bot size={20} />
                  </div>
                )}
                
                <div className="message-body">
                  <div className="text">{msg.content}</div>
                  
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
                    <span>.</span><span>.</span><span>.</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {error && (
            <div className="error-message">
              {error}
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
            placeholder="Ask a question..."
            rows={1}
          />
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
