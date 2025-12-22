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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  GridLegacy as Grid,
} from '@mui/material';
import { 
  GitHub as GitHubIcon, 
  Launch as LaunchIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  ExpandMore as ExpandMoreIcon,
  AutoAwesome as AutoAwesomeIcon,
  Security as SecurityIcon,
  Description as DescriptionIcon
} from '@mui/icons-material';
import { useParams, Link } from 'react-router-dom';
import { apiService, CodeBundle } from '../services/api';
import { useCart } from '../contexts/CartContext';

const CodeBundleDetail: React.FC = () => {
  const { collectionSlug, codebundleSlug } = useParams<{ collectionSlug: string; codebundleSlug: string }>();
  const [codebundle, setCodebundle] = useState<CodeBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const { addToCart, removeFromCart, isInCart } = useCart();
  const [error, setError] = useState<string | null>(null);

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
          
          {codebundle.codecollection?.git_url && (
            <Button
              variant="outlined"
              startIcon={<GitHubIcon />}
              href={codebundle.codecollection.git_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View Repository
            </Button>
          )}
          
          {codebundle.runbook_source_url && (
            <Button
              variant="outlined"
              startIcon={<LaunchIcon />}
              href={codebundle.runbook_source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View Source
            </Button>
          )}
        </Box>

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

          {/* TaskSet Tasks */}
          {codebundle.tasks && codebundle.tasks.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" sx={{ mb: 2, color: 'primary.main', fontWeight: 'bold' }}>
                  TaskSet ({codebundle.tasks.length})
                </Typography>
                <List>
                  {codebundle.tasks.map((task, index) => (
                    <React.Fragment key={index}>
                      <ListItem>
                        <ListItemText 
                          primary={typeof task === 'string' ? task : task.name}
                          secondary={typeof task === 'object' ? task.doc : undefined}
                        />
                      </ListItem>
                      {index < codebundle.tasks!.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {/* SLI Tasks */}
          {codebundle.slis && codebundle.slis.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" sx={{ mb: 2, color: 'secondary.main', fontWeight: 'bold' }}>
                  SLI ({codebundle.slis.length})
                </Typography>
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
              </CardContent>
            </Card>
          )}

          {/* Additional Details */}
          {(codebundle.readme ||
            codebundle.ai_enhanced_description || 
            codebundle.access_level !== 'unknown' || 
            (codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0) ||
            (codebundle.ai_enhanced_metadata?.enhanced_tasks && codebundle.ai_enhanced_metadata.enhanced_tasks.length > 0)) && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                  <AutoAwesomeIcon sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                    Additional Details
                  </Typography>
                </Box>

                {/* README.md Content */}
                {codebundle.readme && (
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <DescriptionIcon sx={{ mr: 1, fontSize: '1.2rem' }} />
                        <Typography variant="subtitle1">README</Typography>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography 
                        variant="body2" 
                        component="pre"
                        sx={{ 
                          whiteSpace: 'pre-wrap', 
                          fontFamily: 'inherit',
                          m: 0 
                        }}
                      >
                        {codebundle.readme}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Enhanced Description */}
                {codebundle.ai_enhanced_description && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <DescriptionIcon sx={{ mr: 1, fontSize: '1.2rem' }} />
                        <Typography variant="subtitle1">Enhanced Description</Typography>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                        {codebundle.ai_enhanced_description}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Security & Access */}
                {(codebundle.access_level !== 'unknown' || 
                  (codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0)) && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <SecurityIcon sx={{ mr: 1, fontSize: '1.2rem' }} />
                        <Typography variant="subtitle1">Security & Access</Typography>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {codebundle.access_level !== 'unknown' && (
                          <Box>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              <strong>Access Level:</strong>
                            </Typography>
                            <Chip 
                              label={codebundle.access_level} 
                              size="small"
                              color={
                                codebundle.access_level === 'read-only' ? 'success' :
                                codebundle.access_level === 'read-write' ? 'warning' : 'default'
                              }
                            />
                          </Box>
                        )}
                        {codebundle.minimum_iam_requirements && codebundle.minimum_iam_requirements.length > 0 && (
                          <Box>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              <strong>Minimum IAM Requirements:</strong>
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                              {codebundle.minimum_iam_requirements.map((requirement, index) => (
                                <Chip 
                                  key={index}
                                  label={requirement} 
                                  size="small"
                                  variant="outlined"
                                />
                              ))}
                            </Box>
                          </Box>
                        )}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Enhanced Task Details */}
                {codebundle.ai_enhanced_metadata?.enhanced_tasks && 
                 codebundle.ai_enhanced_metadata.enhanced_tasks.length > 0 && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle1">
                        Enhanced Task Details ({codebundle.ai_enhanced_metadata.enhanced_tasks.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
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
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Enhancement Metadata */}
                {codebundle.ai_enhanced_metadata && (
                  codebundle.ai_enhanced_metadata.model_used || 
                  codebundle.ai_enhanced_metadata.enhanced_at ||
                  codebundle.last_enhanced
                ) && (
                  <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      {codebundle.ai_enhanced_metadata.enhanced_at && (
                        <>Enhanced: {new Date(codebundle.ai_enhanced_metadata.enhanced_at).toLocaleString()}</>
                      )}
                      {!codebundle.ai_enhanced_metadata.enhanced_at && codebundle.last_enhanced && (
                        <>Enhanced: {new Date(codebundle.last_enhanced).toLocaleString()}</>
                      )}
                      {codebundle.ai_enhanced_metadata.model_used && (
                        <> • Model: {codebundle.ai_enhanced_metadata.model_used}</>
                      )}
                      {codebundle.ai_enhanced_metadata.service_provider && (
                        <> • Provider: {codebundle.ai_enhanced_metadata.service_provider}</>
                      )}
                    </Typography>
                  </Box>
                )}
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

          {/* Configuration Type Information */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Configuration Type
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Auto-Discovered
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {codebundle.configuration_type?.has_generation_rules ? (
                    <>
                      <CheckCircleIcon color="success" fontSize="small" />
                      <Typography variant="body1" color="success.main">
                        Yes
                      </Typography>
                    </>
                  ) : (
                    <>
                      <CancelIcon color="error" fontSize="small" />
                      <Typography variant="body1" color="error.main">
                        No
                      </Typography>
                    </>
                  )}
                </Box>
              </Box>

              {codebundle.configuration_type?.has_generation_rules && (
                <>
                  {codebundle.configuration_type.platform && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Platform
                      </Typography>
                      <Chip 
                        label={codebundle.configuration_type.platform.toUpperCase()} 
                        size="small" 
                        color="primary" 
                        variant="outlined" 
                      />
                    </Box>
                  )}

                  {codebundle.configuration_type.resource_types && codebundle.configuration_type.resource_types.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Resource Types
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {codebundle.configuration_type.resource_types.map((type, index) => (
                          <Chip 
                            key={index}
                            label={type} 
                            size="small" 
                            variant="outlined" 
                          />
                        ))}
                      </Box>
                    </Box>
                  )}

                  {codebundle.configuration_type.templates && codebundle.configuration_type.templates.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Templates ({codebundle.configuration_type.templates.length})
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                        {codebundle.configuration_type.templates.map((template, index) => (
                          <Typography key={index} variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {template}
                          </Typography>
                        ))}
                      </Box>
                    </Box>
                  )}

                  {codebundle.configuration_type.level_of_detail && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Level of Detail
                      </Typography>
                      <Typography variant="body1">
                        {codebundle.configuration_type.level_of_detail}
                      </Typography>
                    </Box>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {codebundle.codecollection && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Collection
                </Typography>
                <Link 
                  to={`/collections/${codebundle.codecollection.slug}`}
                  style={{ 
                    color: '#2f80ed', 
                    textDecoration: 'none'
                  }}
                >
                  <Typography variant="body1" color="primary">
                    {codebundle.codecollection.name}
                  </Typography>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* GitHub Repository Link */}
          {codebundle.codecollection?.git_url && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Repository
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<GitHubIcon />}
                  href={`${codebundle.codecollection.git_url}/tree/main/codebundles/${codebundle.slug}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  fullWidth
                  sx={{ mb: 1 }}
                >
                  View on GitHub
                </Button>
                {codebundle.runbook_source_url && (
                  <Button
                    variant="text"
                    startIcon={<LaunchIcon />}
                    href={codebundle.runbook_source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    fullWidth
                    size="small"
                  >
                    View Runbook Source
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </Box>

      </Box>
    </Container>
  );
};

export default CodeBundleDetail;