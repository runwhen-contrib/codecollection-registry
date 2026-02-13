import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Button,
  TextField,
  Tabs,
  Tab,
  Alert,
  CircularProgress,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Paper,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControlLabel,
  Checkbox,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  BugReport as BugIcon,
  Analytics as AnalyticsIcon,
  History as HistoryIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Visibility as ViewIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import apiService from '../services/api';

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
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

interface ChatDebugEntry {
  timestamp: string;
  question: string;
  conversation_history: Array<{ role: string; content: string }>;
  mcp_response: string;
  relevant_tasks_count: number;
  relevant_tasks: Array<{
    name: string;
    slug: string;
    relevance_score: number;
    platform: string;
    description: string;
  }>;
  llm_system_prompt: string;
  llm_user_prompt: string;
  llm_response: string;
  final_answer: string;
  no_match_flag: boolean;
  query_metadata: any;
}

interface QualityStats {
  time_window_hours: number;
  total_chats: number;
  stats: {
    no_match_rate: string;
    no_match_count: number;
    zero_tasks_rate: string;
    zero_tasks_count: number;
    average_tasks_found: string;
    follow_up_questions: number;
    follow_up_no_match_rate: string;
  };
  problem_queries: Array<{
    question: string;
    timestamp: string;
    conversation_length: number;
  }>;
  recommendations: string[];
}

export default function ChatDebug() {
  const [activeTab, setActiveTab] = useState(0);
  const [recentChats, setRecentChats] = useState<ChatDebugEntry[]>([]);
  const [qualityStats, setQualityStats] = useState<QualityStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Test query state
  const [testQuestion, setTestQuestion] = useState('');
  const [testConversation, setTestConversation] = useState('');
  const [testResult, setTestResult] = useState<any>(null);
  const [testLoading, setTestLoading] = useState(false);
  
  // Recent chats filters
  const [chatLimit, setChatLimit] = useState(20);
  const [includePrompts, setIncludePrompts] = useState(false);
  const [filterType, setFilterType] = useState<'all' | 'no_match' | 'success'>('all');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'most_tasks' | 'least_tasks'>('newest');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Quality analysis filters
  const [windowHours, setWindowHours] = useState(24);
  
  // Detail dialog
  const [detailDialog, setDetailDialog] = useState<ChatDebugEntry | null>(null);

  useEffect(() => {
    if (activeTab === 0) {
      loadRecentChats();
    } else if (activeTab === 2) {
      loadQualityStats();
    }
  }, [activeTab, chatLimit, includePrompts, windowHours]);

  const loadRecentChats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiService.get(
        `/chat/debug/recent-chats?limit=${chatLimit}&include_prompts=${includePrompts}`
      );
      setRecentChats(response.data.chats || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load recent chats');
    } finally {
      setLoading(false);
    }
  };

  const loadQualityStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiService.get(
        `/chat/debug/analyze-quality?window_hours=${windowHours}`
      );
      setQualityStats(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load quality stats');
    } finally {
      setLoading(false);
    }
  };

  const handleTestQuery = async () => {
    if (!testQuestion.trim()) {
      setError('Please enter a test question');
      return;
    }

    setTestLoading(true);
    setError(null);
    setTestResult(null);

    try {
      const conversationHistory = testConversation.trim()
        ? JSON.parse(testConversation)
        : [];

      const response = await apiService.post('/chat/debug/test-query', {
        question: testQuestion,
        conversation_history: conversationHistory,
        context_limit: 10
      });

      setTestResult(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to test query');
    } finally {
      setTestLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Clear all chat debug history?')) return;

    try {
      await apiService.delete('/chat/debug/clear-history');
      loadRecentChats();
    } catch (err: any) {
      setError(err.message || 'Failed to clear history');
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high':
        return <ErrorIcon color="error" fontSize="small" />;
      case 'medium':
        return <WarningIcon color="warning" fontSize="small" />;
      default:
        return <CheckIcon color="success" fontSize="small" />;
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <BugIcon sx={{ fontSize: 40, mr: 2, color: 'primary.main' }} />
          <div>
            <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
              Chat Debug Console
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Analyze chat quality, test queries, and diagnose issues
            </Typography>
          </div>
        </Box>
        <Alert severity="info" sx={{ mb: 2 }}>
          <strong>Admin Tool:</strong> This page is only accessible to authenticated users.
          Use it to debug chat quality issues and test conversation flows.
        </Alert>
      </Box>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
          <Tab icon={<HistoryIcon />} label="Recent Chats" />
          <Tab icon={<PlayIcon />} label="Test Query" />
          <Tab icon={<AnalyticsIcon />} label="Quality Analysis" />
        </Tabs>
      </Box>

      {/* Recent Chats Tab */}
      <TabPanel value={activeTab} index={0}>
        <Box sx={{ mb: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* First row: Main controls */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              label="Limit"
              type="number"
              value={chatLimit}
              onChange={(e) => setChatLimit(Math.max(1, Math.min(100, parseInt(e.target.value) || 20)))}
              size="small"
              sx={{ width: 120 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={includePrompts}
                  onChange={(e) => setIncludePrompts(e.target.checked)}
                />
              }
              label="Include Full Prompts"
            />
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadRecentChats}
              disabled={loading}
            >
              Refresh
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleClearHistory}
            >
              Clear History
            </Button>
          </Box>

          {/* Second row: Filters and sorting */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              label="Search Questions"
              placeholder="Filter by question text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              size="small"
              sx={{ flexGrow: 1, minWidth: 200 }}
            />
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Filter</InputLabel>
              <Select
                value={filterType}
                label="Filter"
                onChange={(e) => setFilterType(e.target.value as any)}
              >
                <MenuItem value="all">All Chats</MenuItem>
                <MenuItem value="no_match">No Match Only</MenuItem>
                <MenuItem value="success">Successful Only</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => setSortBy(e.target.value as any)}
              >
                <MenuItem value="newest">Newest First</MenuItem>
                <MenuItem value="oldest">Oldest First</MenuItem>
                <MenuItem value="most_tasks">Most Tasks</MenuItem>
                <MenuItem value="least_tasks">Least Tasks</MenuItem>
              </Select>
            </FormControl>
            {(filterType !== 'all' || searchQuery || sortBy !== 'newest') && (
              <Chip
                label="Clear Filters"
                onDelete={() => {
                  setFilterType('all');
                  setSearchQuery('');
                  setSortBy('newest');
                }}
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : recentChats.length === 0 ? (
          <Alert severity="info">No recent chats found. Start a conversation in Registry Chat to see debug data.</Alert>
        ) : (
          <Box>
            {(() => {
              const filteredCount = recentChats.filter(chat => {
                if (filterType === 'no_match' && !chat.no_match_flag) return false;
                if (filterType === 'success' && chat.no_match_flag) return false;
                if (searchQuery && !chat.question.toLowerCase().includes(searchQuery.toLowerCase())) return false;
                return true;
              }).length;

              return (
                <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    Showing {filteredCount} of {recentChats.length} chats
                  </Typography>
                  {recentChats.filter(c => c.no_match_flag).length > 0 && (
                    <Chip
                      icon={<ErrorIcon />}
                      label={`${recentChats.filter(c => c.no_match_flag).length} No Match`}
                      size="small"
                      color="error"
                      variant="outlined"
                    />
                  )}
                  {recentChats.filter(c => !c.no_match_flag).length > 0 && (
                    <Chip
                      icon={<CheckIcon />}
                      label={`${recentChats.filter(c => !c.no_match_flag).length} Successful`}
                      size="small"
                      color="success"
                      variant="outlined"
                    />
                  )}
                </Box>
              );
            })()}
            <Box>
            {(() => {
              // Apply filters
              let filteredChats = recentChats.filter(chat => {
                // Filter by type
                if (filterType === 'no_match' && !chat.no_match_flag) return false;
                if (filterType === 'success' && chat.no_match_flag) return false;
                
                // Filter by search query
                if (searchQuery && !chat.question.toLowerCase().includes(searchQuery.toLowerCase())) {
                  return false;
                }
                
                return true;
              });

              // Apply sorting
              const sortedChats = [...filteredChats].sort((a, b) => {
                switch (sortBy) {
                  case 'newest':
                    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
                  case 'oldest':
                    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
                  case 'most_tasks':
                    return b.relevant_tasks_count - a.relevant_tasks_count;
                  case 'least_tasks':
                    return a.relevant_tasks_count - b.relevant_tasks_count;
                  default:
                    return 0;
                }
              });

              if (sortedChats.length === 0) {
                return (
                  <Alert severity="info">
                    No chats match your filters. Try adjusting the filter criteria.
                  </Alert>
                );
              }

              return sortedChats.map((chat, index) => {
              const isFollowup = chat.conversation_history && chat.conversation_history.length > 0;
              const conversationTurns = isFollowup ? Math.floor(chat.conversation_history.length / 2) : 0;
              
              return (
                <Accordion 
                  key={index}
                  sx={{
                    borderLeft: isFollowup ? '4px solid' : 'none', borderLeftColor: isFollowup ? 'primary.main' : undefined,
                    marginLeft: isFollowup ? 2 : 0,
                  }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
                      {chat.no_match_flag ? (
                        <ErrorIcon color="error" fontSize="small" />
                      ) : (
                        <CheckIcon color="success" fontSize="small" />
                      )}
                      {isFollowup && (
                        <Box
                          sx={{
                            width: 4,
                            height: 4,
                            borderRadius: '50%',
                            bgcolor: 'primary.main',
                            mr: -1,
                          }}
                        />
                      )}
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                          {chat.question}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {formatTimestamp(chat.timestamp)} • {chat.relevant_tasks_count} tasks found
                          {isFollowup && (
                            <Chip 
                              label={`Turn ${conversationTurns + 1} in conversation`}
                              size="small"
                              sx={{ 
                                ml: 1, 
                                height: 20,
                                fontSize: '0.7rem',
                                bgcolor: 'primary.main',
                                color: 'white',
                              }}
                            />
                          )}
                        </Typography>
                      </Box>
                      {chat.no_match_flag && (
                        <Chip label="No Match" color="error" size="small" />
                      )}
                      <IconButton size="small" onClick={() => setDetailDialog(chat)}>
                        <ViewIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                          Answer Preview
                        </Typography>
                        <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                          <Typography variant="body2">
                            {chat.final_answer.substring(0, 300)}
                            {chat.final_answer.length > 300 && '...'}
                          </Typography>
                        </Paper>
                      </Box>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                          Relevant Tasks
                        </Typography>
                        {chat.relevant_tasks.length === 0 ? (
                          <Alert severity="info" sx={{ py: 0.5 }}>
                            {isFollowup ? 'Used conversation context only' : 'No tasks found'}
                          </Alert>
                        ) : (
                          chat.relevant_tasks.slice(0, 3).map((task, i) => (
                            <Box key={i} sx={{ mb: 1 }}>
                              <Typography variant="body2">
                                {task.name} ({(task.relevance_score * 100).toFixed(0)}%)
                              </Typography>
                            </Box>
                          ))
                        )}
                      </Box>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              );
            })})()}
            </Box>
          </Box>
        )}
      </TabPanel>

      {/* Test Query Tab */}
      <TabPanel value={activeTab} index={1}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Test a Chat Query
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Test any query with optional conversation history to see detailed debugging information.
                </Typography>
                <Divider sx={{ my: 2 }} />
                
                <TextField
                  fullWidth
                  label="Test Question"
                  placeholder="e.g., Help me troubleshoot a deployment that won't roll out"
                  value={testQuestion}
                  onChange={(e) => setTestQuestion(e.target.value)}
                  sx={{ mb: 2 }}
                />
                
                <TextField
                  fullWidth
                  label="Conversation History (JSON)"
                  placeholder='[{"role": "user", "content": "previous question"}, {"role": "assistant", "content": "previous answer"}]'
                  value={testConversation}
                  onChange={(e) => setTestConversation(e.target.value)}
                  multiline
                  rows={4}
                  sx={{ mb: 2 }}
                  helperText="Optional: Provide previous conversation as JSON array"
                />
                
                <Button
                  variant="contained"
                  startIcon={testLoading ? <CircularProgress size={20} /> : <PlayIcon />}
                  onClick={handleTestQuery}
                  disabled={testLoading || !testQuestion.trim()}
                  size="large"
                >
                  Run Test
                </Button>
              </CardContent>
            </Card>
          </Box>

          {testResult && (
            <>
              <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
                <Box sx={{ flex: { md: 1 }, width: '100%' }}>
                  <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Query Metadata
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Platform:</Typography>
                        <Chip label={testResult.debug_entry.query_metadata.platform_detected || 'None'} size="small" />
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Is Follow-up:</Typography>
                        <Chip 
                          label={testResult.analysis.context.is_followup ? 'Yes' : 'No'} 
                          color={testResult.analysis.context.is_followup ? 'primary' : 'default'}
                          size="small" 
                        />
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">All Tasks Found:</Typography>
                        <Typography variant="body2">{testResult.debug_entry.query_metadata.all_tasks_count}</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Filtered Tasks:</Typography>
                        <Typography variant="body2">{testResult.debug_entry.query_metadata.filtered_tasks_count}</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">No Match Flag:</Typography>
                        <Chip 
                          label={testResult.debug_entry.no_match_flag ? 'True' : 'False'}
                          color={testResult.debug_entry.no_match_flag ? 'error' : 'success'}
                          size="small"
                        />
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
                </Box>

                <Box sx={{ flex: { md: 2 }, width: '100%' }}>
                  <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Issues Detected
                    </Typography>
                    {testResult.analysis.issues.length === 0 ? (
                      <Alert severity="success">No issues detected - response quality looks good!</Alert>
                    ) : (
                      <Box>
                        {testResult.analysis.issues.map((issue: any, i: number) => (
                          <Alert 
                            key={i} 
                            severity={issue.severity === 'high' ? 'error' : issue.severity === 'medium' ? 'warning' : 'info'}
                            sx={{ mb: 1 }}
                          >
                            <strong>{issue.type}:</strong> {issue.message}
                          </Alert>
                        ))}
                      </Box>
                    )}
                  </CardContent>
                </Card>
                </Box>
              </Box>

              <Box>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Recommendations
                    </Typography>
                    <Box component="ul" sx={{ pl: 2 }}>
                      {testResult.recommendations.map((rec: string, i: number) => (
                        <Typography key={i} component="li" variant="body2" sx={{ mb: 0.5 }}>
                          {rec}
                        </Typography>
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Box>

              <Box>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Relevant Tasks
                    </Typography>
                    {testResult.debug_entry.relevant_tasks.length === 0 ? (
                      <Typography variant="body2" color="error">No relevant tasks found</Typography>
                    ) : (
                      <TableContainer>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Name</TableCell>
                              <TableCell>Platform</TableCell>
                              <TableCell align="right">Relevance Score</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {testResult.debug_entry.relevant_tasks.map((task: any, i: number) => (
                              <TableRow key={i}>
                                <TableCell>{task.name}</TableCell>
                                <TableCell>{task.platform}</TableCell>
                                <TableCell align="right">
                                  <Chip 
                                    label={`${(task.relevance_score * 100).toFixed(0)}%`}
                                    color={task.relevance_score >= 0.7 ? 'success' : task.relevance_score >= 0.58 ? 'primary' : 'warning'}
                                    size="small"
                                  />
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    )}
                  </CardContent>
                </Card>
              </Box>

              <Box>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Final Answer
                    </Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.50', maxHeight: 400, overflow: 'auto' }}>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                        {testResult.debug_entry.final_answer}
                      </Typography>
                    </Paper>
                  </CardContent>
                </Card>
              </Box>
            </>
          )}
        </Box>
      </TabPanel>

      {/* Quality Analysis Tab */}
      <TabPanel value={activeTab} index={2}>
        <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            label="Time Window (hours)"
            type="number"
            value={windowHours}
            onChange={(e) => setWindowHours(Math.max(1, parseInt(e.target.value) || 24))}
            size="small"
            sx={{ width: 180 }}
          />
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadQualityStats}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : qualityStats ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {/* Summary Cards */}
            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
              <Box sx={{ flex: 1, minWidth: { xs: "100%", md: "25%" } }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Total Chats
                    </Typography>
                    <Typography variant="h3">{qualityStats.total_chats}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Last {qualityStats.time_window_hours}h
                    </Typography>
                  </CardContent>
                </Card>
              </Box>
              <Box sx={{ flex: 1, minWidth: { xs: "100%", md: "25%" } }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      No-Match Rate
                    </Typography>
                    <Typography 
                      variant="h3" 
                      color={parseFloat(qualityStats.stats.no_match_rate) > 30 ? 'error' : 'success'}
                    >
                      {qualityStats.stats.no_match_rate}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {qualityStats.stats.no_match_count} chats
                    </Typography>
                  </CardContent>
                </Card>
              </Box>
              <Box sx={{ flex: 1, minWidth: { xs: "100%", md: "25%" } }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Avg Tasks Found
                    </Typography>
                    <Typography variant="h3" color="primary">
                      {qualityStats.stats.average_tasks_found}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Per query
                    </Typography>
                  </CardContent>
                </Card>
              </Box>
              <Box sx={{ flex: 1, minWidth: { xs: "100%", md: "25%" } }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Follow-up Failure
                    </Typography>
                    <Typography 
                      variant="h3"
                      color={parseFloat(qualityStats.stats.follow_up_no_match_rate) > 20 ? 'error' : 'success'}
                    >
                      {qualityStats.stats.follow_up_no_match_rate}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {qualityStats.stats.follow_up_questions} follow-ups
                    </Typography>
                  </CardContent>
                </Card>
              </Box>
            </Box>

            {/* Recommendations */}
            <Box>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Recommendations
                  </Typography>
                  {qualityStats.recommendations.length === 0 ? (
                    <Alert severity="success">Chat quality metrics look healthy!</Alert>
                  ) : (
                    <Box>
                      {qualityStats.recommendations.map((rec, i) => (
                        <Alert key={i} severity="info" sx={{ mb: 1 }}>
                          {rec}
                        </Alert>
                      ))}
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Box>

            {/* Problem Queries */}
            {qualityStats.problem_queries.length > 0 && (
              <Box>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Problem Queries
                    </Typography>
                    <TableContainer>
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableCell>Question</TableCell>
                            <TableCell>Timestamp</TableCell>
                            <TableCell align="right">Conversation Length</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {qualityStats.problem_queries.map((query, i) => (
                            <TableRow key={i}>
                              <TableCell>{query.question}</TableCell>
                              <TableCell>{formatTimestamp(query.timestamp)}</TableCell>
                              <TableCell align="right">
                                <Chip 
                                  label={query.conversation_length}
                                  size="small"
                                  color={query.conversation_length > 0 ? 'warning' : 'default'}
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </CardContent>
                </Card>
              </Box>
            )}
          </Box>
        ) : (
          <Alert severity="info">No quality data available. Run some chat queries first.</Alert>
        )}
      </TabPanel>

      {/* Detail Dialog */}
      <Dialog 
        open={Boolean(detailDialog)} 
        onClose={() => setDetailDialog(null)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Chat Detail
        </DialogTitle>
        <DialogContent>
          {detailDialog && (
            <Box>
              <Typography variant="h6" gutterBottom>Question</Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
                <Typography>{detailDialog.question}</Typography>
              </Paper>

              {detailDialog.conversation_history.length > 0 && (
                <>
                  <Typography variant="h6" gutterBottom>Conversation History</Typography>
                  {detailDialog.conversation_history.map((msg, i) => (
                    <Paper key={i} sx={{ p: 2, mb: 1, bgcolor: msg.role === 'user' ? 'primary.50' : 'grey.50' }}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        {msg.role}
                      </Typography>
                      <Typography variant="body2">{msg.content.substring(0, 200)}...</Typography>
                    </Paper>
                  ))}
                </>
              )}

              <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Final Answer</Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50', maxHeight: 300, overflow: 'auto' }}>
                <Typography sx={{ whiteSpace: 'pre-wrap' }}>{detailDialog.final_answer}</Typography>
              </Paper>

              {includePrompts && (
                <>
                  <Typography variant="h6" gutterBottom>System Prompt</Typography>
                  <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50', maxHeight: 200, overflow: 'auto' }}>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {detailDialog.llm_system_prompt}
                    </Typography>
                  </Paper>

                  <Typography variant="h6" gutterBottom>User Prompt</Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.50', maxHeight: 200, overflow: 'auto' }}>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {detailDialog.llm_user_prompt}
                    </Typography>
                  </Paper>
                </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialog(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
