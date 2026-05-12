/**
 * AdminCCVersions — admin view of the PAPI-facing CodeCollection
 * image catalog. Renders the data exposed at:
 *
 *   GET /api/v1/catalog/codecollections
 *   GET /api/v1/catalog/codecollections/{slug}
 *
 * The catalog is populated by `sync_image_tags_task` (see CCV.md), which
 * polls each CC's configured OCI registry on a schedule and upserts a
 * CodeCollectionVersion row per discovered ref. This page is purely
 * read-only — for manual sync triggers, use the Schedules tab or the
 * Data Management tab.
 */
import React, { useState, useEffect, useCallback } from 'react';
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
  FormControlLabel,
  Switch,
  InputLabel,
  GridLegacy as Grid,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Link,
} from '@mui/material';
import {
  FilterList as FilterIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  Inventory2 as CatalogIcon,
  OpenInNew as ExternalLinkIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';

// Mirrors the Pydantic schemas in app/schemas/cc_catalog.py. Keep field
// names aligned with backend — these are part of the PAPI contract.
interface ImageRef {
  ref: string;
  ref_type: string;
  image_registry: string | null;
  image_tag: string;
  image_digest: string | null;
  commit_hash: string | null;
  rt_revision: string | null;
  image_built_at: string | null;
  is_latest: boolean;
  is_prerelease: boolean;
  is_active: boolean;
  synced_at: string | null;
}

interface CatalogEntry {
  slug: string;
  name: string;
  git_url: string;
  visibility: string;
  latest_image_tag: string | null;
  stable_image_tag: string | null;
  image_registry: string | null;
  last_synced: string | null;
}

interface CatalogEntryDetail extends CatalogEntry {
  refs: ImageRef[];
}

const formatTime = (iso: string | null): string => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
};

const truncate = (s: string | null | undefined, n = 12): string => {
  if (!s) return '—';
  return s.length > n ? `${s.slice(0, n)}…` : s;
};

const AdminCCVersions: React.FC = () => {
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState<'' | 'public' | 'hidden'>('');
  const [onlyWithImage, setOnlyWithImage] = useState(true);

  // Detail dialog
  const [detail, setDetail] = useState<CatalogEntryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);

  const loadEntries = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: Record<string, unknown> = {
        only_with_image: onlyWithImage,
      };
      if (visibilityFilter) params.visibility = visibilityFilter;
      const data: CatalogEntry[] = await apiService.getCatalogList(params);
      setEntries(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('Failed to load catalog:', err);
      setError(`Failed to load image catalog: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [onlyWithImage, visibilityFilter]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  const filteredEntries = entries.filter((e) => {
    if (!searchTerm) return true;
    const q = searchTerm.toLowerCase();
    return (
      e.slug.toLowerCase().includes(q) ||
      e.name.toLowerCase().includes(q) ||
      (e.image_registry ?? '').toLowerCase().includes(q)
    );
  });

  // ---------------------------------------------------------------------------
  // Derived stats
  // ---------------------------------------------------------------------------
  const totalTracked = entries.length;
  const publicCount = entries.filter((e) => e.visibility === 'public').length;
  const hiddenCount = entries.filter((e) => e.visibility === 'hidden').length;
  const mostRecentSync = entries.reduce<string | null>((acc, e) => {
    if (!e.last_synced) return acc;
    if (!acc) return e.last_synced;
    return new Date(e.last_synced) > new Date(acc) ? e.last_synced : acc;
  }, null);

  const openDetail = async (slug: string) => {
    try {
      setDetailLoading(true);
      setDetail(null);
      setDetailOpen(true);
      const data: CatalogEntryDetail = await apiService.getCatalogDetail(slug);
      setDetail(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('Failed to load CC detail:', err);
      setError(`Failed to load details for ${slug}: ${msg}`);
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetailOpen(false);
    setDetail(null);
  };

  const refTypeColor = (t: string) => {
    switch (t) {
      case 'tag':
      case 'release':
        return 'success';
      case 'branch':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 2, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h2" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
          <CatalogIcon sx={{ mr: 1 }} />
          CodeCollection Image Catalog
        </Typography>
        <Typography variant="body2" color="text.secondary">
          PAPI-facing image catalog: tracked OCI tags per CodeCollection, populated by{' '}
          <code>sync_image_tags_task</code>. Read-only view of{' '}
          <code>/api/v1/catalog/codecollections</code>.
        </Typography>
      </Box>

      {/* Stats */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Tracked CCs
              </Typography>
              <Typography variant="h4">{totalTracked}</Typography>
              <Typography variant="caption" color="textSecondary">
                {onlyWithImage ? 'with ≥1 image' : 'all'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Public
              </Typography>
              <Typography variant="h4">{publicCount}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Hidden
              </Typography>
              <Typography variant="h4">{hiddenCount}</Typography>
              <Typography variant="caption" color="textSecondary">
                synced for PAPI only
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Most recent sync
              </Typography>
              <Typography variant="body1" sx={{ fontWeight: 500 }}>
                {formatTime(mostRecentSync)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
            <FilterIcon sx={{ mr: 1 }} />
            Filters
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Search by slug, name, or registry"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  endAdornment: (
                    <IconButton size="small">
                      <SearchIcon />
                    </IconButton>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Visibility</InputLabel>
                <Select
                  value={visibilityFilter}
                  onChange={(e) => setVisibilityFilter(e.target.value as '' | 'public' | 'hidden')}
                  label="Visibility"
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="public">Public</MenuItem>
                  <MenuItem value="hidden">Hidden</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={onlyWithImage}
                    onChange={(e) => setOnlyWithImage(e.target.checked)}
                  />
                }
                label="Only with image"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Button
                fullWidth
                variant="outlined"
                onClick={loadEntries}
                startIcon={<RefreshIcon />}
              >
                Refresh
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Error / Loading / Empty / Table */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : filteredEntries.length === 0 ? (
        <Alert severity="info">
          No catalog entries match the current filters. If you expect rows here,
          confirm that <code>sync_image_tags_task</code> has run successfully
          (Schedules tab → manual trigger).
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>CodeCollection</TableCell>
                <TableCell>Visibility</TableCell>
                <TableCell>Image Registry</TableCell>
                <TableCell>Latest</TableCell>
                <TableCell>Stable</TableCell>
                <TableCell>Last Synced</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredEntries.map((e) => (
                <TableRow key={e.slug} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="bold">
                      {e.name}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      {e.slug}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={e.visibility}
                      color={e.visibility === 'hidden' ? 'warning' : 'success'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {e.image_registry ? (
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {e.image_registry}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="textSecondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {e.latest_image_tag ? (
                      <Chip
                        size="small"
                        label={e.latest_image_tag}
                        color="primary"
                        sx={{ fontFamily: 'monospace' }}
                      />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    {e.stable_image_tag ? (
                      <Chip
                        size="small"
                        label={e.stable_image_tag}
                        color="secondary"
                        sx={{ fontFamily: 'monospace' }}
                      />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption">{formatTime(e.last_synced)}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View all refs">
                      <IconButton size="small" onClick={() => openDetail(e.slug)}>
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                    {e.git_url && (
                      <Tooltip title="Open git repo">
                        <IconButton
                          size="small"
                          component={Link}
                          href={e.git_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLinkIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Detail dialog: full ref list for the selected CC */}
      <Dialog open={detailOpen} onClose={closeDetail} maxWidth="lg" fullWidth>
        <DialogTitle>
          {detail ? (
            <>
              {detail.name}{' '}
              <Typography component="span" variant="caption" color="textSecondary">
                ({detail.slug})
              </Typography>
            </>
          ) : (
            'Loading…'
          )}
        </DialogTitle>
        <DialogContent dividers>
          {detailLoading || !detail ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2">
                    <strong>Registry:</strong>{' '}
                    <span style={{ fontFamily: 'monospace' }}>
                      {detail.image_registry ?? '—'}
                    </span>
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2">
                    <strong>Latest:</strong> {detail.latest_image_tag ?? '—'}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Typography variant="body2">
                    <strong>Stable:</strong> {detail.stable_image_tag ?? '—'}
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="caption" color="textSecondary">
                    Last synced: {formatTime(detail.last_synced)} · {detail.refs.length} refs
                  </Typography>
                </Grid>
              </Grid>

              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Ref</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Image Tag</TableCell>
                      <TableCell>Digest</TableCell>
                      <TableCell>Commit</TableCell>
                      <TableCell>Runtime</TableCell>
                      <TableCell>Built</TableCell>
                      <TableCell>Flags</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detail.refs.map((r) => (
                      <TableRow key={`${r.ref}-${r.image_tag}`}>
                        <TableCell sx={{ fontFamily: 'monospace' }}>{r.ref}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={r.ref_type}
                            color={refTypeColor(r.ref_type) as any}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell sx={{ fontFamily: 'monospace' }}>{r.image_tag}</TableCell>
                        <TableCell>
                          <Tooltip title={r.image_digest ?? 'no digest'}>
                            <Typography
                              variant="caption"
                              sx={{ fontFamily: 'monospace' }}
                            >
                              {truncate(r.image_digest, 14)}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Tooltip title={r.commit_hash ?? 'no commit'}>
                            <Typography
                              variant="caption"
                              sx={{ fontFamily: 'monospace' }}
                            >
                              {truncate(r.commit_hash, 7)}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Tooltip title={r.rt_revision ?? 'no rt revision'}>
                            <Typography
                              variant="caption"
                              sx={{ fontFamily: 'monospace' }}
                            >
                              {truncate(r.rt_revision, 7)}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">
                            {formatTime(r.image_built_at)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {r.is_latest && (
                              <Chip size="small" label="latest" color="primary" />
                            )}
                            {r.is_prerelease && (
                              <Chip size="small" label="prerelease" color="warning" />
                            )}
                            {!r.is_active && (
                              <Chip size="small" label="inactive" color="default" />
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDetail}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminCCVersions;
