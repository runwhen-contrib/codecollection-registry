import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Paper,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Link,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Send as SendIcon,
  ExpandMore as ExpandMoreIcon,
  SmartToy as BotIcon,
  Person as PersonIcon,
  ContentCopy as CopyIcon,
  OpenInNew as OpenInNewIcon,
  Lightbulb as LightbulbIcon,
  GitHub as GitHubIcon
} from '@mui/icons-material';
import { chatApi, githubApi, ChatResponse, ExampleQueries, TaskRequestIssue } from '../services/api';

interface ChatMessage {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
  response?: ChatResponse;
  loading?: boolean;
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatHealth, setChatHealth] = useState<any>(null);
  const [examples, setExamples] = useState<ExampleQueries | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new messages are added
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load initial data
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

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date()
    };

    const botMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      type: 'bot',
      content: '',
      timestamp: new Date(),
      loading: true
    };

    setMessages(prev => [...prev, userMessage, botMessage]);
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      // Try the full chat API first, fallback to simple chat
      let response: ChatResponse;
      try {
        response = await chatApi.query({
          question: userMessage.content,
          context_limit: 5,
          include_enhanced_descriptions: true
        });
        
        // Update the bot message with the response
        setMessages(prev => prev.map(msg => 
          msg.id === botMessage.id 
            ? { ...msg, content: response.answer, response, loading: false }
            : msg
        ));
      } catch (mainChatError) {
        console.warn('Main chat failed, trying simple chat:', mainChatError);
        
        // Fallback to simple chat
        const simpleResponse = await chatApi.simpleQuery(userMessage.content);
        
        // Convert simple response to chat response format
        const convertedResponse: ChatResponse = {
          answer: simpleResponse.answer,
          relevant_tasks: simpleResponse.relevant_codebundles.map((cb, index) => ({
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
            access_level: 'unknown',
            minimum_iam_requirements: [],
            runbook_source_url: '',
            relevance_score: 1.0,
            platform: '',
            resource_types: []
          })),
          sources_used: simpleResponse.relevant_codebundles.map(cb => cb.name),
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
    }
  };

  const handleCreateGitHubIssue = async (userQuery: string) => {
    try {
      // Get the issue template
      const template = await githubApi.getIssueTemplate(userQuery);
      
      // Create the issue
      const issueData: TaskRequestIssue = {
        user_query: template.user_query,
        task_description: template.task_description,
        use_case: template.use_case,
        platform: template.platform,
        priority: template.priority
      };
      
      const result = await githubApi.createTaskRequest(issueData);
      
      // Show success message
      alert(`GitHub issue created successfully!\nIssue #${result.issue_number}\nURL: ${result.issue_url}`);
      
      // Optionally open the issue in a new tab
      window.open(result.issue_url, '_blank');
      
    } catch (error: any) {
      console.error('Error creating GitHub issue:', error);
      
      // Show user-friendly error message
      if (error.response?.data?.detail) {
        alert(`Error creating GitHub issue: ${error.response.data.detail}`);
      } else {
        alert('Error creating GitHub issue. Please try again or contact support.');
      }
    }
  };

  const handleExampleClick = async (query: string) => {
    if (loading) return;
    
    // Send the query directly
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: query,
      timestamp: new Date()
    };

    const botMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      type: 'bot',
      content: '',
      timestamp: new Date(),
      loading: true
    };

    setMessages(prev => [...prev, userMessage, botMessage]);
    setLoading(true);
    setError(null);

    try {
      // Use simple chat for examples since it's more reliable
      const simpleResponse = await chatApi.simpleQuery(query);
      
      // Convert simple response to chat response format
      const convertedResponse: ChatResponse = {
        answer: simpleResponse.answer,
        relevant_tasks: simpleResponse.relevant_codebundles.map((cb, index) => ({
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
          access_level: 'unknown',
          minimum_iam_requirements: [],
          runbook_source_url: '',
          relevance_score: 1.0,
          platform: '',
          resource_types: []
        })),
        sources_used: simpleResponse.relevant_codebundles.map(cb => cb.name),
        query_metadata: {
          query_processed_at: new Date().toISOString(),
          context_tasks_count: simpleResponse.relevant_codebundles.length,
          ai_model: 'simple-chat'
        }
      };
      
      setMessages(prev => prev.map(msg => 
        msg.id === botMessage.id 
          ? { ...msg, content: simpleResponse.answer, response: convertedResponse, loading: false }
          : msg
      ));
    } catch (err: any) {
      console.error('Example query failed:', err);
      const errorMessage = err.response?.data?.detail || 'Failed to get response';
      
      setMessages(prev => prev.map(msg => 
        msg.id === botMessage.id 
          ? { ...msg, content: `Sorry, I encountered an error: ${errorMessage}`, loading: false }
          : msg
      ));
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        CodeCollection Assistant
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        Ask questions about available tasks and libraries in the CodeCollection Registry.
      </Typography>


      {/* Health Status */}
      {chatHealth && (
        <Alert 
          severity={chatHealth.status === 'healthy' ? 'success' : 'warning'} 
          sx={{ mb: 2 }}
        >
          Chat service is {chatHealth.status}
          {chatHealth.ai_enabled && chatHealth.model && (
            <span> • Using {chatHealth.ai_provider} ({chatHealth.model})</span>
          )}
        </Alert>
      )}

      {/* Example Queries */}
      {examples && messages.length === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <LightbulbIcon sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h6">Try asking about:</Typography>
          </Box>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {examples.examples.map((category, categoryIndex) => (
              <Box key={categoryIndex} sx={{ flex: '1 1 300px', minWidth: '300px' }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
                  {category.category}
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {category.queries.map((query, queryIndex) => (
                    <Chip
                      key={queryIndex}
                      label={query}
                      variant="outlined"
                      clickable
                      onClick={() => handleExampleClick(query)}
                      sx={{ 
                        justifyContent: 'flex-start',
                        height: 'auto',
                        py: 1,
                        '& .MuiChip-label': {
                          whiteSpace: 'normal',
                          textAlign: 'left'
                        }
                      }}
                    />
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* Chat Messages */}
      <Paper sx={{ height: '60vh', display: 'flex', flexDirection: 'column', mb: 2 }}>
        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
          {messages.length === 0 ? (
            <Box sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              height: '100%',
              color: 'text.secondary'
            }}>
              <Typography>Start a conversation by asking a question about CodeCollection tasks!</Typography>
            </Box>
          ) : (
            messages.map((message) => (
              <Box key={message.id} sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  {message.type === 'user' ? (
                    <PersonIcon sx={{ color: 'primary.main', mt: 0.5 }} />
                  ) : (
                    <BotIcon sx={{ color: 'secondary.main', mt: 0.5 }} />
                  )}
                  
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      {message.type === 'user' ? 'You' : 'Assistant'}
                      <Typography component="span" variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
                        {message.timestamp.toLocaleTimeString()}
                      </Typography>
                    </Typography>
                    
                    <Card variant="outlined">
                      <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                        {message.loading ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <CircularProgress size={16} />
                            <Typography variant="body2" color="text.secondary">
                              Thinking...
                            </Typography>
                          </Box>
                        ) : (
                          <>
                            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                              {message.content}
                            </Typography>
                            
                            {/* GitHub Issue Button for "No Matching Tasks" responses */}
                            {message.type === 'bot' && message.content.includes('No Matching Tasks Found') && (
                              <Box sx={{ mt: 2 }}>
                                <Button
                                  variant="contained"
                                  startIcon={<GitHubIcon />}
                                  onClick={() => {
                                    // Extract the original query from the message content
                                    const match = message.content.match(/request for "([^"]+)"/);
                                    const userQuery = match ? match[1] : 'custom task request';
                                    handleCreateGitHubIssue(userQuery);
                                  }}
                                  sx={{ mr: 1 }}
                                >
                                  Create GitHub Issue
                                </Button>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                                  Request these tasks to be added to the registry
                                </Typography>
                              </Box>
                            )}
                            
                            {message.type === 'bot' && (
                              <Tooltip title="Copy response">
                                <IconButton 
                                  size="small" 
                                  onClick={() => copyToClipboard(message.content)}
                                  sx={{ mt: 1 }}
                                >
                                  <CopyIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </>
                        )}
                      </CardContent>
                    </Card>

                    {/* Relevant Tasks */}
                    {message.response && message.response.relevant_tasks.length > 0 && (
                      <Accordion sx={{ mt: 2 }}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Typography variant="subtitle2">
                            Relevant Tasks ({message.response.relevant_tasks.length})
                          </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {message.response.relevant_tasks.map((task, index) => (
                              <Card key={task.id} variant="outlined">
                                <CardContent>
                                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                                    <Typography variant="h6" component="h3">
                                      {task.codebundle_name}
                                    </Typography>
                                    <Chip 
                                      label={`${Math.round(task.relevance_score * 100)}% match`} 
                                      size="small" 
                                      color="primary" 
                                    />
                                  </Box>
                                  
                                  <Typography variant="body2" color="text.secondary" gutterBottom>
                                    {task.collection_name} • {task.platform || 'Generic'}
                                  </Typography>
                                  
                                  <Typography variant="body2" paragraph>
                                    {task.description}
                                  </Typography>
                                  
                                  {task.support_tags.length > 0 && (
                                    <Box sx={{ mb: 1 }}>
                                      {task.support_tags.map((tag, tagIndex) => (
                                        <Chip key={tagIndex} label={tag} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                                      ))}
                                    </Box>
                                  )}
                                  
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Chip 
                                      label={task.access_level} 
                                      size="small" 
                                      color={task.access_level === 'read-only' ? 'success' : 'warning'} 
                                    />
                                    
                                    {task.runbook_source_url && (
                                      <Link 
                                        href={task.runbook_source_url} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                                      >
                                        View Source
                                        <OpenInNewIcon fontSize="small" />
                                      </Link>
                                    )}
                                  </Box>
                                </CardContent>
                              </Card>
                            ))}
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    )}
                  </Box>
                </Box>
              </Box>
            ))
          )}
          <div ref={messagesEndRef} />
        </Box>

        <Divider />

        {/* Input Area */}
        <Box sx={{ p: 2 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              multiline
              maxRows={4}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about CodeCollection tasks... (e.g., 'What do I run when pods are failing?')"
              disabled={loading || chatHealth?.status !== 'healthy'}
            />
            <Button
              variant="contained"
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || loading || chatHealth?.status !== 'healthy'}
              sx={{ minWidth: 'auto', px: 2 }}
            >
              <SendIcon />
            </Button>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default Chat;
