import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Close as CloseIcon,
  Sort as SortIcon,
  CodeOutlined,
  TimelineOutlined,
} from '@mui/icons-material';
import { apiService, Task, TasksResponse } from '../services/api';

type SortOrder = 'alpha' | 'skill' | 'plugin' | 'diverse';

/** Accent colour per plugin label, used by the dense list dot and language bar. */
const PLUGIN_COLORS: Record<string, string> = {
  Kubernetes: '#326CE5',
  AWS: '#FF9900',
  Azure: '#0078D4',
  GCP: '#4285F4',
  PostgreSQL: '#336791',
  Miscellaneous: '#64748B',
};

/** Alternates used when a plugin has no explicit colour, so unknowns rarely collide. */
const PLUGIN_FALLBACK_COLORS = ['#2F80ED', '#8250DF', '#0F766E'];

/** Short plugin (collection) label: "RunWhen Kubernetes Plugin" -> "Kubernetes". */
const pluginLabel = (task: Task): string =>
  (task.collection_name || '').replace(/^RunWhen\s+/i, '').replace(/\s*Plugin$/i, '').trim() ||
  task.collection_slug;

const pluginColor = (label?: string | null): string => {
  if (label && PLUGIN_COLORS[label]) return PLUGIN_COLORS[label];
  const key = label || '';
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return PLUGIN_FALLBACK_COLORS[hash % PLUGIN_FALLBACK_COLORS.length];
};

/**
 * Language bar — a slim stacked bar of Task counts per plugin plus a legend.
 * Modelled on the GitHub repo language summary: it makes the view read as an
 * inventory of executable automation rather than a list of documents.
 */
const PluginBar: React.FC<{ tasks: Task[] }> = ({ tasks }) => {
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    tasks.forEach(task => {
      const key = pluginLabel(task) || 'Other';
      map.set(key, (map.get(key) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [tasks]);

  if (tasks.length === 0 || counts.length === 0) return null;
  const total = tasks.length;

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', height: 6, borderRadius: 999, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
        {counts.map(([plugin, count]) => (
          <Box
            key={plugin}
            sx={{ width: `${(count / total) * 100}%`, bgcolor: pluginColor(plugin) }}
            title={`${plugin}: ${count}`}
          />
        ))}
      </Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 0.75 }}>
        {counts.map(([plugin, count]) => (
          <Box key={plugin} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: pluginColor(plugin) }} />
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
              <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{plugin}</Box>
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
  const navigate = useNavigate();
  
  const initialTags = searchParams.get('support_tags');
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
  
  const validSorts: SortOrder[] = ['alpha', 'skill', 'plugin', 'diverse'];
  const [sortOrder, setSortOrder] = useState<SortOrder>(initialSort && validSorts.includes(initialSort) ? initialSort : 'alpha');

  // Keep the sort param in sync with sort state
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (sortOrder !== 'alpha') { params.set('sort', sortOrder); } else { params.delete('sort'); }
    setSearchParams(params, { replace: true });
  }, [sortOrder]);
  
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

  const skillCount = new Set(
    filteredTasks.map(task => `${task.collection_slug}/${task.codebundle_slug}`)
  ).size;

  // Sorted flat task list for the dense list
  const sortedFlatTasks = useMemo(() => {
    const list = [...filteredTasks];
    if (sortOrder === 'alpha') {
      list.sort((a, b) => (a.title || a.name).localeCompare(b.title || b.name));
    } else if (sortOrder === 'skill') {
      list.sort((a, b) => a.codebundle_name.localeCompare(b.codebundle_name) || (a.title || a.name).localeCompare(b.title || b.name));
    } else if (sortOrder === 'plugin') {
      list.sort((a, b) => pluginLabel(a).localeCompare(pluginLabel(b)) || a.codebundle_name.localeCompare(b.codebundle_name) || (a.title || a.name).localeCompare(b.title || b.name));
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

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom sx={{ fontSize: { xs: '1.5rem', md: '1.75rem' }, fontWeight: 600, mb: 0.5 }}>
            All Tasks
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ fontSize: '0.9375rem' }}>
            {filteredTasks.length} Tasks across {skillCount} Skills
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          {/* Sort */}
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <Select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              startAdornment={<SortIcon sx={{ mr: 0.5, fontSize: 18, color: 'text.secondary' }} />}
              sx={{ fontSize: '0.875rem' }}
            >
              <MenuItem value="alpha">By Task</MenuItem>
              <MenuItem value="skill">By Skill</MenuItem>
              <MenuItem value="plugin">By Plugin</MenuItem>
              <MenuItem value="diverse">Platform Diversity</MenuItem>
            </Select>
          </FormControl>
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
          sx={{ maxWidth: '100%' }}
        />
      </Box>

      {/* Main Layout: Sidebar + Content */}
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
                  {/* Language bar — Tasks by plugin, like a GitHub repo language summary */}
                  <PluginBar tasks={sortedFlatTasks} />
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
                        Plugin
                      </Typography>
                      <Typography sx={{ width: 220, display: { xs: 'none', lg: 'block' }, fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
                        Script
                      </Typography>
                    </Box>
                    {sortedFlatTasks.map((task, idx) => (
                    <Box
                      key={task.id}
                      role="link"
                      tabIndex={0}
                      aria-label={`${task.title || task.name} — ${task.codebundle_name}`}
                      onClick={() => navigate(`/plugins/${task.collection_slug}/skills/${task.codebundle_slug}`)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          navigate(`/plugins/${task.collection_slug}/skills/${task.codebundle_slug}`);
                        }
                      }}
                      title={task.support_tags.length > 0 ? task.support_tags.join('  ·  ') : undefined}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        px: 2,
                        py: 0.75,
                        minHeight: 40,
                        cursor: 'pointer',
                        borderBottom: idx < sortedFlatTasks.length - 1 ? '1px solid' : 'none',
                        borderBottomColor: 'divider',
                        '&:hover': { bgcolor: 'action.hover' },
                        '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: '-2px' },
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
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, bgcolor: pluginColor(pluginLabel(task)) }} />
                        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {pluginLabel(task)}
                        </Typography>
                      </Box>
                      {task.script ? (
                        <Box
                          component="a"
                          href={`${task.runbook_source_url}/${task.script}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
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
                            textDecoration: 'none',
                            '&:hover': { textDecoration: 'underline' },
                          }}
                        >
                          {task.script}
                        </Box>
                      ) : (
                        <Typography
                          sx={{
                            width: 220,
                            display: { xs: 'none', lg: 'block' },
                            fontFamily: '"SF Mono", "Consolas", "Roboto Mono", monospace',
                            fontSize: '0.6875rem',
                            color: 'text.disabled',
                            pl: 2,
                          }}
                        >
                          —
                        </Typography>
                      )}
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
        </Box>
      </Box>
    </Box>
  );
};

export default AllTasks;
