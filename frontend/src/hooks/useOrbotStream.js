






























import { useCallback, useRef, useState } from 'react';

const API_BASE_URL = (() => {
  const raw =
    (typeof import.meta !== 'undefined' &&
      import.meta.env &&
      import.meta.env.VITE_API_BASE_URL) ||
    'http://localhost:8000/api';
  let clean = raw.replace(/\/+$/, '');
  if (!clean.endsWith('/api')) {
    clean = `${clean}/api`;
  }
  return clean;
})();

function parseSSEBlock(block) {
  
  
  const lines = block.split('\n');
  let event = 'message';
  let dataLines = [];
  for (const line of lines) {
    if (!line) continue;
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }
  const dataStr = dataLines.join('\n');
  let data = null;
  try {
    data = dataStr ? JSON.parse(dataStr) : null;
  } catch (_) {
    data = dataStr;
  }
  return { event, data };
}

export function useOrbotStream() {
  const [state, setState] = useState('idle'); 
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [trace, setTrace] = useState(null);
  const [confidence, setConfidence] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [followups, setFollowups] = useState([]);
  const [error, setError] = useState(null);
  
  
  const [thinkingStage, setThinkingStage] = useState(null);
  const [thinkingLabel, setThinkingLabel] = useState(null);
  
  
  
  const [smartCitations, setSmartCitations] = useState([]);

  const controllerRef = useRef(null);
  
  
  const answerRef = useRef('');
  
  
  
  const [conversationId, setConversationId] = useState(null);
  
  
  const [requestId, setRequestId] = useState(null);
  
  
  const [providerStatus, setProviderStatus] = useState(null);
  
  const [pagePin, setPagePin] = useState(null);

  const reset = useCallback(() => {
    if (controllerRef.current) {
      try { controllerRef.current.abort(); } catch (_) {}
      controllerRef.current = null;
    }
    setState('idle');
    setAnswer('');
    setSources([]);
    setTrace(null);
    setConfidence(null);
    setMetadata(null);
    setFollowups([]);
    setError(null);
    setThinkingStage(null);
    setThinkingLabel(null);
    setSmartCitations([]);
    setConversationId(null);
    setRequestId(null);
    setProviderStatus(null);
    setPagePin(null);
    answerRef.current = '';
  }, []);

  const stop = useCallback(() => {
    if (controllerRef.current) {
      try { controllerRef.current.abort(); } catch (_) {}
      controllerRef.current = null;
    }
    setState((prev) => (prev === 'streaming' ? 'aborted' : prev));
  }, []);

  const start = useCallback(async ({ payload }) => {
    
    setState('streaming');
    setAnswer('');
    setSources([]);
    setTrace(null);
    setConfidence(null);
    setMetadata(null);
    setFollowups([]);
    setError(null);
    setThinkingStage(null);
    setThinkingLabel(null);
    setSmartCitations([]);
    setConversationId(null);
    setRequestId(null);
    setProviderStatus(null);
    setPagePin(null);
    answerRef.current = '';

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        let detail = `Request failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (body && body.detail) detail = body.detail;
        } catch (_) {}
        throw new Error(detail);
      }
      if (!response.body) {
        throw new Error('Streaming not supported by the browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      
      const flush = () => new Promise((r) => setTimeout(r, 0));

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        
        let sepIdx;
        while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
          const rawBlock = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          const { event, data } = parseSSEBlock(rawBlock);
          if (!data) continue;
          switch (event) {
            case 'token': {
              const text = typeof data === 'object' && data ? data.text : data;
              if (text) {
                answerRef.current += text;
                setAnswer(answerRef.current);
                
                
                setThinkingStage(null);
              }
              break;
            }
            case 'thinking': {
              if (data && typeof data.stage === 'string') {
                setThinkingStage(data.stage);
                setThinkingLabel(typeof data.label === 'string' ? data.label : null);
              }
              break;
            }
            case 'meta': {
              if (Array.isArray(data.sources)) setSources(data.sources);
              if (typeof data.trace === 'string' || data.trace === null) setTrace(data.trace);
              if (typeof data.confidence === 'string' || data.confidence === null) setConfidence(data.confidence);
              if (data.metadata && typeof data.metadata === 'object') setMetadata(data.metadata);
              
              
              if (typeof data.conversation_id === 'string' && data.conversation_id) {
                setConversationId(data.conversation_id);
              }
              
              if (typeof data.request_id === 'string' && data.request_id) {
                setRequestId(data.request_id);
              }
              if (data.provider_status && typeof data.provider_status === 'object') {
                setProviderStatus(data.provider_status);
              }
              if (Array.isArray(data.page_pin)) {
                setPagePin(data.page_pin);
              } else if (data.page_pin == null) {
                setPagePin(null);
              }
              
              setThinkingStage(null);
              break;
            }
            case 'followups': {
              if (Array.isArray(data.suggested_followups)) {
                setFollowups(data.suggested_followups.filter((q) => typeof q === 'string' && q.trim()));
              }
              break;
            }
            case 'smart_citations': {
              if (Array.isArray(data.citations)) {
                setSmartCitations(data.citations);
              }
              break;
            }
            case 'done': {
              
              
              
              if (typeof data.answer === 'string' && data.answer.length >= answerRef.current.length) {
                answerRef.current = data.answer;
                setAnswer(data.answer);
              }
              break;
            }
            case 'error': {
              const detail = typeof data === 'object' && data ? data.detail : data;
              throw new Error(detail || 'Streaming failed.');
            }
            default:
              break;
          }
        }
        await flush();
      }

      
      if (buffer.trim()) {
        const { event, data } = parseSSEBlock(buffer);
        if (event === 'error' && data && data.detail) {
          throw new Error(data.detail);
        }
      }

      setState('done');
    } catch (err) {
      
      
      if (err && (err.name === 'AbortError' || controller.signal.aborted)) {
        setState((prev) => (prev === 'aborted' ? 'aborted' : 'aborted'));
        return;
      }
      setError(err && err.message ? err.message : 'Streaming failed.');
      setState('error');
    } finally {
      controllerRef.current = null;
    }
  }, []);

  return {
    state,
    answer,
    sources,
    trace,
    confidence,
    metadata,
    followups,
    error,
    thinkingStage,
    thinkingLabel,
    smartCitations,
    conversationId,
    requestId,
    providerStatus,
    pagePin,
    start,
    stop,
    reset,
  };
}