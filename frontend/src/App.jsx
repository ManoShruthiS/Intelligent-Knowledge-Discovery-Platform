import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import Home from './pages/Home';
import Discover from './pages/Discover';
import Documents from './pages/Documents';
import Recent from './pages/Recent';
import Settings from './pages/Settings';
import Workspaces from './pages/Workspaces';
import WorkspaceDetail from './pages/WorkspaceDetail';
import DocumentWorkspace from './pages/DocumentWorkspace';
import OverviewTab from './pages/workspace_tabs/OverviewTab';
import SummaryTab from './pages/workspace_tabs/SummaryTab';
import InsightsTab from './pages/workspace_tabs/InsightsTab';
import AskAITab from './pages/workspace_tabs/AskAITab';
import SourcesTab from './pages/workspace_tabs/SourcesTab';

function App() {
  return (
    <Router>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/workspaces" element={<Workspaces />} />
          <Route path="/workspaces/:id" element={<WorkspaceDetail />} />
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
      </AppLayout>
    </Router>
  );
}

export default App;
