import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  IconButton,
  Paper,
  Chip,
  Alert,
  CircularProgress,
  Collapse,
  Link,
  Avatar,
  Button
} from '@mui/material';
import {
  Send as SendIcon,
  Person as PersonIcon,
  ContentCopy as CopyIcon,
  Check as CheckIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  GitHub as GitHubIcon,
  OpenInNew as OpenInNewIcon,
  AddCircleOutline as RequestIcon
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, githubApi, ChatResponse, ExampleQueries, TaskRequestIssue } from '../services/api';

interface ChatMessage {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
  response?: ChatResponse;
  loading?: boolean;
  userQuery?: string;  // For bot messages, stores the user's original query
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatHealth, setChatHealth] = useState<any>(null);
  const [examples, setExamples] = useState<ExampleQueries | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [healthData, examplesData] = await Promise.all([
          chatApi.health(),
          chatApi.getExamples()
        ]);
        setChatHealth(healthData);
        setExamples(examplesData);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError('Failed to initialize chat service');
      }
    };
    loadInitialData();
  }, []);

  const handleSendMessage = async (messageText?: string) => {
    const text = messageText || inputValue.trim();
    if (!text || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: text,
      timestamp: new Date()
    };

    const botMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      type: 'bot',
      content: '',
      timestamp: new Date(),
      loading: true,
      userQuery: text  // Store the user's query for the GitHub issue button
    };

    setMessages(prev => [...prev, userMessage, botMessage]);
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      let response: ChatResponse;
      try {
        // Build conversation history from previous messages (last 6 = 3 turns)
        const conversationHistory = messages
          .filter(m => !m.loading && m.content)
          .slice(-6)
          .map(m => ({
            role: (m.type === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
            content: m.content
          }));
        
        response = await chatApi.query({
          question: text,
          context_limit: 8,
          include_enhanced_descriptions: true,
          conversation_history: conversationHistory
        });
        
        setMessages(prev => prev.map(msg => 
          msg.id === botMessage.id 
            ? { ...msg, content: response.answer, response, loading: false }
            : msg
        ));
      } catch (mainChatError) {
        console.warn('Main chat failed, trying simple chat:', mainChatError);
        
        const simpleResponse = await chatApi.simpleQuery(text);
        
        const convertedResponse: ChatResponse = {
          answer: simpleResponse.answer,
          relevant_tasks: simpleResponse.relevant_codebundles.map((cb: any, index: number) => ({
            id: index,
            codebundle_name: cb.name,
            codebundle_slug: cb.name.toLowerCase().replace(/\s+/g, '-'),
            collection_name: cb.collection,
            collection_slug: cb.collection.toLowerCase().replace(/\s+/g, '-'),
            description: cb.description,
            support_tags: cb.support_tags || [],
            tasks: [],
            slis: [],
            author: '',
            access_level: cb.access_level || 'unknown',
            minimum_iam_requirements: [],
            runbook_source_url: cb.runbook_source_url || '',
            relevance_score: cb.relevance_score || 0.5,
            platform: cb.platform || '',
            resource_types: []
          })),
          sources_used: simpleResponse.relevant_codebundles.map((cb: any) => cb.name),
          query_metadata: {
            query_processed_at: new Date().toISOString(),
            context_tasks_count: simpleResponse.relevant_codebundles.length,
            ai_model: 'simple-fallback'
          }
        };
        
        setMessages(prev => prev.map(msg => 
          msg.id === botMessage.id 
            ? { ...msg, content: simpleResponse.answer, response: convertedResponse, loading: false }
            : msg
        ));
      }
    } catch (err: any) {
      console.error('All chat methods failed:', err);
      const errorMessage = err.response?.data?.detail || 'Failed to get response from chat service';
      
      setMessages(prev => prev.map(msg => 
        msg.id === botMessage.id 
          ? { ...msg, content: `Sorry, I encountered an error: ${errorMessage}`, loading: false }
          : msg
      ));
      setError(errorMessage);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleCreateGitHubIssue = async (userQuery: string) => {
    try {
      const template = await githubApi.getIssueTemplate(userQuery);
      const issueData: TaskRequestIssue = {
        user_query: template.user_query,
        task_description: template.task_description,
        use_case: template.use_case,
        platform: template.platform,
        priority: template.priority
      };
      const result = await githubApi.createTaskRequest(issueData);
      window.open(result.issue_url, '_blank');
    } catch (error: any) {
      console.error('Error creating GitHub issue:', error);
      alert(error.response?.data?.detail || 'Error creating GitHub issue');
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleTasks = (messageId: string) => {
    setExpandedTasks(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  const markdownStyles = {
    '& h1': { fontSize: '1.1rem', fontWeight: 600, mt: 1.5, mb: 0.5, color: 'text.primary' },
    '& h2': { fontSize: '1rem', fontWeight: 600, mt: 1.5, mb: 0.5, color: 'text.primary' },
    '& h3': { fontSize: '0.95rem', fontWeight: 600, mt: 1, mb: 0.5, color: 'text.primary' },
    '& p': { fontSize: '0.9rem', mb: 1, lineHeight: 1.6, '&:last-child': { mb: 0 } },
    '& ul, & ol': { pl: 2, mb: 1, fontSize: '0.9rem' },
    '& li': { mb: 0.25, lineHeight: 1.5 },
    '& code': { 
      backgroundColor: 'rgba(0,0,0,0.06)', 
      px: 0.5, 
      py: 0.25, 
      borderRadius: 0.5,
      fontFamily: '"SF Mono", "Consolas", monospace',
      fontSize: '0.8rem'
    },
    '& pre': { 
      backgroundColor: 'rgba(0,0,0,0.04)', 
      p: 1.5, 
      borderRadius: 1,
      overflow: 'auto',
      fontSize: '0.8rem',
      '& code': { backgroundColor: 'transparent', p: 0 }
    },
    '& a': { 
      color: 'primary.main', 
      textDecoration: 'none', 
      '&:hover': { textDecoration: 'underline' },
      display: 'inline-flex',
      alignItems: 'center',
      gap: 0.25
    },
    '& strong': { fontWeight: 600 },
    '& blockquote': { 
      borderLeft: '3px solid',
      borderColor: 'divider',
      pl: 1.5,
      ml: 0,
      color: 'text.secondary',
      fontStyle: 'italic',
      fontSize: '0.9rem'
    },
    '& hr': {
      border: 'none',
      borderTop: '1px solid',
      borderColor: 'divider',
      my: 1.5
    }
  };

  return (
    <Box sx={{ 
      height: 'calc(100vh - 64px)', 
      display: 'flex', 
      flexDirection: 'column',
      backgroundColor: '#f7f7f8'
    }}>
      {/* Messages Area */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {messages.length === 0 ? (
          <Box sx={{ 
            maxWidth: 800, 
            mx: 'auto', 
            p: 4, 
            textAlign: 'center',
            mt: 8
          }}>
            <Avatar 
              src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png"
              sx={{ 
                width: 64, 
                height: 64, 
                mx: 'auto', 
                mb: 3,
                backgroundColor: 'transparent'
              }}
            />
            
            <Typography variant="h4" sx={{ mb: 1, fontWeight: 600 }}>
              Eager Edgar
            </Typography>
            
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 600, mx: 'auto' }}>
              Your Registry Chat assistant, specially trained on documentation, codebundles, authoring guidelines, and the entire CodeCollection ecosystem
            </Typography>

            {chatHealth && chatHealth.status !== 'healthy' && (
              <Alert severity="warning" sx={{ mb: 3, maxWidth: 500, mx: 'auto' }}>
                Chat service is currently unavailable
              </Alert>
            )}

            {examples && (
              <Box sx={{ mt: 4, maxWidth: 900, mx: 'auto' }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 3, textAlign: 'center' }}>
                  Try asking about:
                </Typography>
                <Box sx={{ 
                  display: 'grid', 
                  gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' },
                  gap: 2 
                }}>
                  {examples.examples.slice(0, 6).map((cat, catIdx) => (
                    <Paper 
                      key={cat.category}
                      elevation={0}
                      sx={{ 
                        p: 2, 
                        borderRadius: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        '&:hover': { borderColor: 'primary.main', boxShadow: 1 }
                      }}
                    >
                      <Typography 
                        variant="caption" 
                        sx={{ 
                          fontWeight: 600, 
                          color: 'primary.main',
                          textTransform: 'uppercase',
                          letterSpacing: 0.5
                        }}
                      >
                        {cat.category}
                      </Typography>
                      <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                        {cat.queries.slice(0, 2).map((query, idx) => (
                          <Box
                            key={`${cat.category}-${idx}`}
                            onClick={() => handleSendMessage(query)}
                            sx={{ 
                              cursor: 'pointer',
                              py: 0.75,
                              px: 1,
                              borderRadius: 1,
                              fontSize: '0.85rem',
                              color: 'text.secondary',
                              '&:hover': { 
                                backgroundColor: 'action.hover',
                                color: 'text.primary'
                              }
                            }}
                          >
                            {query}
                          </Box>
                        ))}
                      </Box>
                    </Paper>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        ) : (
          <Box sx={{ maxWidth: 800, mx: 'auto', py: 4, px: 2 }}>
            {messages.map((message) => (
              <Box 
                key={message.id} 
                sx={{ 
                  mb: 3,
                  display: 'flex',
                  gap: 2,
                  alignItems: 'flex-start'
                }}
              >
                <Avatar 
                  src={message.type === 'bot' ? 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png' : undefined}
                  sx={{ 
                    width: 32, 
                    height: 32,
                    backgroundColor: message.type === 'user' ? 'grey.700' : 'transparent',
                    flexShrink: 0
                  }}
                >
                  {message.type === 'user' && <PersonIcon sx={{ fontSize: 18 }} />}
                </Avatar>

                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 600 }}>
                    {message.type === 'user' ? 'You' : 'Eager Edgar'}
                  </Typography>

                  {message.loading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1 }}>
                      <CircularProgress size={16} />
                      <Typography variant="body2" color="text.secondary">
                        Thinking...
                      </Typography>
                    </Box>
                  ) : (
                    <Box>
                      <Box sx={markdownStyles}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.content}
                        </ReactMarkdown>
                      </Box>

                      {message.type === 'bot' && (
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 1, 
                          mt: 2,
                          opacity: 0.7,
                          '&:hover': { opacity: 1 }
                        }}>
                          <IconButton 
                            size="small" 
                            onClick={() => copyToClipboard(message.content, message.id)}
                            sx={{ p: 0.5 }}
                          >
                            {copiedId === message.id ? (
                              <CheckIcon sx={{ fontSize: 16 }} />
                            ) : (
                              <CopyIcon sx={{ fontSize: 16 }} />
                            )}
                          </IconButton>
                          
                        </Box>
                      )}

                      {/* Show Request CodeBundle button when no match found */}
                      {message.response?.no_match && (
                        <Box sx={{ mt: 2 }}>
                          <Button
                            variant="contained"
                            startIcon={<RequestIcon />}
                            onClick={() => handleCreateGitHubIssue(message.userQuery || message.content)}
                            sx={{
                              backgroundColor: '#1976d2',
                              color: 'white',
                              textTransform: 'none',
                              fontWeight: 500,
                              '&:hover': { backgroundColor: '#1565c0' }
                            }}
                          >
                            Request this CodeBundle
                          </Button>
                          <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>
                            Opens a pre-filled GitHub issue to request this automation
                          </Typography>
                        </Box>
                      )}

                      {message.response && message.response.relevant_tasks.length > 0 && (
                        <Box sx={{ mt: 2 }}>
                          <Box 
                            onClick={() => toggleTasks(message.id)}
                            sx={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: 0.5,
                              cursor: 'pointer',
                              color: 'text.secondary',
                              '&:hover': { color: 'text.primary' }
                            }}
                          >
                            {expandedTasks.has(message.id) ? (
                              <ExpandLessIcon sx={{ fontSize: 18 }} />
                            ) : (
                              <ExpandMoreIcon sx={{ fontSize: 18 }} />
                            )}
                            <Typography variant="body2">
                              {message.response.relevant_tasks.length} related codebundle{message.response.relevant_tasks.length > 1 ? 's' : ''}
                            </Typography>
                          </Box>
                          
                          <Collapse in={expandedTasks.has(message.id)}>
                            <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                              {message.response.relevant_tasks.map((task, index) => (
                                <Box 
                                  key={index} 
                                  sx={{ 
                                    p: 1.5,
                                    borderRadius: 1,
                                    border: '1px solid',
                                    borderColor: index === 0 ? 'primary.light' : 'divider',
                                    backgroundColor: index === 0 ? 'rgba(25, 118, 210, 0.04)' : 'background.paper',
                                    transition: 'all 0.15s',
                                    '&:hover': { borderColor: 'primary.main', backgroundColor: 'rgba(25, 118, 210, 0.06)' }
                                  }}
                                >
                                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                                      <Typography 
                                        variant="body2" 
                                        sx={{ 
                                          fontWeight: 600,
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap'
                                        }}
                                      >
                                        {task.codebundle_name}
                                      </Typography>
                                      <Chip 
                                        label={`${Math.round(task.relevance_score * 100)}%`} 
                                        size="small"
                                        sx={{ 
                                          height: 18,
                                          fontSize: '0.65rem',
                                          fontWeight: 600,
                                          backgroundColor: task.relevance_score >= 0.65 ? 'success.main' : task.relevance_score >= 0.6 ? 'warning.light' : 'grey.300',
                                          color: task.relevance_score >= 0.65 ? 'white' : 'text.primary'
                                        }}
                                      />
                                    </Box>
                                    {task.runbook_source_url && (
                                      <Link 
                                        href={task.runbook_source_url} 
                                        sx={{ 
                                          display: 'flex', 
                                          alignItems: 'center', 
                                          fontSize: '0.75rem',
                                          flexShrink: 0,
                                          color: 'primary.main',
                                          textDecoration: 'none',
                                          '&:hover': { textDecoration: 'underline' }
                                        }}
                                      >
                                        View
                                      </Link>
                                    )}
                                  </Box>
                                  
                                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
                                    {task.collection_name} • {task.platform}
                                  </Typography>
                                </Box>
                              ))}
                            </Box>
                          </Collapse>
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
            <div ref={messagesEndRef} />
          </Box>
        )}
      </Box>

      {/* Input Area */}
      <Box sx={{ 
        borderTop: '1px solid',
        borderColor: 'divider',
        backgroundColor: 'background.paper',
        p: 2
      }}>
        <Box sx={{ maxWidth: 800, mx: 'auto' }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
          
          <Paper
            elevation={0}
            sx={{ 
              display: 'flex',
              alignItems: 'flex-end',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 3,
              overflow: 'hidden',
              backgroundColor: '#fff',
              '&:focus-within': {
                borderColor: 'primary.main',
                boxShadow: '0 0 0 2px rgba(25, 118, 210, 0.1)'
              }
            }}
          >
            <TextField
              fullWidth
              multiline
              maxRows={6}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about CodeCollection tasks..."
              disabled={loading || chatHealth?.status !== 'healthy'}
              inputRef={inputRef}
              variant="standard"
              InputProps={{
                disableUnderline: true,
                sx: { px: 2, py: 1.5 }
              }}
            />
            <IconButton
              onClick={() => handleSendMessage()}
              disabled={!inputValue.trim() || loading || chatHealth?.status !== 'healthy'}
              sx={{ 
                m: 1,
                backgroundColor: inputValue.trim() ? 'primary.main' : 'grey.200',
                color: inputValue.trim() ? 'white' : 'grey.500',
                '&:hover': {
                  backgroundColor: inputValue.trim() ? 'primary.dark' : 'grey.300'
                },
                '&.Mui-disabled': {
                  backgroundColor: 'grey.200',
                  color: 'grey.400'
                }
              }}
            >
              {loading ? (
                <CircularProgress size={20} color="inherit" />
              ) : (
                <SendIcon sx={{ fontSize: 20 }} />
              )}
            </IconButton>
          </Paper>
          
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>
            Press Enter to send • Shift+Enter for new line
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Chat;
