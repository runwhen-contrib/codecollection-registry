import React, { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, TextField, IconButton, Paper, Chip, Alert,
  CircularProgress, Collapse, Link, Avatar
} from '@mui/material';
import {
  Send as SendIcon, SmartToy as BotIcon, Person as PersonIcon,
  ContentCopy as CopyIcon, Check as CheckIcon, ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon, GitHub as GitHubIcon, OpenInNew as OpenInNewIcon
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
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
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    const load = async () => {
      try {
        const [h, e] = await Promise.all([chatApi.health(), chatApi.getExamples()]);
        setChatHealth(h); setExamples(e);
      } catch (err) { setError('Failed to initialize chat'); }
    };
    load();
  }, []);

  const send = async (text?: string) => {
    const msg = text || inputValue.trim();
    if (!msg || loading) return;

    const user: ChatMessage = { id: Date.now().toString(), type: 'user', content: msg, timestamp: new Date() };
    const bot: ChatMessage = { id: (Date.now()+1).toString(), type: 'bot', content: '', timestamp: new Date(), loading: true };

    setMessages(p => [...p, user, bot]);
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      let resp: ChatResponse;
      try {
        resp = await chatApi.query({ question: msg, context_limit: 5, include_enhanced_descriptions: true });
        setMessages(p => p.map(m => m.id === bot.id ? { ...m, content: resp.answer, response: resp, loading: false } : m));
      } catch {
        const s = await chatApi.simpleQuery(msg);
        const conv: ChatResponse = {
          answer: s.answer,
          relevant_tasks: s.relevant_codebundles.map((c: any, i: number) => ({
            id: i, codebundle_name: c.name, codebundle_slug: c.name.toLowerCase().replace(/\s+/g, '-'),
            collection_name: c.collection, collection_slug: c.collection.toLowerCase().replace(/\s+/g, '-'),
            description: c.description, support_tags: c.support_tags || [], tasks: [], slis: [],
            author: '', access_level: c.access_level || 'unknown', minimum_iam_requirements: [],
            runbook_source_url: c.runbook_source_url || '', relevance_score: c.relevance_score || 0.5,
            platform: c.platform || '', resource_types: []
          })),
          sources_used: s.relevant_codebundles.map((c: any) => c.name),
          query_metadata: { query_processed_at: new Date().toISOString(), context_tasks_count: s.relevant_codebundles.length, ai_model: 'fallback' }
        };
        setMessages(p => p.map(m => m.id === bot.id ? { ...m, content: s.answer, response: conv, loading: false } : m));
      }
    } catch (e: any) {
      setMessages(p => p.map(m => m.id === bot.id ? { ...m, content: 'Error: ' + (e.response?.data?.detail || 'Failed'), loading: false } : m));
      setError(e.response?.data?.detail || 'Failed');
    } finally { setLoading(false); inputRef.current?.focus(); }
  };

  const createIssue = async (q: string) => {
    try {
      const t = await githubApi.getIssueTemplate(q);
      const r = await githubApi.createTaskRequest({ user_query: t.user_query, task_description: t.task_description, use_case: t.use_case, platform: t.platform, priority: t.priority } as TaskRequestIssue);
      window.open(r.issue_url, '_blank');
    } catch (e: any) { alert(e.response?.data?.detail || 'Error'); }
  };

  const copy = (t: string, id: string) => { navigator.clipboard.writeText(t); setCopiedId(id); setTimeout(() => setCopiedId(null), 2000); };
  const toggle = (id: string) => setExpandedTasks(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const mdStyle = {
    '& h1,& h2,& h3': { fontWeight: 600, mt: 2, mb: 1 },
    '& p': { mb: 1.5, lineHeight: 1.7 }, '& ul,& ol': { pl: 2.5, mb: 1.5 }, '& li': { mb: 0.5 },
    '& code': { backgroundColor: 'rgba(0,0,0,0.05)', px: 0.75, py: 0.25, borderRadius: 0.5, fontFamily: 'monospace', fontSize: '0.875em' },
    '& pre': { backgroundColor: 'rgba(0,0,0,0.05)', p: 2, borderRadius: 1, overflow: 'auto', '& code': { backgroundColor: 'transparent', p: 0 } },
    '& a': { color: 'primary.main' }, '& strong': { fontWeight: 600 }
  };

  return (
    <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', backgroundColor: '#f7f7f8' }}>
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {messages.length === 0 ? (
          <Box sx={{ maxWidth: 800, mx: 'auto', p: 4, textAlign: 'center', mt: 8 }}>
            <Avatar sx={{ width: 64, height: 64, mx: 'auto', mb: 3 }} src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png" />
            <Typography variant="h4" sx={{ mb: 1, fontWeight: 600 }}>CodeCollection Assistant</Typography>
            <Typography color="text.secondary" sx={{ mb: 4 }}>Ask me about tasks and codebundles</Typography>
            {chatHealth?.status !== 'healthy' && <Alert severity="warning" sx={{ mb: 3, maxWidth: 500, mx: 'auto' }}>Chat unavailable</Alert>}
            {examples && <Box sx={{ mt: 4 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>Try:</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
                {examples.examples.slice(0,2).flatMap(c => c.queries.slice(0,2).map((q,i) => <Chip key={c.category+i} label={q} variant="outlined" onClick={() => send(q)} sx={{ cursor: 'pointer' }} />))}
              </Box>
            </Box>}
          </Box>
        ) : (
          <Box sx={{ maxWidth: 800, mx: 'auto', py: 4, px: 2 }}>
            {messages.map(m => (
              <Box key={m.id} sx={{ mb: 3, display: 'flex', gap: 2 }}>
                <Avatar sx={{ width: 32, height: 32, backgroundColor: m.type === 'user' ? 'grey.700' : 'transparent', flexShrink: 0 }} src={m.type === 'bot' ? 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png' : undefined}>
                  {m.type === 'user' && <PersonIcon sx={{ fontSize: 18 }} />}
                </Avatar>
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 600 }}>{m.type === 'user' ? 'You' : 'Assistant'}</Typography>
                  {m.loading ? (
                    <Box sx={{ display: 'flex', gap: 1.5, py: 1 }}><CircularProgress size={16} /><Typography variant="body2" color="text.secondary">Thinking...</Typography></Box>
                  ) : (
                    <Box>
                      <Box sx={mdStyle}><ReactMarkdown>{m.content}</ReactMarkdown></Box>
                      {m.type === 'bot' && <Box sx={{ display: 'flex', gap: 1, mt: 2, opacity: 0.7, '&:hover': { opacity: 1 } }}>
                        <IconButton size="small" onClick={() => copy(m.content, m.id)} sx={{ p: 0.5 }}>{copiedId === m.id ? <CheckIcon sx={{ fontSize: 16 }} /> : <CopyIcon sx={{ fontSize: 16 }} />}</IconButton>
                        {m.content.includes('No Matching') && <IconButton size="small" onClick={() => createIssue(m.content)} sx={{ p: 0.5 }}><GitHubIcon sx={{ fontSize: 16 }} /></IconButton>}
                      </Box>}
                      {(m.response?.relevant_tasks?.length ?? 0) > 0 && <Box sx={{ mt: 2 }}>
                        <Box onClick={() => toggle(m.id)} sx={{ display: 'flex', gap: 0.5, cursor: 'pointer', color: 'text.secondary', '&:hover': { color: 'text.primary' } }}>
                          {expandedTasks.has(m.id) ? <ExpandLessIcon sx={{ fontSize: 18 }} /> : <ExpandMoreIcon sx={{ fontSize: 18 }} />}
                          <Typography variant="body2">{m.response!.relevant_tasks.length} codebundle{m.response!.relevant_tasks.length > 1 ? 's' : ''}</Typography>
                        </Box>
                        <Collapse in={expandedTasks.has(m.id)}>
                          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                            {m.response!.relevant_tasks.map((t, i) => (
                              <Paper key={i} variant="outlined" sx={{ p: 2 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{t.codebundle_name}</Typography>
                                  <Chip label={Math.round(t.relevance_score * 100) + '%'} size="small" sx={{ height: 20, fontSize: '0.7rem', backgroundColor: t.relevance_score > 0.7 ? 'success.light' : 'grey.200' }} />
                                </Box>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>{t.collection_name}{t.platform && ' • ' + t.platform}</Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{t.description}</Typography>
                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                  {t.support_tags.slice(0, 3).map((tag, j) => <Chip key={j} label={tag} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />)}
                                  {t.runbook_source_url && <Link href={t.runbook_source_url} target="_blank" sx={{ display: 'flex', gap: 0.5, fontSize: '0.75rem', ml: 'auto' }}>View <OpenInNewIcon sx={{ fontSize: 12 }} /></Link>}
                                </Box>
                              </Paper>
                            ))}
                          </Box>
                        </Collapse>
                      </Box>}
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
            <div ref={messagesEndRef} />
          </Box>
        )}
      </Box>
      <Box sx={{ borderTop: '1px solid', borderColor: 'divider', backgroundColor: 'background.paper', p: 2 }}>
        <Box sx={{ maxWidth: 800, mx: 'auto' }}>
          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
          <Paper elevation={0} sx={{ display: 'flex', alignItems: 'flex-end', border: '1px solid', borderColor: 'divider', borderRadius: 3, '&:focus-within': { borderColor: 'primary.main' } }}>
            <TextField fullWidth multiline maxRows={6} value={inputValue} onChange={e => setInputValue(e.target.value)} onKeyPress={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="Ask about CodeCollection tasks..." disabled={loading || chatHealth?.status !== 'healthy'} inputRef={inputRef} variant="standard" InputProps={{ disableUnderline: true, sx: { px: 2, py: 1.5 } }} />
            <IconButton onClick={() => send()} disabled={!inputValue.trim() || loading || chatHealth?.status !== 'healthy'} sx={{ m: 1, backgroundColor: inputValue.trim() ? 'primary.main' : 'grey.200', color: inputValue.trim() ? 'white' : 'grey.500', '&:hover': { backgroundColor: inputValue.trim() ? 'primary.dark' : 'grey.300' }, '&.Mui-disabled': { backgroundColor: 'grey.200', color: 'grey.400' } }}>
              {loading ? <CircularProgress size={20} color="inherit" /> : <SendIcon sx={{ fontSize: 20 }} />}
            </IconButton>
          </Paper>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>Enter to send • Shift+Enter for new line</Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Chat;
