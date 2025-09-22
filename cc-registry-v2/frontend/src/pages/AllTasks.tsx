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

  const groupedTasks = tasks.reduce((groups, task) => {
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

      {/* Main Layout: Sidebar + Content */}
      <Box sx={{ display: 'flex', gap: 3 }}>
        {/* Left Sidebar - Filters */}
        <Box sx={{ width: 300, flexShrink: 0 }}>
          <Card sx={{ position: 'sticky', top: 20 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <FilterIcon sx={{ mr: 1 }} />
                Filters
              </Typography>
              

              {/* Support Tags Filter */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Support Tags ({selectedSupportTags.length} selected • {filteredSupportTags.length} available)
                </Typography>
                
                {/* Selected Tags */}
                {selectedSupportTags.length > 0 && (
                  <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selectedSupportTags.map((tag) => (
                      <Chip
                        key={tag}
                        label={tag}
                        size="small"
                        onDelete={() => handleSupportTagRemove(tag)}
                        deleteIcon={<CloseIcon />}
                        color="primary"
                        variant="filled"
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
                />
                
                {/* Available Tags with Checkboxes */}
                <Box sx={{ 
                  mt: 1, 
                  maxHeight: 300, 
                  overflow: 'auto', 
                  border: '1px solid #ddd', 
                  borderRadius: 1,
                  bgcolor: 'background.paper'
                }}>
                  {filteredSupportTags.slice(0, 50).map((tag) => (
                    <Box
                      key={tag}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        p: 1,
                        cursor: 'pointer',
                        '&:hover': { bgcolor: 'action.hover' },
                        borderBottom: '1px solid #eee'
                      }}
                      onClick={() => {
                        if (selectedSupportTags.includes(tag)) {
                          handleSupportTagRemove(tag);
                        } else {
                          handleSupportTagAdd(tag);
                        }
                      }}
                    >
                      <Box
                        sx={{
                          width: 16,
                          height: 16,
                          border: '2px solid',
                          borderColor: selectedSupportTags.includes(tag) ? 'primary.main' : 'grey.400',
                          borderRadius: 0.5,
                          bgcolor: selectedSupportTags.includes(tag) ? 'primary.main' : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          mr: 1,
                          flexShrink: 0
                        }}
                      >
                        {selectedSupportTags.includes(tag) && (
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              bgcolor: 'white',
                              borderRadius: 0.25
                            }}
                          />
                        )}
                      </Box>
                      <Typography variant="body2" sx={{ flex: 1 }}>
                        {tag}
                      </Typography>
                    </Box>
                  ))}
                  {filteredSupportTags.length > 50 && (
                    <Box sx={{ p: 1, textAlign: 'center', color: 'text.secondary' }}>
                      <Typography variant="caption">
                        Showing first 50 of {filteredSupportTags.length} results
                      </Typography>
                    </Box>
                  )}
                  {filteredSupportTags.length === 0 && supportTagSearch.length >= 2 && (
                    <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                      <Typography variant="body2">
                        No tags found matching "{supportTagSearch}"
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Collection Filter */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  CodeCollection
                </Typography>
                <FormControl fullWidth size="small">
                  <Select
                    value={selectedCollection}
                    onChange={(e) => handleCollectionChange(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="">All CodeCollections</MenuItem>
                    {uniqueCollections.map((collection) => (
                      <MenuItem key={collection} value={collection}>
                        {collection}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              {/* Action Buttons */}
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button variant="outlined" onClick={clearFilters} fullWidth>
                  Clear All Filters
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Right Content - Tasks List */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {/* Filter Bar Above List */}
          <Box sx={{ mb: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Showing {Object.keys(groupedTasks).length} CodeBundle{Object.keys(groupedTasks).length !== 1 ? 's' : ''} with {tasks.length} task{tasks.length !== 1 ? 's' : ''} total
                {selectedSupportTags.length > 0 && ` • ${selectedSupportTags.length} tag${selectedSupportTags.length > 1 ? 's' : ''} selected`}
                {selectedCollection && ` • CodeCollection: ${selectedCollection}`}
              </Typography>
              
              {/* Quick Clear Filters */}
              {(selectedSupportTags.length > 0 || selectedCollection) && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={clearFilters}
                  startIcon={<ClearIcon />}
                >
                  Clear Filters
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
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {Object.entries(groupedTasks).map(([key, group]) => (
                    <Card key={key} sx={{ '&:hover': { boxShadow: 4 } }}>
                      <CardContent>
                        {/* CodeBundle Header */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3, pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                          <Box sx={{ flex: 1 }}>
                            <Typography variant="h5" component="h2" gutterBottom>
                              {group.codebundle.name}
                            </Typography>
                            
                          </Box>
                          
                          <Box sx={{ ml: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
                            <Button
                              variant="outlined"
                              size="small"
                              startIcon={<LaunchIcon />}
                              href={`/collections/${group.codebundle.collection_slug}/codebundles/${group.codebundle.slug}`}
                            >
                              View CodeBundle
                            </Button>
                            
                            {group.codebundle.runbook_source_url && (
                              <Button
                                variant="text"
                                size="small"
                                startIcon={<LaunchIcon />}
                                href={group.codebundle.runbook_source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                View Source
                              </Button>
                            )}
                            
                            <Button
                              variant={isInCart(`codebundle_${group.codebundle.id}`) ? "contained" : "outlined"}
                              size="small"
                              color={isInCart(`codebundle_${group.codebundle.id}`) ? "error" : "primary"}
                              startIcon={isInCart(`codebundle_${group.codebundle.id}`) ? <RemoveIcon /> : <AddIcon />}
                              onClick={() => {
                                const codebundleId = `codebundle_${group.codebundle.id}`;
                                if (isInCart(codebundleId)) {
                                  removeFromCart(codebundleId);
                                } else {
                                  // Add the entire codebundle as a single cart item
                                  const codebundleItem = {
                                    id: codebundleId,
                                    name: group.codebundle.name,
                                    type: 'CodeBundle' as const,
                                    codebundle_id: group.codebundle.id,
                                    codebundle_name: group.codebundle.name,
                                    codebundle_slug: group.codebundle.slug,
                                    collection_name: group.codebundle.collection_name,
                                    collection_slug: group.codebundle.collection_slug,
                                    description: group.codebundle.description,
                                    support_tags: group.codebundle.support_tags,
                                    categories: [],
                                    author: group.codebundle.author,
                                    runbook_path: group.codebundle.runbook_path || '',
                                    runbook_source_url: group.codebundle.runbook_source_url || '',
                                    git_url: group.tasks[0]?.git_url || ''
                                  };
                                  addToCart(codebundleItem);
                                }
                              }}
                            >
                              {isInCart(`codebundle_${group.codebundle.id}`) ? "Remove CodeBundle" : "Select CodeBundle"}
                            </Button>
                          </Box>
                        </Box>

                        {/* TaskSet and SLI Tasks */}
                        <Box>
                          {/* TaskSet Tasks */}
                          {group.tasks.filter(task => task.type === 'TaskSet').length > 0 && (
                            <Box sx={{ mb: 3 }}>
                              <Typography variant="h6" gutterBottom sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                                TaskSet
                              </Typography>
                              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                {group.tasks.filter(task => task.type === 'TaskSet').map((task) => (
                                  <Box
                                    key={task.id}
                                    sx={{
                                      p: 2,
                                      bgcolor: 'grey.50',
                                      borderRadius: 1,
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
                                    <Typography variant="body1">
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
                              <Typography variant="h6" gutterBottom sx={{ color: 'secondary.main', fontWeight: 'bold' }}>
                                SLI
                              </Typography>
                              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                {group.tasks.filter(task => task.type === 'SLI').map((task) => (
                                  <Box
                                    key={task.id}
                                    sx={{
                                      p: 2,
                                      bgcolor: 'grey.50',
                                      borderRadius: 1,
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
                                    <Typography variant="body1">
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
