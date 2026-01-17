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
} from '@mui/material';
import { 
  AutoAwesome as AutoAwesomeIcon,
  MonetizationOn as MoneyIcon,
  Update as UpdateIcon,
} from '@mui/icons-material';
import { Link } from 'react-router-dom';
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

// Default category names to display on homepage
const CATEGORY_NAMES = ['KUBERNETES', 'GKE', 'AKS', 'EKS', 'OPENSHIFT', 'GCP', 'AWS', 'AZURE'];

const Home: React.FC = () => {
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [recentCodebundles, setRecentCodebundles] = useState<RecentCodebundle[]>([]);
  const [tagIcons, setTagIcons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Build categories from fetched tag icons
  const categories = CATEGORY_NAMES.map(name => ({
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
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Registry Chat - Clean Card */}
      <Box sx={{ mb: 4 }}>
        <Card
          sx={{
            background: '#fff',
            border: '2px solid #2f80ed',
            borderRadius: 2,
            transition: 'all 0.2s ease',
            '&:hover': {
              boxShadow: '0 4px 20px rgba(47, 128, 237, 0.2)',
              transform: 'translateY(-1px)',
            },
          }}
        >
          <CardActionArea
            component={Link}
            to="/chat"
            sx={{ p: 3 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <AutoAwesomeIcon sx={{ fontSize: 32, color: '#2f80ed' }} />
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" fontWeight="600" sx={{ color: '#333' }}>
                  Registry Chat
                </Typography>
                <Typography variant="body2" sx={{ color: '#666' }}>
                  Chat with Eager Edgar about CodeBundles, documentation, and authoring guidelines
                </Typography>
              </Box>
              <Typography variant="h5" sx={{ color: '#2f80ed', display: { xs: 'none', sm: 'block' } }}>→</Typography>
            </Box>
          </CardActionArea>
        </Card>
      </Box>

      {/* Top Codebundle Categories */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h2" sx={{ mb: 2 }}>
          Top CodeBundle Categories
        </Typography>
        <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {categories.map((category) => (
            <Box key={category.name} sx={{ flex: '0 0 calc(50% - 8px)', '@media (min-width: 600px)': { flex: '0 0 calc(25% - 12px)' } }}>
              <Card
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 120,
                  textAlign: 'center',
                  '&:hover': {
                    boxShadow: 4,
                  },
                }}
              >
                <CardActionArea
                  component={Link}
                  to={`/all-tasks?category=${category.name}`}
                  sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
                >
                  <Box
                    component="img"
                    src={category.icon}
                    alt={`${category.name} icon`}
                    sx={{
                      width: 80,
                      height: 80,
                      mb: 1,
                      borderRadius: 1,
                      padding: 1,
                    }}
                  />
                  <Typography variant="body1" fontWeight="bold">
                    {category.name}
                  </Typography>
                </CardActionArea>
              </Card>
            </Box>
          ))}
          <Box sx={{ flex: '0 0 calc(50% - 8px)', '@media (min-width: 600px)': { flex: '0 0 calc(25% - 12px)' } }}>
            <Card
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 120,
                textAlign: 'center',
                '&:hover': {
                  boxShadow: 4,
                },
              }}
            >
              <CardActionArea
                component={Link}
                to="/categories"
                sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
              >
                <Typography variant="body1" fontWeight="bold">
                  Browse All Categories
                </Typography>
              </CardActionArea>
            </Card>
          </Box>
        </Box>
      </Box>

      {/* Two Column Layout - Recent Updates and Statistics */}
      <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', lg: 'row' } }}>
        {/* Recent Updates */}
        <Box sx={{ flex: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <UpdateIcon sx={{ color: '#666' }} />
            <Typography variant="h2">
              Recent Updates
            </Typography>
          </Box>
          <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {recentCodebundles.map((cb) => (
              <Card
                key={cb.id}
                sx={{
                  '&:hover': { boxShadow: 2 },
                }}
              >
                <CardActionArea
                  component={Link}
                  to={`/collections/${cb.collection_slug}/codebundles/${cb.slug}`}
                  sx={{ p: 2 }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography 
                        variant="subtitle2" 
                        fontWeight="600"
                        sx={{ 
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        {cb.display_name || cb.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {cb.collection_name} • {cb.task_count} task{cb.task_count !== 1 ? 's' : ''}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
                      {cb.platform && cb.platform !== 'Unknown' && (
                        <Chip 
                          label={cb.platform} 
                          size="small" 
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                      )}
                      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                        {formatDate(cb.git_updated_at || cb.updated_at)}
                      </Typography>
                    </Box>
                  </Box>
                </CardActionArea>
              </Card>
            ))}
            {recentCodebundles.length === 0 && (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                No recent updates found
              </Typography>
            )}
          </Box>
        </Box>

        {/* Statistics Sidebar */}
        <Box sx={{ flex: 1 }}>
          <Typography variant="h2" sx={{ mb: 2 }}>
            Registry Stats
          </Typography>
          <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
          
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2" color="text.secondary">CodeCollections</Typography>
                  <Typography variant="h6" fontWeight="600">{stats?.collections || 0}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2" color="text.secondary">CodeBundles</Typography>
                  <Typography variant="h6" fontWeight="600">{stats?.codebundles || 0}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2" color="text.secondary">Total Tasks</Typography>
                  <Typography variant="h6" fontWeight="600" color="primary">{stats?.tasks || 0}</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
          
          {/* Get Paid to Contribute Button */}
          <Button
            variant="outlined"
            fullWidth
            startIcon={<MoneyIcon />}
            href="https://docs.runwhen.com/public/v/runwhen-authors"
            target="_blank"
            rel="noopener"
            sx={{
              borderColor: '#f5af19',
              color: '#e67e00',
              fontWeight: 600,
              py: 1.5,
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
  );
};

export default Home;
