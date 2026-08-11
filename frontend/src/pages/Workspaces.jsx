import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus, Search, MoreVertical, Clock, X } from 'lucide-react';
import { getWorkspaces, createWorkspace, deleteWorkspace } from '../services/api';
import './Workspaces.css';

function Workspaces() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Create Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDesc, setNewWorkspaceDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const fetchWorkspaces = async () => {
    try {
      setLoading(true);
      const data = await getWorkspaces();
      setWorkspaces(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkspace = async (e) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    
    setIsCreating(true);
    try {
      const ws = await createWorkspace(newWorkspaceName, newWorkspaceDesc);
      setWorkspaces([ws, ...workspaces]);
      setShowCreateModal(false);
      setNewWorkspaceName('');
      setNewWorkspaceDesc('');
    } catch (err) {
      alert("Failed to create workspace: " + err.message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteWorkspace = async (e, id) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this workspace?")) {
      try {
        await deleteWorkspace(id);
        setWorkspaces(workspaces.filter(ws => ws.id !== id));
      } catch (err) {
        alert("Failed to delete workspace: " + err.message);
      }
    }
  };

  const filteredWorkspaces = workspaces.filter(ws => 
    ws.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    (ws.description && ws.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="workspaces-container">
      <div className="workspaces-header">
        <div>
          <h1>Workspaces</h1>
          <p>Organize your research, documents, and notes by topic.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={18} />
          New Workspace
        </button>
      </div>

      <div className="workspaces-toolbar">
        <div className="search-box">
          <Search size={18} color="var(--c-888)" />
          <input 
            type="text" 
            placeholder="Search workspaces..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="sort-box">
          <Clock size={16} color="var(--c-555)" />
          <span>Recently updated</span>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading workspaces...</div>
      ) : error ? (
        <div className="error-state">{error}</div>
      ) : filteredWorkspaces.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><FolderKanban size={48} color="var(--c-eee)" strokeWidth={1} /></div>
          <h3>No workspaces found</h3>
          <p>Create a workspace to start organizing your research.</p>
        </div>
      ) : (
        <div className="workspaces-grid">
          {filteredWorkspaces.map(ws => (
            <div key={ws.id} className="workspace-card" onClick={() => navigate(`/workspaces/${ws.id}`)}>
              <div className="workspace-card-header">
                <div className="workspace-icon">
                  <FolderKanban size={24} strokeWidth={1.5} />
                </div>
                <button className="btn-icon delete-btn" onClick={(e) => handleDeleteWorkspace(e, ws.id)}>
                  <MoreVertical size={16} />
                </button>
              </div>
              
              <div className="workspace-card-content">
                <h3>{ws.name}</h3>
                {ws.description && <p className="ws-desc">{ws.description}</p>}
              </div>
              
              <div className="workspace-card-footer">
                <span className="last-updated">Updated {new Date(ws.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Workspace</h2>
              <button className="btn-icon" onClick={() => setShowCreateModal(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateWorkspace}>
              <div className="form-group">
                <label>Workspace Name</label>
                <input 
                  type="text" 
                  value={newWorkspaceName} 
                  onChange={e => setNewWorkspaceName(e.target.value)}
                  placeholder="e.g. Quantum Computing Research"
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label>Description (optional)</label>
                <textarea 
                  value={newWorkspaceDesc} 
                  onChange={e => setNewWorkspaceDesc(e.target.value)}
                  placeholder="Briefly describe what this workspace is for..."
                  rows={3}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={isCreating || !newWorkspaceName.trim()}>
                  {isCreating ? 'Creating...' : 'Create Workspace'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Workspaces;
