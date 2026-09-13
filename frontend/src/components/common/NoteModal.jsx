import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import './NoteModal.css';

export default function NoteModal({ isOpen, onClose, onSave, initialNote = null }) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  useEffect(() => {
    if (initialNote) {
      setTitle(initialNote.title || '');
      setContent(initialNote.content || '');
    } else {
      setTitle('');
      setContent('');
    }
  }, [initialNote, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!content.trim() && !title.trim()) return;
    onSave({
      title: title.trim() || 'Untitled Note',
      content: content.trim()
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{initialNote ? 'Edit Note' : 'Create New Note'}</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="note-title">Title</label>
            <input
              id="note-title"
              type="text"
              placeholder="Note Title..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="modal-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="note-content">Note Content</label>
            <textarea
              id="note-content"
              placeholder="Write your note or insight here..."
              rows={6}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="modal-textarea"
              required
            />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              {initialNote ? 'Save Changes' : 'Create Note'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
