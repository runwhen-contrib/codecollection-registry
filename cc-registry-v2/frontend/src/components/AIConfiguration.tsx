import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Divider,
  GridLegacy as Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  LinearProgress,
} from '@mui/material';
import { 
  Add as AddIcon, 
  Edit as EditIcon, 
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Refresh as RefreshIcon 
} from '@mui/icons-material';
import { apiService } from '../services/api';

interface AIConfig {
  id: number;
  service_provider: string;
  model_name: string;
  enhancement_enabled: boolean;
  auto_enhance_new_bundles: boolean;
  max_requests_per_hour: number;
  max_concurrent_requests: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Azure OpenAI specific fields
  azure_endpoint?: string;
  azure_deployment_name?: string;
  api_version?: string;
}

interface AIStats {
  total_codebundles: number;
  enhancement_status: {
    pending: number;
    processing: number;
    completed: number;
    failed: number;
  };
  access_levels: {
    read_only: number;
    read_write: number;
    unknown: number;
  };
  completion_rate: number;
}

interface EnhancementTask {
  task_id: string;
  state: string;
  current?: number;
  total?: number;
  status?: string;
  result?: any;
  error?: string;
}

interface AIConfigurationProps {
  token: string;
}

const AIConfiguration: React.FC<AIConfigurationProps> = ({ token }) => {
  const [configs, setConfigs] = useState<AIConfig[]>([]);
  const [stats, setStats] = useState<AIStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Dialog states
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AIConfig | null>(null);
  
  // Enhancement states
  const [enhancementTask, setEnhancementTask] = useState<EnhancementTask | null>(null);
  const [enhancementDialogOpen, setEnhancementDialogOpen] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    service_provider: 'openai',
    api_key: '',
    model_name: 'gpt-4',
    enhancement_enabled: true,
    auto_enhance_new_bundles: false,
    max_requests_per_hour: 100,
    max_concurrent_requests: 5,
    // Azure OpenAI specific fields
    azure_endpoint: '',
    azure_deployment_name: '',
    api_version: '2024-02-15-preview'
  });

  useEffect(() => {
    loadConfigs();
    loadStats();
  }, []);

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const data = await apiService.getAIConfigurations(token);
      setConfigs(data);
    } catch (err) {
      setError(`Failed to load configurations: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await apiService.getAIStats(token);
      setStats(data);
    } catch (err) {
      console.error('Failed to load AI stats:', err);
    }
  };

  const handleSaveConfig = async () => {
    try {
      setLoading(true);
      
      if (editingConfig) {
        await apiService.updateAIConfiguration(token, editingConfig.id, formData);
        setSuccess('Configuration updated successfully');
      } else {
        await apiService.createAIConfiguration(token, formData);
        setSuccess('Configuration created successfully');
      }
      
      setConfigDialogOpen(false);
      setEditingConfig(null);
      resetForm();
      await loadConfigs();
      
    } catch (err) {
      setError(`Failed to save configuration: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfig = async (configId: number) => {
    if (!window.confirm('Are you sure you want to delete this configuration?')) return;
    
    try {
      setLoading(true);
      await apiService.deleteAIConfiguration(token, configId);
      setSuccess('Configuration deleted successfully');
      await loadConfigs();
      
    } catch (err) {
      setError(`Failed to delete configuration: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEnhancePending = async () => {
    try {
      const result = await apiService.triggerAIEnhancement(token, { enhance_pending: true });
      setEnhancementTask({ task_id: result.task_id, state: 'PENDING' });
      setEnhancementDialogOpen(true);
      
      // Start polling for status
      pollEnhancementStatus(result.task_id);
      
    } catch (err) {
      setError(`Failed to start enhancement: ${err}`);
    }
  };

  const handleResetEnhancements = async () => {
    if (!window.confirm('Are you sure you want to reset ALL AI enhancement data? This will set all CodeBundles back to pending status and clear all AI-generated content.')) {
      return;
    }
    
    try {
      setLoading(true);
      const result = await apiService.resetAIEnhancements(token);
      setSuccess(`Successfully reset AI enhancement data for ${result.reset_count} CodeBundles`);
      
      // Refresh stats to show updated counts
      loadStats();
      
    } catch (err) {
      setError(`Failed to reset enhancements: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const pollEnhancementStatus = async (taskId: string) => {
    const poll = async () => {
      try {
        const status = await apiService.getEnhancementStatus(token, taskId);
        setEnhancementTask(status);
        
        if (status.state === 'SUCCESS' || status.state === 'FAILURE') {
          await loadStats(); // Refresh stats when done
          return;
        }
        
        // Continue polling
        setTimeout(poll, 2000);
        
      } catch (err) {
        console.error('Failed to poll enhancement status:', err);
      }
    };
    
    poll();
  };

  const resetForm = () => {
    setFormData({
      service_provider: 'openai',
      api_key: '',
      model_name: 'gpt-4',
      enhancement_enabled: true,
      auto_enhance_new_bundles: false,
      max_requests_per_hour: 100,
      max_concurrent_requests: 5,
      // Azure OpenAI specific fields
      azure_endpoint: '',
      azure_deployment_name: '',
      api_version: '2024-02-15-preview'
    });
  };

  const openEditDialog = (config: AIConfig) => {
    setEditingConfig(config);
    setFormData({
      service_provider: config.service_provider,
      api_key: '', // Don't pre-fill API key for security
      model_name: config.model_name,
      enhancement_enabled: config.enhancement_enabled,
      auto_enhance_new_bundles: config.auto_enhance_new_bundles,
      max_requests_per_hour: config.max_requests_per_hour,
      max_concurrent_requests: config.max_concurrent_requests,
      // Azure OpenAI specific fields
      azure_endpoint: config.azure_endpoint || '',
      azure_deployment_name: config.azure_deployment_name || '',
      api_version: config.api_version || '2024-02-15-preview'
    });
    setConfigDialogOpen(true);
  };

  const openCreateDialog = () => {
    setEditingConfig(null);
    resetForm();
    setConfigDialogOpen(true);
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        AI Enhancement Configuration
      </Typography>

      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {/* Statistics Card */}
      {stats && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Enhancement Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">
                  Total CodeBundles: {stats.total_codebundles}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Completion Rate: {stats.completion_rate}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={stats.completion_rate} 
                  sx={{ mt: 1 }}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Box display="flex" gap={1} flexWrap="wrap">
                  <Chip label={`Pending: ${stats.enhancement_status.pending}`} color="default" size="small" />
                  <Chip label={`Processing: ${stats.enhancement_status.processing}`} color="info" size="small" />
                  <Chip label={`Completed: ${stats.enhancement_status.completed}`} color="success" size="small" />
                  <Chip label={`Failed: ${stats.enhancement_status.failed}`} color="error" size="small" />
                </Box>
                <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                  <Chip label={`Read-Only: ${stats.access_levels.read_only}`} color="primary" size="small" />
                  <Chip label={`Read-Write: ${stats.access_levels.read_write}`} color="warning" size="small" />
                  <Chip label={`Unknown: ${stats.access_levels.unknown}`} color="default" size="small" />
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Action Buttons */}
      <Box display="flex" gap={2} mb={3}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={openCreateDialog}
        >
          Add Configuration
        </Button>
        <Button
          variant="outlined"
          startIcon={<PlayIcon />}
          onClick={handleEnhancePending}
          disabled={!configs.some(c => c.is_active && c.enhancement_enabled)}
        >
          Enhance Pending
        </Button>
        <Button
          variant="outlined"
          color="warning"
          startIcon={<DeleteIcon />}
          onClick={handleResetEnhancements}
          disabled={loading}
        >
          Reset All Enhancements
        </Button>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => { loadConfigs(); loadStats(); }}
        >
          Refresh
        </Button>
      </Box>

      {/* Configurations Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Provider</TableCell>
              <TableCell>Model</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Auto Enhance</TableCell>
              <TableCell>Rate Limits</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && configs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : configs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No AI configurations found
                </TableCell>
              </TableRow>
            ) : (
              configs.map((config) => (
                <TableRow key={config.id}>
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      {config.service_provider}
                      {config.is_active && (
                        <Chip label="Active" color="success" size="small" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>{config.model_name}</TableCell>
                  <TableCell>
                    <Chip 
                      label={config.enhancement_enabled ? 'Enabled' : 'Disabled'}
                      color={config.enhancement_enabled ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={config.auto_enhance_new_bundles ? 'Yes' : 'No'}
                      color={config.auto_enhance_new_bundles ? 'info' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {config.max_requests_per_hour}/hr, {config.max_concurrent_requests} concurrent
                  </TableCell>
                  <TableCell>
                    <IconButton onClick={() => openEditDialog(config)} size="small">
                      <EditIcon />
                    </IconButton>
                    <IconButton onClick={() => handleDeleteConfig(config.id)} size="small">
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Configuration Dialog */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingConfig ? 'Edit AI Configuration' : 'Create AI Configuration'}
        </DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField
              label="Service Provider"
              value={formData.service_provider}
              onChange={(e) => setFormData({ ...formData, service_provider: e.target.value })}
              select
              SelectProps={{ native: true }}
            >
              <option value="openai">OpenAI</option>
              <option value="azure-openai">Azure OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </TextField>
            
            <TextField
              label="API Key"
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder={editingConfig ? 'Leave blank to keep current key' : 'Enter API key'}
              required={!editingConfig}
            />
            
            <TextField
              label="Model Name"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
            />
            
            {/* Azure OpenAI specific fields */}
            {formData.service_provider === 'azure-openai' && (
              <>
                <TextField
                  label="Azure Endpoint"
                  value={formData.azure_endpoint}
                  onChange={(e) => setFormData({ ...formData, azure_endpoint: e.target.value })}
                  placeholder="https://your-resource.openai.azure.com"
                  required
                  helperText="Your Azure OpenAI resource endpoint URL"
                />
                
                <TextField
                  label="Deployment Name"
                  value={formData.azure_deployment_name}
                  onChange={(e) => setFormData({ ...formData, azure_deployment_name: e.target.value })}
                  placeholder="gpt-4"
                  required
                  helperText="The deployment name in your Azure OpenAI resource"
                />
                
                <TextField
                  label="API Version"
                  value={formData.api_version}
                  onChange={(e) => setFormData({ ...formData, api_version: e.target.value })}
                  placeholder="2024-02-15-preview"
                  helperText="Azure OpenAI API version"
                />
              </>
            )}
            
            <FormControlLabel
              control={
                <Switch
                  checked={formData.enhancement_enabled}
                  onChange={(e) => setFormData({ ...formData, enhancement_enabled: e.target.checked })}
                />
              }
              label="Enhancement Enabled"
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={formData.auto_enhance_new_bundles}
                  onChange={(e) => setFormData({ ...formData, auto_enhance_new_bundles: e.target.checked })}
                />
              }
              label="Auto Enhance New Bundles"
            />
            
            <TextField
              label="Max Requests per Hour"
              type="number"
              value={formData.max_requests_per_hour}
              onChange={(e) => setFormData({ ...formData, max_requests_per_hour: parseInt(e.target.value) })}
            />
            
            <TextField
              label="Max Concurrent Requests"
              type="number"
              value={formData.max_concurrent_requests}
              onChange={(e) => setFormData({ ...formData, max_concurrent_requests: parseInt(e.target.value) })}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveConfig} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Enhancement Progress Dialog */}
      <Dialog open={enhancementDialogOpen} onClose={() => setEnhancementDialogOpen(false)}>
        <DialogTitle>AI Enhancement Progress</DialogTitle>
        <DialogContent>
          {enhancementTask && (
            <Box>
              <Typography variant="body2" gutterBottom>
                Task ID: {enhancementTask.task_id}
              </Typography>
              <Typography variant="body2" gutterBottom>
                Status: {enhancementTask.state}
              </Typography>
              
              {enhancementTask.state === 'PROGRESS' && (
                <Box>
                  <Typography variant="body2">
                    Progress: {enhancementTask.current || 0} / {enhancementTask.total || 0}
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={((enhancementTask.current || 0) / (enhancementTask.total || 1)) * 100}
                    sx={{ mt: 1 }}
                  />
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {enhancementTask.status}
                  </Typography>
                </Box>
              )}
              
              {enhancementTask.state === 'SUCCESS' && (
                <Alert severity="success">
                  Enhancement completed successfully!
                </Alert>
              )}
              
              {enhancementTask.state === 'FAILURE' && (
                <Alert severity="error">
                  Enhancement failed: {enhancementTask.error}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEnhancementDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AIConfiguration;

