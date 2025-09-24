import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Container,
  Typography,
  Box,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  Button,
  Alert,
  CircularProgress,
  Divider,
  Breadcrumbs,
  Paper,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Launch as LaunchIcon,
  Code as CodeIcon,
  Tag as TagIcon,
  CalendarToday as CalendarIcon,
  Person as PersonIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material';
import { apiService, CodeCollectionVersion, VersionCodebundle } from '../services/api';

const VersionDetail: React.FC = () => {
  const { collectionSlug, versionName } = useParams<{
    collectionSlug: string;
    versionName: string;
  }>();
  
  const [version, setVersion] = useState<CodeCollectionVersion | null>(null);
  const [codebundles, setCodebundles] = useState<VersionCodebundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVersionData = async () => {
      if (!collectionSlug || !versionName) return;

      try {
        setLoading(true);
        
        // Get version details
        const versionData = await apiService.getVersionByName(collectionSlug, versionName);
        setVersion(versionData);
        
        // Get codebundles for this version
        const codebundlesData = await apiService.getVersionCodebundles(collectionSlug, versionName);
        setCodebundles(codebundlesData.codebundles);
        
      } catch (err) {
        console.error('Error fetching version data:', err);
        setError('Failed to load version details');
      } finally {
        setLoading(false);
      }
    };

    fetchVersionData();
  }, [collectionSlug, versionName]);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error || !version) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error">
          {error || 'Version not found'}
        </Alert>
      </Container>
    );
  }

  const getVersionTypeColor = (type: string) => {
    switch (type) {
      case 'main': return 'success';
      case 'tag': return 'primary';
      case 'branch': return 'info';
      default: return 'default';
    }
  };

  const getChangeIcon = (codebundle: VersionCodebundle) => {
    if (codebundle.added_in_version) return <AddIcon color="success" />;
    if (codebundle.modified_in_version) return <EditIcon color="warning" />;
    if (codebundle.removed_in_version) return <RemoveIcon color="error" />;
    return null;
  };

  const getChangeLabel = (codebundle: VersionCodebundle) => {
    if (codebundle.added_in_version) return 'Added';
    if (codebundle.modified_in_version) return 'Modified';
    if (codebundle.removed_in_version) return 'Removed';
    return null;
  };

  const getChangeColor = (codebundle: VersionCodebundle): "success" | "warning" | "error" | undefined => {
    if (codebundle.added_in_version) return 'success';
    if (codebundle.modified_in_version) return 'warning';
    if (codebundle.removed_in_version) return 'error';
    return undefined;
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 3 }}>
        <Link to="/collections" style={{ textDecoration: 'none', color: 'inherit' }}>
          Collections
        </Link>
        <Link 
          to={`/collections/${collectionSlug}`} 
          style={{ textDecoration: 'none', color: 'inherit' }}
        >
          {version.codecollection?.name}
        </Link>
        <Typography color="text.primary">
          Version {version.version_name}
        </Typography>
      </Breadcrumbs>

      {/* Back Button */}
      <Button
        component={Link}
        to={`/collections/${collectionSlug}`}
        startIcon={<ArrowBackIcon />}
        sx={{ mb: 3 }}
      >
        Back to Collection
      </Button>

      {/* Version Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <TagIcon color="primary" />
          <Typography variant="h4" component="h1">
            {version.display_name || version.version_name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip 
              label={version.version_type} 
              color={getVersionTypeColor(version.version_type)}
              size="small"
            />
            {version.is_latest && (
              <Chip label="Latest" color="primary" size="small" />
            )}
            {version.is_prerelease && (
              <Chip label="Pre-release" color="warning" size="small" />
            )}
          </Box>
        </Box>

        {version.description && (
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            {version.description}
          </Typography>
        )}

        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {version.version_date && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CalendarIcon color="action" />
              <Typography variant="body2" color="text.secondary">
                {new Date(version.version_date).toLocaleDateString()}
              </Typography>
            </Box>
          )}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CodeIcon color="action" />
            <Typography variant="body2" color="text.secondary">
              {codebundles.length} codebundles
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Git ref: {version.git_ref.substring(0, 8)}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Codebundles List */}
      <Card>
        <CardContent>
          <Typography variant="h5" sx={{ mb: 2 }}>
            Codebundles ({codebundles.length})
          </Typography>
          
          {codebundles.length > 0 ? (
            <List>
              {codebundles.map((codebundle, index) => (
                <React.Fragment key={codebundle.id}>
                  <ListItem
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      py: 2,
                    }}
                  >
                    <Box sx={{ flexGrow: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        {getChangeIcon(codebundle)}
                        <Typography variant="h6">
                          {codebundle.display_name || codebundle.name}
                        </Typography>
                        {getChangeLabel(codebundle) && (
                          <Chip 
                            label={getChangeLabel(codebundle)} 
                            color={getChangeColor(codebundle)}
                            size="small"
                          />
                        )}
                      </Box>
                      
                      {codebundle.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {codebundle.description}
                        </Typography>
                      )}
                      
                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 1 }}>
                        {codebundle.author && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <PersonIcon fontSize="small" color="action" />
                            <Typography variant="caption" color="text.secondary">
                              {codebundle.author}
                            </Typography>
                          </Box>
                        )}
                        <Typography variant="caption" color="text.secondary">
                          {codebundle.task_count} tasks
                        </Typography>
                        {codebundle.sli_count > 0 && (
                          <Typography variant="caption" color="text.secondary">
                            {codebundle.sli_count} SLIs
                          </Typography>
                        )}
                      </Box>
                      
                      {codebundle.support_tags && codebundle.support_tags.length > 0 && (
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {codebundle.support_tags.slice(0, 5).map((tag, tagIndex) => (
                            <Chip
                              key={tagIndex}
                              label={tag}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                          {codebundle.support_tags.length > 5 && (
                            <Chip
                              label={`+${codebundle.support_tags.length - 5} more`}
                              size="small"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      )}
                    </Box>
                    
                    <Box sx={{ display: 'flex', gap: 1, ml: 2 }}>
                      {codebundle.runbook_source_url && (
                        <Button
                          href={codebundle.runbook_source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          startIcon={<LaunchIcon />}
                          size="small"
                          variant="outlined"
                        >
                          Source
                        </Button>
                      )}
                    </Box>
                  </ListItem>
                  {index < (codebundles?.length || 0) - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="body1" color="text.secondary">
                No codebundles found in this version.
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default VersionDetail;


