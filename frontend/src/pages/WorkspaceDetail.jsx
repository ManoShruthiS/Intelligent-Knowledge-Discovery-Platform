import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Upload, FileText, Database, Code, Bookmark, 
  Edit3, Plus, Trash2, ExternalLink 
} from 'lucide-react';
import { UploadContext } from '../components/layout/AppLayout';
import * as api from '../services/api';
import NoteModal from '../components/common/NoteModal';
import ResourceModal from '../components/common/ResourceModal';
import './WorkspaceDetail.css';

export default function WorkspaceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openUpload } = useContext(UploadContext);
  
  const [workspace, setWorkspace] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [notes, setNotes] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  
  const [noteModalOpen, setNoteModalOpen] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [resourceModalOpen, setResourceModalOpen] = useState(false);
  const [resourceModalType, setResourceModalType] = useState('learning_source');

  const loadWorkspaceData = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const ws = await api.getWorkspace(id);
      setWorkspace(ws);

      const docsData = await api.listWorkspaceDocuments(id);
      const docsList = Array.isArray(docsData) ? docsData : (docsData?.documents || docsData?.items || []);
      setDocuments(docsList);

      const notesData = await api.listNotes(id);
      setNotes(Array.isArray(notesData) ? notesData : []);

      const resourcesData = await api.listResources(id);
      setResources(Array.isArray(resourcesData) ? resourcesData : []);
    } catch (err) {
      console.error(err);
      setError('Failed to load workspace data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspaceData();

    
    const handleUploadComplete = () => {
      loadWorkspaceData();
    };
    window.addEventListener('uploadComplete', handleUploadComplete);

    return () => {
      window.removeEventListener('uploadComplete', handleUploadComplete);
    };
  }, [id]);

  
  const handleOpenAddNote = () => {
    setEditingNote(null);
    setNoteModalOpen(true);
  };

  const handleOpenEditNote = (note) => {
    setEditingNote(note);
    setNoteModalOpen(true);
  };

  const handleSaveNote = async (noteData) => {
    try {
      if (editingNote) {
        await api.updateNote(editingNote.id, noteData);
      } else {
        await api.createNote(id, noteData);
      }
      loadWorkspaceData();
    } catch (err) {
      console.error('Failed to save note:', err);
    }
  };

  const handleDeleteNote = async (noteId, e) => {
    if (e) e.stopPropagation();
    try {
      await api.deleteNote(noteId);
      setNotes(prev => prev.filter(n => n.id !== noteId));
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  };

  
  const handleOpenAddResource = (type) => {
    setResourceModalType(type);
    setResourceModalOpen(true);
  };

  const handleSaveResource = async (resourceData) => {
    try {
      await api.createResource(id, resourceData);
      loadWorkspaceData();
    } catch (err) {
      console.error('Failed to save resource:', err);
    }
  };

  const handleDeleteResource = async (resourceId, e) => {
    if (e) e.stopPropagation();
    try {
      await api.deleteResource(resourceId);
      setResources(prev => prev.filter(r => r.id !== resourceId));
    } catch (err) {
      console.error('Failed to delete resource:', err);
    }
  };

  
  const handleRemoveDocument = async (docId, e) => {
    if (e) e.stopPropagation();
    try {
      await api.removeDocumentFromWorkspace(id, docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err) {
      console.error('Failed to remove document from workspace:', err);
    }
  };

  const handleOpenLink = (url, e) => {
    if (e) e.stopPropagation();
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  if (loading) {
    return (
      <div className="ws-loading-screen">
        <div className="spinner"></div>
        <p>Loading workspace...</p>
      </div>
    );
  }

  if (error || !workspace) {
    return (
      <div className="ws-error-screen">
        <ArrowLeft size={32} className="ws-back-icon" onClick={() => navigate('/workspaces')} />
        <h2>{error || 'Workspace not found'}</h2>
      </div>
    );
  }

  const datasets = resources.filter(r => r.resource_type === 'dataset');
  const repositories = resources.filter(r => r.resource_type === 'repository');
  const learningSources = resources.filter(r => r.resource_type === 'learning_source');

  return (
    <div className="workspace-dashboard-root">
      {}
      <div className="ws-dash-header">
        <div className="ws-dash-title-area">
          <button className="ws-btn-ghost-back" onClick={() => navigate('/workspaces')}>
            <ArrowLeft size={18} />
            <span>Back to Workspaces</span>
          </button>
          <h1 className="ws-dash-headline">{workspace.name || workspace.title || 'Untitled Workspace'}</h1>
          <p className="ws-dash-subline">{workspace.description || 'Manage your collection of resources for this project.'}</p>
        </div>
      </div>

      {}
      <div className="ws-dash-grid">
        
        {}
        <div className="ws-dash-card">
          <div className="ws-dash-card-header">
            <div className="ws-dash-card-title">
              <FileText size={20} className="icon-docs" />
              <span>PDF Documents</span>
            </div>
            <button className="ws-btn-small" onClick={() => openUpload(id)}>
              <Upload size={14} /> Add
            </button>
          </div>
          <div className="ws-dash-card-content">
            {documents.length === 0 ? (
              <p className="empty-state-text">No PDFs uploaded yet. Add some to get started.</p>
            ) : (
              <div className="resource-list">
                {documents.map(doc => (
                  <div 
                    key={doc.id} 
                    className="resource-item group clickable" 
                    onClick={() => navigate(`/documents/${doc.id}`)}
                    title="Click to open PDF viewer"
                  >
                    <div className="resource-icon pdf-icon">PDF</div>
                    <div className="resource-info">
                      <h4>{doc.filename || doc.name}</h4>
                      <span>{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Recently added'}</span>
                    </div>
                    <button 
                      className="item-delete-btn" 
                      title="Remove PDF from Workspace"
                      onClick={(e) => handleRemoveDocument(doc.id, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {}
        <div className="ws-dash-card">
          <div className="ws-dash-card-header">
            <div className="ws-dash-card-title">
              <Database size={20} className="icon-data" />
              <span>Datasets</span>
            </div>
            <button className="ws-btn-small" onClick={() => handleOpenAddResource('dataset')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <div className="ws-dash-card-content">
            {datasets.length === 0 ? (
              <p className="empty-state-text">No datasets added yet. Click Add to link a dataset.</p>
            ) : (
              <div className="resource-list">
                {datasets.map(res => (
                  <div 
                    key={res.id} 
                    className={`resource-item group ${res.url ? 'clickable' : ''}`}
                    onClick={(e) => res.url && handleOpenLink(res.url, e)}
                    title={res.url ? `Open ${res.url}` : res.title}
                  >
                    <div className="resource-icon data-icon">DATA</div>
                    <div className="resource-info">
                      <h4>
                        {res.title} {res.url && <ExternalLink size={12} className="inline-link-icon" />}
                      </h4>
                      {res.description && <span>{res.description}</span>}
                    </div>
                    <button 
                      className="item-delete-btn" 
                      title="Delete Dataset"
                      onClick={(e) => handleDeleteResource(res.id, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {}
        <div className="ws-dash-card">
          <div className="ws-dash-card-header">
            <div className="ws-dash-card-title">
              <Code size={20} className="icon-repos" />
              <span>Repositories</span>
            </div>
            <button className="ws-btn-small" onClick={() => handleOpenAddResource('repository')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <div className="ws-dash-card-content">
            {repositories.length === 0 ? (
              <p className="empty-state-text">No repos added yet. Click Add to link a repository.</p>
            ) : (
              <div className="resource-list">
                {repositories.map(res => (
                  <div 
                    key={res.id} 
                    className={`resource-item group ${res.url ? 'clickable' : ''}`}
                    onClick={(e) => res.url && handleOpenLink(res.url, e)}
                    title={res.url ? `Open ${res.url}` : res.title}
                  >
                    <div className="resource-icon repo-icon">REPO</div>
                    <div className="resource-info">
                      <h4>
                        {res.title} {res.url && <ExternalLink size={12} className="inline-link-icon" />}
                      </h4>
                      {res.description && <span>{res.description}</span>}
                    </div>
                    <button 
                      className="item-delete-btn" 
                      title="Delete Repository"
                      onClick={(e) => handleDeleteResource(res.id, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {}
        <div className="ws-dash-card">
          <div className="ws-dash-card-header">
            <div className="ws-dash-card-title">
              <Bookmark size={20} className="icon-saved" />
              <span>Saved Learning Sources</span>
            </div>
            <button className="ws-btn-small" onClick={() => handleOpenAddResource('learning_source')}>
              <Plus size={14} /> Add
            </button>
          </div>
          <div className="ws-dash-card-content">
            {learningSources.length === 0 ? (
              <p className="empty-state-text">No learning sources saved yet. Click Add to save a source.</p>
            ) : (
              <div className="resource-list">
                {learningSources.map(res => (
                  <div 
                    key={res.id} 
                    className={`resource-item group ${res.url ? 'clickable' : ''}`}
                    onClick={(e) => res.url && handleOpenLink(res.url, e)}
                    title={res.url ? `Open ${res.url}` : res.title}
                  >
                    <div className="resource-icon source-icon">LINK</div>
                    <div className="resource-info">
                      <h4>
                        {res.title} {res.url && <ExternalLink size={12} className="inline-link-icon" />}
                      </h4>
                      {res.description && <span>{res.description}</span>}
                    </div>
                    <button 
                      className="item-delete-btn" 
                      title="Delete Source"
                      onClick={(e) => handleDeleteResource(res.id, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {}
        <div className="ws-dash-card note-card-wide">
          <div className="ws-dash-card-header">
            <div className="ws-dash-card-title">
              <Edit3 size={20} className="icon-notes" />
              <span>Notes & Insights</span>
            </div>
            <button className="ws-btn-small" onClick={handleOpenAddNote}>
              <Plus size={14} /> Add Note
            </button>
          </div>
          <div className="ws-dash-card-content">
            {notes.length === 0 ? (
              <p className="empty-state-text">No personal notes created in this workspace yet. Click Add Note to capture thoughts.</p>
            ) : (
              <div className="notes-grid">
                {notes.map(note => (
                  <div key={note.id} className="note-card-item">
                    <div className="note-card-header">
                      <h4 className="note-card-title">{note.title || 'Untitled Note'}</h4>
                      <div className="note-card-actions">
                        <button className="note-action-btn" title="Edit Note" onClick={() => handleOpenEditNote(note)}>
                          <Edit3 size={14} />
                        </button>
                        <button className="note-action-btn delete" title="Delete Note" onClick={(e) => handleDeleteNote(note.id, e)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <p className="note-card-body">{note.content}</p>
                    <span className="note-card-date">
                      {note.updated_at ? new Date(note.updated_at).toLocaleDateString() : note.created_at ? new Date(note.created_at).toLocaleDateString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>

      {}
      <NoteModal 
        isOpen={noteModalOpen}
        onClose={() => setNoteModalOpen(false)}
        onSave={handleSaveNote}
        initialNote={editingNote}
      />

      <ResourceModal 
        isOpen={resourceModalOpen}
        onClose={() => setResourceModalOpen(false)}
        onSave={handleSaveResource}
        defaultType={resourceModalType}
      />
    </div>
  );
}
