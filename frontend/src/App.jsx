import React, { Suspense, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import ErrorBoundary from './components/common/ErrorBoundary';
import Onboarding from './components/common/Onboarding';
import CommandPalette from './components/common/CommandPalette';
import Home from './pages/Home';

const Discover = React.lazy(() => import('./pages/Discover'));
const Documents = React.lazy(() => import('./pages/Documents'));
const Studio = React.lazy(() => import('./pages/Studio'));
const Recent = React.lazy(() => import('./pages/Recent'));
const Settings = React.lazy(() => import('./pages/Settings'));
const Workspaces = React.lazy(() => import('./pages/Workspaces'));
const WorkspaceDetail = React.lazy(() => import('./pages/WorkspaceDetail'));
const DocumentWorkspace = React.lazy(() => import('./pages/DocumentWorkspace'));
const OverviewTab = React.lazy(() => import('./pages/workspace_tabs/OverviewTab'));
const SummaryTab = React.lazy(() => import('./pages/workspace_tabs/SummaryTab'));
const InsightsTab = React.lazy(() => import('./pages/workspace_tabs/InsightsTab'));
const AskAITab = React.lazy(() => import('./pages/workspace_tabs/AskAITab'));
const SourcesTab = React.lazy(() => import('./pages/workspace_tabs/SourcesTab'));

function SuspenseFallback() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      width: '100%',
    }}>
      <div style={{
        width: 32,
        height: 32,
        border: '3px solid #e5e5e5',
        borderTopColor: '#333',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function App() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(prev => !prev);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <Router>
      <Onboarding />
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <AppLayout>
          <ErrorBoundary>
            <Suspense fallback={<SuspenseFallback />}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/discover" element={<Discover />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/workspaces" element={<Workspaces />} />
                <Route path="/workspaces/:id" element={<WorkspaceDetail />} />
                <Route path="/workspaces/:id/studio" element={<Studio />} />
                <Route path="/documents/:id" element={<DocumentWorkspace />}>
                  <Route index element={<Navigate to="overview" replace />} />
                  <Route path="overview" element={<OverviewTab />} />
                  <Route path="summary" element={<SummaryTab />} />
                  <Route path="insights" element={<InsightsTab />} />
                  <Route path="ask-ai" element={<AskAITab />} />
                  <Route path="sources" element={<SourcesTab />} />
                </Route>
                <Route path="/recent" element={<Recent />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
      </AppLayout>
    </Router>
  );
}

export default App;
