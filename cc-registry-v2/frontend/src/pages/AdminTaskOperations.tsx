/**
 * AdminTaskOperations — task observability inside /admin.
 *
 * This is the read-side counterpart to the schedules-tab "Run Now"
 * trigger surface. It shows:
 *   - Currently-running Celery tasks (auto-refreshing)
 *   - Recent task history with failure tracebacks expandable inline
 *
 * Triggering tasks lives EXCLUSIVELY on the Schedules tab — every
 * triggerable task is declared in schedules.yaml (set `enabled: false`
 * to keep it manual-only) and the Schedules tab auto-generates a
 * "Run Now" button for each. There is intentionally no hardcoded
 * trigger list here.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import {
  BugReport,
  CheckCircle,
  Error as ErrorIcon,
  KeyboardArrowDown,
  KeyboardArrowUp,
  Refresh,
  Schedule,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useAuth, getAuthToken } from '../contexts/AuthContext';

interface RunningTask {
  task_id: string;
  task_name?: string;
  status?: string;
  progress?: number;
  current_step?: string;
  started_at?: string;
  duration_seconds?: number;
}

interface HistoryTask {
  task_id: string;
  task_name?: string;
  status?: string;
  is_successful?: boolean;
  is_failed?: boolean;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  triggered_by?: string;
  error_message?: string;
  traceback?: string;
}

const statusIcon = (status?: string) => {
  switch (status) {
    case 'SUCCESS':
      return <CheckCircle color="success" fontSize="small" />;
    case 'FAILURE':
      return <ErrorIcon color="error" fontSize="small" />;
    case 'PROGRESS':
      return <CircularProgress size={16} />;
    case 'PENDING':
    case 'STARTED':
      return <Schedule color="warning" fontSize="small" />;
    default:
      return <Schedule fontSize="small" />;
  }
};

const statusColor = (status?: string, is_failed?: boolean, is_successful?: boolean) => {
  if (is_successful) return 'success';
  if (is_failed) return 'error';
  switch (status) {
    case 'SUCCESS':
      return 'success';
    case 'FAILURE':
      return 'error';
    case 'STARTED':
    case 'PROGRESS':
      return 'info';
    case 'PENDING':
      return 'warning';
    default:
      return 'default';
  }
};

const AdminTaskOperations: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [running, setRunning] = useState<RunningTask[]>([]);
  const [history, setHistory] = useState<HistoryTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const [tracebackTask, setTracebackTask] = useState<HistoryTask | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    const token = getAuthToken();
    if (!token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [runningData, historyData] = await Promise.all([
        apiService.getRunningTasks(token),
        apiService.getTaskHistory(token, 50, 0),
      ]);

      setRunning(runningData.running_tasks || []);
      setHistory(historyData.tasks || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to load task ops: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refresh();
    if (!autoRefresh) return;
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh, autoRefresh]);

  return (
    <Box>
      {/* Controls */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Button
          variant={autoRefresh ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setAutoRefresh((v) => !v)}
        >
          {autoRefresh ? 'Auto-refresh ON (5s)' : 'Auto-refresh OFF'}
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={loading ? <CircularProgress size={14} /> : <Refresh />}
          onClick={refresh}
          disabled={loading}
        >
          Refresh now
        </Button>
        <Typography variant="caption" color="text.secondary">
          Trigger tasks from the <strong>Schedules</strong> tab — this view is
          observability only.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Running tasks */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Currently Running ({running.length})
          </Typography>
          {running.length === 0 ? (
            <Alert severity="info">No tasks running right now.</Alert>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Task</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Progress</TableCell>
                    <TableCell>Step</TableCell>
                    <TableCell>Started</TableCell>
                    <TableCell>Duration</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {running.map((t) => (
                    <TableRow key={t.task_id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {t.task_name || t.task_id}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {t.task_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          icon={statusIcon(t.status)}
                          label={t.status || 'STARTED'}
                          color="primary"
                        />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CircularProgress
                            variant="determinate"
                            value={t.progress ?? 0}
                            size={18}
                          />
                          <Typography variant="caption">
                            {Math.round(t.progress ?? 0)}%
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">{t.current_step || '—'}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {t.started_at ? new Date(t.started_at).toLocaleString() : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {t.duration_seconds != null
                            ? `${Math.round(t.duration_seconds)}s`
                            : t.started_at
                              ? `${Math.round(
                                  (Date.now() - new Date(t.started_at).getTime()) / 1000,
                                )}s`
                              : '—'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* History */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent History ({history.length})
          </Typography>
          {history.length === 0 ? (
            <Alert severity="info">No completed task runs yet.</Alert>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={32} />
                    <TableCell>Task</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Started</TableCell>
                    <TableCell>Duration</TableCell>
                    <TableCell>Triggered by</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {history.map((t) => {
                    const hasError = t.is_failed && t.error_message;
                    return (
                      <React.Fragment key={t.task_id}>
                        <TableRow
                          hover
                          sx={hasError ? { '& > *': { borderBottom: 'unset' } } : undefined}
                        >
                          <TableCell>
                            {hasError && (
                              <IconButton
                                size="small"
                                onClick={() =>
                                  setExpandedTask(
                                    expandedTask === t.task_id ? null : t.task_id,
                                  )
                                }
                              >
                                {expandedTask === t.task_id ? (
                                  <KeyboardArrowUp />
                                ) : (
                                  <KeyboardArrowDown />
                                )}
                              </IconButton>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold">
                              {t.task_name || t.task_id}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {t.task_id}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              icon={statusIcon(t.status)}
                              label={t.status || (t.is_failed ? 'FAILURE' : 'SUCCESS')}
                              color={
                                statusColor(t.status, t.is_failed, t.is_successful) as any
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {t.started_at ? new Date(t.started_at).toLocaleString() : '—'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {t.duration_seconds != null
                                ? `${Math.round(t.duration_seconds)}s`
                                : '—'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {t.triggered_by || 'system'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                        {hasError && (
                          <TableRow>
                            <TableCell colSpan={6} sx={{ p: 0, border: 0 }}>
                              <Collapse
                                in={expandedTask === t.task_id}
                                timeout="auto"
                                unmountOnExit
                              >
                                <Box
                                  sx={{
                                    m: 1.5,
                                    p: 2,
                                    bgcolor: 'error.lighter',
                                    borderRadius: 1,
                                  }}
                                >
                                  <Box
                                    sx={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 1,
                                      mb: 1,
                                    }}
                                  >
                                    <ErrorIcon color="error" fontSize="small" />
                                    <Typography
                                      variant="subtitle2"
                                      color="error"
                                      fontWeight="bold"
                                    >
                                      Error
                                    </Typography>
                                  </Box>
                                  <Typography
                                    variant="body2"
                                    sx={{
                                      fontFamily: 'monospace',
                                      fontSize: '0.85rem',
                                      mb: 1,
                                      whiteSpace: 'pre-wrap',
                                    }}
                                  >
                                    {t.error_message}
                                  </Typography>
                                  {t.traceback && (
                                    <Button
                                      size="small"
                                      startIcon={<BugReport />}
                                      onClick={() => setTracebackTask(t)}
                                    >
                                      View full traceback
                                    </Button>
                                  )}
                                </Box>
                              </Collapse>
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Traceback dialog */}
      <Dialog
        open={!!tracebackTask}
        onClose={() => setTracebackTask(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {tracebackTask?.task_name || 'Task'} — traceback
        </DialogTitle>
        <DialogContent dividers>
          <Box
            component="pre"
            sx={{
              fontFamily: 'monospace',
              fontSize: '0.8rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              m: 0,
            }}
          >
            {tracebackTask?.traceback || 'No traceback recorded.'}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTracebackTask(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AdminTaskOperations;
