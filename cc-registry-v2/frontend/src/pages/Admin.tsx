import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  TextField,
  Chip,
  Divider,
  Tabs,
  Tab,
} from '@mui/material';
import { apiService } from '../services/api';
import AIConfiguration from '../components/AIConfiguration';
import AdminInventory from './AdminInventory';

const Admin: React.FC = () => {
  const [token, setToken] = useState('admin-dev-token');
  const [populationStatus, setPopulationStatus] = useState<any>(null);
  const [isPopulating, setIsPopulating] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTab, setCurrentTab] = useState(0);

  const checkStatus = async () => {
    try {
      setError(null);
      const status = await apiService.getPopulationStatus(token);
      setPopulationStatus(status);
    } catch (err) {
      setError(`Failed to get status: ${err}`);
    }
  };

  const triggerPopulation = async () => {
    try {
      setIsPopulating(true);
      setError(null);
      setMessage(null);
      
      const result = await apiService.triggerDataPopulation(token);
      setMessage(`Population completed: ${JSON.stringify(result, null, 2)}`);
      
      // Refresh status
      await checkStatus();
    } catch (err) {
      setError(`Population failed: ${err}`);
    } finally {
      setIsPopulating(false);
    }
  };

  const clearData = async () => {
    if (!window.confirm('Are you sure you want to clear ALL data? This cannot be undone!')) {
      return;
    }
    
    try {
      setIsClearing(true);
      setError(null);
      setMessage(null);
      
      const result = await apiService.clearAllData(token);
      setMessage(`Data cleared: ${JSON.stringify(result, null, 2)}`);
      
      // Refresh status
      await checkStatus();
    } catch (err) {
      setError(`Clear data failed: ${err}`);
    } finally {
      setIsClearing(false);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" sx={{ mb: 4 }}>
        Admin Panel
      </Typography>

      {/* Quick Navigation */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Quick Navigation
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button 
              variant="outlined" 
              onClick={() => window.open('/admin/ai-enhancement', '_blank')}
              sx={{ minWidth: 200 }}
            >
              🤖 AI Enhancement Admin
            </Button>
            <Button 
              variant="outlined" 
              onClick={() => window.open('/tasks', '_blank')}
              sx={{ minWidth: 200 }}
            >
              📋 Task Manager
            </Button>
          </Box>
          <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
            Access specialized admin interfaces for AI enhancement and task management
          </Typography>
        </CardContent>
      </Card>

      <Tabs value={currentTab} onChange={handleTabChange} sx={{ mb: 3 }}>
        <Tab label="Data Management" />
        <Tab label="AI Configuration" />
        <Tab label="Database Inventory" />
      </Tabs>

      {currentTab === 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Token Input */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Authentication
            </Typography>
            <TextField
              fullWidth
              label="Admin Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              helperText="Use 'admin-dev-token' for development"
              sx={{ mb: 2 }}
            />
            <Button 
              variant="outlined" 
              onClick={checkStatus}
              disabled={!token}
            >
              Check Status
            </Button>
          </CardContent>
        </Card>

        {/* Current Status */}
        {populationStatus && (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Current Database Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Chip 
                  label={`Collections: ${populationStatus.collections}`} 
                  color="primary" 
                  variant="outlined" 
                />
                <Chip 
                  label={`Codebundles: ${populationStatus.codebundles}`} 
                  color="secondary" 
                  variant="outlined" 
                />
                <Chip 
                  label={`Tasks: ${populationStatus.tasks}`} 
                  color="success" 
                  variant="outlined" 
                />
              </Box>
            </CardContent>
          </Card>
        )}

        {/* Population Actions */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Card sx={{ flex: '1 1 300px' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Data Population
              </Typography>
              <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
                This will clone all repositories from codecollections.yaml, parse all robot files, 
                and populate the database with the complete registry data.
              </Typography>
              <Button
                variant="contained"
                color="primary"
                onClick={triggerPopulation}
                disabled={isPopulating || !token}
                sx={{ mb: 2 }}
                fullWidth
              >
                {isPopulating ? (
                  <>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    Populating Data...
                  </>
                ) : (
                  'Start Data Population'
                )}
              </Button>
              <Typography variant="caption" display="block" sx={{ color: 'text.secondary' }}>
                ⚠️ This process may take several minutes and will download large repositories.
              </Typography>
            </CardContent>
          </Card>

          {/* Clear Data */}
          <Card sx={{ flex: '1 1 300px' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Clear All Data
              </Typography>
              <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
                This will delete all collections, codebundles, and tasks from the database. 
                Use this to start fresh before migration.
              </Typography>
              <Button
                variant="contained"
                color="error"
                onClick={clearData}
                disabled={isClearing || !token}
                sx={{ mb: 2 }}
                fullWidth
              >
                {isClearing ? (
                  <>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    Clearing Data...
                  </>
                ) : (
                  'Clear All Data'
                )}
              </Button>
              <Typography variant="caption" display="block" sx={{ color: 'error.main' }}>
                ⚠️ This action cannot be undone!
              </Typography>
            </CardContent>
          </Card>
        </Box>

        {/* Messages */}
        {message && (
          <Alert severity="success" sx={{ mb: 2 }}>
            <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
              {message}
            </Typography>
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        </Box>
      )}

      {currentTab === 1 && (
        <AIConfiguration token={token} />
      )}

      {currentTab === 2 && (
        <AdminInventory />
      )}
    </Container>
  );
};

export default Admin;
