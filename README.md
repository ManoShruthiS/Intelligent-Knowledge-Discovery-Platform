# Intelligent Knowledge Discovery Platform (IKDP)

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-brightgreen?style=for-the-badge&logo=render)](https://ikdp-frontend.onrender.com/)
[![Backend Health](https://img.shields.io/badge/Backend-FastAPI-blue?style=for-the-badge&logo=fastapi)](https://ikdp-backend.onrender.com/api/health)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An AI-powered knowledge discovery platform that analyzes uploaded documents, organizes research workspaces, and generates grounded insights, summaries, and answers with strict citations.

---

## 🌐 Live Demo & Deployment

- **Live Web Application**: [https://ikdp-frontend.onrender.com/](https://ikdp-frontend.onrender.com/)
- **Backend API Health Check**: [https://ikdp-backend.onrender.com/api/health](https://ikdp-backend.onrender.com/api/health)
- **Source Code Repository**: [https://github.com/sure-trust/MANO-SHRUTHI-S-g6-gen-ai](https://github.com/sure-trust/MANO-SHRUTHI-S-g6-gen-ai)

---

## ✨ Key Features

1. **Orbot RAG AI Assistant**:
   - Document-grounded Q&A with strict lexical verification and citations.
   - Anaphora query expansion for natural multi-turn conversations.
   - Real-time Server-Sent Events (SSE) streaming answers.

2. **Intelligent Research Discovery**:
   - Unified search across academic papers (ArXiv / EuropePMC), code repositories (GitHub), and datasets (HuggingFace).
   - Topic filtering, publication year range selection, and open-access toggles.

3. **Workspace & Asset Management**:
   - Organize research materials into dedicated workspaces.
   - Attach PDFs, code snippets, notes, and datasets per project.

---

## 🛠️ Tech Stack

| Domain | Technologies Used |
| :--- | :--- |
| **Frontend** | React 19, Vite, React Router v7, Framer Motion, Lucide Icons, PDF.js, React Markdown, Vanilla CSS |
| **Backend API** | FastAPI, Python 3.12, Uvicorn, Pydantic v2 |
| **Database & Vector DB** | SQLite3, FAISS (`faiss-cpu`) |
| **AI / ML & RAG** | Google Gemini 2.5 AI, Sentence-Transformers (`all-MiniLM-L6-v2`), Rank-BM25, NetworkX |
| **Document Processing** | PyMuPDF (`fitz`), Python-Docx, OpenPyXL, BeautifulSoup4 |
| **Hosting & DevOps** | Render (Web Service + Static Site), Git & GitHub |

---

## 📁 Repository Structure

```text
Intelligent-Knowledge-Discovery-Platform/
├── backend/
│   ├── ai/                      # Orbot RAG engine, vector store, embeddings, reranker
│   ├── database/                # SQLite database schemas and query layer
│   ├── services/                # Document processor, discovery, citations, OCR
│   ├── Dockerfile               # Production container configuration
│   ├── main.py                  # FastAPI application routes & CORS
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Navigation, modals, ChatBox, cards
│   │   ├── pages/               # Dashboard, Discover, Workspaces, Workspace Detail, Documents
│   │   ├── services/            # API integration & SSE streaming client
│   │   └── App.jsx              # Main router application
│   ├── Dockerfile               # Production container configuration
│   ├── package.json             # React dependencies
│   └── vite.config.js           # Vite build configuration
```

---

## 🚀 Local Quickstart Guide

### Prerequisites
- Python 3.12+
- Node.js 18+

### 1. Clone Repository
```bash
git clone https://github.com/sure-trust/MANO-SHRUTHI-S-g6-gen-ai.git
cd MANO-SHRUTHI-S-g6-gen-ai/"Final capstone project"/Intelligent-Knowledge-Discovery-Platform
```

### 2. Set Up Backend
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

Create a `backend/.env` file:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
```

Run the backend server:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Set Up Frontend
Open a new terminal:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 👩‍💻 Author & Project Info

- **Student Name**: MANO SHRUTHI S
- **Program**: Sure Trust G6 Generative AI Internship
- **Project**: Intelligent Knowledge Discovery Platform (Final Capstone)
