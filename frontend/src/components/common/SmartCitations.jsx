import React from 'react';
import { ThumbsUp, ThumbsDown, MessageSquare, FileText } from 'lucide-react';
import './SmartCitations.css';

const LABELS = {
  supporting: { label: 'Supporting', short: 'Supports', Icon: ThumbsUp },
  contradicting: { label: 'Contradicting', short: 'Contradicts', Icon: ThumbsDown },
  mentioning: { label: 'Mentioning', short: 'Mentions', Icon: MessageSquare },
  neutral: { label: 'Neutral', short: 'Neutral', Icon: MessageSquare },
};










function SmartCitations({ citations, onCitationClick }) {
  if (!Array.isArray(citations) || citations.length === 0) return null;

  return (
    <div className="smart-citations" aria-label="Smart citation analysis">
      <div className="smart-citations-label">How sources back this answer</div>
      <ul className="smart-citations-list">
        {citations.map((c) => {
          const meta = LABELS[c.classification] || LABELS.mentioning;
          const { Icon } = meta;
          const filename = c.filename || 'Unknown source';
          const page = c.page_number;
          const pageStr = page != null ? `, p. ${page}` : '';
          const title = `${meta.label}: ${filename}${pageStr}`;
          const conf = typeof c.confidence === 'number'
            ? Math.round(c.confidence * 100)
            : null;
          return (
            <li
              key={c.number}
              className={`smart-citation smart-citation-${c.classification || 'mentioning'}`}
              title={title}
            >
              <button
                type="button"
                className="smart-citation-btn"
                onClick={() => {
                  if (typeof onCitationClick === 'function') {
                    onCitationClick({
                      number: c.number,
                      filename: c.filename,
                      page: c.page_number,
                      classification: c.classification,
                    });
                  }
                }}
              >
                <span className="smart-citation-num">[{c.number}]</span>
                <Icon size={12} className="smart-citation-icon" aria-hidden="true" />
                <span className="smart-citation-class">{meta.short}</span>
                <span className="smart-citation-file">
                  <FileText size={11} aria-hidden="true" />
                  <span>{filename}{pageStr}</span>
                </span>
                {conf != null && (
                  <span className="smart-citation-conf">{conf}%</span>
                )}
              </button>
              {c.reason && (
                <span className="smart-citation-reason">{c.reason}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default SmartCitations;
