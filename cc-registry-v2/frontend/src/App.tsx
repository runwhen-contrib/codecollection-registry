import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box } from '@mui/material';
import Header from './components/Header';
import Home from './pages/Home';
import CodeCollections from './pages/CodeCollections';
import CodeCollectionDetail from './pages/CodeCollectionDetail';
import CodeBundles from './pages/CodeBundles';
import CodeBundleDetail from './pages/CodeBundleDetail';
import AllTasks from './pages/AllTasks';
import Categories from './pages/Categories';
import TestAPI from './pages/TestAPI';
import Admin from './pages/Admin';
import TaskManager from './pages/TaskManager';
import Footer from './components/Footer';
import { CartProvider } from './contexts/CartContext';

function App() {
  return (
    <CartProvider>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Header />
        <Box component="main" sx={{ flexGrow: 1 }}>
          <Routes>
            <Route path="/" element={<Home />} />
          <Route path="/collections" element={<CodeCollections />} />
          <Route path="/collections/:collectionSlug" element={<CodeCollectionDetail />} />
          <Route path="/codebundles" element={<CodeBundles />} />
          <Route path="/collections/:collectionSlug/codebundles/:codebundleSlug" element={<CodeBundleDetail />} />
          <Route path="/all-tasks" element={<AllTasks />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/test-api" element={<TestAPI />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/tasks" element={<TaskManager />} />
          </Routes>
        </Box>
        <Footer />
      </Box>
    </CartProvider>
  );
}

export default App;