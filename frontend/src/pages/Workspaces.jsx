import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Folder, Plus, Search, Trash2 } from 'lucide-react';
import { getWorkspaces, createWorkspace, deleteWorkspace } from '../services/api';
import './Workspaces.css';


const COLORS = ['teal', 'gold', 'green', 'purple', 'red'];

export default function Workspaces() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  
  
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
      const list = Array.isArray(data) ? data : (data?.items || data?.workspaces || []);
      setWorkspaces(list);
    } catch (err) {
      console.error(err);
      setWorkspaces([]);
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
      setWorkspaces(prev => Array.isArray(prev) ? [ws, ...prev] : [ws]);
      setShowCreateModal(false);
      setNewWorkspaceName('');
      setNewWorkspaceDesc('');
    } catch (err) {
      console.error(err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteWorkspace = async (wsId, e) => {
    e.stopPropagation();
    try {
      await deleteWorkspace(wsId);
      setWorkspaces(prev => prev.filter(w => w.id !== wsId));
    } catch (err) {
      console.error('Failed to delete workspace:', err);
    }
  };

  const list = Array.isArray(workspaces) ? workspaces : [];
  const filteredWorkspaces = list.filter(ws => 
    (ws.name || ws.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="workspaces-root">
      {}
      <div className="ws-header-row">
        <div className="ws-header-text">
          <h1 className="ws-headline">Workspaces</h1>
          <p className="ws-subline">Organize your knowledge</p>
        </div>
        <button className="ws-btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={18} strokeWidth={2} /> New Workspace
        </button>
      </div>

      {}
      <div className="ws-grid">
        {filteredWorkspaces.map((ws, index) => {
          const colorClass = `ws-color-${COLORS[index % COLORS.length]}`;
          
          return (
            <div 
              key={ws.id} 
              className="ws-card compact-card"
              onClick={() => navigate(`/workspaces/${ws.id}`)}
            >
              <div className={`ws-card-icon ${colorClass}`}>
                <Folder size={20} strokeWidth={1.5} />
              </div>
              <div className="ws-card-info">
                <h3>{ws.name}</h3>
              </div>
              <button 
                className="ws-card-delete-btn" 
                title="Delete Workspace" 
                onClick={(e) => handleDeleteWorkspace(ws.id, e)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          );
        })}

        {}
        <div className="ws-card ws-card-create compact-card" onClick={() => setShowCreateModal(true)}>
          <div className="ws-card-icon create-icon-wrapper">
            <Plus size={20} className="ws-create-icon" />
          </div>
          <div className="ws-card-info">
            <h3>Create New Workspace</h3>
          </div>
        </div>
      </div>

      {}
      {showCreateModal && (
        <div className="ws-modal-overlay">
          <div className="ws-modal">
            <h2>Create New Workspace</h2>
            <form onSubmit={handleCreateWorkspace}>
              <div className="ws-form-group">
                <label>Workspace Name</label>
                <input 
                  type="text" 
                  value={newWorkspaceName}
                  onChange={e => setNewWorkspaceName(e.target.value)}
                  placeholder="e.g., Quantum Computing Papers"
                  autoFocus
                />
              </div>
              <div className="ws-form-group">
                <label>Description (optional)</label>
                <textarea 
                  value={newWorkspaceDesc}
                  onChange={e => setNewWorkspaceDesc(e.target.value)}
                  placeholder="What is this workspace about?"
                  rows={3}
                />
              </div>
              <div className="ws-modal-actions">
                <button type="button" className="ws-btn-ghost" onClick={() => setShowCreateModal(false)}>Cancel</button>
                <button type="submit" className="ws-btn-primary" disabled={!newWorkspaceName.trim() || isCreating}>
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
