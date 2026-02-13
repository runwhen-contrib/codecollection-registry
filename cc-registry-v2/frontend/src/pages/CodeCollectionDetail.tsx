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
  Button,
} from '@mui/material';
import {
  GitHub as GitHubIcon,
  Code as CodeIcon,
  Task as TaskIcon,
  LocalOffer as TagIcon,
} from '@mui/icons-material';
import { useParams, Link } from 'react-router-dom';
import { apiService, CodeCollection, CodeCollectionVersion } from '../services/api';

const CodeCollectionDetail: React.FC = () => {
  const { collectionSlug } = useParams<{ collectionSlug: string }>();
  const [collection, setCollection] = useState<CodeCollection | null>(null);
  const [versions, setVersions] = useState<CodeCollectionVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!collectionSlug) return;
      
      try {
        // Get the specific collection and its versions
        const [collectionData, versionsData] = await Promise.all([
          apiService.getCodeCollectionBySlug(collectionSlug),
          apiService.getCollectionVersions(collectionSlug)
        ]);
        
        console.log('Collection data:', collectionData);
        console.log('Versions data:', versionsData);
        console.log('Number of versions:', versionsData.length);
        
        setCollection(collectionData);
        setVersions(versionsData);
        
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
      <Card sx={{ mb: 4, p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box
            component="img"
            src={collection.owner_icon || 'https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg'}
            alt="Icon"
            sx={{
              width: 80,
              height: 80,
              mr: 3,
              borderRadius: 2,
              padding: 1.5,
              bgcolor: 'action.hover',
              border: '2px solid',
              borderColor: 'divider',
            }}
          />
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" sx={{ mb: 0.5, fontWeight: 'bold' }}>
              {collection.name}
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
              by <strong>{collection.owner}</strong>
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip label={collection.git_ref} size="small" variant="outlined" />
              <Chip 
                label={collection.is_active ? 'Active' : 'Inactive'} 
                size="small" 
                color={collection.is_active ? 'success' : 'default'}
              />
              {collection.statistics && (
                <>
                  <Chip 
                    icon={<CodeIcon />}
                    label={`${collection.statistics.codebundle_count} CodeBundles`} 
                    size="small" 
                    variant="outlined"
                  />
                  <Chip 
                    icon={<TaskIcon />}
                    label={`${collection.statistics.total_tasks} Tasks`} 
                    size="small" 
                    variant="outlined"
                  />
                </>
              )}
            </Box>
          </Box>
          <Button
            component="a"
            href={collection.git_url}
            target="_blank"
            rel="noopener noreferrer"
            variant="contained"
            startIcon={<GitHubIcon />}
          >
            View on GitHub
          </Button>
        </Box>

        <Typography variant="body1" color="text.secondary">
          {collection.description}
        </Typography>

      </Card>

      {/* Collection Information */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 3, mb: 4 }}>
        {/* Repository Information */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
              <GitHubIcon color="primary" />
              Repository
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Git URL
                </Typography>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    fontFamily: 'monospace', 
                    fontSize: '0.875rem',
                    wordBreak: 'break-all',
                    bgcolor: 'action.hover',
                    p: 1,
                    borderRadius: 1,
                  }}
                >
                  {collection.git_url}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Branch/Ref
                </Typography>
                <Chip label={collection.git_ref} size="small" sx={{ fontFamily: 'monospace' }} />
              </Box>
              {collection.owner_email && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Owner Email
                  </Typography>
                  <Typography variant="body2">{collection.owner_email}</Typography>
                </Box>
              )}
            </Box>
          </CardContent>
        </Card>

        {/* Timestamps & Status */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
              <TaskIcon color="primary" />
              Status & Timestamps
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Status
                </Typography>
                <Chip 
                  label={collection.is_active ? 'Active' : 'Inactive'} 
                  size="small" 
                  color={collection.is_active ? 'success' : 'default'}
                  sx={{ fontWeight: 600 }}
                />
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Last Synced
                </Typography>
                <Typography variant="body2">
                  {collection.last_synced 
                    ? new Date(collection.last_synced).toLocaleString()
                    : 'Never'
                  }
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Created
                </Typography>
                <Typography variant="body2">
                  {new Date(collection.created_at).toLocaleString()}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Last Updated
                </Typography>
                <Typography variant="body2">
                  {new Date(collection.updated_at).toLocaleString()}
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Release Tags Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            <TagIcon color="primary" />
            Release Tags
          </Typography>
          {versions.length > 0 ? (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {versions.filter(v => v.version_type !== 'main').length} git release tag{versions.filter(v => v.version_type !== 'main').length !== 1 ? 's' : ''} available
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {versions
                  .filter(v => v.version_type !== 'main')
                  .map((version) => (
                    <Chip
                      key={version.id}
                      label={version.version_name}
                      component={Link}
                      to={`/collections/${collection.slug}/versions/${version.version_name}`}
                      clickable
                      size="medium"
                      variant={version.is_latest ? "filled" : "outlined"}
                      color={version.is_latest ? "primary" : "default"}
                      sx={{ 
                        fontFamily: 'monospace',
                        fontWeight: version.is_latest ? 600 : 400,
                        '&:hover': {
                          bgcolor: version.is_latest ? 'primary.dark' : 'action.hover',
                        }
                      }}
                    />
                  ))}
              </Box>
            </>
          ) : (
            <Alert severity="info">
              <Typography variant="body2">
                No release tags have been synced yet. The version sync service needs to fetch git tags from the repository.
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                Git Repository: <strong>{collection.git_ref}</strong>
              </Typography>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Releases Section */}
      {versions.length > 0 && (
        <Box>
          <Typography variant="h5" sx={{ mb: 3, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            <CodeIcon color="primary" />
            Releases
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {versions.map((version, index) => (
              <Card 
                key={version.id}
                sx={{
                  border: version.is_latest ? '2px solid' : '1px solid',
                  borderColor: version.is_latest ? 'primary.main' : 'divider',
                }}
              >
                <CardContent>
                  {/* Release Header */}
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box sx={{ flex: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                        <Typography 
                          variant="h6" 
                          sx={{ 
                            fontFamily: 'monospace', 
                            fontWeight: 'bold',
                          }}
                        >
                          {version.version_name}
                        </Typography>
                        {version.is_latest && (
                          <Chip label="Latest Release" size="small" color="primary" sx={{ fontWeight: 600 }} />
                        )}
                        {version.is_prerelease && (
                          <Chip label="Pre-release" size="small" color="warning" sx={{ fontWeight: 600 }} />
                        )}
                        {version.version_type === 'main' && (
                          <Chip label="Main Branch" size="small" color="success" sx={{ fontWeight: 600 }} />
                        )}
                      </Box>
                      
                      {version.display_name && (
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 600 }}>
                          {version.display_name}
                        </Typography>
                      )}
                      
                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                        {version.version_date && (
                          <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <TaskIcon sx={{ fontSize: '1rem' }} />
                            Released {new Date(version.version_date).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'long',
                              day: 'numeric'
                            })}
                          </Typography>
                        )}
                        {version.codebundle_count !== undefined && (
                          <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <CodeIcon sx={{ fontSize: '1rem' }} />
                            {version.codebundle_count} CodeBundle{version.codebundle_count !== 1 ? 's' : ''}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    
                    <Button
                      component={Link}
                      to={`/collections/${collection.slug}/versions/${version.version_name}`}
                      variant={version.is_latest ? "contained" : "outlined"}
                      size="small"
                    >
                      View Version
                    </Button>
                  </Box>
                  
                  {/* Release Notes */}
                  {version.description && (
                    <Box sx={{ 
                      mt: 2, 
                      pt: 2, 
                      borderTop: '1px solid',
                      borderColor: 'divider'
                    }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                        Release Notes
                      </Typography>
                      <Typography 
                        variant="body2" 
                        color="text.secondary"
                        sx={{ 
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.6
                        }}
                      >
                        {version.description}
                      </Typography>
                    </Box>
                  )}
                  
                  {/* Git Reference */}
                  <Box sx={{ 
                    mt: 2, 
                    pt: 2, 
                    borderTop: '1px solid',
                    borderColor: 'divider',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1
                  }}>
                    <Typography variant="caption" color="text.secondary">
                      Git Reference:
                    </Typography>
                    <Chip 
                      label={version.git_ref} 
                      size="small" 
                      sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                    />
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Box>
      )}

      {/* Browse CodeBundles Link */}
      <Card sx={{ mt: 3, p: 3, textAlign: 'center', bgcolor: 'action.hover' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Browse CodeBundles
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          View all CodeBundles from this collection
        </Typography>
        <Button
          component={Link}
          to={`/codebundles?collection=${collection.id}`}
          variant="contained"
          startIcon={<CodeIcon />}
        >
          View All CodeBundles
        </Button>
      </Card>

    </Container>
  );
};

export default CodeCollectionDetail;
