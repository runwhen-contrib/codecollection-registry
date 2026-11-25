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
  SettingsSuggestOutlined as RunnerIcon,
  CheckCircleOutline as ResolveIcon,
  AccountTreeOutlined as ContextIcon,
  NotificationsActiveOutlined as EventIcon,
  AutoFixHighOutlined as SkillLoopIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { Link, useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import TaskGrowthChart from '../components/TaskGrowthChart';

interface RegistryStats {
  collections: number;
  codebundles: number;
  tasks: number;
  slis: number;
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
  "How do I check replication lag on my Patroni cluster?"
];

const Home: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
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
  
  // Category carousel state
  const [activeCatPage, setActiveCatPage] = useState(0);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to chat with the query
      navigate('/chat', { state: { initialQuery: searchQuery.trim() } });
    }
  };

  const handleTagClick = (tag: string) => {
    navigate(`/all-tasks?support_tags=${encodeURIComponent(tag)}`);
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
    }, 3500);
    return () => clearInterval(interval);

  // Category carousel — 2 pages of 4, cycle every 5s
  }, []);
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveCatPage((prev) => (prev + 1) % 2);
    }, 5000);
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
        background: isDark
          ? 'linear-gradient(180deg, #1a1a2e 0%, #1a1a2e 5%, #16163a 50%, #1e2a4a 100%)'
          : 'linear-gradient(180deg, #2F80ED 0%, #2F80ED 5%, #1a5fc9 50%, #5b9bf5 100%)',
        borderBottom: 'none',
        pt: { xs: 12, md: 16 },
        pb: { xs: 6, md: 10 },
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
            RunWhen Skills Registry
          </Typography>

          {/* Hero pill badges */}
          <Box sx={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 1, mb: 2.5 }}>
            {[
              { label: 'Open-Source Public Registry', accent: false, icon: CollectionIcon },
              { label: 'Day-0 Observability', accent: false, icon: ContextIcon },
              { label: 'Self-Improving Agent Loop', accent: true, icon: SkillLoopIcon },
            ].map((pill) => (
              <Box
                key={pill.label}
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.75,
                  px: 1.5,
                  py: 0.5,
                  borderRadius: '999px',
                  bgcolor: pill.accent ? 'rgba(248,173,75,0.16)' : 'rgba(255,255,255,0.12)',
                  border: '1px solid',
                  borderColor: pill.accent ? 'rgba(248,173,75,0.65)' : 'rgba(255,255,255,0.28)',
                  backdropFilter: 'blur(8px)',
                  color: pill.accent ? '#ffd79a' : 'rgba(255,255,255,0.92)',
                  fontSize: 12,
                  fontWeight: 600,
                  letterSpacing: '0.01em',
                  whiteSpace: 'nowrap',
                }}
              >
                <pill.icon sx={{ fontSize: 14, color: pill.accent ? '#f8ad4b' : 'rgba(255,255,255,0.75)' }} />
                {pill.label}
              </Box>
            ))}
          </Box>

          <Typography 
            variant="body1" 
            align="center" 
            sx={{ 
              mb: 3.5,
              fontSize: { xs: '14px', md: '16px' },
              fontWeight: 400,
              lineHeight: 1.5,
              color: 'rgba(255,255,255,0.90)',
              maxWidth: '820px',
              mx: 'auto'
            }}
          >
            The public catalog of open-source Plugins, Skills, and Tasks built for production operations. Give your Agents Day-0 observability out of the box — so they can automatically investigate INC/CRQ tickets and alerts, deliver root-cause facts before an engineer is paged, and continuously author new private Skills as your environment evolves.
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
                    <SearchIcon sx={{ color: 'text.secondary', fontSize: 24 }} />
                  </InputAdornment>
                ),
                endAdornment: searchQuery && (
                  <InputAdornment position="end">
                    <IconButton type="submit" edge="end" sx={{ color: 'primary.main' }}>
                      <ArrowIcon />
                    </IconButton>
                  </InputAdornment>
                ),
                sx: {
                  backgroundColor: 'background.paper',
                  color: 'text.primary',
                  fontSize: '15px',
                  borderRadius: 3,
                  py: 1.25,
                  fontWeight: 400,
                  '& fieldset': { borderColor: 'divider', borderWidth: 1.5 },
                  '&:hover fieldset': { borderColor: 'primary.main' },
                  '&.Mui-focused fieldset': { borderColor: 'primary.main', borderWidth: 1.5 },
                  '& input::placeholder': {
                    color: 'text.secondary',
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
                icon: CollectionIcon, label: 'Plugins', count: stats?.collections || 0, to: '/plugins',
                desc: 'Integration & skill packages by platform',
                tooltip: 'Plugins bundle a platform integration (resource types, facets, credentials) with diagnostic and remediation Skills — such as kubernetes, aws, azure, gcp, and postgres.',
              },
              {
                icon: BundleIcon, label: 'Skills', count: stats?.codebundles || 0, to: '/skills',
                desc: 'Diagnostic & remediation packages',
                tooltip: 'A Skill is a reusable package targeting a specific service or resource — like k8s-postgres-operator-health or azure-aks-health — containing executable Tasks, settings, inputs, and operational guidance.',
              },
              {
                icon: TaskIcon, label: 'Tasks', count: stats?.tasks || 0, to: '/all-tasks',
                desc: 'Executable actions inside a Skill',
                tooltip: 'Tasks are the runnable units inside a Skill. Each Task is a scripted action — CLI commands, API calls, or queries — that performs a specific operation like "Check Pod Restarts" or "Query Connection Pool." Tasks are either Runbooks (run on demand in response to an event) or Monitors (run on a schedule, emit a 0-1 health score). They execute on private runners in your environment.',
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
                    <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5, color: '#fff' }}>{item.label}</Typography>
                    <Typography sx={{ fontSize: 12, lineHeight: 1.5, color: 'rgba(255,255,255,0.95)' }}>{item.tooltip}</Typography>
                  </Box>
                }
                arrow
                placement="bottom"
                enterDelay={200}
                slotProps={{
                  tooltip: {
                    sx: {
                      bgcolor: '#1a1a2e',
                      color: 'rgba(255,255,255,0.95)',
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

      {/* How It Works — Compact pipeline + Category Carousel */}
      <Box sx={{ py: { xs: 3, md: 4 }, bgcolor: 'background.default', overflow: 'hidden' }}>
        <Container maxWidth="lg">

          {/* ─── Option A: 5-step Day-0 → Event Triage → Self-Improving Skill Loop ─── */}
          <Box sx={{ mb: { xs: 3, md: 4 } }}>
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(5, 1fr)' },
              gap: 1.5,
            }}>
              {[
                {
                  num: '1',
                  kicker: 'Day-0 Context',
                  title: 'Discover & Map',
                  icon: ContextIcon,
                  desc: 'Plugins index cloud, Kubernetes, and database resources + dependencies automatically on Day 0.',
                  accent: false,
                },
                {
                  num: '2',
                  kicker: 'Event or Ask',
                  title: 'Ticket, Alert, or Chat',
                  icon: EventIcon,
                  desc: 'Triggered automatically by INC/CRQ tickets, PagerDuty/Slack alerts, schedules, or human-in-the-loop.',
                  accent: false,
                },
                {
                  num: '3',
                  kicker: 'First-Pass Run',
                  title: 'Run Public & Private Skills',
                  icon: RunnerIcon,
                  desc: "Agents execute public Registry Skills alongside your team's private Skills on your own runners.",
                  accent: false,
                },
                {
                  num: '4',
                  kicker: 'Fast MTTR',
                  title: 'Context & Next Steps',
                  icon: ResolveIcon,
                  desc: 'Root-cause facts, dry-run remediations, code PRs, or smart routing land directly on the ticket.',
                  accent: false,
                },
                {
                  num: '5',
                  kicker: 'Self-Improving',
                  title: 'Build New Skills',
                  icon: SkillLoopIcon,
                  desc: 'Spot a coverage gap? Agents draft, test, and review new private Skills in the Skill Building Harness.',
                  accent: true,
                },
              ].map((step) => (
                <Box
                  key={step.num}
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    p: 1.75,
                    borderRadius: 2,
                    bgcolor: 'background.paper',
                    border: '1px solid',
                    borderColor: step.accent ? 'rgba(248,173,75,0.5)' : 'divider',
                    boxShadow: step.accent ? '0 2px 14px rgba(248,173,75,0.14)' : 'none',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      transform: 'translateY(-2px)',
                      borderColor: step.accent ? '#f8ad4b' : 'primary.main',
                      boxShadow: step.accent
                        ? '0 4px 20px rgba(248,173,75,0.22)'
                        : '0 4px 16px rgba(47,128,237,0.16)',
                    },
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Box sx={{
                      width: 32,
                      height: 32,
                      borderRadius: 1.5,
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      bgcolor: step.accent
                        ? 'rgba(248,173,75,0.14)'
                        : isDark ? 'rgba(47,128,237,0.2)' : 'rgba(47,128,237,0.1)',
                    }}>
                      <step.icon sx={{ fontSize: 18, color: step.accent ? '#f8ad4b' : '#2F80ED' }} />
                    </Box>
                    <Typography sx={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      lineHeight: 1.2,
                      color: step.accent
                        ? (isDark ? '#f8ad4b' : '#a8681a')
                        : 'text.secondary',
                    }}>
                      {step.num} · {step.kicker}
                    </Typography>
                  </Box>
                  <Typography sx={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'text.primary',
                    mb: 0.5,
                    lineHeight: 1.25,
                  }}>
                    {step.title}
                  </Typography>
                  <Typography sx={{ fontSize: 12, color: 'text.secondary', lineHeight: 1.45 }}>
                    {step.desc}
                  </Typography>
                </Box>
              ))}
            </Box>

            {/* Compact loop callout bar */}
            <Box sx={{
              mt: 1.5,
              display: 'flex',
              flexDirection: { xs: 'column', md: 'row' },
              alignItems: { xs: 'flex-start', md: 'center' },
              justifyContent: 'space-between',
              gap: 1.5,
              px: { xs: 2, md: 2.5 },
              py: 1.5,
              borderRadius: 2,
              bgcolor: isDark ? 'rgba(248,173,75,0.08)' : 'rgba(248,173,75,0.07)',
              border: '1px solid',
              borderColor: isDark ? 'rgba(248,173,75,0.28)' : 'rgba(248,173,75,0.35)',
            }}>
              <Typography sx={{ fontSize: 12, lineHeight: 1.5, color: 'text.primary', minWidth: 0 }}>
                <Box component="span" sx={{ color: '#f8ad4b', fontWeight: 700, mr: 0.5 }}>↻</Box>
                <Box component="span" sx={{ fontWeight: 600 }}>The Agent Skill-Building Loop:</Box>{' '}
                Every ticket teaches your workspace what to automate next — combining public Registry Skills with custom private Skills.
              </Typography>
              <Box
                component="a"
                href="https://www.runwhen.com"
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  px: 1.5,
                  py: 0.5,
                  borderRadius: '999px',
                  flexShrink: 0,
                  border: '1px solid',
                  borderColor: isDark ? 'rgba(248,173,75,0.45)' : 'rgba(248,173,75,0.55)',
                  bgcolor: isDark ? 'rgba(248,173,75,0.1)' : '#fff',
                  color: isDark ? '#f8ad4b' : '#a8681a',
                  fontSize: 12,
                  fontWeight: 600,
                  textDecoration: 'none',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.2s',
                  '&:hover': {
                    bgcolor: isDark ? 'rgba(248,173,75,0.18)' : 'rgba(248,173,75,0.12)',
                    borderColor: '#f8ad4b',
                  },
                }}
              >
                Works standalone (CLI · Claude · MCP) or on RunWhen Platform →
              </Box>
            </Box>
          </Box>

          {/* ─── Category Carousel ─── */}
          {(() => {
            const allCategories = [
              // Page 1 — Core Platforms
              {
                name: 'Kubernetes',
                tag: 'KUBERNETES',
                color: '#326CE5',
                tasks: ['Rollout & Pod Status', 'Node Conditions & Capacity', 'PVC & Storage Health', 'Namespace Warning Events'],
              },
              {
                name: 'PostgreSQL',
                tag: 'POSTGRES',
                color: '#336791',
                tasks: ['Patroni Leader & Lag', 'Blocking Lock Chains', 'Connection Saturation', 'Long-Running Queries'],
              },
              {
                name: 'Azure',
                tag: 'AZURE',
                color: '#0078D4',
                tasks: ['AKS Cluster & Node Pools', 'Resource Health Status', 'Key Vault Secret Expiry', 'Activity Log Failures'],
              },
              {
                name: 'AWS & GCP',
                tag: 'DISCOVERY',
                color: '#FF9900',
                tasks: ['AWS Lambda Health & Errors', 'GCP Cloud Functions State', 'GCS Bucket IAM & Lifecycle', 'Multi-Region Account Discovery'],
              },
              // Page 2 — Workloads, Operators & Observability
              {
                name: 'Observability',
                tag: 'PROMETHEUS',
                color: '#E6522C',
                tasks: ['Prometheus Target & TSDB Health', 'Loki Ingestion & Ring Status', 'Jaeger Trace Pipeline', 'OpenTelemetry Collector'],
              },
              {
                name: 'GitOps & Delivery',
                tag: 'ARGOCD',
                color: '#EF7B4D',
                tasks: ['Argo CD App Sync & Health', 'Flux Kustomization & Helm', 'Suspend & Resume Reconcile', 'Jenkins Queue & Executors'],
              },
              {
                name: 'Security & Certificates',
                tag: 'CERT-MANAGER',
                color: '#D4A017',
                tasks: ['Certificate Expiry & Issuers', 'Vault Sealed & HA Status', 'Key Vault Access Policies', 'RBAC Permission Checks'],
              },
              {
                name: 'Resilience & Remediation',
                tag: 'REMEDIATION',
                color: '#7B1FA2',
                tasks: ['Workload Rollback & Restart', 'HPA Bounds & Scaling', 'Patroni Switchover & Reinit', 'Controlled Chaos Experiments'],
              },
            ];
            const pageSize = 4;
            const totalPages = Math.ceil(allCategories.length / pageSize);
            const visibleCats = allCategories.slice(activeCatPage * pageSize, activeCatPage * pageSize + pageSize);

            return (
              <Box>
                <Box sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
                  gap: 2,
                }}>
                  {visibleCats.map((cat) => (
                    <Box
                      key={cat.name}
                      onClick={() => handleTagClick(cat.tag)}
                      sx={{
                        cursor: 'pointer',
                        p: 2.5,
                        borderRadius: 3,
                        bgcolor: 'background.paper',
                        border: '1px solid',
                        borderColor: 'divider',
                        transition: 'all 0.4s ease',
                        animation: 'catFadeIn 0.5s ease-out both',
                        '@keyframes catFadeIn': {
                          from: { opacity: 0, transform: 'scale(0.96)' },
                          to: { opacity: 1, transform: 'scale(1)' },
                        },
                        '&:hover': {
                          borderColor: cat.color,
                          boxShadow: `0 4px 20px ${cat.color}20`,
                          transform: 'translateY(-3px)',
                        },
                      }}
                    >
                      {/* Header: icon + name */}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                        <Box sx={{
                          width: 36, height: 36, borderRadius: 2, bgcolor: isDark ? `${cat.color}25` : `${cat.color}12`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                        }}>
                          {(cat as any).langIcons ? (
                            <Box sx={{ display: 'flex', gap: 0.25 }}>
                              {(cat as any).langIcons.map((src: string, i: number) => (
                                <Box key={i} component="img" src={src} alt="" sx={{ width: 18, height: 18, filter: isDark ? 'brightness(1.5)' : 'none' }} />
                              ))}
                            </Box>
                          ) : tagIcons[cat.tag] ? (
                            <Box component="img" src={tagIcons[cat.tag]} alt={cat.name} sx={{ width: 22, height: 22, filter: isDark ? 'brightness(1.5)' : 'none' }} />
                          ) : (
                            <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: cat.color }} />
                          )}
                        </Box>
                        <Typography sx={{ fontSize: 17, fontWeight: 700, color: 'text.primary' }}>
                          {cat.name}
                        </Typography>
                      </Box>
                      {/* Task chips */}
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                        {cat.tasks.map((task) => (
                          <Chip
                            key={task}
                            label={task}
                            size="small"
                            sx={{
                              fontSize: '12px',
                              height: 28,
                              bgcolor: `${cat.color}0A`,
                              color: cat.color,
                              fontWeight: 500,
                              border: `1px solid ${cat.color}25`,
                              '& .MuiChip-label': { px: 1 },
                            }}
                          />
                        ))}
                      </Box>
                    </Box>
                  ))}
                </Box>
                {/* Page dots + label */}
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.75, mt: 2 }}>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    {Array.from({ length: totalPages }, (_, page) => (
                      <Box
                        key={page}
                        onClick={() => setActiveCatPage(page)}
                        sx={{
                          width: page === activeCatPage ? 24 : 8,
                          height: 8,
                          borderRadius: 4,
                          bgcolor: page === activeCatPage ? '#2F80ED' : '#e2e8f0',
                          cursor: 'pointer',
                          transition: 'all 0.3s',
                        }}
                    />
                  ))}
                  </Box>
                  <Typography sx={{ fontSize: 15, fontWeight: 600, color: 'text.secondary', mt: 0.25 }}>
                    {['Core Platforms', 'Workloads, Operators & Observability'][activeCatPage]}
                  </Typography>
                </Box>
              </Box>
            );
          })()}

        </Container>
      </Box>

      {/* Content Section - Two Columns */}
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' }, gap: 4 }}>
          
          {/* Left Column: Recently Updated Skills */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TrendingIcon sx={{ color: '#2F80ED', fontSize: 24 }} />
              <Typography 
                variant="h2" 
                sx={{ 
                  fontWeight: 600, 
                  fontSize: { xs: '18px', md: '20px' },
                  letterSpacing: '-0.2px'
                }}
              >
                Recently Updated Skills
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
                  to={`/plugins/${cb.collection_slug}/skills/${cb.slug}`}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    p: 1.5,
                    bgcolor: (t: any) => t.palette.mode === 'light' ? 'rgba(82,130,241,0.03)' : 'rgba(82,130,241,0.06)',
                    borderLeft: '3px solid',
                    borderLeftColor: 'primary.main',
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
                      bgcolor: (t: any) => t.palette.mode === 'light' ? 'rgba(82,130,241,0.08)' : 'rgba(82,130,241,0.12)',
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
                      {cb.collection_name.replace(/^RunWhen\s+/i, '')}
                    </Box>
                  </Box>
                  <Box sx={{ textAlign: 'right' }}>
                    <Box
                      sx={{ 
                        fontSize: '13px',
                        fontWeight: 600,
                        fontFamily: 'monospace',
                        color: 'primary.main',
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
              <TrendingIcon sx={{ color: '#2F80ED', fontSize: 24 }} />
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
                  to={`/plugins/${task.collection_slug}/skills/${task.codebundle_slug}`}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    p: 1.5,
                    bgcolor: (t: any) => t.palette.mode === 'light' ? 'rgba(82,130,241,0.03)' : 'rgba(82,130,241,0.06)',
                    borderLeft: '3px solid',
                    borderLeftColor: 'primary.main',
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
                      bgcolor: (t: any) => t.palette.mode === 'light' ? 'rgba(82,130,241,0.08)' : 'rgba(82,130,241,0.12)',
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
                        color: 'primary.main',
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
            to="/skills"
            variant="contained"
            sx={{
              textTransform: 'none',
              fontSize: '15px',
              fontWeight: 600,
              backgroundColor: 'primary.main',
              color: 'white',
              px: 4,
              py: 1.25,
              '&:hover': {
                backgroundColor: 'primary.dark',
                color: 'white'
              }
            }}
          >
            Browse All Skills
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
