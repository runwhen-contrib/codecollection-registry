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

  // Calculate total statistics
  const totalStats = collections.reduce(
    (acc, collection) => {
      if (collection.statistics) {
        acc.totalCodebundles += collection.statistics.codebundle_count;
        acc.totalTasks += collection.statistics.total_tasks;
      }
      return acc;
    },
    { totalCodebundles: 0, totalTasks: 0 }
  );

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h1" sx={{ mb: 2 }}>
        CodeCollections
      </Typography>

      {/* Summary Statistics */}
      <Box sx={{ display: 'flex', gap: 4, mb: 4, p: 2, bgcolor: 'background.paper', borderRadius: 1, boxShadow: 1 }}>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h4" color="primary">
            {collections.length}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Collections
          </Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h4" color="primary">
            {totalStats.totalCodebundles}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Total Codebundles
          </Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h4" color="primary">
            {totalStats.totalTasks}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Total Tasks
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {collections.map((collection) => (
          <Card
            key={collection.id}
            sx={{
              '&:hover': {
                boxShadow: 4,
              },
            }}
          >
            {/* Collection Header */}
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
                  }}
                />
                <Box sx={{ flexGrow: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                    <Typography variant="h5" fontWeight="bold">
                      {collection.name}
                    </Typography>
                    <Button
                      component={Link}
                      to={`/collections/${collection.slug}`}
                      variant="outlined"
                      size="small"
                      startIcon={<LaunchIcon />}
                    >
                      View Details
                    </Button>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    by {collection.owner}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip label={collection.git_ref} size="small" variant="outlined" />
                    <Chip 
                      label={collection.is_active ? 'Active' : 'Inactive'} 
                      size="small" 
                      color={collection.is_active ? 'success' : 'default'}
                    />
                    {collection.versions && collection.versions.length > 0 && (
                      <Chip 
                        label={`${collection.versions.length} versions`} 
                        size="small" 
                        color="info"
                        icon={<ReleaseIcon />}
                      />
                    )}
                  </Box>
                </Box>
              </Box>

              <Typography variant="body1" sx={{ mb: 2 }}>
                {collection.description}
              </Typography>

              {/* Statistics */}
              {collection.statistics && (
                <Box sx={{ display: 'flex', gap: 4, mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <CodeIcon color="primary" />
                    <Typography variant="h6" color="primary">
                      {collection.statistics.codebundle_count}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      codebundles
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <TaskIcon color="primary" />
                    <Typography variant="h6" color="primary">
                      {collection.statistics.total_tasks}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      tasks
                    </Typography>
                  </Box>
                </Box>
              )}
            </CardContent>

            {/* Versions Section */}
            {collection.versions && collection.versions.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ReleaseIcon color="primary" />
                    <Typography variant="h6">
                      Versions ({collection.versions.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <List dense>
                    {collection.versions.slice(0, 5).map((version, index) => (
                      <React.Fragment key={version.id}>
                        <ListItem
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1 }}>
                            <ListItemIcon sx={{ minWidth: 'auto' }}>
                              <TagIcon color={version.is_latest ? 'primary' : 'action'} />
                            </ListItemIcon>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="body1" fontWeight={version.is_latest ? 'bold' : 'normal'}>
                                    {version.version_name}
                                  </Typography>
                                  {version.is_latest && (
                                    <Chip label="Latest" size="small" color="primary" />
                                  )}
                                  {version.is_prerelease && (
                                    <Chip label="Pre-release" size="small" color="warning" />
                                  )}
                                  {version.version_type === 'main' && (
                                    <Chip label="Main" size="small" color="success" />
                                  )}
                                </Box>
                              }
                              secondary={
                                <Box>
                                  {version.display_name && (
                                    <Typography variant="body2" color="text.secondary">
                                      {version.display_name}
                                    </Typography>
                                  )}
                                  <Typography variant="caption" color="text.secondary">
                                    {version.codebundle_count} codebundles
                                    {version.version_date && (
                                      <> • {new Date(version.version_date).toLocaleDateString()}</>
                                    )}
                                  </Typography>
                                </Box>
                              }
                            />
                          </Box>
                          <Tooltip title={`View ${version.version_name} version`}>
                            <IconButton
                              component={Link}
                              to={`/collections/${collection.slug}/versions/${version.version_name}`}
                              size="small"
                            >
                              <LaunchIcon />
                            </IconButton>
                          </Tooltip>
                        </ListItem>
                        {index < Math.min((collection.versions?.length || 0) - 1, 4) && <Divider />}
                      </React.Fragment>
                    ))}
                    {(collection.versions?.length || 0) > 5 && (
                      <ListItem>
                        <ListItemText
                          primary={
                            <Typography variant="body2" color="text.secondary" align="center">
                              ... and {(collection.versions?.length || 0) - 5} more versions
                            </Typography>
                          }
                        />
                      </ListItem>
                    )}
                  </List>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Collection Info Footer */}
            <CardContent sx={{ pt: 0 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  {collection.git_url}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Last synced: {collection.last_synced ? new Date(collection.last_synced).toLocaleDateString() : 'Never'}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {collections.length === 0 && !loading && (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No collections found
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default CodeCollections;