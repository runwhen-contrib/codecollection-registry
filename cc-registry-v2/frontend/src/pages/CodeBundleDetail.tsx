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
  Button,
  Tabs,
  Tab,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Avatar,
} from '@mui/material';
import { 
  GitHub as GitHubIcon, 
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  AutoAwesome as AutoAwesomeIcon,
  Security as SecurityIcon,
  InfoOutlined as InfoIcon,
  Person as PersonIcon,
  CalendarToday as CalendarIcon,
  Code as CodeIcon,
  Language as LanguageIcon,
  Shield as ShieldIcon,
  Verified as VerifiedIcon,
  Update as UpdateIcon,
  Storage as StorageIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
  KeyboardArrowUp as KeyboardArrowUpIcon,
} from '@mui/icons-material';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { apiService, CodeBundle } from '../services/api';
import { useCart } from '../contexts/CartContext';

const CodeBundleDetail: React.FC = () => {
  const { collectionSlug, codebundleSlug } = useParams<{ collectionSlug: string; codebundleSlug: string }>();
  const navigate = useNavigate();
  const [codebundle, setCodebundle] = useState<CodeBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const { addToCart, removeFromCart, isInCart } = useCart();
  const [error, setError] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState(0);
  const [tasksTab, setTasksTab] = useState(0);
  const [expandedVars, setExpandedVars] = useState<{ [key: number]: boolean }>({});

  useEffect(() => {
    const fetchData = async () => {
      if (!collectionSlug || !codebundleSlug) return;
      
      try {
        const codebundleData = await apiService.getCodeBundleBySlug(collectionSlug, codebundleSlug);
        setCodebundle(codebundleData);
      } catch (err) {
        setError('Failed to load codebundle');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [collectionSlug, codebundleSlug]);

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

        {/* Action Buttons */}
        <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant={isInCart(codebundle.id) ? "outlined" : "contained"}
            color={isInCart(codebundle.id) ? "error" : "primary"}
            startIcon={isInCart(codebundle.id) ? <RemoveIcon /> : <AddIcon />}
            onClick={() => {
              if (isInCart(codebundle.id)) {
                removeFromCart(codebundle.id);
              } else {
                addToCart(codebundle);
              }
            }}
          >
            {isInCart(codebundle.id) ? "Remove from Configuration" : "Add to Configuration"}
          </Button>
          
          <Button
            variant="outlined"
            color="primary"
            startIcon={
              <Avatar 
                src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png"
                sx={{ 
                  width: 20, 
                  height: 20, 
                  backgroundColor: 'transparent'
                }}
              />
            }
            onClick={() => {
              // Create context string with codebundle details
              const context = `I have a question about the "${codebundle.display_name}" CodeBundle from the ${codebundle.codecollection?.name || 'unknown'} collection.\n\nCodeBundle Details:\n- Description: ${codebundle.description || 'N/A'}\n- Platform: ${codebundle.discovery_platform || 'N/A'}\n- Tasks: ${codebundle.task_count || 0}\n- Access Level: ${codebundle.access_level || 'N/A'}`;
              
              navigate('/chat', { 
                state: { 
                  initialQuery: context,
                  codebundleContext: {
                    name: codebundle.display_name,
                    slug: codebundle.slug,
                    collectionSlug: codebundle.codecollection?.slug,
                    description: codebundle.description,
                    tasks: codebundle.tasks,
                    platform: codebundle.discovery_platform,
                    accessLevel: codebundle.access_level,
                    iamRequirements: codebundle.minimum_iam_requirements
                  }
                } 
              });
            }}
          >
            Ask Eager Edgar
          </Button>
        </Box>

      </Box>

      <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Sidebar - Left (Upbound style) */}
        <Box sx={{ flex: '0 0 280px', minWidth: { xs: '100%', md: 280 } }}>
          
          {/* Support Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <VerifiedIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                  Support
                </Typography>
              </Box>
              
              {codebundle.codecollection?.git_url && codebundle.codecollection.git_url.includes('runwhen-contrib') ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                    RunWhen Supported
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    Community
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Languages / Tags Section */}
          {codebundle.support_tags && codebundle.support_tags.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <LanguageIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                    Tags
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {codebundle.support_tags.map((tag, index) => (
                    <Chip
                      key={index}
                      label={tag}
                      size="small"
                      sx={{ fontSize: '0.7rem', height: 20 }}
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Configuration Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <CodeIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                  Configuration
                </Typography>
              </Box>
              
              {codebundle.configuration_type?.platform && codebundle.configuration_type.platform !== 'Unknown' && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Platform
                  </Typography>
                  <Chip 
                    label={codebundle.configuration_type.platform.toUpperCase()} 
                    size="small" 
                    color="primary"
                    sx={{ fontWeight: 600 }}
                  />
                </Box>
              )}
              
              {/* Auto-Discovery Status */}
              {codebundle.configuration_type && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Auto-Discovery
                  </Typography>
                  {codebundle.configuration_type.has_generation_rules ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                        Enabled
                      </Typography>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <WarningIcon sx={{ fontSize: '1rem', color: 'warning.main' }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                        Manual Configuration Only
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
              
              {codebundle.configuration_type?.resource_types && codebundle.configuration_type.resource_types.length > 0 && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Resource Types
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {codebundle.configuration_type.resource_types.map((type, index) => (
                      <Chip 
                        key={index}
                        label={type} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem', height: 20 }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
              
              {codebundle.configuration_type?.level_of_detail && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Level of Detail
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {codebundle.configuration_type.level_of_detail}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Security & Access Section */}
          {(codebundle.access_level !== 'unknown' || 
            (codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0)) && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <ShieldIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                    Security & Access
                  </Typography>
                </Box>
                
                {codebundle.access_level !== 'unknown' && (
                  <Box sx={{ mb: 1.5 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      Access Level
                    </Typography>
                    <Chip 
                      label={codebundle.access_level} 
                      size="small"
                      color={
                        codebundle.access_level === 'read-only' ? 'success' :
                        codebundle.access_level === 'read-write' ? 'warning' : 'default'
                      }
                      sx={{ fontWeight: 600 }}
                    />
                  </Box>
                )}
                
                {codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0 && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      IAM Requirements ({codebundle.minimum_iam_requirements.length})
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {codebundle.minimum_iam_requirements.map((req, index) => (
                        <Chip 
                          key={index}
                          label={req} 
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem', height: 20 }}
                        />
                      ))}
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {/* Data Classification Section */}
          {codebundle.data_classifications && Object.keys(codebundle.data_classifications).length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <StorageIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                    Data Classification
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                  {Object.entries(codebundle.data_classifications).map(([tag, info]) => {
                    const isConfig = tag === 'data:config';
                    const isLogs = tag.startsWith('data:logs');
                    const chipColor = isConfig ? 'info' : isLogs ? 'warning' : 'default';
                    const tagLabel = tag.replace('data:', '');
                    return (
                      <Tooltip key={tag} title={`${info.label} — ${info.count} task${info.count !== 1 ? 's' : ''}`}>
                        <Chip
                          label={tagLabel}
                          size="small"
                          color={chipColor as any}
                          variant="outlined"
                          sx={{ fontWeight: 600, fontSize: '0.75rem' }}
                        />
                      </Tooltip>
                    );
                  })}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Details Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <CodeIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                  Details
                </Typography>
              </Box>
              
              <Box sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <PersonIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Author
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {codebundle.author}
                </Typography>
              </Box>

              <Box sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <CalendarIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Last Updated
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {new Date(codebundle.git_updated_at || codebundle.updated_at).toLocaleDateString()}
                </Typography>
              </Box>

              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <CodeIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Total Tasks
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {(codebundle.task_count || 0) + (codebundle.sli_count || 0)}
                  {codebundle.task_count > 0 && codebundle.sli_count > 0 && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      ({codebundle.task_count} TaskSet + {codebundle.sli_count} SLI)
                    </Typography>
                  )}
                  {codebundle.task_count > 0 && !codebundle.sli_count && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      (TaskSet)
                    </Typography>
                  )}
                  {!codebundle.task_count && codebundle.sli_count > 0 && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      (SLI)
                    </Typography>
                  )}
                </Typography>
              </Box>
            </CardContent>
          </Card>

          {/* Source Code Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <GitHubIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: '0.875rem' }}>
                  Source Code
                </Typography>
              </Box>
              
              {codebundle.codecollection && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Collection
                  </Typography>
                  <Link 
                    to={`/collections/${codebundle.codecollection.slug}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <Typography variant="body2" color="primary" sx={{ fontWeight: 500 }}>
                      {codebundle.codecollection.name}
                    </Typography>
                  </Link>
                </Box>
              )}
              
              {codebundle.codecollection?.git_url && (
                <Button
                  variant="outlined"
                  startIcon={<GitHubIcon />}
                  href={`${codebundle.codecollection.git_url}/tree/main/codebundles/${codebundle.slug}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  fullWidth
                  size="small"
                  sx={{ textTransform: 'none', fontSize: '0.8rem' }}
                >
                  View on GitHub
                </Button>
              )}
            </CardContent>
          </Card>

        </Box>

        {/* Main Content - Right */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {/* Overview - Above Tabs */}
          {codebundle.doc && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                Overview
              </Typography>
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                {codebundle.doc}
              </Typography>
            </Box>
          )}

          {/* Main Tabs */}
          <Card sx={{ mb: 4 }}>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={mainTab} onChange={(e, newValue) => setMainTab(newValue)}>
                <Tab label="Description" sx={{ textTransform: 'none' }} />
                <Tab label="Tasks" sx={{ textTransform: 'none' }} />
                <Tab label="Variables" sx={{ textTransform: 'none' }} />
                <Tab label="Security" sx={{ textTransform: 'none' }} />
                <Tab label="Updates" sx={{ textTransform: 'none' }} />
              </Tabs>
            </Box>
            
            {/* Description Tab */}
            {mainTab === 0 && (
              <CardContent>
                {/* AI Enhanced Description */}
                {codebundle.ai_enhanced_description && (
                  <Box sx={{ mb: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <AutoAwesomeIcon sx={{ fontSize: '1.2rem', color: 'primary.main', mt: 0.5 }} />
                      <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', flex: 1 }}>
                        {codebundle.ai_enhanced_description}
                      </Typography>
                    </Box>
                  </Box>
                )}
                
                {/* Link to README */}
                {codebundle.readme && codebundle.codecollection?.git_url && (
                  <Box sx={{ mt: codebundle.ai_enhanced_description ? 0 : 0, pt: codebundle.ai_enhanced_description ? 3 : 0, borderTop: codebundle.ai_enhanced_description ? '1px solid' : 'none', borderColor: 'divider' }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Author README:
                    </Typography>
                    <Typography variant="body2">
                      <a 
                        href={`${codebundle.codecollection.git_url}/blob/main/codebundles/${codebundle.slug}/README.md`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#1976d2', textDecoration: 'none' }}
                      >
                        View README on GitHub →
                      </a>
                    </Typography>
                  </Box>
                )}
                
                {!codebundle.ai_enhanced_description && !codebundle.readme && (
                  <Typography variant="body2" color="text.secondary">
                    No description available.
                  </Typography>
                )}
              </CardContent>
            )}
            
            {/* Tasks Tab */}
            {mainTab === 1 && (
              <CardContent>
                {/* Tasks & SLI Tabs */}
                {((codebundle.tasks && codebundle.tasks.length > 0) || (codebundle.slis && codebundle.slis.length > 0)) ? (
                  <Box>
                    <Box sx={{ borderBottom: 1, borderColor: 'divider', mx: -2, px: 2 }}>
                      <Tabs value={tasksTab} onChange={(e, newValue) => setTasksTab(newValue)}>
                        {codebundle.tasks && codebundle.tasks.length > 0 && (
                          <Tab 
                            label={
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                TaskSet ({codebundle.tasks.length})
                                <Tooltip 
                                  title="TaskSet contains automation tasks for troubleshooting, operations, and maintenance. These are typically triggered on-demand or by specific conditions."
                                  arrow
                                >
                                  <InfoIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                                </Tooltip>
                              </Box>
                            }
                          />
                        )}
                        {codebundle.slis && codebundle.slis.length > 0 && (
                          <Tab 
                            label={
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                SLI ({codebundle.slis.length})
                                <Tooltip 
                                  title="SLI (Service Level Indicator) tasks are automated checks that run continuously to measure and monitor the health and performance of your services."
                                  arrow
                                >
                                  <InfoIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                                </Tooltip>
                              </Box>
                            }
                          />
                        )}
                      </Tabs>
                    </Box>
                    
                    {/* TaskSet Tab Panel */}
                    {codebundle.tasks && codebundle.tasks.length > 0 && tasksTab === 0 && (
                      <Box sx={{ mt: 2 }}>
                        <List>
                          {codebundle.tasks.map((task, index) => {
                            const taskName = typeof task === 'string' ? task : task.name;
                            const taskDoc = typeof task === 'object' ? task.doc : undefined;
                            const taskTags = typeof task === 'object' ? (task as any).tags || [] : [];
                            const dataTags = taskTags.filter((t: string) => t.startsWith('data:'));
                            return (
                              <React.Fragment key={index}>
                                <ListItem sx={{ alignItems: 'flex-start' }}>
                                  <ListItemText 
                                    primary={
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                        <Typography variant="body1">{taskName}</Typography>
                                        {dataTags.map((dt: string) => (
                                          <Chip
                                            key={dt}
                                            label={dt.replace('data:', '')}
                                            size="small"
                                            color={dt === 'data:config' ? 'info' : 'warning'}
                                            variant="outlined"
                                            sx={{ fontSize: '0.65rem', height: 18, fontWeight: 600 }}
                                          />
                                        ))}
                                      </Box>
                                    }
                                    secondary={taskDoc}
                                  />
                                </ListItem>
                                {index < codebundle.tasks!.length - 1 && <Divider />}
                              </React.Fragment>
                            );
                          })}
                        </List>
                      </Box>
                    )}
                    
                    {/* SLI Tab Panel */}
                    {codebundle.slis && codebundle.slis.length > 0 && tasksTab === (codebundle.tasks && codebundle.tasks.length > 0 ? 1 : 0) && (
                      <Box sx={{ mt: 2 }}>
                        <List>
                          {codebundle.slis.map((sli, index) => (
                            <React.Fragment key={index}>
                              <ListItem>
                                <ListItemText 
                                  primary={typeof sli === 'string' ? sli : sli.name}
                                  secondary={typeof sli === 'object' ? sli.doc : undefined}
                                />
                              </ListItem>
                              {index < codebundle.slis!.length - 1 && <Divider />}
                            </React.Fragment>
                          ))}
                        </List>
                      </Box>
                    )}
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No tasks or SLIs defined for this codebundle.
                  </Typography>
                )}
              </CardContent>
            )}
            
            {/* Configuration Tab */}
            {mainTab === 2 && (
              <CardContent>
                {/* User Variables */}
                {codebundle.user_variables && codebundle.user_variables.length > 0 ? (
                  <Box>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                      Configuration Variables
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      These variables can be overridden or tuned as needed:
                    </Typography>
                    <TableContainer component={Paper} variant="outlined">
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 600 }}>Variable</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Default</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {codebundle.user_variables.map((variable, index) => (
                            <TableRow key={index} hover>
                              <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                                {variable.name}
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.875rem' }}>
                                {variable.description || '-'}
                              </TableCell>
                              <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                                {variable.default || variable.example || '-'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                ) : (
                  <Box sx={{ mt: 4, p: 3, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <InfoIcon sx={{ fontSize: '1.2rem', color: 'info.main', mt: 0.25 }} />
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                          No User Variables Documented
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          This CodeBundle may not require user-configured variables, or they have not been extracted yet. 
                          Check the source code on GitHub for the complete configuration requirements.
                        </Typography>
                        {codebundle.codecollection?.git_url && (
                          <Button
                            variant="outlined"
                            size="small"
                            startIcon={<GitHubIcon />}
                            href={`${codebundle.codecollection.git_url}/tree/main/codebundles/${codebundle.slug}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            sx={{ mt: 2, textTransform: 'none' }}
                          >
                            View Source on GitHub
                          </Button>
                        )}
                      </Box>
                    </Box>
                  </Box>
                )}
              </CardContent>
            )}
            
            {/* Security Tab */}
            {mainTab === 3 && (
              <CardContent>
                <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
                  Security & Access Requirements
                </Typography>
                
                {/* Access Level */}
                {codebundle.access_level && codebundle.access_level !== 'unknown' && (
                  <Box sx={{ mb: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <SecurityIcon sx={{ fontSize: '1.2rem', color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        Access Level
                      </Typography>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                      <Chip 
                        label={codebundle.access_level.toUpperCase()} 
                        size="small"
                        color={
                          codebundle.access_level === 'read-only' ? 'success' :
                          codebundle.access_level === 'read-write' ? 'warning' : 'default'
                        }
                        sx={{ fontWeight: 600, fontSize: '0.75rem' }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {codebundle.access_level === 'read-only' 
                        ? 'This CodeBundle requires read-only access to resources. It will not make changes to your infrastructure.'
                        : codebundle.access_level === 'read-write'
                        ? 'This CodeBundle requires read-write access and may modify resources in your infrastructure.'
                        : 'Access level requirements for this CodeBundle.'}
                    </Typography>
                  </Box>
                )}
                
                {/* IAM Requirements */}
                {codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0 && (
                  <Box sx={{ mb: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <ShieldIcon sx={{ fontSize: '1.2rem', color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        IAM Requirements
                      </Typography>
                      <Chip 
                        label={`${codebundle.minimum_iam_requirements.length} permission${codebundle.minimum_iam_requirements.length !== 1 ? 's' : ''}`} 
                        size="small" 
                        color="primary"
                        sx={{ ml: 1 }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      The following IAM permissions are required to execute this CodeBundle:
                    </Typography>
                    <Box 
                      component="ul" 
                      sx={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        gap: 0.5, 
                        pl: 2,
                        m: 0,
                        listStyleType: 'disc'
                      }}
                    >
                      {codebundle.minimum_iam_requirements.map((req, index) => (
                        <Box 
                          component="li" 
                          key={index}
                          sx={{ 
                            pl: 0.5
                          }}
                        >
                          <Typography 
                            variant="body2" 
                            sx={{ 
                              fontFamily: 'monospace', 
                              fontSize: '0.875rem',
                              wordBreak: 'break-all'
                            }}
                          >
                            {req}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                )}
                
                {/* Additional Security Information */}
                <Box sx={{ mt: 4, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                    <InfoIcon sx={{ fontSize: '1rem', color: 'info.main', mt: 0.25 }} />
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                        Security Best Practices
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Always follow the principle of least privilege when granting IAM permissions. 
                        Review these requirements with your security team before deployment.
                      </Typography>
                    </Box>
                  </Box>
                </Box>
                
                {!codebundle.access_level && (!codebundle.minimum_iam_requirements || codebundle.minimum_iam_requirements.length === 0) && (
                  <Alert severity="info">
                    No specific security requirements have been documented for this CodeBundle.
                  </Alert>
                )}
              </CardContent>
            )}
            
            {/* Updates Tab */}
            {mainTab === 4 && (
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                  Version History
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {/* Latest Update */}
                  <Box sx={{ pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Chip 
                        label="Current" 
                        size="small" 
                        color="primary"
                        sx={{ fontWeight: 600 }}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {new Date(codebundle.git_updated_at || codebundle.updated_at).toLocaleDateString('en-US', { 
                          year: 'numeric', 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      <strong>Tasks:</strong> {codebundle.task_count} task{codebundle.task_count !== 1 ? 's' : ''}
                      {codebundle.tasks && codebundle.tasks.length > 0 && ` (${codebundle.tasks.length} TaskSet)`}
                      {codebundle.slis && codebundle.slis.length > 0 && ` + ${codebundle.slis.length} SLI`}
                    </Typography>
                    {codebundle.configuration_type?.platform && codebundle.configuration_type.platform !== 'Unknown' && (
                      <Typography variant="body2">
                        <strong>Platform:</strong> {codebundle.configuration_type.platform}
                      </Typography>
                    )}
                    </Box>

                    {/* Git Information */}
                  {codebundle.codecollection?.git_url && (
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                        Source Repository
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        View the complete change history and commit log on GitHub.
                      </Typography>
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<GitHubIcon />}
                        href={`${codebundle.codecollection.git_url}/commits/main/codebundles/${codebundle.slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ textTransform: 'none' }}
                      >
                        View Commit History
                      </Button>
                    </Box>
                  )}
                </Box>
              </CardContent>
            )}
          </Card>

          {/* Enhanced Task Details */}
          {codebundle.ai_enhanced_metadata?.enhanced_tasks && 
           codebundle.ai_enhanced_metadata.enhanced_tasks.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <AutoAwesomeIcon sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                    Enhanced Task Details ({codebundle.ai_enhanced_metadata.enhanced_tasks.length})
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {codebundle.ai_enhanced_metadata.enhanced_tasks.map((task, index) => (
                    <Card key={index} variant="outlined">
                      <CardContent sx={{ p: 2 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                          {task.name}
                        </Typography>
                        
                        {task.ai_purpose && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Purpose:
                            </Typography>
                            <Typography variant="body2">
                              {task.ai_purpose}
                            </Typography>
                          </Box>
                        )}
                        
                        {task.ai_function && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Function:
                            </Typography>
                            <Typography variant="body2">
                              {task.ai_function}
                            </Typography>
                          </Box>
                        )}
                        
                        {task.ai_requirements && task.ai_requirements.length > 0 && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Requirements:
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                              {task.ai_requirements.map((req, reqIndex) => (
                                <Chip 
                                  key={reqIndex}
                                  label={req} 
                                  size="small"
                                  variant="outlined"
                                  color="secondary"
                                />
                              ))}
                            </Box>
                          </Box>
                        )}
                        
                        {task.tags && task.tags.length > 0 && (
                          <Box>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Tags:
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                              {task.tags.map((tag, tagIndex) => (
                                <Chip 
                                  key={tagIndex}
                                  label={tag} 
                                  size="small"
                                  variant="outlined"
                                />
                              ))}
                            </Box>
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}
        </Box>

      </Box>
    </Container>
  );
};

export default CodeBundleDetail;