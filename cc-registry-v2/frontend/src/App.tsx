import React from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { Box } from '@mui/material';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Home from './pages/Home';
import CodeCollections from './pages/CodeCollections';
import CodeCollectionDetail from './pages/CodeCollectionDetail';
import CodeBundles from './pages/CodeBundles';
import CodeBundleDetail from './pages/CodeBundleDetail';
import VersionDetail from './pages/VersionDetail';
import AllTasks from './pages/AllTasks';
import Categories from './pages/Categories';
import TestAPI from './pages/TestAPI';
import Admin from './pages/Admin';
import TaskManager from './pages/TaskManager';
import Login from './pages/Login';
import ConfigBuilder from './pages/ConfigBuilder';
import Chat from './pages/Chat';
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
          <Route path="/collections" element={<CodeCollections />} />
          <Route path="/collections/:collectionSlug" element={<CodeCollectionDetail />} />
          <Route path="/collections/:collectionSlug/versions/:versionName" element={<VersionDetail />} />
          <Route path="/codebundles" element={<CodeBundles />} />
          <Route path="/collections/:collectionSlug/codebundles/:codebundleSlug" element={<CodeBundleDetail />} />
          <Route path="/all-tasks" element={<AllTasks />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/test-api" element={<TestAPI />} />
          <Route path="/login" element={<Login />} />
          
          {/* Protected Routes */}
          <Route 
            path="/admin" 
            element={
              <ProtectedRoute requiredRole="admin">
                <Admin />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/tasks" 
            element={
              <ProtectedRoute requiredRole="admin">
                <TaskManager />
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