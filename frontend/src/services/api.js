const API_BASE_URL = 'http://localhost:8000/api';

export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Upload failed with status ${response.status}`);
  }

  return response.json();
};

export const getDocuments = async () => {
  const response = await fetch(`${API_BASE_URL}/documents`);
  if (!response.ok) {
    throw new Error(`Failed to fetch documents with status ${response.status}`);
  }
  return response.json();
};

export const getDocument = async (id) => {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Document not found");
    }
    throw new Error(`Failed to fetch document with status ${response.status}`);
  }
  return response.json();
};

export const deleteDocument = async (id) => {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document with status ${response.status}`);
  }
  return response.json();
};

export const createWorkspace = async (name, description = '') => {
  const response = await fetch(`${API_BASE_URL}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!response.ok) throw new Error('Failed to create workspace');
  return response.json();
};

export const getWorkspaces = async () => {
  const response = await fetch(`${API_BASE_URL}/workspaces`);
  if (!response.ok) throw new Error('Failed to fetch workspaces');
  return response.json();
};

export const getWorkspace = async (id) => {
  const response = await fetch(`${API_BASE_URL}/workspaces/${id}`);
  if (!response.ok) throw new Error('Failed to fetch workspace');
  return response.json();
};

export const updateWorkspace = async (id, name, description = '') => {
  const response = await fetch(`${API_BASE_URL}/workspaces/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!response.ok) throw new Error('Failed to update workspace');
  return response.json();
};

export const deleteWorkspace = async (id) => {
  const response = await fetch(`${API_BASE_URL}/workspaces/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete workspace');
  return response.json();
};

export const addDocumentToWorkspace = async (workspaceId, documentId) => {
  const response = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/documents/${documentId}`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to add document to workspace');
  return response.json();
};

export const removeDocumentFromWorkspace = async (workspaceId, documentId) => {
  const response = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to remove document from workspace');
  return response.json();
};

export const askWorkspace = async (workspaceId, question) => {
  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, workspace_id: workspaceId }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || 'Failed to get answer');
  }
  return response.json();
};
