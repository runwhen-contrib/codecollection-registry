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
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { Link } from 'react-router-dom';
import { apiService, CodeBundle, CodeCollection } from '../services/api';

const CodeBundles: React.FC = () => {
  const [codebundles, setCodebundles] = useState<CodeBundle[]>([]);
  const [collections, setCollections] = useState<CodeCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [codebundlesData, collectionsData] = await Promise.all([
          apiService.getCodeBundles({
            search: searchTerm || undefined,
            collection_id: selectedCollection ? parseInt(selectedCollection) : undefined,
          }),
          apiService.getCodeCollections(),
        ]);
        setCodebundles(codebundlesData);
        setCollections(collectionsData);
      } catch (err) {
        setError('Failed to load codebundles');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [searchTerm, selectedCollection]);

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

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h1" sx={{ mb: 4 }}>
        CodeBundles
      </Typography>

      {/* Search and Filter Controls */}
      <Box sx={{ mb: 4, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          placeholder="Search codebundles..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 300 }}
        />
        
        <FormControl sx={{ minWidth: 200 }}>
          <InputLabel>Collection</InputLabel>
          <Select
            value={selectedCollection}
            onChange={(e) => setSelectedCollection(e.target.value)}
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
      </Box>

      {/* CodeBundles Grid */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
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
                to={`/codebundles/${codebundle.id}`}
                sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" fontWeight="bold" sx={{ mb: 1 }}>
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
                      {codebundle.task_count} tasks
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

      {codebundles.length === 0 && !loading && (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No codebundles found
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default CodeBundles;