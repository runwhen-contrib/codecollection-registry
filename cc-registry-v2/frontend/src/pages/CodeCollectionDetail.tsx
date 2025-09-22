import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Chip,
  Grid,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  Avatar,
} from '@mui/material';
import {
  GitHub as GitHubIcon,
  Schedule as ScheduleIcon,
  Code as CodeIcon,
  Task as TaskIcon,
} from '@mui/icons-material';
import { useParams, Link } from 'react-router-dom';
import { apiService, CodeCollection, CodeBundle } from '../services/api';

const CodeCollectionDetail: React.FC = () => {
  const { collectionSlug } = useParams<{ collectionSlug: string }>();
  const [collection, setCollection] = useState<CodeCollection | null>(null);
  const [codebundles, setCodebundles] = useState<CodeBundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!collectionSlug) return;
      
      try {
        // Get the specific collection and all codebundles
        const [collectionData, codebundlesData] = await Promise.all([
          apiService.getCodeCollectionBySlug(collectionSlug),
          apiService.getCodeBundles()
        ]);
        
        setCollection(collectionData);
        
        // Filter codebundles for this collection
        const collectionCodebundles = codebundlesData.filter(
          cb => cb.codecollection?.slug === collectionSlug
        );
        setCodebundles(collectionCodebundles);
        
      } catch (err) {
        setError('Failed to load collection details');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [collectionSlug]);

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

  if (!collection) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="warning">Collection not found</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <Avatar
            src={collection.owner_icon || 'https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg'}
            sx={{ width: 80, height: 80, mr: 3 }}
          />
          <Box>
            <Typography variant="h1" sx={{ mb: 1 }}>
              {collection.name}
            </Typography>
            <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
              by {collection.owner}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip label={collection.git_ref} size="small" variant="outlined" />
              <Chip 
                label={collection.is_active ? 'Active' : 'Inactive'} 
                size="small" 
                color={collection.is_active ? 'success' : 'default'}
              />
            </Box>
          </Box>
        </Box>

        <Typography variant="body1" sx={{ mb: 3, fontSize: '1.1rem' }}>
          {collection.description}
        </Typography>

        {/* Statistics Cards */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
          <Box sx={{ flex: '1 1 calc(25% - 12px)', minWidth: '200px' }}>
            <Card sx={{ textAlign: 'center', p: 2 }}>
              <CodeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h4" color="primary">
                {collection.statistics?.codebundle_count || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Codebundles
              </Typography>
            </Card>
          </Box>
          <Box sx={{ flex: '1 1 calc(25% - 12px)', minWidth: '200px' }}>
            <Card sx={{ textAlign: 'center', p: 2 }}>
              <TaskIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h4" color="primary">
                {collection.statistics?.total_tasks || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Tasks
              </Typography>
            </Card>
          </Box>
          <Box sx={{ flex: '1 1 calc(25% - 12px)', minWidth: '200px' }}>
            <Card sx={{ textAlign: 'center', p: 2 }}>
              <ScheduleIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6" color="primary">
                {collection.last_synced ? new Date(collection.last_synced).toLocaleDateString() : 'Never'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Last Synced
              </Typography>
            </Card>
          </Box>
          <Box sx={{ flex: '1 1 calc(25% - 12px)', minWidth: '200px' }}>
            <Card sx={{ textAlign: 'center', p: 2 }}>
              <GitHubIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Button
                component="a"
                href={collection.git_url}
                target="_blank"
                rel="noopener noreferrer"
                variant="outlined"
                size="small"
              >
                View Repository
              </Button>
            </Card>
          </Box>
        </Box>
      </Box>

      <Divider sx={{ mb: 4 }} />

      {/* Codebundles Section */}
      <Typography variant="h4" sx={{ mb: 3 }}>
        Codebundles ({codebundles.length})
      </Typography>

      {codebundles.length > 0 ? (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {codebundles.map((codebundle) => (
            <Box key={codebundle.id} sx={{ flex: '0 0 calc(33.333% - 16px)', '@media (max-width: 900px)': { flex: '0 0 calc(50% - 12px)' }, '@media (max-width: 600px)': { flex: '0 0 100%' } }}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  '&:hover': {
                    boxShadow: 4,
                  },
                }}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" fontWeight="bold" sx={{ mb: 1 }}>
                    {codebundle.display_name}
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {codebundle.description}
                  </Typography>

                  {codebundle.support_tags && codebundle.support_tags.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      {codebundle.support_tags.slice(0, 2).map((tag) => (
                        <Chip
                          key={tag}
                          label={tag}
                          size="small"
                          sx={{ mr: 1, mb: 1 }}
                        />
                      ))}
                      {codebundle.support_tags.length > 2 && (
                        <Chip
                          label={`+${codebundle.support_tags.length - 2} more`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  )}

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      {codebundle.task_count} tasks
                    </Typography>
                    <Button
                      component={Link}
                      to={`/collections/${collection.slug}/codebundles/${codebundle.slug}`}
                      variant="outlined"
                      size="small"
                    >
                      View Details
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
      ) : (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No codebundles found in this collection
          </Typography>
        </Box>
      )}

      {/* Collection Details */}
      <Divider sx={{ my: 4 }} />
      
      <Typography variant="h5" sx={{ mb: 3 }}>
        Collection Details
      </Typography>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Box sx={{ flex: '1 1 calc(50% - 12px)', minWidth: '300px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Repository Information
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Git URL" 
                    secondary={collection.git_url}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Branch/Ref" 
                    secondary={collection.git_ref}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Owner Email" 
                    secondary={collection.owner_email}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Box>
        
        <Box sx={{ flex: '1 1 calc(50% - 12px)', minWidth: '300px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Timestamps
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Created" 
                    secondary={new Date(collection.created_at).toLocaleString()}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Last Updated" 
                    secondary={new Date(collection.updated_at).toLocaleString()}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Last Synced" 
                    secondary={collection.last_synced ? new Date(collection.last_synced).toLocaleString() : 'Never'}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Container>
  );
};

export default CodeCollectionDetail;
