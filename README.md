# Intelligent Knowledge Discovery Platform

An AI-powered web platform where users can upload documents and use AI to generate summaries, ask questions, and discover meaningful insights from those documents.

## Project Structure

- `frontend/`: React + Vite frontend application
- `backend/`: Python + FastAPI backend application

## Prerequisites

- Node.js (v18+)
- Python (3.10+)

## Running the Application Locally

### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies (first time only):
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a Python virtual environment (first time only):
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the FastAPI server:
   ```bash
   fastapi dev main.py
   # OR
   # uvicorn main:app --reload
   ```
   The backend will be available at `http://localhost:8000` (API documentation at `http://localhost:8000/docs`)