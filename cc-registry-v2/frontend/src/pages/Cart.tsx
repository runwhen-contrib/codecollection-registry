import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Divider,
  Alert,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tooltip,
  Collapse,
} from '@mui/material';
import Editor from '@monaco-editor/react';
import {
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ContentCopy as ContentCopyIcon,
  GitHub as GitHubIcon,
  Launch as LaunchIcon,
  Clear as ClearIcon,
  ShoppingCart as ShoppingCartIcon,
  Code as CodeIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { useCart } from '../contexts/CartContext';

const Cart: React.FC = () => {
  const { items, removeFromCart, clearCart, getRepositoryConfigs } = useCart();
  const repositoryConfigs = getRepositoryConfigs();
  const [showYamlEditor, setShowYamlEditor] = useState(true);

  const handleCopyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // Could add a toast notification here
  };

  const generateConfigYaml = () => {
    return `# RunWhen Configuration
# Total CodeBundles: ${items.length}
# Total Repositories: ${repositoryConfigs.length}

codeCollections:${repositoryConfigs.map(repo => `
- repoURL: ${repo.git_url}
  tag: ${repo.git_ref}`).join('')}

# CodeBundles included:${repositoryConfigs.map(repo => `
# ${repo.collection_name} (${repo.git_ref}):${repo.codebundles.map(item => `
#   - ${item.codebundle.display_name || item.codebundle.name} (${item.codebundle.task_count} tasks, ${item.codebundle.sli_count} SLIs)`).join('')}`).join('')}
`;
  };

  if (items.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <ShoppingCartIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h4" gutterBottom color="text.secondary">
            Your Configuration Builder is Empty
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Add CodeBundles to your collection to build a configuration
          </Typography>
          <Button
            component={Link}
            to="/codebundles"
            variant="contained"
            size="large"
          >
            Browse CodeBundles
          </Button>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Configuration Builder
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {items.length} CodeBundle{items.length !== 1 ? 's' : ''} from {repositoryConfigs.length} repositor{repositoryConfigs.length !== 1 ? 'ies' : 'y'}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<ClearIcon />}
            onClick={clearCart}
          >
            Clear All
          </Button>
          <Button
            variant="contained"
            startIcon={<ContentCopyIcon />}
            onClick={() => handleCopyToClipboard(generateConfigYaml())}
          >
            Copy Configuration
          </Button>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Repository Configuration */}
        <Box sx={{ flex: 2 }}>
          <Typography variant="h5" gutterBottom>
            Repository Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            These are the repositories and branches you'll need access to:
          </Typography>

          {repositoryConfigs.map((repo, index) => (
            <Accordion key={repo.collection_slug} defaultExpanded={index === 0}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {repo.collection_name}
                  </Typography>
                  <Chip 
                    label={`${repo.codebundles.length} CodeBundle${repo.codebundles.length !== 1 ? 's' : ''}`} 
                    size="small" 
                    color="primary" 
                  />
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Repository URL:
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {repo.git_url}
                    </Typography>
                    <Tooltip title="Open in GitHub">
                      <IconButton
                        size="small"
                        href={repo.git_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <GitHubIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Copy URL">
                      <IconButton
                        size="small"
                        onClick={() => handleCopyToClipboard(repo.git_url)}
                      >
                        <ContentCopyIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Branch/Ref:
                    </Typography>
                    <Chip label={repo.git_ref} size="small" variant="outlined" />
                  </Box>
                </Box>

                <Typography variant="subtitle2" gutterBottom>
                  CodeBundles ({repo.codebundles.length}):
                </Typography>
                <List dense>
                  {repo.codebundles.map((item) => (
                    <ListItem key={item.codebundle.id} divider>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Link
                              to={`/collections/${repo.collection_slug}/codebundles/${item.codebundle.slug}`}
                              style={{ textDecoration: 'none', color: 'inherit' }}
                            >
                              <Typography variant="body2" sx={{ '&:hover': { color: 'primary.main' } }}>
                                {item.codebundle.display_name || item.codebundle.name}
                              </Typography>
                            </Link>
                            {item.codebundle.discovery?.is_discoverable && (
                              <Chip 
                                label={item.codebundle.discovery.platform?.toUpperCase() || 'DISCOVERABLE'} 
                                size="small" 
                                color="success" 
                                variant="outlined" 
                              />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                            <Chip label={`${item.codebundle.task_count} Tasks`} size="small" variant="outlined" />
                            {item.codebundle.sli_count > 0 && (
                              <Chip label={`${item.codebundle.sli_count} SLIs`} size="small" variant="outlined" />
                            )}
                            <Typography variant="caption" color="text.secondary">
                              Added {new Date(item.addedAt).toLocaleDateString()}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          aria-label="remove"
                          onClick={() => removeFromCart(item.codebundle.id)}
                          size="small"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>

        {/* Summary and Actions */}
        <Box sx={{ flex: 1, minWidth: { xs: '100%', md: '300px' } }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Configuration Summary
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Total CodeBundles
                </Typography>
                <Typography variant="h4" color="primary">
                  {items.length}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Repositories Required
                </Typography>
                <Typography variant="h4" color="primary">
                  {repositoryConfigs.length}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Total Tasks
                </Typography>
                <Typography variant="h4" color="primary">
                  {items.reduce((sum, item) => sum + item.codebundle.task_count, 0)}
                </Typography>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary">
                  Total SLIs
                </Typography>
                <Typography variant="h4" color="primary">
                  {items.reduce((sum, item) => sum + item.codebundle.sli_count, 0)}
                </Typography>
              </Box>

              <Divider sx={{ mb: 2 }} />

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Discoverable CodeBundles
                </Typography>
                <Typography variant="body1">
                  {items.filter(item => item.codebundle.discovery?.is_discoverable).length} of {items.length}
                </Typography>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Platforms
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {Array.from(new Set(
                    items
                      .filter(item => item.codebundle.discovery?.platform)
                      .map(item => item.codebundle.discovery!.platform!)
                  )).map(platform => (
                    <Chip 
                      key={platform} 
                      label={platform.toUpperCase()} 
                      size="small" 
                      color="primary" 
                      variant="outlined" 
                    />
                  ))}
                </Box>
              </Box>

              <Button
                fullWidth
                variant="contained"
                startIcon={<ContentCopyIcon />}
                onClick={() => handleCopyToClipboard(generateConfigYaml())}
                sx={{ mb: 1 }}
              >
                Copy Configuration YAML
              </Button>

              <Button
                fullWidth
                variant="outlined"
                component={Link}
                to="/codebundles"
              >
                Add More CodeBundles
              </Button>
            </CardContent>
          </Card>

          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Next Steps:</strong><br />
              1. Copy the configuration YAML<br />
              2. Clone the required repositories<br />
              3. Use the RunWhen CLI to deploy your selected CodeBundles
            </Typography>
          </Alert>
        </Box>
      </Box>

      {/* YAML Configuration Editor */}
      <Box sx={{ mt: 4 }}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CodeIcon />
                <Typography variant="h5">
                  Configuration YAML
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={showYamlEditor ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  onClick={() => setShowYamlEditor(!showYamlEditor)}
                >
                  {showYamlEditor ? 'Hide' : 'Show'} Editor
                </Button>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<ContentCopyIcon />}
                  onClick={() => handleCopyToClipboard(generateConfigYaml())}
                >
                  Copy YAML
                </Button>
              </Box>
            </Box>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              This configuration can be used with the RunWhen CLI to deploy your selected CodeBundles.
            </Typography>

            <Collapse in={showYamlEditor}>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                <Editor
                  height="400px"
                  defaultLanguage="yaml"
                  value={generateConfigYaml()}
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    fontSize: 14,
                    lineNumbers: 'on',
                    renderWhitespace: 'boundary',
                    wordWrap: 'on',
                    theme: 'vs-light',
                    automaticLayout: true,
                    folding: true,
                    lineDecorationsWidth: 10,
                    lineNumbersMinChars: 3,
                    glyphMargin: false
                  }}
                  loading={
                    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
                      <Typography variant="body2" color="text.secondary">
                        Loading YAML editor...
                      </Typography>
                    </Box>
                  }
                />
              </Box>
            </Collapse>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default Cart;
