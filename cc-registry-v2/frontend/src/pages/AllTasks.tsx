import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  Chip,
  Button,
  CircularProgress,
  Alert,
  Pagination,
  InputAdornment
} from '@mui/material';
import {
  Search as SearchIcon,
  Clear as ClearIcon,
  FilterList as FilterIcon,
  Launch as LaunchIcon,
  Close as CloseIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  GitHub as GitHubIcon
} from '@mui/icons-material';
import { apiService, Task, TasksResponse } from '../services/api';
import { useCart } from '../contexts/CartContext';

const AllTasks: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [supportTags, setSupportTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filter states
  const [selectedSupportTags, setSelectedSupportTags] = useState<string[]>([]);
  const [supportTagSearch, setSupportTagSearch] = useState('');
  const [supportTagSearchInput, setSupportTagSearchInput] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');
  const [taskSearch, setTaskSearch] = useState('');
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const tasksPerPage = 200;
  
  // Cart functionality
  const { addToCart, removeFromCart, isInCart } = useCart();

  // Fetch tasks
  const fetchTasks = async (
    search?: string,
    supportTags?: string[],
    collectionSlug?: string,
    pageNum: number = 1
  ) => {
    try {
      setLoading(true);
      setError(null);
      
      const offset = (pageNum - 1) * tasksPerPage;
      const response: TasksResponse = await apiService.getAllTasks({
        search: search || undefined,
        support_tags: supportTags && supportTags.length > 0 ? supportTags : undefined,
        collection_slug: collectionSlug || undefined,
        limit: tasksPerPage,
        offset
      });
      
      setTasks(response.tasks);
      setTotalCount(response.total_count);
      setHasMore(response.pagination.has_more);
      setSupportTags(response.support_tags);
      
    } catch (err) {
      console.error('Error fetching tasks:', err);
      setError('Failed to load tasks. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchTasks();
  }, []);

  // Handle filter changes (support tags and collection)
  useEffect(() => {
    setPage(1);
    fetchTasks('', selectedSupportTags, selectedCollection, 1);
  }, [selectedSupportTags, selectedCollection]);

  // Debounce tag search input (only filter after user stops typing for 200ms)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setSupportTagSearch(supportTagSearchInput);
    }, 200);

    return () => clearTimeout(timeoutId);
  }, [supportTagSearchInput]);


  // Handle filter changes
  const handleSupportTagAdd = (tag: string) => {
    if (!selectedSupportTags.includes(tag)) {
      const newTags = [...selectedSupportTags, tag];
      setSelectedSupportTags(newTags);
      setPage(1);
      fetchTasks('', newTags, selectedCollection, 1);
    }
  };

  const handleSupportTagRemove = (tag: string) => {
    const newTags = selectedSupportTags.filter(t => t !== tag);
    setSelectedSupportTags(newTags);
    setPage(1);
    fetchTasks('', newTags, selectedCollection, 1);
  };

  const handleCollectionChange = (collection: string) => {
    setSelectedCollection(collection);
    setPage(1);
    fetchTasks('', selectedSupportTags, collection, 1);
  };

  // Clear filters
  const clearFilters = () => {
    setSelectedSupportTags([]);
    setSupportTagSearch('');
    setSupportTagSearchInput('');
    setSelectedCollection('');
    setTaskSearch('');
    setPage(1);
    fetchTasks('', [], '', 1);
  };

  // Handle pagination
  const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    fetchTasks('', selectedSupportTags, selectedCollection, value);
  };

  // Get unique collections from tasks
  const uniqueCollections = Array.from(
    new Set(tasks.map(task => task.collection_slug))
  ).sort();

  // Filter support tags based on search (show all if less than 2 characters)
  const filteredSupportTags = supportTags.filter(tag =>
    supportTagSearch.length < 2 || tag.toLowerCase().includes(supportTagSearch.toLowerCase())
  );

  // Group tasks by CodeBundle
  interface CodeBundleGroup {
    id: number;
    name: string;
    slug: string;
    collection_name: string;
    collection_slug: string;
    description: string;
    support_tags: string[];
    author: string;
    runbook_path: string;
    runbook_source_url: string;
  }

  // Filter tasks by search term (searches both task names and codebundle names)
  const filteredTasks = tasks.filter(task => {
    if (!taskSearch) return true;
    const searchLower = taskSearch.toLowerCase();
    return (
      task.name.toLowerCase().includes(searchLower) ||
      task.codebundle_name.toLowerCase().includes(searchLower)
    );
  });

  const groupedTasks = filteredTasks.reduce((groups, task) => {
    const key = `${task.collection_slug}/${task.codebundle_slug}`;
    if (!groups[key]) {
      groups[key] = {
        codebundle: {
          id: task.codebundle_id,
          name: task.codebundle_name,
          slug: task.codebundle_slug,
          collection_name: task.collection_name,
          collection_slug: task.collection_slug,
          description: task.description,
          support_tags: task.support_tags,
          author: task.author,
          runbook_path: task.runbook_path,
          runbook_source_url: task.runbook_source_url
        },
        tasks: []
      };
    }
    groups[key].tasks.push(task);
    return groups;
  }, {} as Record<string, { codebundle: CodeBundleGroup; tasks: Task[] }>);

  const totalPages = Math.ceil(totalCount / tasksPerPage);

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          All Tasks
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Browse and search through all available tasks across all CodeCollections.
        </Typography>
      </Box>

      {/* Search Bar */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          placeholder="Search tasks and codebundles..."
          value={taskSearch}
          onChange={(e) => setTaskSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            )
          }}
          sx={{ maxWidth: 600 }}
        />
      </Box>

      {/* Main Layout: Full Width Support Tags + Content */}
      <Box sx={{ display: 'flex', gap: 1.5, height: 'calc(100vh - 200px)' }}>
        {/* Left: Support Tags Filter - Full Height */}
        <Box sx={{ width: 280, flexShrink: 0 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ p: 1.5, display: 'flex', flexDirection: 'column', height: '100%', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', fontWeight: 600, mb: 1 }}>
                <FilterIcon sx={{ mr: 1, fontSize: 18 }} />
                Support Tags ({selectedSupportTags.length}/{filteredSupportTags.length})
              </Typography>
              
              {/* Selected Tags */}
              {selectedSupportTags.length > 0 && (
                <Box sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selectedSupportTags.map((tag) => (
                    <Chip
                      key={tag}
                      label={tag}
                      size="small"
                      onDelete={() => handleSupportTagRemove(tag)}
                      deleteIcon={<CloseIcon />}
                      color="primary"
                      variant="filled"
                      sx={{ height: 20, fontSize: '0.65rem' }}
                    />
                  ))}
                </Box>
              )}
              
              {/* Tag Search */}
              <TextField
                fullWidth
                size="small"
                placeholder="Filter tags..."
                value={supportTagSearchInput}
                onChange={(e) => setSupportTagSearchInput(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  )
                }}
                sx={{ mb: 1 }}
              />
              
              {/* Available Tags - Full Height List */}
              <Box sx={{ 
                flex: 1,
                overflow: 'auto', 
                border: '1px solid #ddd', 
                borderRadius: 1,
                bgcolor: 'background.paper'
              }}>
                {filteredSupportTags.map((tag, index) => (
                  <Box
                    key={tag}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      px: 1,
                      py: 0.25,
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                      borderBottom: index < filteredSupportTags.length - 1 ? '1px solid #eee' : 'none',
                      bgcolor: selectedSupportTags.includes(tag) ? 'primary.50' : 'transparent'
                    }}
                    onClick={() => {
                      if (selectedSupportTags.includes(tag)) {
                        handleSupportTagRemove(tag);
                      } else {
                        handleSupportTagAdd(tag);
                      }
                    }}
                  >
                    <Typography variant="body2" sx={{ 
                      flex: 1,
                      fontSize: '0.75rem',
                      fontWeight: selectedSupportTags.includes(tag) ? 500 : 400,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {tag}
                    </Typography>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        border: '2px solid',
                        borderColor: selectedSupportTags.includes(tag) ? 'primary.main' : 'grey.400',
                        borderRadius: 0.5,
                        bgcolor: selectedSupportTags.includes(tag) ? 'primary.main' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0
                      }}
                    >
                      {selectedSupportTags.includes(tag) && (
                        <Box
                          sx={{
                            width: 6,
                            height: 6,
                            bgcolor: 'white',
                            borderRadius: 0.25
                          }}
                        />
                      )}
                    </Box>
                  </Box>
                ))}
                {filteredSupportTags.length === 0 && supportTagSearch.length >= 2 && (
                  <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
                      No tags found matching "{supportTagSearch}"
                    </Typography>
                  </Box>
                )}
              </Box>

              {/* Collection Filter & Clear Button */}
              <Box sx={{ mt: 1 }}>
                <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                  <Select
                    value={selectedCollection}
                    onChange={(e) => handleCollectionChange(e.target.value)}
                    displayEmpty
                    sx={{ fontSize: '0.8rem' }}
                  >
                    <MenuItem value="">All Collections</MenuItem>
                    {uniqueCollections.map((collection) => (
                      <MenuItem key={collection} value={collection}>
                        {collection}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                
                <Button variant="outlined" onClick={clearFilters} fullWidth size="small" sx={{ py: 0.25, fontSize: '0.7rem' }}>
                  Clear Filters
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Right Content - Tasks List */}
        <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
          {/* Compact Filter Bar */}
          <Box sx={{ mb: 1, p: 1, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {Object.keys(groupedTasks).length} CodeBundle{Object.keys(groupedTasks).length !== 1 ? 's' : ''} • {filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''}
                {selectedSupportTags.length > 0 && ` • ${selectedSupportTags.length} tag${selectedSupportTags.length > 1 ? 's' : ''}`}
                {selectedCollection && ` • ${selectedCollection}`}
              </Typography>
              
              {/* Quick Clear Filters */}
              {(selectedSupportTags.length > 0 || selectedCollection) && (
                <Button
                  size="small"
                  variant="text"
                  onClick={clearFilters}
                  startIcon={<ClearIcon />}
                  sx={{ fontSize: '0.7rem', minHeight: 'auto', py: 0.25, px: 0.5 }}
                >
                  Clear
                </Button>
              )}
            </Box>
          </Box>

          {/* Loading */}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          )}

          {/* Error */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {/* Tasks List */}
          {!loading && !error && (
            <>
              {Object.keys(groupedTasks).length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {Object.entries(groupedTasks).map(([key, group]) => (
                    <Card key={key} sx={{ '&:hover': { boxShadow: 2 } }}>
                      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                        {/* CodeBundle Header */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                          <Box sx={{ flex: 1 }}>
                            <Typography variant="h6" component="h2" sx={{ mb: 0.5, fontSize: '1.1rem', fontWeight: 600 }}>
                              {group.codebundle.name}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                              {group.codebundle.collection_name} • {group.tasks.filter(t => t.type === 'TaskSet').length} tasks • {group.tasks.filter(t => t.type === 'SLI').length} SLIs
                            </Typography>
                          </Box>
                          
                          <Box sx={{ ml: 1.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Button
                              variant="outlined"
                              size="small"
                              startIcon={<LaunchIcon />}
                              href={`/collections/${group.codebundle.collection_slug}/codebundles/${group.codebundle.slug}`}
                              sx={{ fontSize: '0.75rem', py: 0.5, px: 1 }}
                            >
                              View
                            </Button>
                            
                            {group.codebundle.runbook_source_url && (
                              <Button
                                variant="text"
                                size="small"
                                startIcon={<GitHubIcon />}
                                href={group.codebundle.runbook_source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                sx={{ fontSize: '0.75rem', py: 0.5, px: 1 }}
                              >
                                Source
                              </Button>
                            )}
                            
                            <Button
                              variant={isInCart(group.codebundle.id) ? "contained" : "outlined"}
                              size="small"
                              color={isInCart(group.codebundle.id) ? "error" : "primary"}
                              startIcon={isInCart(group.codebundle.id) ? <RemoveIcon /> : <AddIcon />}
                              sx={{ fontSize: '0.75rem', py: 0.5, px: 1 }}
                              onClick={() => {
                                if (isInCart(group.codebundle.id)) {
                                  removeFromCart(group.codebundle.id);
                                } else {
                                  // Create a proper CodeBundle object for the cart
                                  const codebundleItem = {
                                    id: group.codebundle.id,
                                    name: group.codebundle.name,
                                    slug: group.codebundle.slug,
                                    display_name: group.codebundle.name,
                                    description: group.codebundle.description,
                                    doc: '',
                                    readme: null,
                                    author: group.codebundle.author,
                                    support_tags: group.codebundle.support_tags,
                                    tasks: group.tasks.filter(t => t.type === 'TaskSet').map(t => ({name: t.name, doc: t.description || '', tags: []})),
                                    slis: group.tasks.filter(t => t.type === 'SLI').map(t => ({name: t.name, doc: t.description || '', tags: []})),
                                    task_count: group.tasks.filter(t => t.type === 'TaskSet').length,
                                    sli_count: group.tasks.filter(t => t.type === 'SLI').length,
                                    runbook_source_url: group.codebundle.runbook_source_url || '',
                                    created_at: new Date().toISOString(),
                                    configuration_type: {
                                      type: 'Manual' as const,
                                      has_generation_rules: false,
                                      platform: null,
                                      resource_types: [],
                                      match_patterns: [],
                                      templates: [],
                                      output_items: [],
                                      level_of_detail: null,
                                      runwhen_directory_path: null
                                    },
                                    codecollection: {
                                      id: 0, // We don't have this info in the current structure
                                      name: group.codebundle.collection_name,
                                      slug: group.codebundle.collection_slug,
                                      git_url: group.tasks[0]?.git_url || '',
                                      git_ref: (group.tasks[0] as any)?.git_ref || 'main'
                                    }
                                  };
                                  addToCart(codebundleItem);
                                }
                              }}
                            >
                              {isInCart(group.codebundle.id) ? "Remove CodeBundle" : "Select CodeBundle"}
                            </Button>
                          </Box>
                        </Box>

                        {/* TaskSet and SLI Tasks */}
                        <Box>
                          {/* TaskSet Tasks */}
                          {group.tasks.filter(task => task.type === 'TaskSet').length > 0 && (
                            <Box sx={{ mb: 1.5 }}>
                              <Typography variant="subtitle2" sx={{ color: 'primary.main', fontWeight: 600, mb: 0.5, fontSize: '0.85rem' }}>
                                TaskSet ({group.tasks.filter(task => task.type === 'TaskSet').length})
                              </Typography>
                              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {group.tasks.filter(task => task.type === 'TaskSet').map((task) => (
                                  <Box
                                    key={task.id}
                                    sx={{
                                      px: 1.5,
                                      py: 0.75,
                                      bgcolor: 'grey.50',
                                      borderRadius: 0.5,
                                      border: '1px solid',
                                      borderColor: 'grey.200',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      '&:hover': {
                                        bgcolor: 'grey.100',
                                        borderColor: 'primary.main'
                                      }
                                    }}
                                  >
                                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                                      {task.name}
                                    </Typography>
                                  </Box>
                                ))}
                              </Box>
                            </Box>
                          )}

                          {/* SLI Tasks */}
                          {group.tasks.filter(task => task.type === 'SLI').length > 0 && (
                            <Box>
                              <Typography variant="subtitle2" sx={{ color: 'secondary.main', fontWeight: 600, mb: 0.5, fontSize: '0.85rem' }}>
                                SLI ({group.tasks.filter(task => task.type === 'SLI').length})
                              </Typography>
                              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {group.tasks.filter(task => task.type === 'SLI').map((task) => (
                                  <Box
                                    key={task.id}
                                    sx={{
                                      px: 1.5,
                                      py: 0.75,
                                      bgcolor: 'grey.50',
                                      borderRadius: 0.5,
                                      border: '1px solid',
                                      borderColor: 'grey.200',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      '&:hover': {
                                        bgcolor: 'grey.100',
                                        borderColor: 'secondary.main'
                                      }
                                    }}
                                  >
                                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                                      {task.name}
                                    </Typography>
                                  </Box>
                                ))}
                              </Box>
                            </Box>
                          )}
                        </Box>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              ) : (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No tasks found
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Try adjusting your search criteria or clearing filters.
                  </Typography>
                </Box>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                    size="large"
                    showFirstButton
                    showLastButton
                  />
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default AllTasks;
