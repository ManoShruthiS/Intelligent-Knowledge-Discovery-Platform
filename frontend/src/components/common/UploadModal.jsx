import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react';
import { uploadDocument } from '../../services/api';
import { useNavigate } from 'react-router-dom';
import './UploadModal.css';

const UploadModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, processing, success, error
  const [uploadError, setUploadError] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const processFile = async (file) => {
    if (!file) return;

    // Validate extension roughly on client side
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) {
      setUploadError(`Unsupported file type: ${ext}. Please upload PDF, DOCX, or TXT.`);
      setUploadStatus('error');
      return;
    }

    setUploadStatus('processing');
    setUploadError(null);
    setUploadResult(null);

    try {
      const result = await uploadDocument(file);
      setUploadResult(result);
      setUploadStatus('success');
    } catch (err) {
      setUploadError(err.message || 'Unable to process this document');
      setUploadStatus('error');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const triggerSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const resetAndClose = () => {
    setUploadStatus('idle');
    setUploadError(null);
    setUploadResult(null);
    onClose();
  };

  const renderUploadArea = () => {
    if (uploadStatus === 'processing') {
      return (
        <div className="modal-upload-area processing">
          <Loader2 size={48} className="upload-icon spinning" strokeWidth={1.5} />
          <h2 className="upload-title">Analyzing document...</h2>
          <p className="upload-desc">Extracting text and identifying structure</p>
        </div>
      );
    }

    if (uploadStatus === 'success') {
      return (
        <div className="modal-upload-area success">
          <CheckCircle2 size={48} className="upload-icon success-icon" strokeWidth={1.5} />
          <h2 className="upload-title">Document analyzed</h2>
          <p className="upload-desc">Your document is ready for knowledge discovery</p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', width: '100%' }}>
            <button className="btn-primary" style={{ flex: 1 }} onClick={() => {
              resetAndClose();
              navigate(`/documents/${uploadResult.id}`);
            }}>
              Open document
            </button>
            <button className="btn-secondary" style={{ flex: 1 }} onClick={() => {
              setUploadStatus('idle');
              setUploadResult(null);
            }}>
              Upload another
            </button>
          </div>
        </div>
      );
    }

    if (uploadStatus === 'error') {
      return (
        <div className="modal-upload-area error" onClick={triggerSelect}>
          <AlertCircle size={48} className="upload-icon error-icon" strokeWidth={1.5} />
          <h2 className="upload-title">Unable to process</h2>
          <p className="upload-desc error-text">{uploadError}</p>
          <button className="btn-secondary" style={{ marginTop: '1.5rem' }}>Try again</button>
        </div>
      );
    }

    // Default Idle State
    return (
      <div 
        className={`modal-upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={triggerSelect}
      >
        <div className="upload-icon-wrapper">
          <UploadCloud size={32} strokeWidth={1.5} color="var(--c-555)" />
        </div>
        <h2 className="upload-title">Select a document</h2>
        <p className="upload-desc">Drag and drop, or click to browse</p>
        <p className="upload-formats">Supported formats: PDF, DOCX, TXT</p>
      </div>
    );
  };

  return (
    <div className="modal-overlay" onClick={resetAndClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Upload Papers</h3>
          <button className="modal-close" onClick={resetAndClose}>
            <X size={20} strokeWidth={1.5} />
          </button>
        </div>
        <div className="modal-body">
          <input 
            ref={fileInputRef}
            type="file" 
            style={{ display: 'none' }}
            accept=".pdf,.docx,.txt"
            onChange={handleChange}
          />
          {renderUploadArea()}
        </div>
      </div>
    </div>
  );
};

export default UploadModal;
