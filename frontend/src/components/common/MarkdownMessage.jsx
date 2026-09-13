import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check, Sparkles, RotateCw, Square, ChevronDown, ChevronUp, ShieldCheck, Download, FileDown, FileCode2 } from 'lucide-react';
import SmartCitations from './SmartCitations';
import { verifyGrounding, exportAnswer } from '../../services/api';





































function CopyButton({ text, label = 'Copy code' }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      
    }
  };
  return (
    <button
      type="button"
      onClick={onCopy}
      className="orbot-copy-btn"
      aria-label={label}
      title={label}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}










function preprocessCitations(text) {
  if (!text) return '';
  return String(text).replace(
    /\[(\d+)\]\s*\(([^)]+)\)/g,
    (match, n, rest) => {
      const pageMatch = rest.match(/p\.\s*(\d+)|page\s*(\d+)/i);
      const page = pageMatch ? (pageMatch[1] || pageMatch[2] || '') : '';
      const filename = rest
        .replace(/,\s*p\.\s*\d+/i, '')
        .replace(/,\s*page\s*\d+/i, '')
        .trim();
      return `[\\[${n}\\]](cite://${n}/${encodeURIComponent(filename)}/${page})`;
    },
  );
}

function ActionButton({ onClick, icon: Icon, label, title, variant = 'default' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`orbot-action-btn orbot-action-${variant}`}
      aria-label={label}
      title={title || label}
    >
      <Icon size={13} strokeWidth={1.5} />
      <span className="orbot-action-label">{title || label}</span>
    </button>
  );
}

function ExportMenu({ onExport, isOpen, setOpen, disabled }) {
  const handleClick = (kind) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    setOpen(false);
    if (typeof onExport === 'function') onExport(kind);
  };
  return (
    <span className="orbot-export-wrap">
      <ActionButton
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(!isOpen); }}
        icon={Download}
        label="Export answer"
        title="Export"
      />
      {isOpen && !disabled && (
        <span
          className="orbot-export-menu"
          role="menu"
          aria-label="Export formats"
          onClick={(e) => e.stopPropagation()}
        >
          <button type="button" className="orbot-export-item" role="menuitem" onClick={handleClick('markdown')}>
            <FileDown size={13} /> Markdown (.md)
          </button>
          <button type="button" className="orbot-export-item" role="menuitem" onClick={handleClick('txt')}>
            <FileCode2 size={13} /> Plain text (.txt)
          </button>
        </span>
      )}
    </span>
  );
}

function TracePanel({
  trace,
  sources,
  confidence,
  metadata,
  userQuestion,
  answer,
  conversationId,
}) {
  
  
  const [open, setOpen] = useState(false);
  const [groundingState, setGroundingState] = useState({ status: 'idle', result: null, error: null });

  
  
  const hasTrace = typeof trace === 'string' && trace.trim().length > 0;
  // Sources footer is intentionally hidden at end of answer.
  const hasSources = false;
  const hasMeta = metadata && typeof metadata === 'object' && Object.keys(metadata).length > 0;
  const showGrounding = false;
  if (!hasTrace && !hasMeta && !confidence) return null;

  const summary = hasTrace ? 'Retrieval details' : 'Evidence';

  const confidenceLabel = confidence === 'grounded'
    ? 'Grounded in documents'
    : confidence === 'partial'
    ? 'Partially grounded'
    : confidence === 'unverified'
    ? 'Unverified — limited evidence'
    : null;

  const runGroundingCheck = async () => {
    if (!hasSources || !userQuestion || !answer) return;
    setGroundingState({ status: 'loading', result: null, error: null });
    try {
      const sourcesPayload = sources.map((s) => ({
        filename: s.filename,
        page_number: s.page_number,
        text: s.text,
        similarity: s.similarity,
      }));
      const res = await verifyGrounding({ question: userQuestion, answer, sources: sourcesPayload });
      setGroundingState({ status: 'done', result: res, error: null });
    } catch (err) {
      setGroundingState({ status: 'error', result: null, error: err && err.message ? err.message : 'Verification failed.' });
    }
  };

  return (
    <div className={`orbot-trace-panel ${open ? 'open' : ''}`}>
      <button
        type="button"
        className="orbot-trace-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="orbot-trace-body"
      >
        <ShieldCheck size={12} strokeWidth={1.5} />
        <span className="orbot-trace-toggle-label">Research Trace</span>
        <span className="orbot-trace-summary">{summary}</span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div className="orbot-trace-body" id="orbot-trace-body">
          <div className="orbot-trace-steps" aria-label="Pipeline steps">
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Query understood</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Documents searched</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Chunks retrieved</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Chunks selected</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Sources used</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Evidence confidence</div>
            <div className="orbot-trace-step"><span className="orbot-trace-step-dot" /> Answer grounded</div>
          </div>
          {hasTrace && (
            <pre className="orbot-trace-text">{trace}</pre>
          )}
          {confidenceLabel && (
            <div className={`orbot-trace-confidence orbot-confidence-${confidence}`}>
              {confidenceLabel}
            </div>
          )}
          {hasMeta && (
            <ul className="orbot-trace-meta">
              {metadata.provider && <li><strong>Provider:</strong> {metadata.provider}</li>}
              {typeof metadata.retrieval_latency_ms === 'number' && (
                <li><strong>Retrieval:</strong> {metadata.retrieval_latency_ms} ms</li>
              )}
              {typeof metadata.llm_latency_ms === 'number' && (
                <li><strong>Generation:</strong> {metadata.llm_latency_ms} ms</li>
              )}
              {typeof metadata.multi_step_retrieval === 'boolean' && metadata.multi_step_retrieval && (
                <li><strong>Multi-step retrieval:</strong> yes</li>
              )}
              {conversationId && <li><strong>Conversation ID:</strong> <code>{conversationId}</code></li>}
            </ul>
          )}
          {showGrounding && (
            <div className="orbot-trace-grounding">
              <div className="orbot-trace-grounding-header">
                <strong>Evidence Check</strong>
                <button
                  type="button"
                  className="orbot-action-btn orbot-action-default orbot-grounding-btn"
                  onClick={runGroundingCheck}
                  disabled={groundingState.status === 'loading'}
                >
                  {groundingState.status === 'loading' ? 'Checking…' : 'Run grounding check'}
                </button>
              </div>
              {groundingState.status === 'error' && (
                <div className="orbot-grounding-error">{groundingState.error}</div>
              )}
              {groundingState.status === 'done' && groundingState.result && (
                <div className="orbot-grounding-result">
                  <div className={`orbot-grounding-badge orbot-grounding-${groundingState.result.support_level}`}>
                    {groundingState.result.support_level === 'high' && 'Evidence strongly supports this answer'}
                    {groundingState.result.support_level === 'partial' && 'Evidence partially supports this answer'}
                    {groundingState.result.support_level === 'low' && 'Evidence is weak — cross-check important claims'}
                    {groundingState.result.support_level === 'unsupported' && 'No direct evidence in the cited sources'}
                  </div>
                  {groundingState.result.supported_claims && groundingState.result.supported_claims.length > 0 && (
                    <div className="orbot-grounding-list">
                      <div className="orbot-grounding-list-label">Supported</div>
                      <ul>
                        {groundingState.result.supported_claims.map((c, i) => <li key={`s-${i}`}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                  {groundingState.result.unsupported_claims && groundingState.result.unsupported_claims.length > 0 && (
                    <div className="orbot-grounding-list">
                      <div className="orbot-grounding-list-label">Not directly supported</div>
                      <ul>
                        {groundingState.result.unsupported_claims.map((c, i) => <li key={`u-${i}`}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                  {groundingState.result.note && (
                    <div className="orbot-grounding-note">{groundingState.result.note}</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const MarkdownMessage = ({
  content,
  trace = null,
  confidence = null,
  followups = null,
  onFollowupClick = null,
  className = '',
  sources = null,
  metadata = null,
  onCopy = null,
  onRegenerate = null,
  onStop = null,
  onExport = null,
  isStreaming = false,
  isGenerating = false,
  
  userQuestion = null,
  conversationId = null,
  
  epistemicTags = null,
  
  externalLabels = null,
  
  
  onCitationClick = null,
  
  
  smartCitations = null,
}) => {
  if (!content && !isStreaming && !isGenerating) return null;

  const hasFollowups = Array.isArray(followups) && followups.length > 0 && typeof onFollowupClick === 'function';
  // Do not trigger trace panel on sources alone — sources footer is hidden.
  const showTracePanel = !isStreaming && (trace || metadata || userQuestion);
  const [exportOpen, setExportOpen] = useState(false);

  
  useEffect(() => {
    if (!exportOpen) return undefined;
    const onClick = () => setExportOpen(false);
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [exportOpen]);

  
  
  const renderedContent = preprocessCitations(content || '');

  
  
  const handleCitationClick = (sourceNumber, filename, page) => {
    
    
    if (typeof onCitationClick !== 'function') return;
    const idx = Number(sourceNumber) - 1;
    const match = Array.isArray(sources) && idx >= 0 ? sources[idx] : null;
    onCitationClick({
      source: match,
      number: sourceNumber,
      filename,
      page,
    });
  };

  const handleCopy = () => {
    if (typeof onCopy === 'function') onCopy(content || '');
  };

  const handleRegenerate = () => {
    if (typeof onRegenerate === 'function') onRegenerate();
  };

  const handleStop = () => {
    if (typeof onStop === 'function') onStop();
  };

  const handleExport = (kind) => {
    if (typeof onExport === 'function') onExport(kind);
  };

  return (
    <div className={`orbot-markdown ${className} ${isStreaming ? 'streaming' : ''} ${isGenerating ? 'generating' : ''}`}>
      <div className="orbot-meta">
        {isStreaming ? (
          <span className="orbot-generating-pill" aria-live="polite">
            <span className="orbot-generating-dot" /> Generating…
          </span>
        ) : isGenerating ? (
          <span className="orbot-generating-pill" aria-live="polite">
            <span className="orbot-generating-dot" /> Preparing answer…
          </span>
        ) : null}
        {!isStreaming && trace && <span className="orbot-trace">{trace}</span>}
        {!isStreaming && confidence && (
          <span className={`orbot-confidence orbot-confidence-${confidence}`}>
            {confidence === 'grounded'
              ? 'Grounded in sources'
              : confidence === 'partial'
              ? 'Partially grounded'
              : 'Unverified — answer based on general knowledge'}
          </span>
        )}
        {!isStreaming && epistemicTags && epistemicTags.length > 0 && (
          <span className="orbot-epistemic-tags" aria-label="Epistemic tags">
            {epistemicTags.map((t, i) => (
              <span key={`${t}-${i}`} className={`orbot-epistemic-tag orbot-epistemic-${t.toLowerCase()}`}>{t}</span>
            ))}
          </span>
        )}
        {!isStreaming && externalLabels && externalLabels.length > 0 && (
          <span className="orbot-external-labels" aria-label="Source labels">
            {externalLabels.map((l, i) => (
              <span key={`${l}-${i}`} className={`orbot-external-label orbot-label-${l.toLowerCase()}`}>{l}</span>
            ))}
          </span>
        )}
        {(onCopy || (onRegenerate && !isStreaming) || (onStop && isStreaming) || onExport) && (
          <span className="orbot-action-bar" role="toolbar" aria-label="Response actions">
            {onCopy && !isStreaming && (
              <ActionButton onClick={handleCopy} icon={Copy} label="Copy answer" title="Copy" />
            )}
            {onExport && !isStreaming && (
              <ExportMenu onExport={handleExport} isOpen={exportOpen} setOpen={setExportOpen} disabled={isStreaming} />
            )}
            {onStop && isStreaming && (
              <ActionButton onClick={handleStop} icon={Square} label="Stop generation" title="Stop" variant="danger" />
            )}
            {onRegenerate && !isStreaming && (
              <ActionButton onClick={handleRegenerate} icon={RotateCw} label="Regenerate" title="Regenerate" />
            )}
          </span>
        )}
      </div>

      <div className="orbot-markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node, href, children, ...props }) => {
              if (typeof href === 'string' && href.startsWith('cite://')) {
                
                const stripped = href.slice('cite://'.length);
                const [n, encFname = '', page = ''] = stripped.split('/');
                const filename = decodeURIComponent(encFname || '');
                return (
                  <sup
                    className="orbot-citation"
                    data-cite={n}
                    title={
                      filename
                        ? `${filename}${page ? `, p. ${page}` : ''}`
                        : `Source ${n}`
                    }
                    role="button"
                    tabIndex={0}
                    onClick={() => handleCitationClick(n, filename, page)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleCitationClick(n, filename, page);
                      }
                    }}
                  >
                    [{n}]
                  </sup>
                );
              }
              return (
                <a {...props} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              );
            },
            code: ({ inline, className: cls, children, ...props }) => {
              const text = String(children || '').replace(/\n$/, '');
              if (inline) {
                return (
                  <code className="orbot-inline-code" {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <div className="orbot-code-block">
                  <CopyButton text={text} />
                  <pre>
                    <code className={cls} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
              );
            },
          }}
        >
          {renderedContent}
        </ReactMarkdown>
        {isStreaming && <span className="orbot-stream-cursor" aria-hidden="true" />}
      </div>

      {showTracePanel && (
        <TracePanel
          trace={trace}
          sources={sources}
          confidence={confidence}
          metadata={metadata}
          userQuestion={userQuestion}
          answer={content}
          conversationId={conversationId}
        />
      )}

      {hasFollowups && (
        <div className="orbot-followups" role="group" aria-label="Suggested follow-up questions">
          <div className="orbot-followups-label">
            <Sparkles size={12} strokeWidth={1.5} />
            <span>Follow-up</span>
          </div>
          <div className="orbot-followups-list">
            {followups.slice(0, 4).map((q, idx) => (
              <button
                key={`${idx}-${String(q).slice(0, 32)}`}
                type="button"
                className="orbot-followup-chip"
                onClick={() => onFollowupClick(q)}
                title={q}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isStreaming && Array.isArray(smartCitations) && smartCitations.length > 0 && (
        <SmartCitations
          citations={smartCitations}
          onCitationClick={onCitationClick}
        />
      )}
    </div>
  );
};


export async function exportAnswerDownload(payload) {
  const res = await exportAnswer(payload);
  const content = res && res.content ? res.content : '';
  const mime = (res && res.mime) || 'text/markdown; charset=utf-8';
  const ext = (res && res.format) === 'txt' ? 'txt' : 'md';
  const safeTitle = (payload && payload.title ? payload.title : 'orbot_answer')
    .replace(/[^a-z0-9_-]+/gi, '_')
    .toLowerCase()
    .slice(0, 60) || 'orbot_answer';
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safeTitle}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

export default MarkdownMessage;
