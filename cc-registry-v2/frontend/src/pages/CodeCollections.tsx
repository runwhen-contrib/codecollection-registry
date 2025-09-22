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
} from '@mui/material';
import { Link } from 'react-router-dom';
import { apiService, CodeCollection } from '../services/api';

const CodeCollections: React.FC = () => {
  const [collections, setCollections] = useState<CodeCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const collectionsData = await apiService.getCodeCollections();
        setCollections(collectionsData);
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

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {collections.map((collection) => (
          <Box key={collection.id} sx={{ flex: '0 0 calc(100% - 12px)', '@media (min-width: 900px)': { flex: '0 0 calc(50% - 12px)' } }}>
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
              <CardActionArea
                component={Link}
                to={`/collections/${collection.slug}`}
                sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}
              >
                <CardContent sx={{ flexGrow: 1 }}>
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
                    <Box>
                      <Typography variant="h5" fontWeight="bold">
                        {collection.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        by {collection.owner}
                      </Typography>
                    </Box>
                  </Box>

                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {collection.description}
                  </Typography>

                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                    <Chip label={collection.git_ref} size="small" variant="outlined" />
                    <Chip 
                      label={collection.is_active ? 'Active' : 'Inactive'} 
                      size="small" 
                      color={collection.is_active ? 'success' : 'default'}
                    />
                  </Box>

                  {/* Statistics */}
                  {collection.statistics && (
                    <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="h6" color="primary">
                          {collection.statistics.codebundle_count}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          codebundles
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="h6" color="primary">
                          {collection.statistics.total_tasks}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          tasks
                        </Typography>
                      </Box>
                    </Box>
                  )}

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      {collection.git_url}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Last synced: {collection.last_synced ? new Date(collection.last_synced).toLocaleDateString() : 'Never'}
                    </Typography>
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
            </Box>
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