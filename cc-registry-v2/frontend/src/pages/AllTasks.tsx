import React, { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  Card,
  CardContent,
  Chip,
  Button,
  CircularProgress,
  Alert,
  Pagination,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import {
  Search as SearchIcon,
  Clear as ClearIcon,
  FilterList as FilterIcon,
  Launch as LaunchIcon,
  Close as CloseIcon,
  ViewList as ListIcon,
  ViewModule as GroupedIcon,
  Sort as SortIcon,
  CodeOutlined,
  TimelineOutlined,
} from '@mui/icons-material';
import { apiService, Task, TasksResponse } from '../services/api';

type ViewMode = 'grouped' | 'presentation';
type SortOrder = 'alpha' | 'diverse' | 'codebundle';

/** Accent colour per platform, used by the presentation-mode language dot. */
const PLATFORM_COLORS: Record<string, string> = {
  Kubernetes: '#326CE5',
  AWS: '#FF9900',
  Azure: '#0078D4',
  GCP: '#4285F4',
  PostgreSQL: '#336791',
  Misc: '#64748B',
};

const platformColor = (platform?: string | null): string =>
  (platform && PLATFORM_COLORS[platform]) || '#2F80ED';

/**
 * Language bar — a slim stacked bar of Task counts per platform plus a legend.
 * Modelled on the GitHub repo language summary: it makes the view read as an
 * inventory of executable automation rather than a list of documents.
 */
const PlatformBar: React.FC<{ tasks: Task[] }> = ({ tasks }) => {
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    tasks.forEach(task => {
      const key = task.platform || 'Other';
      map.set(key, (map.get(key) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [tasks]);

  if (tasks.length === 0 || counts.length === 0) return null;
  const total = tasks.length;

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', height: 6, borderRadius: 999, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
        {counts.map(([platform, count]) => (
          <Box
            key={platform}
            sx={{ width: `${(count / total) * 100}%`, bgcolor: platformColor(platform) }}
            title={`${platform}: ${count}`}
          />
        ))}
      </Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 0.75 }}>
        {counts.map(([platform, count]) => (
          <Box key={platform} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: platformColor(platform) }} />
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
              <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{platform}</Box>
              {` ${count}`}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

const AllTasks: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [supportTags, setSupportTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const initialTags = searchParams.get('support_tags');
  const initialView = searchParams.get('view') as ViewMode | null;
  const initialSort = searchParams.get('sort') as SortOrder | null;
  
  const [selectedSupportTags, setSelectedSupportTags] = useState<string[]>(
    initialTags ? initialTags.split(',').map(t => t.trim()).filter(Boolean) : []
  );
  const [supportTagSearch, setSupportTagSearch] = useState('');
  const [supportTagSearchInput, setSupportTagSearchInput] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');
  const [taskSearch, setTaskSearch] = useState('');
  
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const tasksPerPage = 200;
  
  const validViews: ViewMode[] = ['grouped', 'presentation'];
  const validSorts: SortOrder[] = ['alpha', 'diverse', 'codebundle'];
  const [viewMode, setViewMode] = useState<ViewMode>(initialView && validViews.includes(initialView) ? initialView : 'grouped');
  const [sortOrder, setSortOrder] = useState<SortOrder>(initialSort && validSorts.includes(initialSort) ? initialSort : 'alpha');

  // Keep URL params in sync with view/sort state
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (viewMode !== 'grouped') { params.set('view', viewMode); } else { params.delete('view'); }
    if (sortOrder !== 'alpha') { params.set('sort', sortOrder); } else { params.delete('sort'); }
    setSearchParams(params, { replace: true });
  }, [viewMode, sortOrder]);
  
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

  useEffect(() => {
    fetchTasks();
  }, []);

  useEffect(() => {
    setPage(1);
    fetchTasks('', selectedSupportTags, selectedCollection, 1);
  }, [selectedSupportTags, selectedCollection]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setSupportTagSearch(supportTagSearchInput);
    }, 200);
    return () => clearTimeout(timeoutId);
  }, [supportTagSearchInput]);

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

  const clearFilters = () => {
    setSelectedSupportTags([]);
    setSupportTagSearch('');
    setSupportTagSearchInput('');
    setSelectedCollection('');
    setTaskSearch('');
    setPage(1);
    fetchTasks('', [], '', 1);
  };

  const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    fetchTasks('', selectedSupportTags, selectedCollection, value);
  };

  const uniqueCollections = Array.from(
    new Set(tasks.map(task => task.collection_slug))
  ).sort();

  const filteredSupportTags = supportTags.filter(tag =>
    supportTagSearch.length < 2 || tag.toLowerCase().includes(supportTagSearch.toLowerCase())
  );

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

  const filteredTasks = tasks.filter(task => {
    // Hide generic templated tasks that accept arbitrary user input
    if (task.name.includes('${TASK_TITLE}')) return false;
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

  // Sorted flat task list for presentation mode
  const sortedFlatTasks = useMemo(() => {
    const list = [...filteredTasks];
    if (sortOrder === 'alpha') {
      list.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortOrder === 'codebundle') {
      list.sort((a, b) => a.codebundle_name.localeCompare(b.codebundle_name) || a.name.localeCompare(b.name));
    } else if (sortOrder === 'diverse') {
      // Round-robin across primary support tag to interleave platforms
      const buckets: Record<string, Task[]> = {};
      for (const task of list) {
        const tag = task.support_tags?.[0] || '_other';
        if (!buckets[tag]) buckets[tag] = [];
        buckets[tag].push(task);
      }
      // Sort within each bucket alphabetically
      for (const key of Object.keys(buckets)) {
        buckets[key].sort((a, b) => a.name.localeCompare(b.name));
      }
      const keys = Object.keys(buckets).sort();
      const result: Task[] = [];
      let remaining = true;
      let idx = 0;
      while (remaining) {
        remaining = false;
        for (const key of keys) {
          if (idx < buckets[key].length) {
            result.push(buckets[key][idx]);
            remaining = true;
          }
        }
        idx++;
      }
      return result;
    }
    return list;
  }, [filteredTasks, sortOrder]);

  const totalPages = Math.ceil(totalCount / tasksPerPage);

  const isPresentation = viewMode === 'presentation';

  return (
    <Box sx={{ p: 3 }}>
      {/* Header with view toggle */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom sx={{ fontSize: { xs: '1.5rem', md: '1.75rem' }, fontWeight: 600, mb: 0.5 }}>
            All Tasks
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ fontSize: '0.9375rem' }}>
            {filteredTasks.length} Tasks across {Object.keys(groupedTasks).length} Skills
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          {/* Sort (presentation mode only) */}
          {isPresentation && (
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <Select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                startAdornment={<SortIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />}
                sx={{ fontSize: '0.875rem' }}
              >
                <MenuItem value="alpha">Alphabetical</MenuItem>
                <MenuItem value="diverse">Platform Diversity</MenuItem>
                <MenuItem value="codebundle">By Skill</MenuItem>
              </Select>
            </FormControl>
          )}

          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, v) => { if (v) setViewMode(v); }}
            size="small"
          >
            <ToggleButton value="grouped" sx={{ px: 1.5, textTransform: 'none', fontSize: '0.8125rem' }}>
              <GroupedIcon sx={{ fontSize: 18, mr: 0.5 }} /> Grouped
            </ToggleButton>
            <ToggleButton value="presentation" sx={{ px: 1.5, textTransform: 'none', fontSize: '0.8125rem' }}>
              <ListIcon sx={{ fontSize: 18, mr: 0.5 }} /> Presentation
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* Search Bar */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          placeholder="Search Tasks and Skills..."
          value={taskSearch}
          onChange={(e) => setTaskSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
            sx: {
              backgroundColor: 'background.paper',
              color: 'text.primary',
              '& fieldset': { borderColor: 'divider' },
              '&:hover fieldset': { borderColor: 'primary.main' },
              '&.Mui-focused fieldset': { borderColor: 'primary.main' },
            }
          }}
          sx={{ maxWidth: isPresentation ? '100%' : 600 }}
        />
      </Box>

      {/* Main Layout: Sidebar + Content (shared across both modes) */}
      <Box sx={{ display: 'flex', gap: 1.5, height: 'calc(100vh - 220px)' }}>
        {/* Left: Support Tags Filter */}
        <Box sx={{ width: 280, flexShrink: 0 }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ p: 1.5, display: 'flex', flexDirection: 'column', height: '100%', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', fontWeight: 600, mb: 1 }}>
                <FilterIcon sx={{ mr: 1, fontSize: 18 }} />
                Support Tags ({selectedSupportTags.length}/{filteredSupportTags.length})
              </Typography>
              
              {selectedSupportTags.length > 0 && (
                <Box sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selectedSupportTags.map((tag) => (
                    <Chip key={tag} label={tag} size="small" onDelete={() => handleSupportTagRemove(tag)} deleteIcon={<CloseIcon />} color="primary" variant="filled" sx={{ height: 24, fontSize: '0.75rem' }} />
                  ))}
                </Box>
              )}
              
              <TextField
                fullWidth size="small" placeholder="Filter tags..."
                value={supportTagSearchInput}
                onChange={(e) => setSupportTagSearchInput(e.target.value)}
                InputProps={{ startAdornment: (<InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>) }}
                sx={{ mb: 1 }}
              />
              
              <Box sx={{ flex: 1, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, bgcolor: 'background.paper' }}>
                {filteredSupportTags.map((tag, index) => (
                  <Box
                    key={tag}
                    sx={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      px: 1, py: 0.5, cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                      borderBottom: index < filteredSupportTags.length - 1 ? '1px solid' : 'none',
                      borderBottomColor: 'divider',
                      bgcolor: selectedSupportTags.includes(tag) ? 'primary.50' : 'transparent'
                    }}
                    onClick={() => {
                      if (selectedSupportTags.includes(tag)) { handleSupportTagRemove(tag); }
                      else { handleSupportTagAdd(tag); }
                    }}
                  >
                    <Typography variant="body2" sx={{ flex: 1, fontSize: '0.75rem', fontWeight: selectedSupportTags.includes(tag) ? 500 : 400, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {tag}
                    </Typography>
                    <Box sx={{ width: 12, height: 12, border: '2px solid', borderColor: selectedSupportTags.includes(tag) ? 'primary.main' : 'grey.400', borderRadius: 0.5, bgcolor: selectedSupportTags.includes(tag) ? 'primary.main' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {selectedSupportTags.includes(tag) && <Box sx={{ width: 6, height: 6, bgcolor: 'white', borderRadius: 0.25 }} />}
                    </Box>
                  </Box>
                ))}
                {filteredSupportTags.length === 0 && supportTagSearch.length >= 2 && (
                  <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>No tags found matching "{supportTagSearch}"</Typography>
                  </Box>
                )}
              </Box>

              <Box sx={{ mt: 1 }}>
                <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                  <Select value={selectedCollection} onChange={(e) => handleCollectionChange(e.target.value)} displayEmpty sx={{ fontSize: '0.8125rem' }}>
                    <MenuItem value="">All Plugins</MenuItem>
                    {uniqueCollections.map((collection) => (<MenuItem key={collection} value={collection}>{collection}</MenuItem>))}
                  </Select>
                </FormControl>
                <Button variant="outlined" onClick={clearFilters} fullWidth size="small" sx={{ py: 0.5, fontSize: '0.75rem' }}>Clear Filters</Button>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Right Content */}
        <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
          {isPresentation ? (
            /* ============================================================
               PRESENTATION MODE — flat task list
               ============================================================ */
            <>
              {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                  <CircularProgress />
                </Box>
              )}

              {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

              {!loading && !error && (
                <>
                  {sortedFlatTasks.length > 0 ? (
                    <Box>
                      {/* Language bar — Tasks by platform, like a GitHub repo language summary */}
                      <PlatformBar tasks={sortedFlatTasks} />
                      <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                        {/* Header row */}
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            px: 2,
                            py: 0.75,
                            bgcolor: 'action.hover',
                            borderBottom: '1px solid',
                            borderColor: 'divider',
                          }}
                        >
                          <Typography sx={{ flex: 1, fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
                            Task
                          </Typography>
                          <Typography sx={{ width: 240, display: { xs: 'none', md: 'block' }, fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
                            Skill
                          </Typography>
                          <Typography sx={{ width: 150, display: { xs: 'none', sm: 'block' }, fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
                            Platform
                          </Typography>
                          <Typography sx={{ width: 220, display: { xs: 'none', lg: 'block' }, fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
                            Script
                          </Typography>
                        </Box>
                        {sortedFlatTasks.map((task, idx) => (
                        <Box
                          key={task.id}
                          title={task.support_tags.length > 0 ? task.support_tags.join('  ·  ') : undefined}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            px: 2,
                            py: 0.75,
                            minHeight: 40,
                            borderBottom: idx < sortedFlatTasks.length - 1 ? '1px solid' : 'none',
                            borderBottomColor: 'divider',
                            '&:hover': { bgcolor: 'action.hover' },
                            transition: 'background-color 0.1s',
                          }}
                        >
                          <Box sx={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 0.75 }}>
                            {task.type === 'SLI' ? (
                              <TimelineOutlined sx={{ fontSize: 15, color: 'secondary.main', flexShrink: 0 }} />
                            ) : (
                              <CodeOutlined sx={{ fontSize: 15, color: 'text.secondary', flexShrink: 0 }} />
                            )}
                            <Typography
                              sx={{
                                fontFamily: '"SF Mono", "Consolas", "Roboto Mono", monospace',
                                fontSize: '0.8125rem',
                                fontWeight: 500,
                                color: 'text.primary',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {task.title || task.name}
                            </Typography>
                          </Box>
                          <Typography
                            sx={{
                              width: 240,
                              display: { xs: 'none', md: 'block' },
                              fontSize: '0.75rem',
                              color: 'text.secondary',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              pl: 2,
                            }}
                          >
                            {task.codebundle_name}
                          </Typography>
                          <Box sx={{ width: 150, display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.625, flexShrink: 0, pl: 2 }}>
                            <Box sx={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, bgcolor: platformColor(task.platform) }} />
                            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {task.platform || 'Other'}
                            </Typography>
                          </Box>
                          <Typography
                            sx={{
                              width: 220,
                              display: { xs: 'none', lg: 'block' },
                              fontFamily: '"SF Mono", "Consolas", "Roboto Mono", monospace',
                              fontSize: '0.6875rem',
                              color: 'text.disabled',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              pl: 2,
                            }}
                          >
                            {task.script || '—'}
                          </Typography>
                        </Box>
                        ))}
                      </Box>
                    </Box>
                  ) : (
                    <Box sx={{ textAlign: 'center', py: 8 }}>
                      <Typography variant="h6" color="text.secondary" gutterBottom>No Tasks found</Typography>
                      <Typography variant="body2" color="text.secondary">Try adjusting your search criteria or clearing filters.</Typography>
                    </Box>
                  )}

                  {totalPages > 1 && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                      <Pagination count={totalPages} page={page} onChange={handlePageChange} color="primary" size="large" showFirstButton showLastButton />
                    </Box>
                  )}
                </>
              )}
            </>
          ) : (
            /* ============================================================
               GROUPED MODE — codebundle cards
               ============================================================ */
            <>
            <Box sx={{ mb: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  {Object.keys(groupedTasks).length} Skill{Object.keys(groupedTasks).length !== 1 ? 's' : ''} • {filteredTasks.length} Task{filteredTasks.length !== 1 ? 's' : ''}
                  {selectedSupportTags.length > 0 && ` • ${selectedSupportTags.length} tag${selectedSupportTags.length > 1 ? 's' : ''}`}
                  {selectedCollection && ` • ${selectedCollection}`}
                </Typography>
                {(selectedSupportTags.length > 0 || selectedCollection) && (
                  <Button size="small" variant="text" onClick={clearFilters} startIcon={<ClearIcon />} sx={{ fontSize: '0.75rem', minHeight: 'auto', py: 0.25, px: 0.5 }}>Clear</Button>
                )}
              </Box>
            </Box>

            {loading && (<Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>)}
            {error && (<Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>)}

            {!loading && !error && (
              <>
                {Object.keys(groupedTasks).length > 0 ? (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {Object.entries(groupedTasks).map(([key, group]) => (
                      <Card key={key}>
                        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                            <Box sx={{ flex: 1 }}>
                              <Typography variant="h6" component="h2" sx={{ mb: 0.5, fontSize: '1.125rem', fontWeight: 600, color: 'text.primary' }}>
                                {group.codebundle.name}
                              </Typography>
                              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                                {group.codebundle.collection_name} • {group.tasks.length} Task{group.tasks.length !== 1 ? 's' : ''}
                              </Typography>
                            </Box>
                            <Box sx={{ ml: 1.5, display: 'flex', flexDirection: 'row', gap: 0.75, alignItems: 'center' }}>
                              <Button
                                variant="outlined"
                                size="small"
                                startIcon={<LaunchIcon />}
                                component={Link}
                                to={`/plugins/${group.codebundle.collection_slug}/skills/${group.codebundle.slug}`}
                                sx={{ fontSize: '0.75rem', py: 0.5, px: 1.5, whiteSpace: 'nowrap' }}
                              >
                                View
                              </Button>
                            </Box>
                          </Box>

                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            {group.tasks.map((task) => (
                              <Box key={task.id} sx={{ px: 1.5, py: 0.75, minHeight: 40, bgcolor: 'action.hover', borderRadius: 0.5, border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography variant="body2" sx={{ flex: 1, fontSize: '0.9375rem', fontWeight: 500, color: 'text.primary' }}>{task.name}</Typography>
                                {task.type === 'SLI' && (
                                  <Chip label="Monitor" size="small" variant="outlined" color="secondary" sx={{ fontSize: '0.6875rem', height: 20 }} />
                                )}
                              </Box>
                            ))}
                          </Box>
                        </CardContent>
                      </Card>
                    ))}
                  </Box>
                ) : (
                  <Box sx={{ textAlign: 'center', py: 8 }}>
                    <Typography variant="h6" color="text.secondary" gutterBottom>No Tasks found</Typography>
                    <Typography variant="body2" color="text.secondary">Try adjusting your search criteria or clearing filters.</Typography>
                  </Box>
                )}

                {totalPages > 1 && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <Pagination count={totalPages} page={page} onChange={handlePageChange} color="primary" size="large" showFirstButton showLastButton />
                  </Box>
                )}
              </>
            )}
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default AllTasks;
