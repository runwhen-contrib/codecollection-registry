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
  List,
  ListItem,
  ListItemText,
  Divider,
  Grid,
} from '@mui/material';
import { useParams, Link } from 'react-router-dom';
import { apiService, CodeBundle } from '../services/api';

const CodeBundleDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [codebundle, setCodebundle] = useState<CodeBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;
      
      try {
        const codebundleData = await apiService.getCodeBundle(parseInt(id));
        setCodebundle(codebundleData);
      } catch (err) {
        setError('Failed to load codebundle');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

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

  if (!codebundle) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="warning">CodeBundle not found</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h1" sx={{ mb: 2 }}>
          {codebundle.display_name}
        </Typography>
        
        {codebundle.codecollection && (
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
            From{' '}
            <Link to={`/collections/${codebundle.codecollection.slug}`}>
              {codebundle.codecollection.name}
            </Link>
          </Typography>
        )}

        <Typography variant="body1" sx={{ mb: 3 }}>
          {codebundle.description}
        </Typography>

        {codebundle.support_tags && codebundle.support_tags.length > 0 && (
          <Box sx={{ mb: 3 }}>
            {codebundle.support_tags.map((tag) => (
              <Chip
                key={tag}
                label={tag}
                sx={{ mr: 1, mb: 1 }}
              />
            ))}
          </Box>
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Main Content */}
        <Box sx={{ flex: 2 }}>
          {codebundle.doc && (
            <Card sx={{ mb: 4 }}>
              <CardContent>
                <Typography variant="h5" sx={{ mb: 2 }}>
                  Documentation
                </Typography>
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {codebundle.doc}
                </Typography>
              </CardContent>
            </Card>
          )}

          {codebundle.tasks && codebundle.tasks.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h5" sx={{ mb: 2 }}>
                  Tasks ({codebundle.task_count})
                </Typography>
                <List>
                  {codebundle.tasks.map((task, index) => (
                    <React.Fragment key={index}>
                      <ListItem>
                        <ListItemText primary={task} />
                      </ListItem>
                      {index < codebundle.tasks!.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}
        </Box>

        {/* Sidebar */}
        <Box sx={{ flex: 1 }}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Details
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Author
                </Typography>
                <Typography variant="body1">
                  {codebundle.author}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Created
                </Typography>
                <Typography variant="body1">
                  {new Date(codebundle.created_at).toLocaleDateString()}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Tasks
                </Typography>
                <Typography variant="body1">
                  {codebundle.task_count}
                </Typography>
              </Box>
            </CardContent>
          </Card>

          {codebundle.codecollection && (
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Collection
                </Typography>
                <Link to={`/collections/${codebundle.codecollection.slug}`}>
                  <Typography variant="body1" color="primary">
                    {codebundle.codecollection.name}
                  </Typography>
                </Link>
              </CardContent>
            </Card>
          )}
        </Box>
      </Box>
    </Container>
  );
};

export default CodeBundleDetail;