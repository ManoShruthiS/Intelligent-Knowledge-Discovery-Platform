import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';

/**
 * Renders ORBOT text content as Markdown.
 *
 * Features:
 *  - GitHub-flavored markdown (tables, task lists, strikethrough)
 *  - Sane typography (headings, lists, blockquotes, tables)
 *  - Code blocks: monospace, scroll-x, copy-to-clipboard button
 *  - Inline code: subtle background, monospace
 *  - Links open in a new tab safely
 *  - No external HTML / no XSS vector (react-markdown escapes by default)
 *
 * Anti-hallucination UI:
 *  - If `trace` is provided, a small process-trace line is shown above the body
 *  - If `confidence` is provided, a small badge is shown above the body
 */

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      // Clipboard may be unavailable (e.g. insecure context) — fail silently.
    }
  };
  return (
    <button
      type="button"
      onClick={onCopy}
      className="orbot-copy-btn"
      aria-label="Copy code"
      title="Copy code"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

const MarkdownMessage = ({
  content,
  trace = null,
  confidence = null,
  className = '',
}) => {
  if (!content) return null;

  return (
    <div className={`orbot-markdown ${className}`}>
      {(trace || confidence) && (
        <div className="orbot-meta">
          {trace && <span className="orbot-trace">{trace}</span>}
          {confidence && (
            <span className={`orbot-confidence orbot-confidence-${confidence}`}>
              {confidence === 'grounded'
                ? 'Grounded in sources'
                : confidence === 'partial'
                ? 'Partially grounded'
                : 'Unverified — answer based on general knowledge'}
            </span>
          )}
        </div>
      )}

      <div className="orbot-markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node, ...props }) => (
              <a {...props} target="_blank" rel="noopener noreferrer" />
            ),
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
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default MarkdownMessage;
