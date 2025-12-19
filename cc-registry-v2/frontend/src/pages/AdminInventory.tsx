import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  GridLegacy as Grid,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Visibility as ViewIcon,
  FilterList as FilterIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Storage as StorageIcon,
  SmartToy as AIIcon,
  Security as SecurityIcon,
  Task as TaskIcon,
  Code as CodeIcon
} from '@mui/icons-material';
import { apiService } from '../services/api';

interface CodeBundleInventoryItem {
  id: number;
  name: string;
  slug: string;
  display_name?: string;
  description?: string;
  doc?: string;
  author?: string;
  collection_id: number;
  collection_name: string;
  collection_slug: string;
  tasks: Array<{name: string; doc: string; tags: string[]} | string>;
  slis: Array<{name: string; doc: string; tags: string[]} | string>;
  task_count: number;
  sli_count: number;
  support_tags: string[];
  categories: string[];
  enhancement_status: string;
  ai_enhanced_description?: string;
  access_level: string;
  minimum_iam_requirements: string[];
  ai_enhanced_metadata: any;
  last_enhanced?: string;
  is_discoverable: boolean;
  discovery_platform?: string;
  discovery_resource_types: string[];
  created_at: string;
  updated_at?: string;
}

interface CollectionInventoryItem {
  id: number;
  name: string;
  slug: string;
  description?: string;
  owner?: string;
  owner_email?: string;
  git_url: string;
  git_ref: string;
  codebundle_count: number;
  total_tasks: number;
  total_slis: number;
  ai_enhancement_stats: any;
  created_at: string;
  updated_at?: string;
  last_synced?: string;
}

interface InventoryStats {
  collections: { total: number };
  codebundles: {
    total: number;
    enhancement_status: any;
    access_levels: any;
  };
  tasks: {
    total_tasks: number;
    total_slis: number;
  };
}

const AdminInventory: React.FC = () => {
  const [currentTab, setCurrentTab] = useState(0);
  const [codebundles, setCodebundles] = useState<CodeBundleInventoryItem[]>([]);
  const [collections, setCollections] = useState<CollectionInventoryItem[]>([]);
  const [stats, setStats] = useState<InventoryStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [collectionFilter, setCollectionFilter] = useState('');
  const [enhancementStatusFilter, setEnhancementStatusFilter] = useState('');
  const [accessLevelFilter, setAccessLevelFilter] = useState('');
  
  // Detail dialog
  const [selectedCodebundle, setSelectedCodebundle] = useState<CodeBundleInventoryItem | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  const token = 'admin-dev-token'; // In production, get from auth context

  useEffect(() => {
    loadData();
  }, [currentTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Always load stats
      const statsData = await apiService.getInventoryStats(token);
      setStats(statsData);

      if (currentTab === 0) {
        // Load codebundles
        const params: any = {
          limit: 100,
          offset: 0
        };
        
        if (searchTerm) params.search = searchTerm;
        if (collectionFilter) params.collection_slug = collectionFilter;
        if (enhancementStatusFilter) params.enhancement_status = enhancementStatusFilter;
        if (accessLevelFilter) params.access_level = accessLevelFilter;

        const data = await apiService.getInventoryCodebundles(token, params);
        setCodebundles(data);
      } else if (currentTab === 1) {
        // Load collections
        const data = await apiService.getInventoryCollections(token);
        setCollections(data);
      }
    } catch (err) {
      console.error('Error loading inventory data:', err);
      setError(`Failed to load data: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    loadData();
  };

  const clearFilters = () => {
    setSearchTerm('');
    setCollectionFilter('');
    setEnhancementStatusFilter('');
    setAccessLevelFilter('');
  };

  const openDetailDialog = (codebundle: CodeBundleInventoryItem) => {
    setSelectedCodebundle(codebundle);
    setDetailDialogOpen(true);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'pending': return 'warning';
      case 'processing': return 'info';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const getAccessLevelColor = (level: string) => {
    switch (level) {
      case 'read-only': return 'success';
      case 'read-write': return 'warning';
      case 'unknown': return 'default';
      default: return 'default';
    }
  };

  const TabPanel = ({ children, value, index }: any) => (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
          <StorageIcon sx={{ mr: 2 }} />
          Admin Inventory
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Detailed database view of CodeCollections and CodeBundles with AI enhancement data
        </Typography>
      </Box>

      {/* Statistics Cards */}
      {stats && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Collections
                </Typography>
                <Typography variant="h4">
                  {stats.collections.total}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  CodeBundles
                </Typography>
                <Typography variant="h4">
                  {stats.codebundles.total}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  {stats.codebundles.enhancement_status.completed} AI Enhanced
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Tasks
                </Typography>
                <Typography variant="h4">
                  {stats.tasks.total_tasks}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  {stats.tasks.total_slis} SLIs
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  AI Enhancement
                </Typography>
                <Typography variant="h4" color="success.main">
                  {Math.round((stats.codebundles.enhancement_status.completed / stats.codebundles.total) * 100)}%
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Completion Rate
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={currentTab} onChange={(e, newValue) => setCurrentTab(newValue)}>
          <Tab label="CodeBundles" icon={<CodeIcon />} />
          <Tab label="Collections" icon={<StorageIcon />} />
        </Tabs>
      </Box>

      {/* CodeBundles Tab */}
      <TabPanel value={currentTab} index={0}>
        {/* Filters */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <FilterIcon sx={{ mr: 1 }} />
              Filters
            </Typography>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} sm={6} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  label="Search"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  InputProps={{
                    endAdornment: (
                      <IconButton onClick={handleSearch} size="small">
                        <SearchIcon />
                      </IconButton>
                    )
                  }}
                />
              </Grid>
              <Grid item xs={12} sm={6} md={2}>
                <FormControl fullWidth size="small">
                  <InputLabel>Collection</InputLabel>
                  <Select
                    value={collectionFilter}
                    onChange={(e) => setCollectionFilter(e.target.value)}
                    label="Collection"
                  >
                    <MenuItem value="">All</MenuItem>
                    {collections.map((col) => (
                      <MenuItem key={col.slug} value={col.slug}>
                        {col.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} md={2}>
                <FormControl fullWidth size="small">
                  <InputLabel>Enhancement Status</InputLabel>
                  <Select
                    value={enhancementStatusFilter}
                    onChange={(e) => setEnhancementStatusFilter(e.target.value)}
                    label="Enhancement Status"
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="completed">Completed</MenuItem>
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="processing">Processing</MenuItem>
                    <MenuItem value="failed">Failed</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} md={2}>
                <FormControl fullWidth size="small">
                  <InputLabel>Access Level</InputLabel>
                  <Select
                    value={accessLevelFilter}
                    onChange={(e) => setAccessLevelFilter(e.target.value)}
                    label="Access Level"
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="read-only">Read Only</MenuItem>
                    <MenuItem value="read-write">Read Write</MenuItem>
                    <MenuItem value="unknown">Unknown</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Button
                  variant="outlined"
                  onClick={clearFilters}
                  sx={{ mr: 1 }}
                >
                  Clear
                </Button>
                <Button
                  variant="contained"
                  onClick={handleSearch}
                  startIcon={<SearchIcon />}
                  sx={{ mr: 1 }}
                >
                  Search
                </Button>
                <IconButton onClick={loadData}>
                  <RefreshIcon />
                </IconButton>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* CodeBundles Table */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Collection</TableCell>
                  <TableCell>Tasks</TableCell>
                  <TableCell>Enhancement Status</TableCell>
                  <TableCell>Access Level</TableCell>
                  <TableCell>AI Enhanced</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {codebundles.map((cb) => (
                  <TableRow key={cb.id} hover>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" fontWeight="bold">
                          {cb.display_name || cb.name}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {cb.slug}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {cb.collection_name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                          size="small"
                          label={`${cb.task_count} Tasks`}
                          color="primary"
                          variant="outlined"
                        />
                        {cb.sli_count > 0 && (
                          <Chip
                            size="small"
                            label={`${cb.sli_count} SLIs`}
                            color="secondary"
                            variant="outlined"
                          />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={cb.enhancement_status}
                        color={getStatusColor(cb.enhancement_status) as any}
                        icon={<AIIcon />}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={cb.access_level}
                        color={getAccessLevelColor(cb.access_level) as any}
                        icon={<SecurityIcon />}
                      />
                    </TableCell>
                    <TableCell>
                      {cb.ai_enhanced_description || cb.ai_enhanced_metadata ? (
                        <Chip size="small" label="Yes" color="success" />
                      ) : (
                        <Chip size="small" label="No" color="default" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title="View Details">
                        <IconButton
                          size="small"
                          onClick={() => openDetailDialog(cb)}
                        >
                          <ViewIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>

      {/* Collections Tab */}
      <TabPanel value={currentTab} index={1}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={3}>
            {collections.map((collection) => (
              <Grid item xs={12} md={6} lg={4} key={collection.id}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      {collection.name}
                    </Typography>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      {collection.description}
                    </Typography>
                    
                    <Box sx={{ mt: 2, mb: 2 }}>
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Typography variant="body2">
                            <strong>CodeBundles:</strong> {collection.codebundle_count}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2">
                            <strong>Tasks:</strong> {collection.total_tasks}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2">
                            <strong>SLIs:</strong> {collection.total_slis}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2">
                            <strong>Owner:</strong> {collection.owner || 'Unknown'}
                          </Typography>
                        </Grid>
                      </Grid>
                    </Box>

                    <Divider sx={{ my: 2 }} />
                    
                    <Typography variant="subtitle2" gutterBottom>
                      AI Enhancement Status
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      <Chip
                        size="small"
                        label={`${collection.ai_enhancement_stats.completed} Completed`}
                        color="success"
                      />
                      <Chip
                        size="small"
                        label={`${collection.ai_enhancement_stats.pending} Pending`}
                        color="warning"
                      />
                      <Chip
                        size="small"
                        label={`${collection.ai_enhancement_stats.failed} Failed`}
                        color="error"
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </TabPanel>

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          CodeBundle Details: {selectedCodebundle?.display_name || selectedCodebundle?.name}
        </DialogTitle>
        <DialogContent>
          {selectedCodebundle && (
            <Box>
              {/* Basic Info */}
              <Accordion defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Basic Information</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Name:</strong> {selectedCodebundle.name}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Slug:</strong> {selectedCodebundle.slug}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Author:</strong> {selectedCodebundle.author || 'Unknown'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Collection:</strong> {selectedCodebundle.collection_name}
                      </Typography>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body2">
                        <strong>Description:</strong> {selectedCodebundle.description || 'No description'}
                      </Typography>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>

              {/* AI Enhancement Data */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">AI Enhancement Data</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Status:</strong>{' '}
                        <Chip
                          size="small"
                          label={selectedCodebundle.enhancement_status}
                          color={getStatusColor(selectedCodebundle.enhancement_status) as any}
                        />
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Access Level:</strong>{' '}
                        <Chip
                          size="small"
                          label={selectedCodebundle.access_level}
                          color={getAccessLevelColor(selectedCodebundle.access_level) as any}
                        />
                      </Typography>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body2">
                        <strong>AI Enhanced Description:</strong>{' '}
                        {selectedCodebundle.ai_enhanced_description || 'Not available'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body2">
                        <strong>Minimum IAM Requirements:</strong>
                      </Typography>
                      {selectedCodebundle.minimum_iam_requirements.length > 0 ? (
                        <List dense>
                          {selectedCodebundle.minimum_iam_requirements.map((req, index) => (
                            <ListItem key={index}>
                              <ListItemIcon>
                                <SecurityIcon fontSize="small" />
                              </ListItemIcon>
                              <ListItemText primary={req} />
                            </ListItem>
                          ))}
                        </List>
                      ) : (
                        <Typography variant="body2" color="textSecondary">
                          No IAM requirements specified
                        </Typography>
                      )}
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body2">
                        <strong>AI Enhanced Metadata:</strong>
                      </Typography>
                      <Box sx={{ mt: 1, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                        <pre style={{ fontSize: '12px', margin: 0, whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(selectedCodebundle.ai_enhanced_metadata, null, 2)}
                        </pre>
                      </Box>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>

              {/* Tasks and SLIs */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Tasks & SLIs</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Tasks ({selectedCodebundle.task_count})
                      </Typography>
                      <List dense>
                        {selectedCodebundle.tasks.map((task, index) => (
                          <ListItem key={index}>
                            <ListItemIcon>
                              <TaskIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText primary={typeof task === 'string' ? task : task.name} />
                          </ListItem>
                        ))}
                      </List>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        SLIs ({selectedCodebundle.sli_count})
                      </Typography>
                      <List dense>
                        {selectedCodebundle.slis.map((sli, index) => (
                          <ListItem key={index}>
                            <ListItemIcon>
                              <TaskIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText primary={typeof sli === 'string' ? sli : sli.name} />
                          </ListItem>
                        ))}
                      </List>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>

              {/* Support Tags */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Support Tags & Categories</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Support Tags
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selectedCodebundle.support_tags.map((tag, index) => (
                        <Chip key={index} size="small" label={tag} />
                      ))}
                    </Box>
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Categories
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selectedCodebundle.categories.map((category, index) => (
                        <Chip key={index} size="small" label={category} color="secondary" />
                      ))}
                    </Box>
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminInventory;
