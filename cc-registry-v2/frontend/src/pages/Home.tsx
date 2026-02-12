import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Button,
  Chip,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip,
} from '@mui/material';
import { 
  Search as SearchIcon,
  TrendingUp as TrendingIcon,
  MonetizationOn as MoneyIcon,
  ArrowForward as ArrowIcon,
  FolderSpecialOutlined as CollectionIcon,
  IntegrationInstructionsOutlined as BundleIcon,
  TerminalOutlined as TaskIcon,
  MenuBookOutlined as DocsIcon,
} from '@mui/icons-material';
import { Link, useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import TaskGrowthChart from '../components/TaskGrowthChart';

interface RegistryStats {
  collections: number;
  codebundles: number;
  tasks: number;
  slis: number;
  tasks_over_time: Array<{ month: string; tasks: number }>;
}

interface RecentCodebundle {
  id: number;
  name: string;
  slug: string;
  display_name: string;
  description: string;
  collection_name: string;
  collection_slug: string;
  platform: string;
  task_count: number;
  git_updated_at: string | null;
  updated_at: string | null;
}

interface RecentTask {
  task_name: string;
  codebundle_name: string;
  codebundle_slug: string;
  collection_name: string;
  collection_slug: string;
  git_updated_at: string | null;
}

// Example search queries to cycle through
const EXAMPLE_SEARCHES = [
  "My pods are stuck in CrashLoopBackOff, what should I check?",
  "How do I troubleshoot Postgres connection timeouts?",
  "Help me check if my Prometheus instance is healthy",
  "I need to diagnose issues with my AKS cluster",
  "Show me how to parse JSON output in Robot Framework"
];

const Home: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [recentCodebundles, setRecentCodebundles] = useState<RecentCodebundle[]>([]);
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([]);
  const [tagIcons, setTagIcons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  
  // Flipboard state - track which 5 items to display
  const [codebundleOffset, setCodebundleOffset] = useState(0);
  const [taskOffset, setTaskOffset] = useState(0);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to chat with the query
      navigate('/chat', { state: { initialQuery: searchQuery.trim() } });
    }
  };

  const handleTagClick = (tag: string) => {
    navigate(`/all-tasks?category=${tag}`);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, recentData, tasksData, iconsData] = await Promise.all([
          apiService.getRegistryStats(),
          apiService.getRecentCodebundles(),
          apiService.getRecentTasks(),
          apiService.getTagIcons()
        ]);
        setStats(statsData);
        setRecentCodebundles(recentData);
        setRecentTasks(tasksData);
        setTagIcons(iconsData.icons || {});
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(`Failed to load data: ${err}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Flipboard rotation - all rows flip together every 7.5 seconds
  useEffect(() => {
    if (recentCodebundles.length <= 5 && recentTasks.length <= 5) return;
    
    const interval = setInterval(() => {
      if (recentCodebundles.length > 5) {
        setCodebundleOffset(prev => {
          const next = prev + 1;
          return next >= recentCodebundles.length - 4 ? 0 : next;
        });
      }
      
      if (recentTasks.length > 5) {
        setTaskOffset(prev => {
          const next = prev + 1;
          return next >= recentTasks.length - 4 ? 0 : next;
        });
      }
    }, 7500);

    return () => clearInterval(interval);
  }, [recentCodebundles.length, recentTasks.length]);

  // Cycle through placeholder examples
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % EXAMPLE_SEARCHES.length);
    }, 3500); // Change every 3.5 seconds

    return () => clearInterval(interval);
  }, []);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    // Handle future dates or same day (could be timezone differences)
    if (diffDays < 0 || diffMs < 0) return 'Today';
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) > 1 ? 's' : ''} ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  return (
    <Box>
      {/* Hero Registry Chat Section */}
      <Box sx={{ 
        background: 'linear-gradient(180deg, #5282f1 0%, #5282f1 5%, #4a75d9 50%, #6b93f5 100%)',
        borderBottom: 'none',
        py: { xs: 6, md: 10 },
        mt: '-1px',
        position: 'relative',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 30% 40%, rgba(248,173,75,0.12) 0%, transparent 60%), radial-gradient(circle at 70% 60%, rgba(255,255,255,0.1) 0%, transparent 50%)',
          pointerEvents: 'none'
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          bottom: '-20%',
          right: '10%',
          width: '400px',
          height: '400px',
          background: 'radial-gradient(circle, rgba(248,173,75,0.15) 0%, transparent 70%)',
          borderRadius: '50%',
          pointerEvents: 'none'
        }
      }}>
        <Container maxWidth="md" sx={{ position: 'relative', zIndex: 1 }}>
          <Typography 
            variant="h1" 
            align="center" 
            sx={{ 
              mb: 1.5,
              fontWeight: 600,
              fontSize: { xs: '24px', sm: '30px', md: '36px' },
              color: 'white',
              letterSpacing: '-0.3px',
              lineHeight: 1.2
            }}
          >
            CodeCollection Registry
          </Typography>
          
          <Typography 
            variant="body1" 
            align="center" 
            sx={{ 
              mb: 3.5,
              fontSize: { xs: '14px', md: '16px' },
              fontWeight: 400,
              lineHeight: 1.5,
              color: 'rgba(255,255,255,0.90)',
              maxWidth: '750px',
              mx: 'auto'
            }}
          >
            Explore the largest open library of AI SRE tools. Describe your problem and the assistant will suggest the right automation — then run it securely in your own environment.
          </Typography>

          {/* Search Bar that routes to Registry Chat */}
          <Box component="form" onSubmit={handleSearch} sx={{ maxWidth: 700, mx: 'auto', mb: 6 }}>
            <TextField
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={EXAMPLE_SEARCHES[placeholderIndex]}
              variant="outlined"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: '#666', fontSize: 24 }} />
                  </InputAdornment>
                ),
                endAdornment: searchQuery && (
                  <InputAdornment position="end">
                    <IconButton type="submit" edge="end" sx={{ color: '#5282f1' }}>
                      <ArrowIcon />
                    </IconButton>
                  </InputAdornment>
                ),
                sx: {
                  backgroundColor: 'white',
                  fontSize: '15px',
                  borderRadius: 3,
                  py: 1.25,
                  fontWeight: 400,
                  '& fieldset': { borderColor: '#d0d0d0', borderWidth: 1.5 },
                  '&:hover fieldset': { borderColor: '#5282f1' },
                  '&.Mui-focused fieldset': { borderColor: '#5282f1', borderWidth: 1.5 },
                  '& input::placeholder': {
                    color: '#666',
                    opacity: 0.8,
                    fontSize: '15px',
                    fontStyle: 'italic'
                  }
                }
              }}
            />
          </Box>

          {/* Taxonomy bar — sleek inline row */}
          <Box sx={{
            display: 'flex',
            justifyContent: 'center',
            gap: { xs: 1.5, md: 2.5 },
            flexWrap: 'wrap',
            alignItems: 'stretch',
          }}>
            {[
              {
                icon: CollectionIcon, label: 'CodeCollections', count: stats?.collections || 0, to: '/collections',
                desc: 'Groups of bundles by provider',
                tooltip: 'CodeCollections group related CodeBundles by technology or provider — like aws-codecollection or k8s-codecollection. Each collection is backed by a Git repository maintained by the community.',
              },
              {
                icon: BundleIcon, label: 'CodeBundles', count: stats?.codebundles || 0, to: '/codebundles',
                desc: 'Scripted automation packages',
                tooltip: 'A CodeBundle is a self-contained automation package that targets a specific service or resource — like "Postgres Health" or "AKS Triage." Each bundle contains one or more executable tasks, configuration variables, and documentation.',
              },
              {
                icon: TaskIcon, label: 'Tasks', count: stats?.tasks || 0, to: '/all-tasks',
                desc: 'CLI & API actions to run',
                tooltip: 'Tasks are the runnable units inside a CodeBundle. Each task is a scripted action — CLI commands, API calls, or queries — that performs a specific operation like "Check Pod Restarts" or "Query Connection Pool." Tasks run on private runners in your environment.',
              },
              {
                icon: DocsIcon, label: 'Docs', count: null, to: '/chat',
                desc: 'Guides & references',
                tooltip: 'Documentation includes authoring guides, platform configuration references, and keyword library docs. Ask the assistant or browse directly.',
              },
            ].map((item) => (
              <Tooltip
                key={item.label}
                title={
                  <Box sx={{ p: 0.5, maxWidth: 280 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>{item.label}</Typography>
                    <Typography sx={{ fontSize: 12, lineHeight: 1.5 }}>{item.tooltip}</Typography>
                  </Box>
                }
                arrow
                placement="bottom"
                enterDelay={200}
                slotProps={{
                  tooltip: {
                    sx: {
                      bgcolor: '#1a1a2e',
                      color: 'rgba(255,255,255,0.88)',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                      borderRadius: 2,
                      px: 2,
                      py: 1.5,
                      '& .MuiTooltip-arrow': { color: '#1a1a2e' },
                    },
                  },
                }}
              >
                <Box
                  component={Link}
                  to={item.to}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    bgcolor: 'rgba(255,255,255,0.12)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    borderRadius: 2,
                    px: { xs: 1.5, md: 2 },
                    py: 1,
                    textDecoration: 'none',
                    color: 'white',
                    transition: 'all 0.2s',
                    backdropFilter: 'blur(8px)',
                    '&:hover': {
                      bgcolor: 'rgba(255,255,255,0.2)',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <item.icon sx={{ fontSize: 20, color: 'rgba(255,255,255,0.85)' }} />
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75 }}>
                      {item.count !== null && (
                        <Typography sx={{ fontSize: 18, fontWeight: 700, color: 'white', lineHeight: 1 }}>
                          {item.count}
                        </Typography>
                      )}
                      <Typography sx={{ fontSize: 13, fontWeight: 600, color: 'white', lineHeight: 1 }}>
                        {item.label}
                      </Typography>
                    </Box>
                    <Typography sx={{ fontSize: 10, color: 'rgba(255,255,255,0.7)', mt: 0.25 }}>
                      {item.desc}
                    </Typography>
                  </Box>
                </Box>
              </Tooltip>
            ))}
          </Box>
        </Container>
      </Box>

      {/* How It Works — Vertical Flow */}
      <Box sx={{ py: { xs: 4, md: 5 }, bgcolor: 'white', overflow: 'hidden' }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>

            {/* ─── ROW 1: Workspace Chat ─── */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%', justifyContent: 'center' }}>
              <Box
                sx={{
                  width: { xs: 160, md: 180 },
                  borderRadius: 3,
                  border: '2px solid #e0e4ec',
                  bgcolor: 'white',
                  boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
                  overflow: 'hidden',
                  flexShrink: 0,
                }}
              >
                <Box sx={{ bgcolor: '#5282f1', px: 1.5, py: 0.75, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.5)' }} />
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.5)' }} />
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.5)' }} />
                  <Typography sx={{ fontSize: 9, color: 'white', ml: 0.5, fontWeight: 600 }}>Workspace Chat</Typography>
                </Box>
                <Box sx={{ p: 1.25, display: 'flex', flexDirection: 'column', gap: 0.6 }}>
                  <Box sx={{ bgcolor: '#f0f2f5', borderRadius: 1.5, px: 1, py: 0.4, alignSelf: 'flex-start', maxWidth: '85%' }}>
                    <Typography sx={{ fontSize: 8, color: '#444' }}>My pods keep crashing...</Typography>
                  </Box>
                  <Box sx={{ bgcolor: '#5282f1', borderRadius: 1.5, px: 1, py: 0.4, alignSelf: 'flex-end', maxWidth: '85%' }}>
                    <Typography sx={{ fontSize: 8, color: 'white' }}>Found 3 matching tools!</Typography>
                  </Box>
                  <Box sx={{ bgcolor: '#f0f2f5', borderRadius: 1.5, px: 1, py: 0.4, alignSelf: 'flex-start', maxWidth: '85%' }}>
                    <Typography sx={{ fontSize: 8, color: '#444' }}>Check my database...</Typography>
                  </Box>
                  <Box sx={{ bgcolor: '#5282f1', borderRadius: 1.5, px: 1, py: 0.4, alignSelf: 'flex-end', maxWidth: '85%' }}>
                    <Typography sx={{ fontSize: 8, color: 'white' }}>Running health check...</Typography>
                  </Box>
                </Box>
              </Box>
              <Box sx={{ maxWidth: 260 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 700, color: '#1a1a2e', mb: 0.5 }}>
                  Chat With Your Environment
                </Typography>
                <Typography sx={{ fontSize: 12, color: 'text.secondary', lineHeight: 1.5 }}>
                  Ask questions in natural language — AI interprets real-time data from your applications, infrastructure, and services.
                </Typography>
              </Box>
            </Box>

            {/* ─── Vertical connector ─── */}
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
              <Box sx={{
                width: 3, height: 36,
                background: 'linear-gradient(180deg, #b8caf7 0%, #5282f1 100%)',
                borderRadius: 2,
                position: 'relative',
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  bottom: -5,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: 0, height: 0,
                  borderTop: '7px solid #5282f1',
                  borderLeft: '4px solid transparent',
                  borderRight: '4px solid transparent',
                },
              }} />
            </Box>

            {/* ─── ROW 2: RunWhen Platform ─── */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                px: 3,
                py: 2,
                borderRadius: 3,
                bgcolor: '#ffffff',
                boxShadow: '0 4px 24px rgba(82,130,241,0.2)',
                border: '2px solid #e0e8f5',
                animation: 'corePulse 3s ease-in-out infinite',
                '@keyframes corePulse': {
                  '0%, 100%': { boxShadow: '0 4px 24px rgba(82,130,241,0.2)' },
                  '50%': { boxShadow: '0 4px 36px rgba(82,130,241,0.35)' },
                },
              }}
            >
              <Box
                component="img"
                src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png"
                alt="RunWhen AI Assistant"
                sx={{ width: 48, height: 48, borderRadius: '50%', border: '2px solid #e0e8f5', flexShrink: 0 }}
              />
              <Box>
                <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#3a5cb8', lineHeight: 1.1 }}>
                  RunWhen Platform
                </Typography>
                <Typography sx={{ fontSize: 11, color: '#5282f1', mt: 0.25 }}>
                  Builds context from your systems and decides what to run, and when
                </Typography>
              </Box>
            </Box>

            {/* ─── Vertical connector ─── */}
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
              <Box sx={{
                width: 3, height: 36,
                background: 'linear-gradient(180deg, #5282f1 0%, #2E7D32 100%)',
                borderRadius: 2,
                position: 'relative',
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  bottom: -5,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: 0, height: 0,
                  borderTop: '7px solid #2E7D32',
                  borderLeft: '4px solid transparent',
                  borderRight: '4px solid transparent',
                },
              }} />
            </Box>

            {/* ─── ROW 3: Private Runners (Your VPC) ─── */}
            <Box
              sx={{
                border: '2px dashed #43a047',
                borderRadius: 3,
                px: 3,
                py: 2,
                bgcolor: 'rgba(46,125,50,0.03)',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                gap: 2.5,
              }}
            >
              <Typography sx={{
                position: 'absolute',
                top: -10,
                left: '50%',
                transform: 'translateX(-50%)',
                bgcolor: 'white',
                px: 1.5,
                fontSize: 9,
                fontWeight: 600,
                color: '#2E7D32',
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                whiteSpace: 'nowrap',
              }}>
                Your VPC
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {[1, 2].map((n) => (
                  <Box
                    key={n}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.75,
                      bgcolor: 'white',
                      border: '1px solid #c8e6c9',
                      borderRadius: 2,
                      px: 1.5,
                      py: 0.75,
                    }}
                  >
                    <Box sx={{
                      width: 8, height: 8, borderRadius: '50%', bgcolor: '#4caf50', flexShrink: 0,
                      boxShadow: '0 0 0 2px rgba(76,175,80,0.25)',
                      animation: 'runnerPulse 2s ease-in-out infinite',
                      animationDelay: `${n * 0.5}s`,
                      '@keyframes runnerPulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
                    }} />
                    <Typography sx={{ fontSize: 10, fontWeight: 600, color: '#2E7D32', whiteSpace: 'nowrap' }}>
                      Runner {n}
                    </Typography>
                  </Box>
                ))}
              </Box>
              <Box>
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: '#2E7D32' }}>
                  Private Runners
                </Typography>
                <Typography sx={{ fontSize: 11, color: '#558b2f', lineHeight: 1.4 }}>
                  Tasks run securely inside your environment
                </Typography>
              </Box>
            </Box>

            {/* ─── Vertical connector ─── */}
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
              <Box sx={{
                width: 3, height: 36,
                background: 'linear-gradient(180deg, #2E7D32 0%, #b8caf7 100%)',
                borderRadius: 2,
                position: 'relative',
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  bottom: -5,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: 0, height: 0,
                  borderTop: '7px solid #b8caf7',
                  borderLeft: '4px solid transparent',
                  borderRight: '4px solid transparent',
                },
              }} />
            </Box>

            {/* ─── ROW 4: Category grid fan-out ─── */}
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
              gap: 1.5,
              width: '100%',
            }}>
              {[
                { name: 'Kubernetes', tag: 'KUBERNETES', color: '#326CE5', tasks: ['Deployment Health', 'CrashLoopBackOff Triage'] },
                { name: 'AWS', tag: 'AWS', color: '#FF9900', tasks: ['IAM Audit', 'CloudWatch Alerts'] },
                { name: 'Azure', tag: 'AZURE', color: '#0078D4', tasks: ['App Service Health', 'AKS Monitoring'] },
                { name: 'Database', tag: 'POSTGRES', color: '#336791', tasks: ['Connection Health', 'Replication Lag'] },
                { name: 'Applications', tag: 'APPLICATION', color: '#7B1FA2', tasks: ['Python Troubleshoot', 'Go Services'],
                  langIcons: [
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original-wordmark.svg',
                  ],
                },
                { name: 'Cost', tag: 'COST', color: '#2E7D32', tasks: ['Find Savings', 'Idle Resources'] },
                { name: 'Observability', tag: 'PROMETHEUS', color: '#E6522C', tasks: ['Prometheus Health', 'Log Pipelines'] },
                { name: 'GCP', tag: 'GCP', color: '#4285F4', tasks: ['GKE Health', 'Cloud SQL'] },
              ].map((cat, idx) => (
                <Box
                  key={cat.name}
                  onClick={() => handleTagClick(cat.tag)}
                  sx={{
                    cursor: 'pointer',
                    p: 1.5,
                    borderRadius: 2,
                    bgcolor: 'white',
                    border: '1px solid #e8ecf2',
                    transition: 'all 0.2s',
                    '&:hover': {
                      borderColor: cat.color,
                      boxShadow: `0 2px 12px ${cat.color}22`,
                      transform: 'translateY(-2px)',
                    },
                    animation: 'fadeSlideUp 0.4s ease-out both',
                    animationDelay: `${idx * 0.06}s`,
                    '@keyframes fadeSlideUp': {
                      from: { opacity: 0, transform: 'translateY(12px)' },
                      to: { opacity: 1, transform: 'translateY(0)' },
                    },
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
                    <Box sx={{
                      width: 10, height: 10, borderRadius: '50%', bgcolor: cat.color, flexShrink: 0,
                      boxShadow: `0 0 0 3px ${cat.color}22`,
                    }} />
                    {(cat as any).langIcons ? (
                      <Box sx={{ display: 'flex', gap: 0.25 }}>
                        {(cat as any).langIcons.map((src: string, i: number) => (
                          <Box key={i} component="img" src={src} alt="" sx={{ width: 16, height: 16, flexShrink: 0 }} />
                        ))}
                      </Box>
                    ) : tagIcons[cat.tag] ? (
                      <Box component="img" src={tagIcons[cat.tag]} alt={cat.name} sx={{ width: 18, height: 18, flexShrink: 0 }} />
                    ) : null}
                    <Typography sx={{ fontSize: 12, fontWeight: 700, color: '#1a1a2e', lineHeight: 1 }}>
                      {cat.name}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.4 }}>
                    {cat.tasks.map((task) => (
                      <Chip
                        key={task}
                        label={task}
                        size="small"
                        sx={{
                          fontSize: '9px',
                          height: 20,
                          bgcolor: `${cat.color}0D`,
                          color: cat.color,
                          fontWeight: 500,
                          border: `1px solid ${cat.color}33`,
                          '& .MuiChip-label': { px: 0.75 },
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              ))}
            </Box>

          </Box>
        </Container>
      </Box>

      {/* Content Section - Two Columns */}
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' }, gap: 4 }}>
          
          {/* Left Column: Recently Updated CodeBundles */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TrendingIcon sx={{ color: '#5282f1', fontSize: 24 }} />
              <Typography 
                variant="h2" 
                sx={{ 
                  fontWeight: 600, 
                  fontSize: { xs: '18px', md: '20px' },
                  letterSpacing: '-0.2px'
                }}
              >
                Recently Updated CodeBundles
              </Typography>
            </Box>
            
            <Box 
              sx={{ 
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 2,
                minHeight: '320px',
                minWidth: 0,
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5
              }}
            >
              {recentCodebundles.slice(codebundleOffset, codebundleOffset + 5).map((cb, index) => (
                <Box
                  key={`${cb.id}-${codebundleOffset}`}
                  component={Link}
                  to={`/collections/${cb.collection_slug}/codebundles/${cb.slug}`}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    p: 1.5,
                    bgcolor: 'rgba(82, 130, 241, 0.03)',
                    borderLeft: '3px solid #5282f1',
                    textDecoration: 'none',
                    color: 'inherit',
                    transition: 'all 0.3s ease',
                    animation: 'flipCard 1.2s ease-in-out',
                    animationDelay: `${index * 0.3}s`,
                    transformStyle: 'preserve-3d',
                    '@keyframes flipCard': {
                      '0%': {
                        transform: 'perspective(800px) rotateX(0deg)',
                        opacity: 1,
                      },
                      '50%': {
                        transform: 'perspective(800px) rotateX(90deg)',
                        opacity: 0.3,
                      },
                      '100%': {
                        transform: 'perspective(800px) rotateX(0deg)',
                        opacity: 1,
                      }
                    },
                    '&:hover': {
                      bgcolor: 'rgba(82, 130, 241, 0.08)',
                      transform: 'translateX(4px)',
                    }
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                    <Box
                      sx={{ 
                        fontSize: '14px',
                        fontWeight: 500,
                        mb: 0.25,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontFamily: 'monospace'
                      }}
                    >
                      {cb.display_name || cb.name}
                    </Box>
                    <Box
                      sx={{ 
                        fontSize: '11px',
                        color: 'text.secondary',
                        fontFamily: 'monospace'
                      }}
                    >
                      {cb.collection_name.replace('rw-', '').replace('-codecollection', '').toUpperCase()}
                    </Box>
                  </Box>
                  <Box sx={{ textAlign: 'right' }}>
                    <Box
                      sx={{ 
                        fontSize: '13px',
                        fontWeight: 600,
                        fontFamily: 'monospace',
                        color: '#5282f1',
                        letterSpacing: '0.5px'
                      }}
                    >
                      {cb.git_updated_at ? new Date(cb.git_updated_at).toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        year: 'numeric'
                      }).toUpperCase() : 'N/A'}
                    </Box>
                    <Box
                      sx={{ 
                        fontSize: '11px',
                        fontFamily: 'monospace',
                        color: 'text.secondary'
                      }}
                    >
                      {cb.git_updated_at ? new Date(cb.git_updated_at).toLocaleTimeString('en-US', { 
                        hour: '2-digit', 
                        minute: '2-digit',
                        hour12: false 
                      }) : ''}
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>

          {/* Right Column: Recently Updated Tasks */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TrendingIcon sx={{ color: '#5282f1', fontSize: 24 }} />
              <Typography 
                variant="h2" 
                sx={{ 
                  fontWeight: 600, 
                  fontSize: { xs: '18px', md: '20px' },
                  letterSpacing: '-0.2px'
                }}
              >
                Recently Updated Tasks
              </Typography>
            </Box>
            
            <Box 
              sx={{ 
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 2,
                minHeight: '320px',
                minWidth: 0,
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5
              }}
            >
              {recentTasks.slice(taskOffset, taskOffset + 5).map((task, index) => (
                <Box
                  key={`${task.codebundle_slug}-${task.task_name}-${taskOffset}`}
                  component={Link}
                  to={`/collections/${task.collection_slug}/codebundles/${task.codebundle_slug}`}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    p: 1.5,
                    bgcolor: 'rgba(82, 130, 241, 0.03)',
                    borderLeft: '3px solid #5282f1',
                    textDecoration: 'none',
                    color: 'inherit',
                    transition: 'all 0.3s ease',
                    animation: 'flipCard 1.2s ease-in-out',
                    animationDelay: `${index * 0.3}s`,
                    transformStyle: 'preserve-3d',
                    '@keyframes flipCard': {
                      '0%': {
                        transform: 'perspective(800px) rotateX(0deg)',
                        opacity: 1,
                      },
                      '50%': {
                        transform: 'perspective(800px) rotateX(90deg)',
                        opacity: 0.3,
                      },
                      '100%': {
                        transform: 'perspective(800px) rotateX(0deg)',
                        opacity: 1,
                      }
                    },
                    '&:hover': {
                      bgcolor: 'rgba(82, 130, 241, 0.08)',
                      transform: 'translateX(4px)',
                    }
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                    <Box
                      sx={{ 
                        fontSize: '14px',
                        fontWeight: 500,
                        mb: 0.25,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontFamily: 'monospace'
                      }}
                    >
                      {task.task_name}
                    </Box>
                    <Box
                      sx={{ 
                        fontSize: '11px',
                        color: 'text.secondary',
                        fontFamily: 'monospace'
                      }}
                    >
                      {task.codebundle_name.substring(0, 40)}
                    </Box>
                  </Box>
                  <Box sx={{ textAlign: 'right' }}>
                    <Box
                      sx={{ 
                        fontSize: '13px',
                        fontWeight: 600,
                        fontFamily: 'monospace',
                        color: '#5282f1',
                        letterSpacing: '0.5px'
                      }}
                    >
                      {task.git_updated_at ? new Date(task.git_updated_at).toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        year: 'numeric'
                      }).toUpperCase() : 'N/A'}
                    </Box>
                    <Box
                      sx={{ 
                        fontSize: '11px',
                        fontFamily: 'monospace',
                        color: 'text.secondary'
                      }}
                    >
                      {task.git_updated_at ? new Date(task.git_updated_at).toLocaleTimeString('en-US', { 
                        hour: '2-digit', 
                        minute: '2-digit',
                        hour12: false 
                      }) : ''}
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        {/* Browse All / Contribute CTAs */}
        <Box sx={{ 
          display: 'flex', 
          gap: 2, 
          justifyContent: 'center',
          flexWrap: 'wrap',
          mt: 4
        }}>
          <Button
            component={Link}
            to="/codebundles"
            variant="contained"
            sx={{
              textTransform: 'none',
              fontSize: '15px',
              fontWeight: 600,
              backgroundColor: '#5282f1',
              color: 'white',
              px: 4,
              py: 1.25,
              '&:hover': {
                backgroundColor: '#3a5cb8',
                color: 'white'
              }
            }}
          >
            Browse All CodeBundles
          </Button>
          <Button
            variant="outlined"
            startIcon={<MoneyIcon />}
            href="https://docs.runwhen.com/public/v/runwhen-authors"
            target="_blank"
            rel="noopener"
            sx={{
              borderColor: '#f5af19',
              color: '#e67e00',
              fontSize: '15px',
              fontWeight: 600,
              px: 4,
              py: 1.25,
              textTransform: 'none',
              '&:hover': {
                borderColor: '#e67e00',
                backgroundColor: 'rgba(245, 175, 25, 0.08)',
              },
            }}
          >
            Get Paid to Contribute
          </Button>
        </Box>
      </Container>

      {/* Task Growth Chart */}
      <Box sx={{ bgcolor: 'background.default', py: 6 }}>
        <Container maxWidth="lg">
          <TaskGrowthChart />
        </Container>
      </Box>
    </Box>
  );
};

export default Home;
