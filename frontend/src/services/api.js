












const RAW_BASE =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000/api";

let CLEAN_BASE = RAW_BASE.replace(/\/+$/, "");
if (!CLEAN_BASE.endsWith("/api")) {
  CLEAN_BASE = `${CLEAN_BASE}/api`;
}
const API_BASE_URL = CLEAN_BASE;

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

// Returns a stable per-browser UUID stored in localStorage.
// Created once on first visit, persists across refreshes.
const _getClientId = () => {
  try {
    const KEY = "kno.user_id";
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch (_) {
    return "anonymous";
  }
};

async function request(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;

  // Always attach the per-browser client ID so the backend can filter
  // documents / workspaces per user without a full auth system.
  const clientId = _getClientId();
  const existingHeaders = options.headers || {};
  options = {
    ...options,
    headers: {
      ...existingHeaders,
      "X-Client-Id": clientId,
    },
  };

  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new APIError(BACKEND_DOWN_MSG, { status: null });
  }
  return handle(response);
}



export const uploadDocument = async (file, workspaceId = null) => {
  const formData = new FormData();
  formData.append("file", file);
  if (workspaceId) {
    formData.append("workspace_id", workspaceId);
  }
  return request("/documents/upload", { method: "POST", body: formData });
};


export const getDocuments = async () => request("/documents");
export const listDocuments = getDocuments;

export const getDocument = async (id) => request(`/documents/${id}`);

export const getDocumentChunks = async (id) =>
  request(`/documents/${id}/chunks`);

export const generateDocumentSummary = async (id) =>
  request(`/documents/${id}/generate-summary`, { method: "POST" });






export const getChunkHighlight = async (chunkId) =>
  request(`/chunks/${chunkId}/highlight`);





export const getDocumentFileUrl = (id) =>
  `${API_BASE_URL}/documents/${id}/file`;







export const exportCitations = async ({ style = 'bibtex', ids, workspace_id } = {}) =>
  request('/citations/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ style, ids, workspace_id }),
  });

export const deleteDocument = async (id) =>
  request(`/documents/${id}`, { method: "DELETE" });

export const toggleDocumentStar = async (id, starred) =>
  request(`/documents/${id}/star`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ starred }),
  });

export const createDocument = async (workspaceId, payload) =>
  request("/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId, ...payload }),
  });

export const importDocument = async (payload) =>
  request("/documents/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateDocument = async (id, payload) =>
  request(`/documents/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const listWorkspaceDocuments = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/documents`);

export const getDocumentSummary = async (id, { forceRegenerate = false } = {}) => {
  const q = forceRegenerate ? '?force_regenerate=true' : '';
  return request(`/documents/${id}/summary${q}`);
};

export const getDocumentInsights = async (id, { forceRegenerate = false } = {}) => {
  const q = forceRegenerate ? '?force_regenerate=true' : '';
  return request(`/documents/${id}/insights${q}`);
};

export const getDocumentSources = async (id) =>
  request(`/documents/${id}/sources`);

export const deleteDocumentAnalysis = async (id, kind = null) => {
  const q = kind ? `?kind=${encodeURIComponent(kind)}` : '';
  return request(`/documents/${id}/analysis${q}`, { method: 'DELETE' });
};

export const getDocumentVersions = async (id) =>
  request(`/documents/${id}/versions`);

export const createDocumentVersion = async (id) =>
  request(`/documents/${id}/versions`, { method: "POST" });



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



export const listResources = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/resources`);

export const createResource = async (workspaceId, payload) =>
  request(`/workspaces/${workspaceId}/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteResource = async (resourceId) =>
  request(`/resources/${resourceId}`, { method: "DELETE" });





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



export const analyzeResearchGap = async (workspaceId) =>
  request(`/workspaces/${workspaceId}/research-gap`, { method: "POST" });

export const synthesizeWorkspace = async (workspaceId, question = null) =>
  request(`/workspaces/${workspaceId}/synthesis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });



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
export const removeCitation = deleteCitation;

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






export const discoverResearch = async (
  query,
  limitPerSource = 10,
  {
    sortBy = "relevance",
    yearFrom = null,
    yearTo = null,
    openAccessOnly = false,
    minCitations = 0,
    page = 1,
    pageSize = 50,
  } = {}
) => {
  const data = await request("/discover/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit_per_source: limitPerSource,
      sort_by: sortBy,
      year_from: yearFrom,
      year_to: yearTo,
      open_access_only: openAccessOnly,
      min_citations: minCitations,
      page,
      page_size: pageSize,
    }),
  });
  
  
  return { ...data, results: data.combined || [] };
};

export const discoverGithub = async (query, limit = 12, sort = "best-match") =>
  request("/discover/github", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit, sort }),
  });

export const discoverDatasets = async (query, limit = 12) =>
  request("/discover/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });

export const discoverLearning = async (query, limit = 12) =>
  request("/discover/learning", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });





export const discoverAnalyzePaper = async (action, paper) =>
  request("/discover/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      title: paper.title,
      abstract: paper.abstract,
      authors: paper.authors,
      year: paper.year,
      venue: paper.venue,
    }),
  });




export const discoverLandscape = async (query, papers = [], repositories = []) =>
  request("/discover/landscape", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, papers, repositories }),
  });




export const discoverRefine = async (query) =>
  request("/discover/refine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });





export const discoverComparePapers = async (papers) =>
  request("/discover/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ papers }),
  });



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








const USER_ID_STORAGE_KEY = "kno.user_id";

export const getOrCreateLocalUserId = () => {
  try {
    let id = localStorage.getItem(USER_ID_STORAGE_KEY);
    if (!id) {
      
      id = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
      localStorage.setItem(USER_ID_STORAGE_KEY, id);
    }
    return id;
  } catch (_) {
    
    return "anonymous";
  }
};

export const createConversation = async ({
  userId = null,
  scope = "home",
  workspaceId = null,
  title = null,
  mode = "research",
}) => {
  const body = {
    user_id: userId || getOrCreateLocalUserId(),
    scope,
    workspace_id: workspaceId,
    title,
    mode,
  };
  return request("/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
};

export const listConversations = async ({
  userId = null,
  scope = null,
  workspaceId = null,
  limit = 50,
} = {}) => {
  const params = new URLSearchParams();
  if (userId || true) params.set("user_id", userId || getOrCreateLocalUserId());
  if (scope) params.set("scope", scope);
  if (workspaceId) params.set("workspace_id", workspaceId);
  params.set("limit", String(limit));
  return request(`/conversations?${params.toString()}`);
};

export const getConversation = async (id) =>
  request(`/conversations/${encodeURIComponent(id)}`);

export const updateConversation = async (id, { title = null, mode = null } = {}) =>
  request(`/conversations/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, mode }),
  });

export const deleteConversation = async (id) =>
  request(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });

export const appendConversationMessage = async (
  conversationId,
  { role, content, sources = null, trace = null, confidence = null, metadata = null, suggested_followups = null, insufficient_evidence = false }
) =>
  request(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      role,
      content,
      sources,
      trace,
      confidence,
      metadata,
      suggested_followups,
      insufficient_evidence,
    }),
  });

export const conversationAsk = async ({
  question,
  mode = "research",
  userId = null,
  conversationId = null,
  title = null,
  documentId = null,
  workspaceId = null,
  historyWindow = 16,
}) =>
  request("/conversations/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      mode,
      user_id: userId || getOrCreateLocalUserId(),
      conversation_id: conversationId,
      title,
      document_id: documentId,
      workspace_id: workspaceId,
      history_window: historyWindow,
    }),
  });

export const exportConversation = async (id, { format = "markdown", download = true } = {}) => {
  const params = new URLSearchParams();
  params.set("format", format);
  if (download) params.set("download", "true");
  const url = `${API_BASE_URL}/conversations/${encodeURIComponent(id)}/export?${params.toString()}`;
  if (download && typeof window !== "undefined") {
    
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return { ok: true };
  }
  return request(`/conversations/${encodeURIComponent(id)}/export?${params.toString()}`);
};

export const exportConversationText = async (id) => exportConversation(id, { format: "txt" });
export const exportConversationMarkdown = async (id) => exportConversation(id, { format: "markdown" });



export const exportAnswer = async ({
  userQuestion,
  answer,
  title = null,
  sources = null,
  trace = null,
  confidence = null,
  metadata = null,
  followups = null,
  format = "markdown",
  conversationId = null,
}) =>
  request("/answers/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_question: userQuestion,
      answer,
      title,
      sources,
      trace,
      confidence,
      metadata,
      followups,
      format,
      conversation_id: conversationId,
    }),
  });



export const verifyGrounding = async ({ question, answer, sources }) =>
  request("/grounding/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, answer, sources }),
  });



export const getResearchTraceInfo = async () => request("/orbot/research-trace");





export const buildCitationGraph = async (documentId, { force = false } = {}) =>
  request(`/documents/${documentId}/citation-graph/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force }),
  });

export const getCitationGraph = async (documentId) =>
  request(`/documents/${documentId}/citation-graph`);

export const addCitationReference = async (documentId, payload) =>
  request(`/documents/${documentId}/citation-graph/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const lookupCitationMetadata = async (payload) =>
  request(`/citations/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const importCitationAsDocument = async (payload) =>
  request(`/citations/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });



export const getDocumentMetadata = async (documentId) =>
  request(`/documents/${documentId}/metadata`);

export const retryDocumentMetadata = async (documentId) =>
  request(`/documents/${documentId}/metadata/retry`, { method: "POST" });






export const pollDocumentMetadata = async (
  documentId,
  { intervalMs = 1500, timeoutMs = 30000 } = {},
) => {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const payload = await getDocumentMetadata(documentId);
    if (
      payload &&
      payload.metadata_status &&
      payload.metadata_status !== "pending"
    ) {
      return payload;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  
  
  return getDocumentMetadata(documentId);
};






export const orbotWorkspaceBrief = async ({
  workspaceId,
  maxDocuments = 6,
  topKPerDoc = 2,
  question = null,
}) =>
  request("/orbot/workspace-brief", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_id: workspaceId,
      max_documents: maxDocuments,
      top_k_per_doc: topKPerDoc,
      question,
    }),
  });

export const orbotWorkspaceSynthesis = async ({
  workspaceId,
  question,
  documentIds = null,
  topK = 8,
}) =>
  request("/orbot/workspace-synthesis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_id: workspaceId,
      question,
      document_ids: documentIds,
      top_k: topK,
    }),
  });

export const orbotClaimEvidence = async ({
  question,
  citationNumber,
  sources,
}) =>
  request("/orbot/claim-evidence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      citation_number: citationNumber,
      sources,
    }),
  });

export const orbotCompareTwo = async ({
  documentIdA,
  documentIdB,
  question = null,
}) =>
  request("/orbot/compare-two", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id_a: documentIdA,
      document_id_b: documentIdB,
      question,
    }),
  });

export const orbotProviderStatus = async () =>
  request("/orbot/provider-status");



