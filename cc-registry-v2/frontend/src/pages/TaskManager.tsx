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
  const [taskHistory, setTaskHistory] = useState<any[]>([]);
  const [runningTasks, setRunningTasks] = useState<any[]>([]);
  const [taskStats, setTaskStats] = useState<any>(null);
  const [taskMetrics, setTaskMetrics] = useState<any>(null);
  const [workerStats, setWorkerStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

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

      // Get live task data, task health and admin metrics
      const [taskHistoryData, runningTasksData, taskStatsData, taskHealth, adminMetrics] = await Promise.all([
        apiService.getTaskHistory(token, 50, 0),
        apiService.getRunningTasks(token),
        apiService.getTaskStats(token, 7),
        apiService.getTaskHealth(token),
        apiService.getAdminMetrics(token, 7)
      ]);

      setTaskHistory(taskHistoryData.tasks || []);
      setRunningTasks(runningTasksData.running_tasks || []);
      setTaskStats(taskStatsData);
      setTaskMetrics(adminMetrics);
      setWorkerStats(taskHealth);

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

      setMessage(`Task started: ${taskType} (ID: ${response.task_id})`);
      
      // Refresh to get updated task list
      setTimeout(() => refreshData(), 1000);

    } catch (err) {
      setError(`Failed to trigger task: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh effect
  useEffect(() => {
    refreshData(); // Initial load
    
    if (autoRefresh) {
      const interval = setInterval(() => {
        refreshData();
      }, 5000); // Refresh every 5 seconds
      
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, autoRefresh]);

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
          <Tab label={`Running Tasks (${runningTasks.length})`} />
          <Tab label={`Task History (${taskHistory.length})`} />
          <Tab label="Trigger Tasks" />
          <Tab label="System Info" />
          <Tab label="Metrics & Stats" />
        </Tabs>
      </Box>

      {/* Auto-refresh toggle */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          variant={autoRefresh ? "contained" : "outlined"}
          onClick={() => setAutoRefresh(!autoRefresh)}
          size="small"
        >
          {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
        </Button>
        {autoRefresh && (
          <Typography variant="body2" color="text.secondary">
            Refreshing every 5 seconds
          </Typography>
        )}
      </Box>

      {/* Running Tasks Tab */}
      <TabPanel value={activeTab} index={0}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Currently Running Tasks ({runningTasks.length})
          </Typography>
          
          {runningTasks.length === 0 ? (
            <Alert severity="info">No tasks are currently running</Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Task Name</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Progress</TableCell>
                    <TableCell>Current Step</TableCell>
                    <TableCell>Started</TableCell>
                    <TableCell>Duration</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {runningTasks.map((task) => (
                    <TableRow key={task.task_id}>
                      <TableCell>
                        <Box>
                          <Typography variant="body2" fontWeight="bold">
                            {task.task_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {task.task_id}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          icon={getStatusIcon(task.status)} 
                          label={task.status} 
                          color={task.status === 'STARTED' ? 'primary' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CircularProgress 
                            variant="determinate" 
                            value={task.progress || 0} 
                            size={20} 
                          />
                          <Typography variant="body2">
                            {Math.round(task.progress || 0)}%
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.current_step || 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.started_at ? new Date(task.started_at).toLocaleString() : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.duration_seconds ? `${Math.round(task.duration_seconds)}s` : 
                           task.started_at ? `${Math.round((Date.now() - new Date(task.started_at).getTime()) / 1000)}s` : 'N/A'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </TabPanel>

      {/* Task History Tab */}
      <TabPanel value={activeTab} index={1}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Task History ({taskHistory.length})
          </Typography>
          
          {taskHistory.length === 0 ? (
            <Alert severity="info">No task history available</Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Task Name</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Started</TableCell>
                    <TableCell>Completed</TableCell>
                    <TableCell>Duration</TableCell>
                    <TableCell>Triggered By</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {taskHistory.map((task) => (
                    <TableRow key={task.task_id}>
                      <TableCell>
                        <Box>
                          <Typography variant="body2" fontWeight="bold">
                            {task.task_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {task.task_id}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          icon={getStatusIcon(task.status)} 
                          label={task.status} 
                          color={task.is_successful ? 'success' : task.is_failed ? 'error' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.started_at ? new Date(task.started_at).toLocaleString() : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.completed_at ? new Date(task.completed_at).toLocaleString() : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.duration_seconds ? `${Math.round(task.duration_seconds)}s` : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {task.triggered_by || 'system'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </TabPanel>

      {/* Trigger Tasks Tab */}
      <TabPanel value={activeTab} index={2}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Trigger New Tasks
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

      </TabPanel>

      {/* System Info Tab */}
      <TabPanel value={activeTab} index={3}>
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


      {/* Metrics & Stats Tab */}
      <TabPanel value={activeTab} index={4}>
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

