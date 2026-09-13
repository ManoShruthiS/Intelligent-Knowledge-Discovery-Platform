import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, UploadCloud, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { uploadDocument } from '../../services/api';
import './UploadModal.css';


const STATUS = {
  PENDING: 'pending',
  UPLOADING: 'uploading',
  DONE: 'done',
  FAILED: 'failed',
};

export default function UploadModal({ isOpen, onClose, workspaceId }) {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  
  const fileInputRef = useRef(null);

  
  const addFile = (file) => {
    const newItem = {
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      file,
      name: file.name,
      size: file.size,
      status: STATUS.PENDING,
      progress: 0,
      result: null,
      error: null,
    };
    setItems(prev => [...prev, newItem]);
  };

  
  const processQueue = async () => {
    for (const item of items) {
      if (item.status !== STATUS.PENDING) continue;
      setItems(prev => prev.map(i => i.id === item.id ? { ...i, status: STATUS.UPLOADING, progress: 30 } : i));
      try {
        const result = await uploadDocument(item.file, workspaceId);
        window.dispatchEvent(new Event('uploadComplete'));
        setItems(prev => prev.map(i =>
          i.id === item.id ? { ...i, status: STATUS.DONE, progress: 100, result } : i
        ));
      } catch (err) {
        setItems(prev => prev.map(i =>
          i.id === item.id ? { ...i, status: STATUS.FAILED, error: err.message || 'Upload failed' } : i
        ));
      }
    }
  };

  
  React.useEffect(() => {
    if (items.some(i => i.status === STATUS.PENDING)) {
      processQueue();
    }
  }, [items, processQueue]);

  
  const triggerSelect = () => fileInputRef.current?.click();

  
  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(addFile);
    
    e.target.value = '';
  };

  
  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    files.forEach(addFile);
  };

  
  const handleClose = () => {
    setItems([]);
    onClose();
  };

  
  const successCount = items.filter(i => i.status === STATUS.DONE).length;
  const failedCount = items.filter(i => i.status === STATUS.FAILED).length;
  const allDone = items.length > 0 && items.every(i => i.status === STATUS.DONE || i.status === STATUS.FAILED);

  
  const renderQueue = () => (
    <div className="upload-queue">
      {items.map(item => (
        <div key={item.id} className="upload-queue-item">
          <div className="upload-queue-icon">
            <FileText size={18} />
          </div>
          <div className="upload-queue-info">
            <div className="upload-queue-name">{item.name}</div>
            <div className="upload-queue-size">
              {(item.size / 1024).toFixed(1)} KB
            </div>
            {item.status === STATUS.UPLOADING && (
              <div className="upload-queue-progress">
                <div className="upload-queue-progress-bar" style={{ width: `${item.progress}%` }} />
              </div>
            )}
            {item.status === STATUS.FAILED && (
              <div className="upload-queue-error">{item.error}</div>
            )}
          </div>
          <div className="upload-queue-status">
            {item.status === STATUS.PENDING && <span className="status-pending">Pending</span>}
            {item.status === STATUS.UPLOADING && <Loader2 size={16} className="spinning" />}
            {item.status === STATUS.DONE && <CheckCircle size={16} className="status-done" />}
            {item.status === STATUS.FAILED && <AlertCircle size={16} className="status-failed" />}
          </div>
        </div>
      ))}
    </div>
  );

  
  const renderSummary = () => (
    <div className="upload-summary">
      <p>
        {successCount} uploaded
        {failedCount > 0 && `, ${failedCount} failed`}.
      </p>
      {successCount > 0 && (
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem' }}>
          <button
            className="btn-primary"
            style={{ flex: 1 }}
            onClick={() => {
              
              const first = items.find(i => i.status === STATUS.DONE);
              if (first?.result?.id) {
                onClose();
                navigate(`/documents/${first.result.id}`);
              }
            }}
          >
            View Document
          </button>
          <button
            className="btn-secondary"
            style={{ flex: 1 }}
            onClick={handleClose}
          >
            Close
          </button>
        </div>
      )}
    </div>
  );

  
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="upload-modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
        >
          <motion.div
            className="upload-modal"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
          >
            {}
            <div className="upload-modal-header">
              <h2>Upload Documents</h2>
              <button className="upload-modal-close" onClick={handleClose} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            {}
            <div
              className="upload-dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={triggerSelect}
            >
              <UploadCloud size={28} strokeWidth={1.5} color="var(--c-555)" />
              <span className="upload-area-text">
                Drop files here or click to browse — PDFs, Word (.docx), Text (.txt, .md), Data (.csv, .xlsx, .json) (Max 25 MB per file)
              </span>
            </div>

            {}
            {items.length > 0 && renderQueue()}
            {allDone && items.length > 0 && renderSummary()}

            {}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.json"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
