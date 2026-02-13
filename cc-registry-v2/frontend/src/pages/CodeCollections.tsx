import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActionArea,
  CircularProgress,
  Alert,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Button,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  LocalOffer as TagIcon,
  Code as CodeIcon,
  Task as TaskIcon,
  NewReleases as ReleaseIcon,
  Launch as LaunchIcon,
  GitHub as GitHubIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { apiService, CodeCollection, CodeCollectionVersion } from '../services/api';

const CodeCollections: React.FC = () => {
  const [collections, setCollections] = useState<CodeCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Try to get collections with versions first, fallback to regular collections
        try {
          const collectionsWithVersions = await apiService.getCollectionsWithVersions();
          setCollections(collectionsWithVersions);
        } catch (versionError) {
          console.warn('Failed to load versions, falling back to basic collections:', versionError);
          const collectionsData = await apiService.getCodeCollections();
          setCollections(collectionsData);
        }
      } catch (err) {
        setError('Failed to load collections');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
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
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 600 }}>
          CodeCollections
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Browse and explore automation code collections from the RunWhen community
        </Typography>
      </Box>

      <Box sx={{ 
        display: 'grid', 
        gridTemplateColumns: { 
          xs: '1fr', 
          sm: 'repeat(2, 1fr)', 
          lg: 'repeat(3, 1fr)' 
        },
        gap: 3 
      }}>
        {collections.map((collection) => (
          <Card
            key={collection.id}
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              transition: 'all 0.3s ease',
              '&:hover': {
                boxShadow: 6,
                transform: 'translateY(-2px)',
              },
            }}
          >
            {/* Collection Header */}
            <CardActionArea
              component={Link}
              to={`/collections/${collection.slug}`}
              sx={{ flexGrow: 1 }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Box
                    component="img"
                    src={collection.owner_icon || 'https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg'}
                    alt="Icon"
                    sx={{
                      width: 60,
                      height: 60,
                      mr: 2,
                      borderRadius: 1.5,
                      padding: 1,
                      bgcolor: 'action.hover',
                    }}
                  />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }} noWrap>
                      {collection.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      by {collection.owner}
                    </Typography>
                  </Box>
                </Box>

                <Typography 
                  variant="body2" 
                  color="text.secondary" 
                  sx={{ 
                    mb: 2, 
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    minHeight: '3.6em',
                  }}
                >
                  {collection.description}
                </Typography>

                {/* Statistics */}
                {collection.statistics && (
                  <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CodeIcon color="primary" fontSize="small" />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {collection.statistics.codebundle_count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        CodeBundles
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <TaskIcon color="primary" fontSize="small" />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {collection.statistics.total_tasks}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Tasks
                      </Typography>
                    </Box>
                  </Box>
                )}

                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip 
                    label={collection.git_ref} 
                    size="small" 
                    variant="outlined"
                  />
                  {collection.versions && collection.versions.length > 0 && (
                    <Chip 
                      label={`${collection.versions.length} version${collection.versions.length !== 1 ? 's' : ''}`} 
                      size="small" 
                      color="primary"
                      variant="outlined"
                    />
                  )}
                </Box>
              </CardContent>
            </CardActionArea>

            {/* Bottom Actions */}
            <CardContent sx={{ pt: 0, mt: 'auto' }}>
              <Button
                component="a"
                href={collection.git_url}
                target="_blank"
                rel="noopener noreferrer"
                variant="outlined"
                size="small"
                startIcon={<GitHubIcon />}
                fullWidth
                onClick={(e) => e.stopPropagation()}
              >
                View on GitHub
              </Button>
            </CardContent>
          </Card>
        ))}
      </Box>

      {collections.length === 0 && !loading && (
        <Card sx={{ p: 6, textAlign: 'center' }}>
          <CodeIcon sx={{ fontSize: '4rem', color: 'text.secondary', mb: 2 }} />
          <Typography variant="h5" sx={{ mb: 1, fontWeight: 600 }}>
            No CodeCollections Found
          </Typography>
          <Typography variant="body1" color="text.secondary">
            There are currently no CodeCollections available in the registry
          </Typography>
        </Card>
      )}
    </Container>
  );
};

export default CodeCollections;