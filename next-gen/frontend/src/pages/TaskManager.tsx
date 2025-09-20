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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tabs,
  Tab,
  Grid,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Refresh,
  CheckCircle,
  Error,
  Schedule,
  TrendingUp,
  Assessment,
} from '@mui/icons-material';
import { apiService } from '../services/api';

interface Task {
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
  const [token, setToken] = useState('admin-dev-token');
  const [activeTab, setActiveTab] = useState(0);
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [scheduledTasks, setScheduledTasks] = useState<Task[]>([]);
  const [taskHistory, setTaskHistory] = useState<Task[]>([]);
  const [taskMetrics, setTaskMetrics] = useState<any>(null);
  const [workerStats, setWorkerStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const refreshData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get active tasks
      const activeResponse = await apiService.getActiveTasks(token);
      setActiveTasks(activeResponse.active_tasks || []);

      // Get scheduled tasks
      const scheduledResponse = await apiService.getScheduledTasks(token);
      setScheduledTasks(scheduledResponse.scheduled_tasks || []);

      // Get task history
      const historyResponse = await apiService.getTaskHistory(token);
      setTaskHistory(historyResponse.task_history || []);

      // Get metrics
      const metricsResponse = await apiService.getTaskMetrics(token);
      setTaskMetrics(metricsResponse);

      // Get worker stats
      const workerResponse = await apiService.getWorkerStats(token);
      setWorkerStats(workerResponse);

    } catch (err) {
      setError(`Failed to refresh data: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const triggerTask = async (taskType: string, params: any = {}) => {
    try {
      setLoading(true);
      setError(null);
      setMessage(null);

      let response;
      switch (taskType) {
        case 'populate-registry':
          response = await apiService.triggerRegistryPopulation(token, params.collection_slugs);
          break;
        case 'sync-collections':
          response = await apiService.triggerCollectionsSync(token, params.collection_slugs);
          break;
        case 'parse-codebundles':
          response = await apiService.triggerCodebundlesParsing(token);
          break;
        case 'enhance-codebundles':
          response = await apiService.triggerCodebundlesEnhancement(token);
          break;
        case 'generate-insights':
          response = await apiService.triggerAIInsightsGeneration(token);
          break;
        default:
          throw new Error(`Unknown task type: ${taskType}`);
      }

      setMessage(`Task started: ${JSON.stringify(response, null, 2)}`);
      await refreshData();

    } catch (err) {
      setError(`Failed to trigger task: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const cancelTask = async (taskId: string) => {
    try {
      await apiService.cancelTask(token, taskId);
      setMessage(`Task ${taskId} cancelled successfully`);
      await refreshData();
    } catch (err) {
      setError(`Failed to cancel task: ${err}`);
    }
  };

  const retryTask = async (taskId: string) => {
    try {
      const response = await apiService.retryTask(token, taskId);
      setMessage(`Task retried: ${response.new_task_id}`);
      await refreshData();
    } catch (err) {
      setError(`Failed to retry task: ${err}`);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle color="success" />;
      case 'FAILURE':
        return <Error color="error" />;
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
    refreshData();
  }, []);

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" sx={{ mb: 4 }}>
        Task Manager
      </Typography>

      {/* Authentication */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <TextField
              label="Admin Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              size="small"
              sx={{ minWidth: 200 }}
            />
            <Button
              variant="outlined"
              onClick={refreshData}
              disabled={loading || !token}
              startIcon={<Refresh />}
            >
              Refresh
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
          <Tab label="Active Tasks" />
          <Tab label="Scheduled Tasks" />
          <Tab label="Task History" />
          <Tab label="Metrics & Stats" />
        </Tabs>
      </Box>

      {/* Active Tasks Tab */}
      <TabPanel value={activeTab} index={0}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Active Tasks ({activeTasks.length})
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              onClick={() => triggerTask('populate-registry')}
              disabled={loading}
              startIcon={<PlayArrow />}
            >
              Populate Registry
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('sync-collections')}
              disabled={loading}
              startIcon={<PlayArrow />}
            >
              Sync Collections
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('parse-codebundles')}
              disabled={loading}
              startIcon={<PlayArrow />}
            >
              Parse Codebundles
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('enhance-codebundles')}
              disabled={loading}
              startIcon={<PlayArrow />}
            >
              Enhance Codebundles
            </Button>
            <Button
              variant="contained"
              onClick={() => triggerTask('generate-insights')}
              disabled={loading}
              startIcon={<PlayArrow />}
            >
              Generate AI Insights
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
                <TableCell>Current Step</TableCell>
                <TableCell>Started At</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {activeTasks.map((task) => (
                <TableRow key={task.task_id}>
                  <TableCell>{task.task_id}</TableCell>
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
                    {task.progress !== undefined ? `${task.progress}%` : 'N/A'}
                  </TableCell>
                  <TableCell>{task.current_step || 'N/A'}</TableCell>
                  <TableCell>
                    {task.started_at ? new Date(task.started_at).toLocaleString() : 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Tooltip title="Cancel Task">
                        <IconButton
                          size="small"
                          onClick={() => cancelTask(task.task_id)}
                          color="error"
                        >
                          <Stop />
                        </IconButton>
                      </Tooltip>
                      {task.is_failed && (
                        <Tooltip title="Retry Task">
                          <IconButton
                            size="small"
                            onClick={() => retryTask(task.task_id)}
                            color="primary"
                          >
                            <Refresh />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Scheduled Tasks Tab */}
      <TabPanel value={activeTab} index={1}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Scheduled Tasks ({scheduledTasks.length})
        </Typography>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Task ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Worker</TableCell>
                <TableCell>ETA</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {scheduledTasks.map((task) => (
                <TableRow key={task.task_id}>
                  <TableCell>{task.task_id}</TableCell>
                  <TableCell>{task.name}</TableCell>
                  <TableCell>{task.worker}</TableCell>
                  <TableCell>
                    {task.eta ? new Date(task.eta).toLocaleString() : 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Tooltip title="Cancel Task">
                      <IconButton
                        size="small"
                        onClick={() => cancelTask(task.task_id)}
                        color="error"
                      >
                        <Stop />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Task History Tab */}
      <TabPanel value={activeTab} index={2}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Task History ({taskHistory.length})
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
              {taskHistory.map((task) => (
                <TableRow key={task.task_id}>
                  <TableCell>{task.task_id}</TableCell>
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
                    {task.started_at ? new Date(task.started_at).toLocaleString() : 'N/A'}
                  </TableCell>
                  <TableCell>
                    {task.is_failed && (
                      <Tooltip title="Retry Task">
                        <IconButton
                          size="small"
                          onClick={() => retryTask(task.task_id)}
                          color="primary"
                        >
                          <Refresh />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Metrics & Stats Tab */}
      <TabPanel value={activeTab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
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
          </Grid>

          <Grid item xs={12} md={6}>
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
          </Grid>
        </Grid>
      </TabPanel>
    </Container>
  );
};

export default TaskManager;

