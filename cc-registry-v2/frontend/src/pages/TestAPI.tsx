import React, { useState, useEffect } from 'react';
import { Box, Typography, Button, Alert } from '@mui/material';
import { apiService } from '../services/api';

const TestAPI: React.FC = () => {
  const [health, setHealth] = useState<any>(null);
  const [collections, setCollections] = useState<any[]>([]);
  const [codebundles, setCodebundles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const testAPI = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('Testing API...');
      
      // Test health endpoint
      const healthData = await apiService.getHealth();
      setHealth(healthData);
      console.log('Health:', healthData);
      
      // Test collections endpoint
      const collectionsData = await apiService.getCodeCollections();
      setCollections(collectionsData);
      console.log('Collections:', collectionsData);
      
      // Test codebundles endpoint
      const codebundlesResponse = await apiService.getCodeBundles();
      const codebundlesData = codebundlesResponse.codebundles;
      setCodebundles(codebundlesData);
      console.log('Codebundles:', codebundlesData);
      
    } catch (err) {
      console.error('API Test Error:', err);
      setError(`API Test Failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        API Connection Test
      </Typography>
      
      <Button 
        variant="contained" 
        onClick={testAPI} 
        disabled={loading}
        sx={{ mb: 3 }}
      >
        {loading ? 'Testing...' : 'Test API Connection'}
      </Button>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {health && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6">Health Check:</Typography>
          <pre>{JSON.stringify(health, null, 2)}</pre>
        </Box>
      )}

      {collections.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6">Collections ({collections.length}):</Typography>
          <pre>{JSON.stringify(collections, null, 2)}</pre>
        </Box>
      )}

      {codebundles.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6">Codebundles ({codebundles.length}):</Typography>
          <pre>{JSON.stringify(codebundles, null, 2)}</pre>
        </Box>
      )}
    </Box>
  );
};

export default TestAPI;
