import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import './NoteModal.css';

export default function ResourceModal({ isOpen, onClose, onSave, defaultType = 'learning_source' }) {
  const [resourceType, setResourceType] = useState(defaultType);
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    setResourceType(defaultType || 'learning_source');
    setTitle('');
    setUrl('');
    setDescription('');
  }, [defaultType, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    onSave({
      resource_type: resourceType,
      title: title.trim(),
      url: url.trim(),
      description: description.trim()
    });
    onClose();
  };

  const getModalTitle = () => {
    switch (resourceType) {
      case 'dataset': return 'Add Dataset';
      case 'repository': return 'Add Repository';
      case 'learning_source': default: return 'Add Saved Learning Source';
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{getModalTitle()}</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="resource-type">Resource Category</label>
            <select
              id="resource-type"
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              className="modal-select"
            >
              <option value="dataset">Dataset (Kaggle, HuggingFace, etc.)</option>
              <option value="repository">Repository (GitHub, GitLab, etc.)</option>
              <option value="learning_source">Saved Learning Source (Article, Video, Paper)</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="resource-title">Title / Name</label>
            <input
              id="resource-title"
              type="text"
              placeholder="e.g. Climate Change Dataset 2024"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="modal-input"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="resource-url">Resource URL (optional)</label>
            <input
              id="resource-url"
              type="url"
              placeholder="https://..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="modal-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="resource-description">Description / Notes (optional)</label>
            <textarea
              id="resource-description"
              placeholder="Brief overview of this resource..."
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="modal-textarea"
            />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Add Resource
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
