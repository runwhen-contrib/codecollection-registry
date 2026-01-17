import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CardActionArea,
  CircularProgress,
  Alert,
  Button,
  Chip,
  TextField,
  InputAdornment,
  IconButton,
} from '@mui/material';
import { 
  Search as SearchIcon,
  TrendingUp as TrendingIcon,
  MonetizationOn as MoneyIcon,
  ArrowForward as ArrowIcon,
} from '@mui/icons-material';
import { Link, useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';

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

// Featured category names to display on homepage
const FEATURED_CATEGORIES = ['KUBERNETES', 'GKE', 'AKS', 'EKS', 'AWS', 'AZURE', 'GCP', 'POSTGRES'];

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
  const [tagIcons, setTagIcons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

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
        const [statsData, recentData, iconsData] = await Promise.all([
          apiService.getRegistryStats(),
          apiService.getRecentCodebundles(),
          apiService.getTagIcons()
        ]);
        setStats(statsData);
        setRecentCodebundles(recentData);
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

  // Cycle through placeholder examples
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % EXAMPLE_SEARCHES.length);
    }, 3500); // Change every 3.5 seconds

    return () => clearInterval(interval);
  }, []);

  // Build featured categories from fetched tag icons
  const featuredCategories = FEATURED_CATEGORIES.map(name => ({
    name,
    icon: tagIcons[name] || tagIcons[name.toUpperCase()] || ''
  }));

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
            Ask Eager Edgar to help explore CodeBundles, documentation, and authoring guidelines. Get assistance with troubleshooting tasks, SLIs, and automation workflows across the CodeCollection ecosystem.
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

          {/* Stats Bar - Now inside hero */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            gap: { xs: 4, md: 8 },
            flexWrap: 'wrap'
          }}>
            <Box 
              component={Link}
              to="/codebundles"
              sx={{ 
                textAlign: 'center',
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)'
                }
              }}
            >
              <Typography 
                variant="h4" 
                sx={{ 
                  fontWeight: 700, 
                  color: 'white', 
                  mb: 0.5,
                  fontSize: { xs: '20px', md: '24px' }
                }}
              >
                {stats?.codebundles || 0}
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  color: 'rgba(255,255,255,0.88)',
                  fontSize: '12px',
                  fontWeight: 500,
                  letterSpacing: '0.3px'
                }}
              >
                CodeBundles
              </Typography>
            </Box>
            <Box 
              component={Link}
              to="/all-tasks"
              sx={{ 
                textAlign: 'center',
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)'
                }
              }}
            >
              <Typography 
                variant="h4" 
                sx={{ 
                  fontWeight: 700, 
                  color: 'white', 
                  mb: 0.5,
                  fontSize: { xs: '20px', md: '24px' }
                }}
              >
                {stats?.tasks || 0}
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  color: 'rgba(255,255,255,0.88)',
                  fontSize: '12px',
                  fontWeight: 500,
                  letterSpacing: '0.3px'
                }}
              >
                Tasks
              </Typography>
            </Box>
            <Box 
              component={Link}
              to="/collections"
              sx={{ 
                textAlign: 'center',
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)'
                }
              }}
            >
              <Typography 
                variant="h4" 
                sx={{ 
                  fontWeight: 700, 
                  color: 'white', 
                  mb: 0.5,
                  fontSize: { xs: '20px', md: '24px' }
                }}
              >
                {stats?.collections || 0}
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  color: 'rgba(255,255,255,0.88)',
                  fontSize: '12px',
                  fontWeight: 500,
                  letterSpacing: '0.3px'
                }}
              >
                Collections
              </Typography>
            </Box>
          </Box>
        </Container>
      </Box>

      {/* Featured Categories Section */}
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Typography 
          variant="h2" 
          sx={{ 
            mb: 3, 
            textAlign: 'center', 
            fontWeight: 600, 
            fontSize: { xs: '20px', md: '24px' },
            letterSpacing: '-0.2px'
          }}
        >
          Featured Categories
        </Typography>
        
        <Box sx={{ 
          display: 'grid',
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', md: 'repeat(4, 1fr)', lg: 'repeat(5, 1fr)' },
          gap: 2,
          mb: 2
        }}>
          {featuredCategories.map((category) => (
            <Card
              key={category.name}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 100,
                textAlign: 'center',
                border: '1px solid #e0e0e0',
                '&:hover': {
                  boxShadow: 3,
                  borderColor: '#5282f1',
                },
                transition: 'all 0.2s'
              }}
            >
              <CardActionArea
                onClick={() => handleTagClick(category.name)}
                sx={{ p: 1.5, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}
              >
                {category.icon && (
                  <Box
                    component="img"
                    src={category.icon}
                    alt={`${category.name} icon`}
                    sx={{
                      width: 50,
                      height: 50,
                      mb: 0.5,
                      borderRadius: 1,
                      padding: 0.5,
                    }}
                  />
                )}
                <Typography variant="body2" fontWeight="600" sx={{ fontSize: '14px', letterSpacing: '0.2px' }}>
                  {category.name}
                </Typography>
              </CardActionArea>
            </Card>
          ))}
          <Card
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 100,
              textAlign: 'center',
              border: '1px solid #e0e0e0',
              '&:hover': {
                boxShadow: 3,
                borderColor: '#5282f1',
              },
              transition: 'all 0.2s'
            }}
          >
            <CardActionArea
              component={Link}
              to="/categories"
              sx={{ p: 1.5, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}
            >
              <Typography variant="body2" fontWeight="600" sx={{ fontSize: '14px', letterSpacing: '0.2px' }}>
                View All →
              </Typography>
            </CardActionArea>
          </Card>
        </Box>
      </Container>

      {/* Content Section */}
      <Container maxWidth="lg" sx={{ py: 4 }}>
        {/* Trending CodeBundles */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
            <TrendingIcon sx={{ color: '#5282f1', fontSize: 26 }} />
            <Typography 
              variant="h2" 
              sx={{ 
                fontWeight: 600, 
                fontSize: { xs: '20px', md: '24px' },
                letterSpacing: '-0.2px'
              }}
            >
              Recently Updated
            </Typography>
          </Box>
          
          <Box sx={{ 
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
            gap: 2,
            mb: 4
          }}>
            {recentCodebundles.slice(0, 6).map((cb) => (
              <Card
                key={cb.id}
                sx={{
                  border: '1px solid #e0e0e0',
                  '&:hover': { 
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    borderColor: '#5282f1'
                  },
                  transition: 'all 0.2s'
                }}
              >
                <CardActionArea
                  component={Link}
                  to={`/collections/${cb.collection_slug}/codebundles/${cb.slug}`}
                  sx={{ p: 2.5, height: '100%' }}
                >
                  <Typography 
                    className="codebundle-name"
                    sx={{ 
                      fontSize: '15px',
                      mb: 1,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {cb.display_name || cb.name}
                  </Typography>
                  
                  <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
                    <Chip 
                      label={cb.collection_name.replace('rw-', '').replace('-codecollection', '')}
                      size="small" 
                      sx={{ 
                        height: 22,
                        fontSize: '12px',
                        backgroundColor: '#f0f0f0'
                      }}
                    />
                    {cb.platform && cb.platform !== 'Unknown' && (
                      <Chip 
                        label={cb.platform} 
                        size="small" 
                        sx={{ 
                          height: 22,
                          fontSize: '12px',
                          backgroundColor: '#e3f2fd',
                          color: '#1976d2'
                        }}
                      />
                    )}
                  </Box>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      {cb.task_count} task{cb.task_count !== 1 ? 's' : ''}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(cb.git_updated_at || cb.updated_at)}
                    </Typography>
                  </Box>
                </CardActionArea>
              </Card>
            ))}
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
        </Box>
      </Container>
    </Box>
  );
};

export default Home;
