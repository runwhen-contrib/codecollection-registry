import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box } from '@mui/material';
import Header from './components/Header';
import Home from './pages/Home';
import CodeCollections from './pages/CodeCollections';
import CodeBundles from './pages/CodeBundles';
import CodeBundleDetail from './pages/CodeBundleDetail';
import Categories from './pages/Categories';
import TestAPI from './pages/TestAPI';
import Admin from './pages/Admin';
import TaskManager from './pages/TaskManager';
import Footer from './components/Footer';

function App() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <Box component="main" sx={{ flexGrow: 1 }}>
        <Routes>
          <Route path="/" element={<Home />} />
        <Route path="/collections" element={<CodeCollections />} />
        <Route path="/codebundles" element={<CodeBundles />} />
        <Route path="/codebundles/:id" element={<CodeBundleDetail />} />
        <Route path="/categories" element={<Categories />} />
        <Route path="/test-api" element={<TestAPI />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/tasks" element={<TaskManager />} />
        </Routes>
      </Box>
      <Footer />
    </Box>
  );
}

export default App;