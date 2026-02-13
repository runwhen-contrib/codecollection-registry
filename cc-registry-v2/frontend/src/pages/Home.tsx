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
  ChatBubbleOutline as ChatIcon,
  SettingsSuggestOutlined as RunnerIcon,
  CheckCircleOutline as ResolveIcon,
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
    }, 3500);
    return () => clearInterval(interval);

  // Category carousel — 4 pages of 4, cycle every 5s
  }, []);
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveCatPage((prev) => (prev + 1) % 4);
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
          : 'linear-gradient(180deg, #5282f1 0%, #5282f1 5%, #4a75d9 50%, #6b93f5 100%)',
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

          {/* ─── Flow timeline ─── */}
          <Box sx={{ position: 'relative', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', mb: { xs: 3, md: 4 }, px: 2 }}>
            {/* Connecting line */}
            <Box sx={{
              position: 'absolute',
              top: 20,
              left: '12%',
              right: '12%',
              height: 2,
              background: '#5282f1',
              borderRadius: 1,
              zIndex: 0,
            }} />
            {/* Steps */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: 700, position: 'relative', zIndex: 1 }}>
              {[
                { label: 'Ask', color: '#5282f1', muiIcon: ChatIcon },
                { label: 'Run Tools', color: '#5282f1', muiIcon: RunnerIcon },
                { label: 'Collect Insights', color: '#5282f1', img: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png' },
                { label: 'Resolve', color: '#5282f1', muiIcon: ResolveIcon },
              ].map((step) => (
                <Box key={step.label} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.75 }}>
                  <Box sx={{
                    width: 40, height: 40, borderRadius: '50%', bgcolor: 'background.paper',
                    border: `2.5px solid ${step.color}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: (t: any) => `0 0 0 4px ${t.palette.background.default}, 0 2px 8px ${step.color}20`,
                  }}>
                    {step.img ? (
                      <Box component="img" src={step.img} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
                    ) : step.muiIcon ? (
                      <step.muiIcon sx={{ fontSize: 20, color: step.color }} />
                    ) : null}
                  </Box>
                  <Typography sx={{ fontSize: 12, fontWeight: 600, color: step.color, textAlign: 'center', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
                    {step.label}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>

          {/* ─── Category Carousel ─── */}
          {(() => {
            const allCategories = [
              // Page 1 — Core platforms
              { name: 'Kubernetes', tag: 'KUBERNETES', color: '#326CE5', tasks: ['Inspect Deployment Health', 'Triage CrashLoopBackOff Pods', 'Check Namespace Resources', 'Audit RBAC Policies'] },
              { name: 'AWS', tag: 'AWS', color: '#FF9900', tasks: ['Audit IAM Policies', 'Check CloudWatch Alerts', 'Monitor EC2 Health', 'Inspect S3 Buckets'] },
              { name: 'Azure', tag: 'AZURE', color: '#0078D4', tasks: ['Check App Service Health', 'Monitor AKS Clusters', 'Audit Key Vault', 'Inspect Azure SQL'] },
              { name: 'GCP', tag: 'GCP', color: '#4285F4', tasks: ['GKE Cluster Health', 'Cloud SQL Monitoring', 'IAM Audit', 'Load Balancer Check'] },
              // Page 2 — Operations
              { name: 'Database', tag: 'POSTGRES', color: '#336791', tasks: ['Check Connection Health', 'Monitor Replication Lag', 'Query Connection Pool', 'Inspect Slow Queries'] },
              { name: 'Cost Optimization', tag: 'COST', color: '#2E7D32', tasks: ['Find Cost Savings', 'Identify Idle Resources', 'Right-Size Instances', 'Budget Alerts'] },
              { name: 'Observability', tag: 'PROMETHEUS', color: '#E6522C', tasks: ['Verify Prometheus Health', 'Check Log Pipelines', 'Alert Rule Audit', 'Dashboard Health'] },
              { name: 'Applications', tag: 'APPLICATION', color: '#7B1FA2', tasks: ['Troubleshoot Python Apps', 'Inspect Go Services', 'Check Runtime Health', 'Debug API Latency'],
                langIcons: [
                  'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg',
                  'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original-wordmark.svg',
                ],
              },
              // Page 3 — DevOps & Engineering
              { name: 'CI/CD Pipelines', tag: 'GITHUB', color: '#8b949e', tasks: ['GitHub Actions Health', 'Build Failure Triage', 'GitLab Pipeline Status', 'Artifact Registry Audit'] },
              { name: 'GitOps', tag: 'ARGOCD', color: '#EF7B4D', tasks: ['ArgoCD Sync Health', 'FluxCD Drift Detection', 'Deployment Reconciliation', 'Helm Release Status'] },
              { name: 'OpenShift', tag: 'OPENSHIFT', color: '#EE0000', tasks: ['Cluster Health', 'Route Monitoring', 'Build Config Audit', 'Operator Status'] },
              { name: 'Cloud Governance', tag: 'CLOUDCUSTODIAN', color: '#1B9AAA', tasks: ['Policy Compliance', 'Tag Enforcement', 'Resource Rules Audit', 'Cost Policy Check'] },
              // Page 4 — Security, Networking & Managed K8s
              { name: 'Security & Certs', tag: 'CERT-MANAGER', color: '#D4A017', tasks: ['Certificate Expiry Check', 'Vault Secrets Audit', 'TLS Configuration', 'Issuer Health'] },
              { name: 'Networking', tag: 'HTTP', color: '#0097A7', tasks: ['Ingress Health Check', 'DNS Resolution Audit', 'API Gateway Status', 'Endpoint Latency'] },
              { name: 'Managed Kubernetes', tag: 'EKS', color: '#FF9900', tasks: ['EKS Node Health', 'AKS Upgrade Status', 'GKE Autopilot Check', 'Cluster Add-ons Audit'] },
              { name: 'Monitoring Platforms', tag: 'DATADOG', color: '#632CA6', tasks: ['Datadog Agent Health', 'Sysdig Monitor Status', 'Grafana Dashboard Check', 'Alert Channel Audit'] },
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
                          bgcolor: page === activeCatPage ? '#5282f1' : '#d0d8e8',
                          cursor: 'pointer',
                          transition: 'all 0.3s',
                        }}
                    />
                  ))}
                  </Box>
                  <Typography sx={{ fontSize: 15, fontWeight: 600, color: 'text.secondary', mt: 0.25 }}>
                    {['Platforms', 'Operations', 'DevOps & Engineering', 'Security & Networking'][activeCatPage]}
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
                      {cb.collection_name.replace('rw-', '').replace('-codecollection', '').toUpperCase()}
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
            to="/codebundles"
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
