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
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tabs,
  Tab,
} from '@mui/material';
import {
  PlayArrow,
  Refresh,
  CheckCircle,
  Error as ErrorIcon,
  Schedule,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useAuth, getAuthToken } from '../contexts/AuthContext';

interface TaskStatus {
  task_id: string;
  status: string;
  result?: any;
  progress?: number;
  current_step?: string;
  started_at?: string;
  is_ready?: boolean;
  is_successful?: boolean;
  is_failed?: boolean;
  error?: string;
  name?: string;
  worker?: string;
  eta?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const TaskManager: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState(0);
  const [triggeredTasks, setTriggeredTasks] = useState<{[key: string]: any}>({});
  const [taskMetrics, setTaskMetrics] = useState<any>(null);
  const [workerStats, setWorkerStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const refreshData = async () => {
    if (!isAuthenticated) {
      setError('Authentication required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const token = getAuthToken();
      if (!token) {
        setError('No authentication token available');
        return;
      }

      // Get task health and admin metrics
      const [taskHealth, adminMetrics] = await Promise.all([
        apiService.getTaskHealth(token),
        apiService.getAdminMetrics(token, 7)
      ]);

      setTaskMetrics(adminMetrics);
      setWorkerStats(taskHealth);

      // Note: Skip task status refresh to avoid infinite loops
      // Individual task status updates will be handled when tasks are triggered

    } catch (err) {
      setError(`Failed to refresh data: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const triggerTask = async (taskType: string, params: any = {}) => {
    if (!isAuthenticated) {
      setError('Authentication required');
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setError('No authentication token available');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setMessage(null);

      let response: any;
      switch (taskType) {
        case 'seed-database':
          response = await apiService.triggerSeedDatabase(token);
          break;
        case 'validate-yaml':
          response = await apiService.triggerValidateYaml(token);
          break;
        case 'sync-collections':
          response = await apiService.triggerSyncCollections(token);
          break;
        case 'parse-codebundles':
          response = await apiService.triggerParseCodebundles(token);
          break;
        case 'enhance-codebundles':
          response = await apiService.triggerEnhanceCodebundles(token);
          break;
        case 'generate-metrics':
          response = await apiService.triggerGenerateMetrics(token);
          break;
        default:
          throw new Error(`Unknown task type: ${taskType}`);
      }

      // Add task to triggered tasks list
      const newTask = {
        task_id: response.task_id,
        task_type: taskType,
        status: response.status,
        message: response.message,
        triggered_at: new Date().toISOString(),
        last_checked: new Date().toISOString()
      };
      
      setTriggeredTasks(prev => ({
        ...prev,
        [response.task_id]: newTask
      }));

      setMessage(`Task started: ${taskType} (ID: ${response.task_id})`);
      
      // Refresh to get initial status
      setTimeout(() => refreshData(), 1000);

    } catch (err) {
      setError(`Failed to trigger task: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  // Note: Cancel and retry functions removed - not available in database-driven task system
  // Tasks are managed through the new database-driven architecture

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle color="success" />;
      case 'FAILURE':
        return <ErrorIcon color="error" />;
      case 'PENDING':
        return <Schedule color="warning" />;
      case 'PROGRESS':
        return <CircularProgress size={20} />;
      default:
        return <Schedule />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return 'success';
      case 'FAILURE':
        return 'error';
      case 'PENDING':
        return 'warning';
      case 'PROGRESS':
        return 'info';
      default:
        return 'default';
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      refreshData();
    }
  }, [isAuthenticated]); // Remove refreshData from dependencies to prevent infinite loop

  // Show loading if not authenticated (should be handled by ProtectedRoute, but just in case)
  if (!isAuthenticated) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" sx={{ mb: 4 }}>
        Task Manager
      </Typography>

      {/* User Info and Refresh */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h6">
                Welcome, {user?.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {user?.email} • {user?.roles?.join(', ')}
              </Typography>
            </Box>
            <Button
              variant="outlined"
              onClick={refreshData}
              disabled={loading || !isAuthenticated}
              startIcon={loading ? <CircularProgress size={16} /> : <Refresh />}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Messages */}
      {message && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {message}
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Triggered Tasks" />
          <Tab label="System Info" />
          <Tab label="Task Details" />
          <Tab label="Metrics & Stats" />
        </Tabs>
      </Box>

      {/* Active Tasks Tab */}
      <TabPanel value={activeTab} index={0}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Triggered Tasks ({Object.keys(triggeredTasks).length})
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              onClick={() => triggerTask('seed-database')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Seed Database
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('sync-collections')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Sync Collections
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('parse-codebundles')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Parse Codebundles
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('enhance-codebundles')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Enhance Codebundles
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('validate-yaml')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Validate YAML
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('generate-metrics')}
              disabled={loading || !isAuthenticated}
              startIcon={<PlayArrow />}
            >
              Generate Metrics
            </Button>
          </Box>
        </Box>

        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Task ID</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Progress</TableCell>
                <TableCell>Task Type</TableCell>
                <TableCell>Triggered At</TableCell>
                <TableCell>Last Checked</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.values(triggeredTasks).map((task: any) => (
                <TableRow key={task.task_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {task.task_id.substring(0, 8)}...
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getStatusIcon(task.status)}
                      <Chip
                        label={task.status}
                        color={getStatusColor(task.status) as any}
                        size="small"
                      />
                    </Box>
                  </TableCell>
                  <TableCell>
                    {task.progress ? JSON.stringify(task.progress) : 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Chip label={task.task_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    {new Date(task.triggered_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      Last checked: {new Date(task.last_checked).toLocaleString()}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {Object.keys(triggeredTasks).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography variant="body2" color="text.secondary">
                      No tasks triggered yet. Click a button above to start a task.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Scheduled Tasks Tab */}
      <TabPanel value={activeTab} index={1}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          System Information
        </Typography>
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Task System Status
            </Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2">
                <strong>Status:</strong> {workerStats?.status || 'Unknown'}
              </Typography>
              <Typography variant="body2">
                <strong>Celery Status:</strong> {workerStats?.celery_status || 'Unknown'}
              </Typography>
              <Typography variant="body2">
                <strong>Task System:</strong> {workerStats?.task_system || 'Database-driven'}
              </Typography>
              {workerStats?.workers && (
                <Typography variant="body2">
                  <strong>Workers:</strong> {workerStats.workers.join(', ')}
                </Typography>
              )}
            </Box>
            
            {taskMetrics && (
              <>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  System Metrics
                </Typography>
                <Typography variant="body2">
                  <strong>Total Collections:</strong> {taskMetrics.system_metrics?.total_collections || 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Total Codebundles:</strong> {taskMetrics.system_metrics?.total_codebundles || 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Total Tasks:</strong> {taskMetrics.system_metrics?.total_tasks || 0}
                </Typography>
              </>
            )}
          </CardContent>
        </Card>
      </TabPanel>

      {/* Task History Tab */}
      <TabPanel value={activeTab} index={2}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Task Details
        </Typography>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Task ID</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Result</TableCell>
                <TableCell>Started At</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.values(triggeredTasks).map((task: any) => (
                <TableRow key={task.task_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {task.task_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getStatusIcon(task.status)}
                      <Chip
                        label={task.status}
                        color={getStatusColor(task.status) as any}
                        size="small"
                      />
                    </Box>
                  </TableCell>
                  <TableCell>
                    {task.result ? JSON.stringify(task.result).substring(0, 100) + '...' : 'N/A'}
                  </TableCell>
                  <TableCell>
                    {task.triggered_at ? new Date(task.triggered_at).toLocaleString() : 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {task.task_type}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {Object.keys(triggeredTasks).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography variant="body2" color="text.secondary">
                      No tasks triggered yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Metrics & Stats Tab */}
      <TabPanel value={activeTab} index={3}>
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Task Metrics
                </Typography>
                {taskMetrics && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Typography>Total Tasks: {taskMetrics.total_tasks_executed || 0}</Typography>
                    <Typography>Successful: {taskMetrics.successful_tasks || 0}</Typography>
                    <Typography>Failed: {taskMetrics.failed_tasks || 0}</Typography>
                    <Typography>Success Rate: {(taskMetrics.success_rate * 100).toFixed(1)}%</Typography>
                    <Typography>Avg Execution Time: {taskMetrics.average_execution_time || 0}s</Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Worker Stats
                </Typography>
                {workerStats && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Typography>Total Workers: {workerStats.total_workers || 0}</Typography>
                    <Typography>Total Tasks: {workerStats.total_tasks || 0}</Typography>
                    <Typography>Active Workers: {Object.keys(workerStats.workers || {}).length}</Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>
        </Box>
      </TabPanel>
    </Container>
  );
};

export default TaskManager;

