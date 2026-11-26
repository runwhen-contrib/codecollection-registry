import React from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Box } from '@mui/material';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Home from './pages/Home';
import Plugins from './pages/Plugins';
import PluginDetail from './pages/PluginDetail';
import Skills from './pages/Skills';
import SkillDetail from './pages/SkillDetail';
import VersionDetail from './pages/VersionDetail';
import AllTasks from './pages/AllTasks';
import TestAPI from './pages/TestAPI';
import Admin from './pages/Admin';
import Login from './pages/Login';
import ConfigBuilder from './pages/ConfigBuilder';
import Chat from './pages/Chat';
import ChatDebug from './pages/ChatDebug';
import IntakeWizard from './pages/IntakeWizard';
import Footer from './components/Footer';
import { CartProvider } from './contexts/CartContext';
import { AuthProvider } from './contexts/AuthContext';

function AppContent() {
  const location = useLocation();
  const isChatPage = location.pathname === '/chat';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <Box component="main" sx={{ flexGrow: 1 }}>
        <Routes>
          <Route path="/" element={<Home />} />

          {/* Plugins (formerly "CodeCollections") */}
          <Route path="/plugins" element={<Plugins />} />
          <Route path="/plugins/:collectionSlug" element={<PluginDetail />} />
          <Route path="/plugins/:collectionSlug/versions/:versionName" element={<VersionDetail />} />

          {/* Skills (formerly "CodeBundles") */}
          <Route path="/skills" element={<Skills />} />
          <Route path="/plugins/:collectionSlug/skills/:codebundleSlug" element={<SkillDetail />} />

          {/* Tasks */}
          <Route path="/all-tasks" element={<AllTasks />} />

          {/* Backward-compatible aliases so old bookmarks do not 404 */}
          <Route path="/collections" element={<Navigate to="/plugins" replace />} />
          <Route path="/collections/:collectionSlug" element={<PluginDetail />} />
          <Route path="/collections/:collectionSlug/versions/:versionName" element={<VersionDetail />} />
          <Route path="/codebundles" element={<Navigate to="/skills" replace />} />
          <Route path="/collections/:collectionSlug/codebundles/:codebundleSlug" element={<SkillDetail />} />
          <Route path="/all-tools" element={<Navigate to="/all-tasks" replace />} />

          <Route path="/chat" element={<Chat />} />
          <Route path="/intake" element={<IntakeWizard />} />
          <Route path="/test-api" element={<TestAPI />} />
          <Route path="/login" element={<Login />} />
          
          {/* Protected Routes */}
          <Route 
            path="/chat-debug" 
            element={
              <ProtectedRoute requiredRole="admin">
                <ChatDebug />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin" 
            element={
              <ProtectedRoute requiredRole="admin">
                <Admin />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/config-builder" 
            element={<ConfigBuilder />} 
          />
        </Routes>
      </Box>
      {!isChatPage && <Footer />}
    </Box>
  );
}

function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <AppContent />
      </CartProvider>
    </AuthProvider>
  );
}

export default App;