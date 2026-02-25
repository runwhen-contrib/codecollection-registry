import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  CircularProgress,
  Alert,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  Button,
  Autocomplete,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import { Link, useSearchParams } from 'react-router-dom';
import { apiService, CodeBundle, CodeCollection } from '../services/api';

const CodeBundles: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [codebundles, setCodebundles] = useState<CodeBundle[]>([]);
  const [collections, setCollections] = useState<CodeCollection[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');
  const [selectedPlatform, setSelectedPlatform] = useState('');
  const [selectedAccessLevel, setSelectedAccessLevel] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [hasAutoDiscovery, setHasAutoDiscovery] = useState<string>('');
  const [sortBy, setSortBy] = useState('name');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [allTags, setAllTags] = useState<string[]>([]);
  const itemsPerPage = 24;

  // Fetch all tags on mount and set initial collection filter from URL
  useEffect(() => {
    const fetchCollectionsAndTags = async () => {
      try {
        const [collectionsData, allCodebundlesData] = await Promise.all([
          apiService.getCodeCollections(),
          apiService.getCodeBundles({ limit: 500 }), // Get all to extract unique tags
        ]);
        setCollections(collectionsData);
        
        // Extract unique tags
        const tagsSet = new Set<string>();
        allCodebundlesData.codebundles.forEach(cb => {
          if (cb.support_tags) {
            cb.support_tags.forEach(tag => tagsSet.add(tag));
          }
        });
        setAllTags(Array.from(tagsSet).sort());
        
        // Set collection filter from URL params
        const collectionParam = searchParams.get('collection');
        if (collectionParam) {
          setSelectedCollection(collectionParam);
        }
      } catch (err) {
        console.error('Error fetching collections and tags:', err);
      }
    };
    fetchCollectionsAndTags();
  }, [searchParams]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Use searching state for subsequent loads, initial loading for first load
        if (initialLoading) {
          setInitialLoading(true);
        } else {
          setSearching(true);
        }
        
        const offset = (page - 1) * itemsPerPage;
        const params: any = {
          limit: itemsPerPage,
          skip: offset,
        };
        
        if (searchTerm) params.search = searchTerm;
        if (selectedCollection) params.collection_id = parseInt(selectedCollection);
        if (selectedTags.length > 0) params.tags = selectedTags.join(',');
        if (selectedPlatform) params.platform = selectedPlatform;
        if (selectedAccessLevel) params.access_level = selectedAccessLevel;
        if (hasAutoDiscovery !== '') params.has_auto_discovery = hasAutoDiscovery === 'true';
        if (sortBy) params.sort_by = sortBy;
        
        const codebundlesData = await apiService.getCodeBundles(params);
        setCodebundles(codebundlesData.codebundles);
        setTotalCount(codebundlesData.total_count);
      } catch (err) {
        setError('Failed to load codebundles');
        console.error('Error fetching data:', err);
      } finally {
        setInitialLoading(false);
        setSearching(false);
      }
    };

    // Debounce search to avoid excessive API calls
    const timeoutId = setTimeout(() => {
      fetchData();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchTerm, selectedCollection, selectedPlatform, selectedAccessLevel, selectedTags, hasAutoDiscovery, sortBy, page]);

  if (initialLoading) {
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

  const totalPages = Math.ceil(totalCount / itemsPerPage);

  const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleClearFilters = () => {
    setSearchTerm('');
    setSelectedCollection('');
    setSelectedPlatform('');
    setSelectedAccessLevel('');
    setSelectedTags([]);
    setHasAutoDiscovery('');
    setPage(1);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          All CodeBundles
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {searching && <CircularProgress size={16} />}
          <Typography variant="body1" color="text.secondary">
            {searching ? 'Searching...' : `${totalCount} codebundle${totalCount !== 1 ? 's' : ''} found`}
          </Typography>
        </Box>
      </Box>

      {/* Search and Filter Controls */}
      <Card sx={{ mb: 3, p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <FilterListIcon color="primary" />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Search & Filters
          </Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Button size="small" onClick={handleClearFilters} variant="outlined">
            Clear All
          </Button>
        </Box>

        {/* Row 1: Search and Collection */}
        <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            placeholder="Search codebundles..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
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
            sx={{ flex: '1 1 300px' }}
            size="small"
          />
          
          <FormControl sx={{ flex: '1 1 200px' }} size="small">
            <InputLabel>Collection</InputLabel>
            <Select
              value={selectedCollection}
              onChange={(e) => { setSelectedCollection(e.target.value); setPage(1); }}
              label="Collection"
            >
              <MenuItem value="">All Collections</MenuItem>
              {collections.map((collection) => (
                <MenuItem key={collection.id} value={collection.id.toString()}>
                  {collection.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl sx={{ flex: '1 1 150px' }} size="small">
            <InputLabel>Sort By</InputLabel>
            <Select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              label="Sort By"
            >
              <MenuItem value="name">Name (A-Z)</MenuItem>
              <MenuItem value="updated">Recently Updated</MenuItem>
              <MenuItem value="tasks">Most Tasks</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {/* Row 2: Additional Filters */}
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Autocomplete
            multiple
            options={allTags}
            value={selectedTags}
            onChange={(event, newValue) => { setSelectedTags(newValue); setPage(1); }}
            renderInput={(params) => (
              <TextField {...params} label="Tags" placeholder="Select tags..." size="small" />
            )}
            sx={{ flex: '1 1 300px' }}
            size="small"
          />

          <FormControl sx={{ flex: '1 1 150px' }} size="small">
            <InputLabel>Platform</InputLabel>
            <Select
              value={selectedPlatform}
              onChange={(e) => { setSelectedPlatform(e.target.value); setPage(1); }}
              label="Platform"
            >
              <MenuItem value="">All Platforms</MenuItem>
              <MenuItem value="kubernetes">Kubernetes</MenuItem>
              <MenuItem value="aws">AWS</MenuItem>
              <MenuItem value="gcp">GCP</MenuItem>
              <MenuItem value="azure">Azure</MenuItem>
            </Select>
          </FormControl>

          <FormControl sx={{ flex: '1 1 150px' }} size="small">
            <InputLabel>Access Level</InputLabel>
            <Select
              value={selectedAccessLevel}
              onChange={(e) => { setSelectedAccessLevel(e.target.value); setPage(1); }}
              label="Access Level"
            >
              <MenuItem value="">All Levels</MenuItem>
              <MenuItem value="read-only">Read Only</MenuItem>
              <MenuItem value="read-write">Read/Write</MenuItem>
            </Select>
          </FormControl>

          <FormControl sx={{ flex: '1 1 150px' }} size="small">
            <InputLabel>Auto-Discovery</InputLabel>
            <Select
              value={hasAutoDiscovery}
              onChange={(e) => { setHasAutoDiscovery(e.target.value); setPage(1); }}
              label="Auto-Discovery"
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="true">Enabled</MenuItem>
              <MenuItem value="false">Manual Only</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Card>

      {/* CodeBundles Grid */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, opacity: searching ? 0.6 : 1, transition: 'opacity 0.2s' }}>
        {codebundles.map((codebundle) => (
          <Box key={codebundle.id} sx={{ flex: '0 0 calc(100% - 12px)', '@media (min-width: 600px)': { flex: '0 0 calc(50% - 12px)' }, '@media (min-width: 900px)': { flex: '0 0 calc(33.333% - 16px)' } }}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                '&:hover': {
                  boxShadow: 4,
                },
              }}
            >
              <CardActionArea
                component={Link}
                to={`/collections/${codebundle.codecollection?.slug}/codebundles/${codebundle.slug}`}
                sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>
                    {codebundle.display_name}
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {codebundle.description}
                  </Typography>

                  {codebundle.support_tags && codebundle.support_tags.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      {codebundle.support_tags.slice(0, 3).map((tag) => (
                        <Chip
                          key={tag}
                          label={tag}
                          size="small"
                          sx={{ mr: 1, mb: 1 }}
                        />
                      ))}
                      {codebundle.support_tags.length > 3 && (
                        <Chip
                          label={`+${codebundle.support_tags.length - 3} more`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  )}

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      {(codebundle.task_count || 0) + (codebundle.sli_count || 0)} task{((codebundle.task_count || 0) + (codebundle.sli_count || 0)) !== 1 ? 's' : ''}
                      {codebundle.sli_count > 0 && (
                        <Typography component="span" variant="caption" sx={{ ml: 0.5 }}>
                          ({codebundle.sli_count} SLI)
                        </Typography>
                      )}
                    </Typography>
                    {codebundle.codecollection && (
                      <Typography variant="body2" color="primary">
                        {codebundle.codecollection.name}
                      </Typography>
                    )}
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
            </Box>
          ))}
        </Box>

      {codebundles.length === 0 && !searching && (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No codebundles found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Try adjusting your filters or search terms
          </Typography>
        </Box>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
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
    </Container>
  );
};

export default CodeBundles;