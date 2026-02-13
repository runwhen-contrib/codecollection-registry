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
import AdminInventory from './AdminInventory';

const Admin: React.FC = () => {
  const [token, setToken] = useState('admin-dev-token');
  const [populationStatus, setPopulationStatus] = useState<any>(null);
  const [isPopulating, setIsPopulating] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [aiStatus, setAiStatus] = useState<any>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [schedules, setSchedules] = useState<any>(null);

  const checkStatus = async () => {
    try {
      setError(null);
      const status = await apiService.getPopulationStatus(token);
      setPopulationStatus(status);
      // Also check AI status
      await checkAiStatus();
    } catch (err) {
      setError(`Failed to get status: ${err}`);
    }
  };

  const checkAiStatus = async () => {
    try {
      const status = await apiService.getAiEnhancementStatus(token);
      setAiStatus(status);
    } catch (err) {
      console.error('Failed to get AI status:', err);
    }
  };

  const fetchSchedules = async () => {
    try {
      const data = await apiService.getSchedules(token);
      setSchedules(data);
    } catch (err) {
      console.error('Failed to get schedules:', err);
    }
  };

  const triggerSchedule = async (scheduleName: string) => {
    try {
      setError(null);
      setMessage(null);
      const result = await apiService.triggerScheduleNow(scheduleName, token);
      setMessage(`Triggered: ${result.message}`);
    } catch (err: any) {
      setError(`Failed to trigger schedule: ${err.response?.data?.detail || err.message || err}`);
    }
  };

  const triggerAiEnhancement = async (limit: number = 20) => {
    try {
      setIsEnhancing(true);
      setError(null);
      setMessage(null);
      
      const result = await apiService.runAiEnhancement(token, limit);
      setMessage(`AI Enhancement: ${result.message}\nEnhanced: ${result.enhanced}, Failed: ${result.failed}, Remaining: ${result.remaining}`);
      
      // Refresh status
      await checkAiStatus();
    } catch (err: any) {
      setError(`AI Enhancement failed: ${err.response?.data?.detail || err.message || err}`);
    } finally {
      setIsEnhancing(false);
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
    fetchSchedules();
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
              onClick={() => window.open('/tasks', '_blank')}
              sx={{ minWidth: 200 }}
            >
              📋 Task Manager
            </Button>
            <Button 
              variant="outlined" 
              onClick={() => window.open('/chat-debug', '_blank')}
              sx={{ minWidth: 200 }}
            >
              🐛 Chat Debug Console
            </Button>
          </Box>
          <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
            Access specialized admin interfaces for task management and chat quality debugging
          </Typography>
        </CardContent>
      </Card>

      <Tabs value={currentTab} onChange={handleTabChange} sx={{ mb: 3 }}>
        <Tab label="Data Management" />
        <Tab label="Database Inventory" />
        <Tab label="Schedules" />
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

        {/* AI Enhancement */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              🤖 AI Enhancement
            </Typography>
            
            {aiStatus && (
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                  <Chip 
                    label={aiStatus.ai_enabled ? `AI: ${aiStatus.ai_provider}` : 'AI: Not Configured'} 
                    color={aiStatus.ai_enabled ? 'success' : 'error'}
                    variant="outlined"
                  />
                  <Chip 
                    label={`Enhanced: ${aiStatus.enhanced}/${aiStatus.total_codebundles} (${aiStatus.enhancement_percentage}%)`}
                    color="primary"
                    variant="outlined"
                  />
                  <Chip 
                    label={`Pending: ${aiStatus.pending}`}
                    color="warning"
                    variant="outlined"
                  />
                  {aiStatus.failed > 0 && (
                    <Chip 
                      label={`Failed: ${aiStatus.failed}`}
                      color="error"
                      variant="outlined"
                    />
                  )}
                </Box>
                {aiStatus.ai_model && (
                  <Typography variant="caption" color="text.secondary">
                    Model: {aiStatus.ai_model}
                  </Typography>
                )}
              </Box>
            )}
            
            <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
              Use AI to generate enhanced descriptions, access level classifications, and IAM requirements for codebundles.
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                color="primary"
                onClick={() => triggerAiEnhancement(10)}
                disabled={isEnhancing || !token || !aiStatus?.ai_enabled}
                sx={{ minWidth: 150 }}
              >
                {isEnhancing ? (
                  <>
                    <CircularProgress size={20} sx={{ mr: 1 }} color="inherit" />
                    Enhancing...
                  </>
                ) : (
                  'Enhance 10'
                )}
              </Button>
              <Button
                variant="outlined"
                color="primary"
                onClick={() => triggerAiEnhancement(50)}
                disabled={isEnhancing || !token || !aiStatus?.ai_enabled}
                sx={{ minWidth: 150 }}
              >
                Enhance 50
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                onClick={() => triggerAiEnhancement(aiStatus?.pending || 100)}
                disabled={isEnhancing || !token || !aiStatus?.ai_enabled || !aiStatus?.pending}
                sx={{ minWidth: 150 }}
              >
                Enhance All ({aiStatus?.pending || 0})
              </Button>
            </Box>
            
            {!aiStatus?.ai_enabled && (
              <Typography variant="caption" display="block" sx={{ mt: 2, color: 'warning.main' }}>
                ⚠️ AI is not configured. Set AZURE_OPENAI_* environment variables in az.secret.
              </Typography>
            )}
          </CardContent>
        </Card>

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
        <AdminInventory />
      )}

      {currentTab === 2 && (
        <Box>
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

          {schedules && (
            <>
              <Alert severity="info" sx={{ mb: 3 }}>
                {schedules.note}
              </Alert>

              <Typography variant="h6" sx={{ mb: 2 }}>
                Configured Schedules ({schedules.total})
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {schedules.schedules && schedules.schedules.map((schedule: any) => (
                  <Card key={schedule.id}>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="h6" sx={{ mb: 1 }}>
                            {schedule.task_name}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {schedule.description}
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            <Chip 
                              label={schedule.schedule_value}
                              color="primary"
                              variant="outlined"
                              size="small"
                            />
                            <Chip 
                              label={schedule.schedule_type}
                              color="secondary"
                              variant="outlined"
                              size="small"
                            />
                            {schedule.is_active && (
                              <Chip 
                                label="Active"
                                color="success"
                                size="small"
                              />
                            )}
                          </Box>
                        </Box>
                        <Button
                          variant="contained"
                          size="small"
                          onClick={() => triggerSchedule(schedule.task_name)}
                          sx={{ ml: 2 }}
                        >
                          Run Now
                        </Button>
                      </Box>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="caption" color="text.secondary">
                        Task: {schedule.task_path}
                      </Typography>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            </>
          )}
        </Box>
      )}
    </Container>
  );
};

export default Admin;
