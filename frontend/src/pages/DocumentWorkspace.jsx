import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FileText, File, Loader2, AlertCircle, Copy, Check, CheckCircle2, Lightbulb, Target
} from 'lucide-react';
import { getDocument, getDocumentVersions, createDocumentVersion, generateDocumentSummary } from '../services/api';
import ChatBox from '../components/ChatBox';
import './DocumentWorkspace.css';

function DocumentWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [versions, setVersions] = useState([]);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [copied, setCopied] = useState(false);
  
  useEffect(() => {
    const fetchDocument = async () => {
      try {
        setLoading(true);
        const data = await getDocument(id);
        setDocument(data);
        fetchVersions();
      } catch (err) {
        setError(err.message || 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };
    fetchDocument();
  }, [id]);

  const fetchVersions = async () => {
    try {
      const res = await getDocumentVersions(id);
      setVersions(res.versions || []);
    } catch {}
  };

  const handleGenerateSummary = async () => {
    try {
      setGeneratingSummary(true);
      const updatedDoc = await generateDocumentSummary(id);
      setDocument(updatedDoc);
    } catch (err) {
      alert("Failed to generate summary: " + err.message);
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleCopyText = () => {
    if (document && document.extracted_text) {
      navigator.clipboard.writeText(document.extracted_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) return <div className="doc-detail-container loading-state"><Loader2 size={40} className="spinning" style={{ color: 'var(--c-555)' }} /></div>;
  if (error) return (
    <div className="doc-detail-container">
      <div className="doc-detail-error-card">
        <AlertCircle size={48} style={{ color: '#E53E3E', margin: '0 auto' }} />
        <h2>Unable to load document</h2>
        <p>{error}</p>
        <button className="doc-btn-icon-label" onClick={() => navigate('/documents')}>Back to Documents</button>
      </div>
    </div>
  );
  if (!document) return null;

  const DocIcon = document.file_type === 'PDF' ? FileText : File;

  let parsedInsights = null;
  if (document.insights) {
    try {
      parsedInsights = typeof document.insights === 'string' ? JSON.parse(document.insights) : document.insights;
    } catch (e) {
      console.error("Failed to parse insights", e);
    }
  }

  return (
    <div className="doc-detail-container">
      <div className="doc-detail-header">
        <div className="doc-detail-title-group">
          <div className="doc-detail-icon">
            <DocIcon size={20} />
          </div>
          <h1 className="doc-detail-filename" title={document.filename}>{document.filename}</h1>
        </div>
      </div>

      <div className="doc-detail-chat-only-layout">
        <div className="doc-detail-right-pane">
          <ChatBox documentId={id} document={document} />
        </div>
      </div>
    </div>
  );
}

export default DocumentWorkspace;

