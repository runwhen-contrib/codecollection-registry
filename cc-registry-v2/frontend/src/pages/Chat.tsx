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
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
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
import { useLocation } from 'react-router-dom';
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
  const location = useLocation();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatHealth, setChatHealth] = useState<any>(null);
  const [examples, setExamples] = useState<ExampleQueries | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  const [requestContext, setRequestContext] = useState('');
  const [currentRequestQuery, setCurrentRequestQuery] = useState('');
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [initialQueryProcessed, setInitialQueryProcessed] = useState(false);
  const [codebundleContext, setCodebundleContext] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-focus input on mount and after messages
  useEffect(() => {
    inputRef.current?.focus();
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

  // Handle initial query from homepage search or codebundle detail page
  useEffect(() => {
    const state = location.state as { initialQuery?: string; codebundleContext?: any } | null;
    if (state?.initialQuery && !initialQueryProcessed && chatHealth?.status === 'healthy') {
      setInitialQueryProcessed(true);
      
      // Store codebundle context if provided
      if (state.codebundleContext) {
        setCodebundleContext(state.codebundleContext);
      }
      
      handleSendMessage(state.initialQuery);
      // Clear the state so it doesn't re-trigger
      window.history.replaceState({}, document.title);
    }
  }, [location.state, chatHealth, initialQueryProcessed]);

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
        // This provides context to the LLM about the ongoing conversation
        const conversationHistory = messages
          .filter(m => !m.loading && m.content)
          .slice(-6)
          .map(m => ({
            role: (m.type === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
            content: m.content
          }));
        
        // Build additional context if we have codebundle context
        let additionalContext = '';
        if (codebundleContext) {
          additionalContext = `Context: This question is about the "${codebundleContext.name}" CodeBundle`;
          if (codebundleContext.collectionSlug) {
            additionalContext += ` (slug: ${codebundleContext.slug}, collection: ${codebundleContext.collectionSlug})`;
          }
          if (codebundleContext.description) {
            additionalContext += `. Description: ${codebundleContext.description}`;
          }
          if (codebundleContext.accessLevel) {
            additionalContext += `. Access Level: ${codebundleContext.accessLevel}`;
          }
          if (codebundleContext.iamRequirements && codebundleContext.iamRequirements.length > 0) {
            additionalContext += `. IAM Requirements: ${codebundleContext.iamRequirements.join(', ')}`;
          }
        }
        
        console.log('Sending query to API:', {
          question: text,
          conversationHistoryLength: conversationHistory.length,
          conversationHistory: conversationHistory,
          codebundleContext: codebundleContext ? codebundleContext.name : 'none',
          additionalContext
        });
        
        response = await chatApi.query({
          question: additionalContext ? `${additionalContext}\n\nQuestion: ${text}` : text,
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

  const handleOpenRequestDialog = (userQuery: string) => {
    setCurrentRequestQuery(userQuery);
    setRequestContext('');
    setRequestDialogOpen(true);
  };

  const handleCloseRequestDialog = () => {
    setRequestDialogOpen(false);
    setRequestContext('');
    setCurrentRequestQuery('');
  };

  const handleSubmitRequest = async () => {
    setSubmittingRequest(true);
    try {
      // Combine the original query with additional context
      const fullQuery = requestContext.trim() 
        ? `${currentRequestQuery}\n\nAdditional context: ${requestContext}`
        : currentRequestQuery;
      
      const template = await githubApi.getIssueTemplate(fullQuery);
      const issueData: TaskRequestIssue = {
        user_query: template.user_query,
        task_description: template.task_description,
        use_case: template.use_case,
        platform: template.platform,
        priority: template.priority
      };
      const result = await githubApi.createTaskRequest(issueData);
      window.open(result.issue_url, '_blank');
      handleCloseRequestDialog();
    } catch (error: any) {
      console.error('Error creating GitHub issue:', error);
      alert(error.response?.data?.detail || 'Error creating GitHub issue');
    } finally {
      setSubmittingRequest(false);
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
      <Box sx={{ flexGrow: 1, overflow: 'auto', pb: 2 }}>
        {messages.length === 0 ? (
          <Box sx={{ 
            maxWidth: 768, 
            mx: 'auto', 
            p: 3, 
            textAlign: 'center',
            mt: { xs: 2, md: 8 }
          }}>
            <Typography variant="h4" sx={{ mb: 2, fontWeight: 500, color: '#202124' }}>
              Welcome to Registry Chat
            </Typography>
            
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 3 }}>
              <Avatar 
                src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png"
                sx={{ 
                  width: 48, 
                  height: 48, 
                  backgroundColor: 'transparent',
                  border: '2px solid',
                  borderColor: 'primary.main'
                }}
              />
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                Eager Edgar
              </Typography>
            </Box>

            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 600, mx: 'auto', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Ask Eager Edgar to help explore CodeBundles, documentation, and authoring guidelines. Get assistance with troubleshooting tasks, SLIs, and automation workflows across the CodeCollection ecosystem.
            </Typography>

            {chatHealth && chatHealth.status !== 'healthy' && (
              <Alert severity="warning" sx={{ mb: 3, maxWidth: 500, mx: 'auto' }}>
                Chat service is currently unavailable
              </Alert>
            )}

            {examples && (
              <Box sx={{ mt: 4, maxWidth: 768, mx: 'auto' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2, textAlign: 'center', fontWeight: 500 }}>
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
          <Box sx={{ width: '100%', minHeight: '100%' }}>
            {messages.map((message, index) => (
              <Box 
                key={message.id} 
                sx={{ 
                  py: { xs: 3, md: 4 },
                  px: { xs: 2, md: 3 }
                }}
              >
                <Box 
                  sx={{
                    maxWidth: 768,
                    mx: 'auto',
                    display: 'flex',
                    gap: 3,
                    alignItems: 'flex-start'
                  }}
                >
                <Avatar 
                  src={message.type === 'bot' ? 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png' : undefined}
                  sx={{ 
                    width: 36, 
                    height: 36,
                    backgroundColor: message.type === 'user' ? '#5282f1' : 'transparent',
                    flexShrink: 0
                  }}
                >
                  {message.type === 'user' && <PersonIcon sx={{ fontSize: 20, color: 'white' }} />}
                </Avatar>

                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>
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
                      {message.type === 'user' ? (
                        <Typography 
                          variant="body2" 
                          component="pre"
                          sx={{ 
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            fontFamily: 'inherit',
                            fontSize: '0.9rem',
                            lineHeight: 1.6,
                            m: 0
                          }}
                        >
                          {message.content}
                        </Typography>
                      ) : (
                        <Box sx={markdownStyles}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                          </ReactMarkdown>
                        </Box>
                      )}

                      {message.type === 'bot' && !message.response?.no_match && (
                        <Box sx={{ mt: 2 }}>
                          {/* MCP tool data is in response.query_metadata.mcp_tools - hidden from UI but available for inspection */}
                          
                          <Box sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 1
                          }}>
                            <IconButton 
                              size="small" 
                              onClick={() => copyToClipboard(message.content, message.id)}
                              sx={{ 
                                p: 0.5,
                                opacity: 0.7,
                                '&:hover': { opacity: 1 }
                              }}
                            >
                              {copiedId === message.id ? (
                                <CheckIcon sx={{ fontSize: 16 }} />
                              ) : (
                                <CopyIcon sx={{ fontSize: 16 }} />
                              )}
                            </IconButton>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<RequestIcon sx={{ fontSize: 16 }} />}
                              onClick={() => handleOpenRequestDialog(message.userQuery || message.content)}
                              sx={{
                                textTransform: 'none',
                                fontSize: '0.75rem',
                                borderColor: 'divider',
                                color: 'text.secondary',
                                fontWeight: 500,
                                '&:hover': { 
                                  borderColor: 'primary.main',
                                  color: 'primary.main',
                                  backgroundColor: 'rgba(25, 118, 210, 0.04)'
                                }
                              }}
                            >
                              Request CodeBundle
                            </Button>
                          </Box>
                        </Box>
                      )}

                      {/* Show prominent Request CodeBundle button when no match found */}
                      {message.response?.no_match && (
                        <Box sx={{ mt: 2 }}>
                          <Alert 
                            severity="info" 
                            sx={{ 
                              backgroundColor: 'rgba(25, 118, 210, 0.04)',
                              border: '1px solid rgba(25, 118, 210, 0.2)'
                            }}
                            action={
                              <Button
                                variant="contained"
                                size="small"
                                startIcon={<RequestIcon />}
                                onClick={() => handleOpenRequestDialog(message.userQuery || message.content)}
                                sx={{
                                  backgroundColor: '#1976d2',
                                  color: 'white',
                                  textTransform: 'none',
                                  fontWeight: 500,
                                  '&:hover': { 
                                    backgroundColor: '#1565c0',
                                    color: 'white'
                                  }
                                }}
                              >
                                Request CodeBundle
                              </Button>
                            }
                          >
                            <Typography variant="body2">
                              Can't find what you're looking for? Request a new CodeBundle for this use case.
                            </Typography>
                          </Alert>
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
              </Box>
            ))}
            <div ref={messagesEndRef} />
          </Box>
        )}
      </Box>

      {/* Input Area - ChatGPT-style fixed bottom input */}
      <Box sx={{ 
        backgroundColor: '#f7f7f8',
        pt: 2,
        pb: { xs: 2, md: 3 },
        px: 2
      }}>
        <Box sx={{ maxWidth: 768, mx: 'auto' }}>
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
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              transition: 'border-color 0.15s, box-shadow 0.15s',
              '&:focus-within': {
                borderColor: 'primary.main',
                boxShadow: '0 2px 12px rgba(82, 130, 241, 0.2)'
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
              placeholder="Message Eager Edgar..."
              disabled={loading || chatHealth?.status !== 'healthy'}
              inputRef={inputRef}
              variant="standard"
              InputProps={{
                disableUnderline: true,
                sx: { 
                  px: 3, 
                  py: 2,
                  fontSize: '0.95rem',
                  lineHeight: 1.5
                }
              }}
            />
            <IconButton
              onClick={() => handleSendMessage()}
              disabled={!inputValue.trim() || loading || chatHealth?.status !== 'healthy'}
              sx={{ 
                m: 1.5,
                mb: 1,
                width: 36,
                height: 36,
                backgroundColor: inputValue.trim() ? 'primary.main' : 'grey.300',
                color: inputValue.trim() ? 'white' : 'grey.500',
                transition: 'background-color 0.15s, transform 0.1s',
                '&:hover': {
                  backgroundColor: inputValue.trim() ? 'primary.dark' : 'grey.400',
                  transform: inputValue.trim() ? 'scale(1.05)' : 'none'
                },
                '&.Mui-disabled': {
                  backgroundColor: 'grey.200',
                  color: 'grey.400'
                }
              }}
            >
              {loading ? (
                <CircularProgress size={18} sx={{ color: 'inherit' }} />
              ) : (
                <SendIcon sx={{ fontSize: 18 }} />
              )}
            </IconButton>
          </Paper>
          
          <Typography 
            variant="caption" 
            color="text.secondary" 
            sx={{ 
              display: 'block', 
              textAlign: 'center', 
              mt: 1.5,
              fontSize: '0.7rem'
            }}
          >
            Eager Edgar can make mistakes. Press Enter to send • Shift+Enter for new line
          </Typography>
        </Box>
      </Box>

      {/* Request CodeBundle Dialog */}
      <Dialog 
        open={requestDialogOpen} 
        onClose={handleCloseRequestDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Request a CodeBundle
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Your original query:
            </Typography>
            <Paper sx={{ p: 2, backgroundColor: 'grey.50', mb: 3 }}>
              <Typography variant="body2">
                {currentRequestQuery}
              </Typography>
            </Paper>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Add more context to help us understand your needs (optional):
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={4}
              value={requestContext}
              onChange={(e) => setRequestContext(e.target.value)}
              placeholder="e.g., I need this to work with AWS EKS clusters, integrate with PagerDuty alerts, and run every 5 minutes..."
              variant="outlined"
            />
            
            <Alert severity="info" sx={{ mt: 2 }}>
              This will create a GitHub issue with your request. The more details you provide, the better we can help!
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button 
            onClick={handleCloseRequestDialog}
            disabled={submittingRequest}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSubmitRequest}
            variant="contained"
            startIcon={submittingRequest ? <CircularProgress size={16} sx={{ color: 'white' }} /> : <RequestIcon />}
            disabled={submittingRequest}
            sx={{
              backgroundColor: '#1976d2',
              color: 'white',
              '&:hover': { 
                backgroundColor: '#1565c0',
                color: 'white'
              },
              '&.Mui-disabled': {
                backgroundColor: 'rgba(25, 118, 210, 0.6)',
                color: 'white'
              }
            }}
          >
            {submittingRequest ? 'Creating...' : 'Submit Request'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Chat;
