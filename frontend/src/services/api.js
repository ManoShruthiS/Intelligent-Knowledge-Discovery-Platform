/**
 * Centralized API client for KNO.
 *
 * Goals:
 *  - One place for the backend base URL (env-configurable).
 *  - Friendly error messages for common failures (network down, 4xx, 5xx).
 *  - Backwards compatible: every existing export keeps the same signature.
 *
 * Env config (Vite):
 *   VITE_API_BASE_URL  e.g. "http://localhost:8000/api"
 *                      defaults to "http://localhost:8000/api".
 */

const RAW_BASE =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000/api";

const API_BASE_URL = RAW_BASE.replace(/\/+$/, "");

const BACKEND_DOWN_MSG =
  "Unable to connect to KNO's research service. Please check that the backend is running on " +
  API_BASE_URL.replace(/\/api$/, "") +
  ".";

class APIError extends Error {
  constructor(message, { status = null, detail = null } = {}) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
  }
}

async function handle(response) {
  let body = null;
  try {
    body = await response.json();
  } catch (_) {}
  if (response.ok) return body;
  const detail =
    (body && (body.detail || body.message)) ||
    response.statusText ||
    `Request failed with status ${response.status}`;
  return Promise.reject(
    new APIError(typeof detail === "string" ? detail : JSON.stringify(detail), {
      status: response.status,
      detail,
    })
  );
}

async function request(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new APIError(BACKEND_DOWN_MSG, { status: null });
  }
  return handle(response);
}

// ---------- Documents ----------

export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return request("/documents/upload", { method: "POST", body: formData });
};

export const getDocuments = async () => request("/documents");

export const getDocument = async (id) => request(`/documents/${id}`);

export const getDocumentChunks = async (id) =>
  request(`/documents/${id}/chunks`);

export const deleteDocument = async (id) =>
  request(`/documents/${id}`, { method: "DELETE" });

export const createDocument = async (workspaceId, payload) =>
  request("/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId, ...payload }),
  });

export const updateDocument = async (id, payload) =>
  request(`/documents/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const listWorkspaceDocuments = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/documents`);

export const getDocumentSummary = async (id) =>
  request(`/documents/${id}/summary`);

export const getDocumentInsights = async (id) =>
  request(`/documents/${id}/insights`);

export const getDocumentSources = async (id) =>
  request(`/documents/${id}/sources`);

export const getDocumentVersions = async (id) =>
  request(`/documents/${id}/versions`);

export const createDocumentVersion = async (id) =>
  request(`/documents/${id}/versions`, { method: "POST" });

// ---------- Workspaces ----------

export const createWorkspace = async (name, description = "") =>
  request("/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });

export const getWorkspaces = async () => request("/workspaces");

export const getWorkspace = async (id) => request(`/workspaces/${id}`);

export const updateWorkspace = async (id, name, description = "") =>
  request(`/workspaces/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });

export const deleteWorkspace = async (id) =>
  request(`/workspaces/${id}`, { method: "DELETE" });

export const addDocumentToWorkspace = async (workspaceId, documentId) =>
  request(`/workspaces/${workspaceId}/documents/${documentId}`, {
    method: "POST",
  });

export const removeDocumentFromWorkspace = async (workspaceId, documentId) =>
  request(`/workspaces/${workspaceId}/documents/${documentId}`, {
    method: "DELETE",
  });

export const compareWorkspacePapers = async (workspaceId, documentIds) =>
  request(`/workspaces/${workspaceId}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });

// ---------- Notes ----------

export const listNotes = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/notes`);

export const createNote = async (workspaceId, payload) =>
  request(`/workspaces/${workspaceId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateNote = async (noteId, payload) =>
  request(`/notes/${noteId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteNote = async (noteId) =>
  request(`/notes/${noteId}`, { method: "DELETE" });

// ---------- Research Brief ----------

export const getBrief = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/brief`);

export const updateBrief = async (workspaceId, fields) =>
  request(`/workspaces/${workspaceId}/brief`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });

export const autoDraftBrief = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/brief/auto-draft`, {
    method: "POST",
  });

// ---------- Project Plan ----------

export const getProjectPlan = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/project-plan`);

export const updateProjectPlan = async (workspaceId, fields) =>
  request(`/workspaces/${workspaceId}/project-plan`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });

export const autoGenerateProjectPlan = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/project-plan/auto-generate`, {
    method: "POST",
  });

// ---------- Experiments ----------

export const listExperiments = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/experiments`);

export const createExperiment = async (workspaceId, payload) =>
  request(`/workspaces/${workspaceId}/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateExperiment = async (experimentId, payload) =>
  request(`/experiments/${experimentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteExperiment = async (experimentId) =>
  request(`/experiments/${experimentId}`, { method: "DELETE" });

export const getExperimentAnalytics = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/experiments/analytics`);

// ---------- Research Gap + Synthesis ----------

export const analyzeResearchGap = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/research-gap`, { method: "POST" });

export const synthesizeWorkspace = async (workspaceId, question = null) =>
  request(`/workspaces/${workspaceId}/synthesis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

// ---------- Citations ----------

export const listCitations = async (workspaceId = null) => {
  const q = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return request(`/citations${q}`);
};

export const addCitation = async (payload) =>
  request("/citations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteCitation = async (id) =>
  request(`/citations/${id}`, { method: "DELETE" });

export const extractCitations = async (documentId) =>
  request(`/documents/${documentId}/citations/extract`, { method: "POST" });

export const formatCitation = async (id, style = "ieee") =>
  request(`/citations/format?id=${encodeURIComponent(id)}&style=${encodeURIComponent(style)}`);

export const bibliography = async (style, ids) =>
  request("/citations/bibliography", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ style, ids }),
  });

// ---------- Discovery ----------

export const discoverResearch = async (query, limitPerSource = 8) =>
  request("/discover/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit_per_source: limitPerSource }),
  });

export const discoverGithub = async (query, limit = 10) =>
  request("/discover/github", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });

export const discoverDatasets = async (query, limit = 10) =>
  request("/discover/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });

// ---------- Studio ----------

export const listStudioTemplates = async () =>
  request("/studio/templates");

export const listStudioDocs = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/studio`);

export const createStudioDoc = async (workspaceId, template, title) =>
  request("/studio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId, template, title }),
  });

export const getStudioDoc = async (sid) => request(`/studio/${sid}`);

export const updateStudioDoc = async (sid, payload) =>
  request(`/studio/${sid}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteStudioDoc = async (sid) =>
  request(`/studio/${sid}`, { method: "DELETE" });

export const studioHelp = async (sid, action, instruction = "") =>
  request(`/studio/${sid}/help`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, instruction }),
  });

// ---------- Settings ----------

export const getProvidersStatus = async () =>
  request("/settings/providers");

export const getSettings = async () => request("/settings");

export const updateSettings = async (payload) =>
  request("/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

// ---------- Workspace Templates ----------

export const listWorkspaceTemplates = async () =>
  request("/workspace-templates");

export const createWorkspaceTemplate = async (payload) =>
  request("/workspace-templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteWorkspaceTemplate = async (id) =>
  request(`/workspace-templates/${id}`, { method: "DELETE" });

export const applyWorkspaceTemplate = async (workspaceId, templateId) =>
  request(`/workspaces/${workspaceId}/apply-template/${templateId}`, {
    method: "POST",
  });

// ---------- Document Tags ----------

export const addDocumentTag = async (documentId, tag) =>
  request(`/documents/${documentId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag }),
  });

export const removeDocumentTag = async (documentId, tag) =>
  request(`/documents/${documentId}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  });

export const getDocumentTags = async (documentId) =>
  request(`/documents/${documentId}/tags`);

export const getAllTags = async () => request("/tags");

// ---------- Search + Ask ----------

export const askOrbot = async (payload) =>
  request("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const searchDocuments = async ({
  query,
  documentId = null,
  workspaceId = null,
  topK = 5,
}) =>
  request("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      document_id: documentId,
      workspace_id: workspaceId,
      top_k: topK,
    }),
  });
