import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Sparkles, AlertCircle } from 'lucide-react';
import { useOrbotStream } from '../hooks/useOrbotStream';
import { getDocument } from '../services/api';
import MarkdownMessage from './common/MarkdownMessage';
import './ChatBox.css';

const EXAMPLE_QUESTIONS = [
  'Summarize this document',
  'Explain the methodology',
  'What are the key findings?',
  'What are the main contributions?',
];

function ChatBox({ documentId, document: propDocument = null, workspaceId = null }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [doc, setDoc] = useState(propDocument);
  const historyEndRef = useRef(null);

  
  useEffect(() => {
    if (propDocument) {
      setDoc(propDocument);
      return;
    }
    if (documentId) {
      let cancelled = false;
      getDocument(documentId)
        .then((data) => {
          if (!cancelled && data) setDoc(data);
        })
        .catch(() => {});
      return () => {
        cancelled = true;
      };
    }
  }, [documentId, propDocument]);

  const docFilename = doc?.filename || doc?.title || 'this document';
  const docStatus = (doc?.status || 'ready').toLowerCase();
  const extractedText = (doc?.extracted_text || doc?.text || '').trim();
  const isProcessing = docStatus === 'processing' || docStatus === 'pending';
  const isFailed = docStatus === 'failed' || docStatus === 'error' || (docStatus === 'ready' && doc && !extractedText);

  
  
  
  const [conversationId, setConversationId] = useState(() => {
    try {
      return localStorage.getItem(`kno_doc_conv_id_${documentId}`) || null;
    } catch (_) {
      return null;
    }
  });

  const {
    state, answer, sources, error, confidence, followups,
    conversationId: streamedConversationId,
    start, stop, reset,
  } = useOrbotStream();

  
  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, answer]);

  
  
  useEffect(() => {
    if (state !== 'done' || !answer) return;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'user') return prev;
      return [
        ...prev,
        {
          role: 'orbot',
          content: answer,
          sources,
          confidence,
          followups,
        },
      ];
    });
    if (streamedConversationId && streamedConversationId !== conversationId) {
      setConversationId(streamedConversationId);
      try {
        localStorage.setItem(`kno_doc_conv_id_${documentId}`, streamedConversationId);
      } catch (_) {}
    }
  }, [state, answer, sources, confidence, followups, streamedConversationId, conversationId, documentId]);

  
  useEffect(() => {
    if (state === 'done' || state === 'error' || state === 'aborted') {
      reset();
    }
  }, [state, reset]);

  const sendQuestion = useCallback(
    (text) => {
      const q = (text ?? input).trim();
      if (!q || state === 'streaming' || !documentId || isProcessing || isFailed) return;
      const userMsg = { role: 'user', content: q };
      const historyForBackend = messages.map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      start({
        payload: {
          question: q,
          document_id: documentId,
          workspace_id: workspaceId,
          history: historyForBackend,
          mode: 'research',
          
          persist_conversation: true,
          
          conversation_id: conversationId || undefined,
        },
      });
    },
    [input, messages, state, documentId, workspaceId, conversationId, isProcessing, isFailed, start]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  };

  const isStreaming = state === 'streaming';
  const isError = state === 'error' && !!error;
  const hasMessages = messages.length > 0;

  const getPlaceholder = () => {
    if (isProcessing) return 'Your document is still being processed…';
    if (isFailed) return "I couldn't access extracted text for this document…";
    return 'Ask ORBOT anything about this document…';
  };

  return (
    <div className="chatbox-root">

      <div className="chatbox-history" role="log" aria-live="polite" aria-relevant="additions">
        {!hasMessages && !isStreaming && (
          <div className="chatbox-empty">
            <h3>Hello! I'm ORBOT.</h3>
            {isProcessing ? (
              <p>Your document is still being processed. I'll be ready to answer questions about it once the analysis is complete.</p>
            ) : isFailed ? (
              <p>I couldn't access the extracted text for this document. Please retry the document analysis.</p>
            ) : (
              <>
                <p>
                  I'm here to help you understand and explore <strong>{docFilename}</strong>. Ask me about its content, methodology, findings, concepts, or anything you'd like to understand better.
                </p>
                <div className="chatbox-suggestions">
                  {EXAMPLE_QUESTIONS.map((q, i) => (
                    <button
                      key={`ex-${i}`}
                      type="button"
                      className="chatbox-suggestion"
                      onClick={() => sendQuestion(q)}
                      disabled={!documentId || isProcessing || isFailed}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {isError && (
          <div className="chatbox-error" role="alert">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {messages.map((m, i) => {
          
          const isStreamingMsg = isStreaming && i === messages.length - 1;
          return (
            <div
              key={`msg-${i}`}
              className={`chatbox-msg chatbox-msg-${m.role}${isStreamingMsg ? ' chatbox-msg-streaming' : ''}`}
            >
              <div className="chatbox-msg-bubble">
                <div className="chatbox-msg-role">{m.role === 'user' ? 'You' : 'ORBOT'}</div>
                {m.role === 'user' ? (
                  <div className="chatbox-msg-text">{m.content}</div>
                ) : (
                  <MarkdownMessage
                    content={m.content}
                    sources={m.sources}
                    confidence={m.confidence}
                    followups={m.followups}
                    isStreaming={isStreamingMsg}
                  />
                )}
                {m.role === 'orbot' && Array.isArray(m.followups) && m.followups.length > 0 && !isStreamingMsg && (
                  <div className="chatbox-followups" role="group" aria-label="Suggested follow-up questions">
                    {m.followups.slice(0, 4).map((q, idx) => (
                      <button
                        key={`fu-${i}-${idx}`}
                        type="button"
                        className="chatbox-followup-chip"
                        onClick={() => sendQuestion(q)}
                        disabled={isStreaming || !documentId || isProcessing || isFailed}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {}
        {isStreaming && !hasMessages && answer && (
          <div className="chatbox-msg chatbox-msg-orbot chatbox-msg-streaming">
            <div className="chatbox-msg-bubble">
              <div className="chatbox-msg-role">ORBOT</div>
              <MarkdownMessage
                content={answer}
                sources={sources}
                confidence={confidence}
                isStreaming={true}
              />
            </div>
          </div>
        )}

        <div ref={historyEndRef} />
      </div>

      <div className="chatbox-input-wrap">
        <div className="chatbox-input-row">
          <textarea
            className="chatbox-input"
            placeholder={getPlaceholder()}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={isStreaming || !documentId || isProcessing || isFailed}
          />
          {isStreaming ? (
            <button type="button" className="chatbox-send chatbox-stop" onClick={stop}>
              Stop
            </button>
          ) : (
            <button
              type="button"
              className="chatbox-send"
              onClick={() => sendQuestion()}
              disabled={!input.trim() || !documentId || isProcessing || isFailed}
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChatBox;
