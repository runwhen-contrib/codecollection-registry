import React, { useState, useEffect, useMemo } from 'react';
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
  Tabs,
  Tab,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Avatar,
  Breadcrumbs,
} from '@mui/material';
import { 
  GitHub as GitHubIcon, 
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  AutoAwesome as AutoAwesomeIcon,
  Security as SecurityIcon,
  InfoOutlined as InfoIcon,
  Person as PersonIcon,
  CalendarToday as CalendarIcon,
  Code as CodeIcon,
  Language as LanguageIcon,
  Shield as ShieldIcon,
  Verified as VerifiedIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { useParams, Link, useNavigate } from 'react-router-dom';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiService, CodeBundle } from '../services/api';
import { labelForType } from '../lib/terminology';

/** Strip a leading `--- ... ---` YAML frontmatter block. */
const stripFrontmatter = (text: string): string =>
  (text || '').replace(/^\uFEFF?---\s*\r?\n[\s\S]*?\r?\n---\s*\r?\n?/, '').trim();

/**
 * Inline-code references such as `kubernetes:k8s-workload-ops/delete-pods`
 * or `kubernetes:k8s-postgres-operator-health` point at a sibling skill.
 */
const CROSS_SKILL_RE = /^([a-z0-9-]+):([a-z0-9-]+)(?:\/([a-z0-9-]+))?$/;

const monospace = { fontFamily: 'monospace' } as const;

const SkillMarkdown: React.FC<{ content: string }> = ({ content }) => {
  const components = useMemo<Components>(() => ({
    h1: ({ children }) => (
      <Typography variant="h6" sx={{ mt: 3, mb: 1.5, fontWeight: 600, color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    h2: ({ children }) => (
      <Typography variant="h6" sx={{ mt: 3.5, mb: 1.5, fontWeight: 600, fontSize: '1.05rem', color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    h3: ({ children }) => (
      <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600, color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    h4: ({ children }) => (
      <Typography variant="subtitle2" sx={{ mt: 2.5, mb: 1, fontWeight: 600, color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    p: ({ children }) => (
      <Typography variant="body1" sx={{ mb: 2, lineHeight: 1.7, color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    ul: ({ children }) => (
      <Box component="ul" sx={{ mt: 0, mb: 2, pl: 3, '& li': { mb: 0.75 } }}>
        {children}
      </Box>
    ),
    ol: ({ children }) => (
      <Box component="ol" sx={{ mt: 0, mb: 2, pl: 3, '& li': { mb: 0.75 } }}>
        {children}
      </Box>
    ),
    li: ({ children }) => (
      <Typography component="li" variant="body1" sx={{ lineHeight: 1.7, color: 'text.primary' }}>
        {children}
      </Typography>
    ),
    blockquote: ({ children }) => (
      <Box
        sx={{
          borderLeft: '3px solid',
          borderColor: 'primary.main',
          pl: 2,
          my: 2,
          color: 'text.secondary',
          bgcolor: 'action.hover',
          borderRadius: 1,
          py: 0.5,
          '& p:last-of-type': { mb: 0 },
        }}
      >
        {children}
      </Box>
    ),
    hr: () => <Divider sx={{ my: 3 }} />,
    a: ({ href, children }) => (
      <Box
        component="a"
        href={href}
        target={href?.startsWith('http') ? '_blank' : undefined}
        rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
        sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
      >
        {children}
      </Box>
    ),
    table: ({ children }) => (
      <Box sx={{ overflowX: 'auto', my: 2 }}>
        <Box
          component="table"
          sx={{
            borderCollapse: 'collapse',
            width: '100%',
            fontSize: '0.875rem',
            '& th, & td': {
              border: '1px solid',
              borderColor: 'divider',
              px: 1.5,
              py: 1,
              textAlign: 'left',
              verticalAlign: 'top',
            },
            '& th': { bgcolor: 'action.hover', fontWeight: 600 },
          }}
        >
          {children}
        </Box>
      </Box>
    ),
    pre: ({ children }) => (
      <Box
        component="pre"
        sx={{
          bgcolor: 'action.hover',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 2,
          mb: 2,
          overflowX: 'auto',
          fontSize: '0.8125rem',
          lineHeight: 1.6,
          ...monospace,
        }}
      >
        {children}
      </Box>
    ),
    code: ({ className, children }) => {
      const text = String(children ?? '').replace(/\n$/, '');
      if (className) {
        // Fenced code block — `pre` provides the frame and typography.
        return <code className={className}>{children}</code>;
      }
      const match = CROSS_SKILL_RE.exec(text.trim());
      if (match) {
        const [, plugin, skill] = match;
        return (
          <Chip
            component={Link}
            to={`/plugins/${plugin}/skills/${skill}`}
            clickable
            size="small"
            label={text.trim()}
            color="primary"
            variant="outlined"
            sx={{
              height: 24,
              fontSize: '0.75rem',
              fontWeight: 500,
              my: 0.25,
              ...monospace,
              '& .MuiChip-label': { px: 1 },
            }}
          />
        );
      }
      return (
        <Box
          component="code"
          sx={{
            ...monospace,
            fontSize: '0.8125rem',
            px: 0.6,
            py: 0.15,
            borderRadius: 0.75,
            bgcolor: 'action.hover',
            border: '1px solid',
            borderColor: 'divider',
            color: 'text.primary',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {children}
        </Box>
      );
    },
  }), []);

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
};

const MetaSection: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <Box sx={{ mt: 2 }}>
    <Typography
      variant="caption"
      sx={{ display: 'block', mb: 0.75, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'text.secondary' }}
    >
      {label}
    </Typography>
    {children}
  </Box>
);

const SkillDetail: React.FC = () => {
  const { collectionSlug, codebundleSlug } = useParams<{ collectionSlug: string; codebundleSlug: string }>();
  const navigate = useNavigate();
  const [codebundle, setCodebundle] = useState<CodeBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState(0);
  const [tasksTab, setTasksTab] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      if (!collectionSlug || !codebundleSlug) return;
      
      try {
        const codebundleData = await apiService.getCodeBundleBySlug(collectionSlug, codebundleSlug);
        setCodebundle(codebundleData);
      } catch (err) {
        setError('Failed to load skill');
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [collectionSlug, codebundleSlug]);

  const docMarkdown = useMemo(
    () => stripFrontmatter(codebundle?.doc || codebundle?.readme || ''),
    [codebundle]
  );

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
        <Alert severity="warning">Skill not found</Alert>
      </Container>
    );
  }

  const pluginName = codebundle.codecollection?.name || 'Plugins';
  const pluginSlug = codebundle.codecollection?.slug;
  const totalTools = (codebundle.task_count || 0) + (codebundle.sli_count || 0);
  const toolCount = codebundle.tasks?.length || 0;
  const variableCount = codebundle.user_variables?.length || 0;
  const iamRequirements = codebundle.minimum_iam_requirements || [];
  const hasSliTab = !!codebundle.slis && codebundle.slis.length > 0;
  const platformName = (codebundle as any).platform || codebundle.configuration_type?.platform || 'N/A';

  return (
    <Container maxWidth="lg" sx={{ mt: 3, mb: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs
        aria-label="breadcrumb"
        sx={{ mb: 2, fontSize: '0.8125rem', '& .MuiBreadcrumbs-separator': { mx: 1 } }}
      >
        <Typography
          component={Link}
          to="/plugins"
          sx={{ fontSize: '0.8125rem', color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
        >
          Plugins
        </Typography>
        {pluginSlug && (
          <Typography
            component={Link}
            to={`/plugins/${pluginSlug}`}
            sx={{ fontSize: '0.8125rem', color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
          >
            {pluginName}
          </Typography>
        )}
        <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary' }}>
          {codebundle.display_name}
        </Typography>
      </Breadcrumbs>

      {/* Header */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
            {codebundle.display_name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
            {codebundle.access_level && codebundle.access_level !== 'unknown' && (
              <Chip
                label={codebundle.access_level}
                size="small"
                color={codebundle.access_level === 'read-only' ? 'success' : 'warning'}
                variant="outlined"
                sx={{ height: 24, fontSize: '0.75rem', fontWeight: 600 }}
              />
            )}
            <Chip
              label={`${totalTools} Task${totalTools !== 1 ? 's' : ''}`}
              size="small"
              variant="outlined"
              sx={{ height: 24, fontSize: '0.75rem' }}
            />
          </Box>
        </Box>

        <Button
          variant="outlined"
          color="primary"
          startIcon={
            <Avatar 
              src="https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Eager-Edgar-Happy.png"
              sx={{ width: 20, height: 20, backgroundColor: 'transparent' }}
            />
          }
          onClick={() => {
            const context = `I have a question about the "${codebundle.display_name}" Skill from the ${codebundle.codecollection?.name || 'unknown'} plugin.\n\nSkill Details:\n- Description: ${codebundle.description || 'N/A'}\n- Platform: ${platformName}\n- Tasks: ${codebundle.task_count || 0}\n- Access Level: ${codebundle.access_level || 'N/A'}`;
            
            navigate('/chat', { 
              state: { 
                initialQuery: context,
                codebundleContext: {
                  name: codebundle.display_name,
                  slug: codebundle.slug,
                  collectionSlug: codebundle.codecollection?.slug,
                  description: codebundle.description,
                  tasks: codebundle.tasks,
                  platform: platformName,
                  accessLevel: codebundle.access_level,
                  iamRequirements: codebundle.minimum_iam_requirements
                }
              } 
            });
          }}
        >
          Ask Eager Edgar
        </Button>
      </Box>

      {/* Lead summary */}
      {codebundle.description && (
        <Typography
          variant="body1"
          sx={{ mb: 3, fontSize: '15px', lineHeight: 1.65, color: 'text.secondary', maxWidth: '80ch' }}
        >
          {codebundle.description}
        </Typography>
      )}

      <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Sidebar - Left */}
        <Box sx={{ flex: '0 0 280px', minWidth: { xs: '100%', md: 280 } }}>
          
          {/* Support Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <VerifiedIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                  Support
                </Typography>
              </Box>
              
              {codebundle.codecollection?.git_url && codebundle.codecollection.git_url.includes('runwhen-contrib') ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                    RunWhen Supported
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    Community
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Languages / Tags Section */}
          {codebundle.support_tags && codebundle.support_tags.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <LanguageIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                    Tags
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {codebundle.support_tags.map((tag, index) => (
                    <Chip
                      key={index}
                      label={tag}
                      size="small"
                      sx={{ fontSize: '0.75rem', height: 24 }}
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Configuration Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <CodeIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                  Configuration
                </Typography>
              </Box>
              
              {codebundle.configuration_type?.platform && codebundle.configuration_type.platform !== 'Unknown' && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Platform
                  </Typography>
                  <Chip 
                    label={codebundle.configuration_type.platform.toUpperCase()} 
                    size="small" 
                    color="primary"
                    sx={{ fontWeight: 600 }}
                  />
                </Box>
              )}
              
              {/* Auto-Discovery Status */}
              {codebundle.configuration_type && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Auto-Discovery
                  </Typography>
                  {codebundle.configuration_type.has_generation_rules ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main' }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                        Enabled
                      </Typography>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <WarningIcon sx={{ fontSize: '1rem', color: 'warning.main' }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                        Manual Configuration Only
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
              
              {codebundle.configuration_type?.resource_types && codebundle.configuration_type.resource_types.length > 0 && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Resource Types
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {codebundle.configuration_type.resource_types.map((type, index) => (
                      <Chip 
                        key={index}
                        label={type} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.75rem', height: 24 }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
              
              {codebundle.configuration_type?.level_of_detail && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Level of Detail
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {codebundle.configuration_type.level_of_detail}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Security & Access Section */}
          {(codebundle.access_level !== 'unknown' || iamRequirements.length > 0) && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <ShieldIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                    Security & Access
                  </Typography>
                </Box>
                
                {codebundle.access_level !== 'unknown' && (
                  <Box sx={{ mb: 1.5 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      Access Level
                    </Typography>
                    <Chip 
                      label={codebundle.access_level} 
                      size="small"
                      color={
                        codebundle.access_level === 'read-only' ? 'success' :
                        codebundle.access_level === 'read-write' ? 'warning' : 'default'
                      }
                      sx={{ fontWeight: 600 }}
                    />
                  </Box>
                )}
                
                {iamRequirements.length > 0 && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      IAM Requirements ({iamRequirements.length})
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {iamRequirements.slice(0, 4).map((req, index) => (
                        <Chip 
                          key={index}
                          label={req} 
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem', height: 22, maxWidth: '100%', ...monospace, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                        />
                      ))}
                      {iamRequirements.length > 4 && (
                        <Chip
                          label={`+${iamRequirements.length - 4} more`}
                          size="small"
                          onClick={() => setMainTab(3)}
                          clickable
                          color="primary"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem', height: 22, fontWeight: 600 }}
                        />
                      )}
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {/* Data Classification Section */}
          {codebundle.data_classifications && Object.keys(codebundle.data_classifications).length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                  <StorageIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                    Data Classification
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                  {Object.entries(codebundle.data_classifications).map(([tag, info]) => {
                    const isConfig = tag === 'data:config';
                    const isLogs = tag.startsWith('data:logs');
                    const chipColor = isConfig ? 'info' : isLogs ? 'warning' : 'default';
                    const tagLabel = tag.replace('data:', '');
                    return (
                      <Tooltip key={tag} title={`${info.label} — ${info.count} task${info.count !== 1 ? 's' : ''}`}>
                        <Chip
                          label={tagLabel}
                          size="small"
                          color={chipColor as any}
                          variant="outlined"
                          sx={{ fontWeight: 600, fontSize: '0.75rem' }}
                        />
                      </Tooltip>
                    );
                  })}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Details Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <CodeIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                  Details
                </Typography>
              </Box>
              
              <Box sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <PersonIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Author
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {codebundle.author}
                </Typography>
              </Box>

              <Box sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <CalendarIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Last Updated
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {new Date(codebundle.git_updated_at || codebundle.updated_at).toLocaleDateString()}
                </Typography>
              </Box>

              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                  <CodeIcon sx={{ fontSize: '0.9rem', color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary">
                    Total Tasks
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, pl: 2.5 }}>
                  {`${totalTools} Tasks`}
                  {codebundle.sli_count > 0 && codebundle.task_count > 0 && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      ({codebundle.task_count} {labelForType('TaskSet')} + {codebundle.sli_count} {labelForType('SLI')})
                    </Typography>
                  )}
                </Typography>
              </Box>
            </CardContent>
          </Card>

          {/* Source Code Section */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                <GitHubIcon sx={{ fontSize: '1.1rem', mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                  Source Code
                </Typography>
              </Box>
              
              {codebundle.codecollection && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Plugin
                  </Typography>
                  <Link 
                    to={`/plugins/${codebundle.codecollection.slug}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <Typography variant="body2" color="primary" sx={{ fontWeight: 500 }}>
                      {codebundle.codecollection.name}
                    </Typography>
                  </Link>
                </Box>
              )}
              
              {codebundle.codecollection?.git_url && (
                <Button
                  variant="outlined"
                  startIcon={<GitHubIcon />}
                  href={codebundle.runbook_source_url || `${codebundle.codecollection.git_url}/tree/${(codebundle.codecollection as any).git_ref || 'main'}/codebundles/${codebundle.slug}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  fullWidth
                  size="small"
                  sx={{ textTransform: 'none', fontSize: '0.8125rem' }}
                >
                  View on GitHub
                </Button>
              )}
            </CardContent>
          </Card>

        </Box>

        {/* Main Content - Right */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {/* Main Tabs */}
          <Card sx={{ mb: 4 }}>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={mainTab} onChange={(e, newValue) => setMainTab(newValue)} variant="scrollable" allowScrollButtonsMobile>
                <Tab label="Skill" sx={{ textTransform: 'none' }} />
                <Tab label={`Tasks (${toolCount})`} sx={{ textTransform: 'none' }} />
                <Tab label={`Variables (${variableCount})`} sx={{ textTransform: 'none' }} />
                <Tab label="Security" sx={{ textTransform: 'none' }} />
                <Tab label="Updates" sx={{ textTransform: 'none' }} />
              </Tabs>
            </Box>
            
            {/* Skill Tab */}
            {mainTab === 0 && (
              <CardContent>
                {docMarkdown ? (
                  <>
                    <SkillMarkdown content={docMarkdown} />
                    {codebundle.runbook_source_url?.includes('/plugins/') ? (
                      <Typography variant="body2" sx={{ mt: 3, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                        <a
                          href={`${codebundle.runbook_source_url}/SKILL.md`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'inherit' }}
                        >
                          View SKILL.md on GitHub →
                        </a>
                      </Typography>
                    ) : codebundle.codecollection?.git_url && (
                      <Typography variant="body2" sx={{ mt: 3, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                        <a
                          href={`${codebundle.codecollection.git_url}/blob/${(codebundle.codecollection as any).git_ref || 'main'}/codebundles/${codebundle.slug}/README.md`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'inherit' }}
                        >
                          View README on GitHub →
                        </a>
                      </Typography>
                    )}
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No skill definition available.
                  </Typography>
                )}
              </CardContent>
            )}
            
            {/* Tasks Tab */}
            {mainTab === 1 && (
              <CardContent>
                {((codebundle.tasks && codebundle.tasks.length > 0) || (codebundle.slis && codebundle.slis.length > 0)) ? (
                  <Box>
                    {/* Inner Runbook / Monitor tabs only when the skill has Monitors */}
                    {hasSliTab && (
                      <Box sx={{ borderBottom: 1, borderColor: 'divider', mx: -2, px: 2, mb: 2 }}>
                        <Tabs value={tasksTab} onChange={(e, newValue) => setTasksTab(newValue)}>
                          {codebundle.tasks && codebundle.tasks.length > 0 && (
                            <Tab 
                              label={
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  {labelForType('TaskSet')} ({codebundle.tasks.length})
                                  <Tooltip 
                                    title="A Runbook is a Task that runs on demand in response to an event or request and emits structured findings with next-steps. Use them for troubleshooting, operations, and incident response."
                                    arrow
                                  >
                                    <InfoIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                                  </Tooltip>
                                </Box>
                              }
                            />
                          )}
                          {codebundle.slis && codebundle.slis.length > 0 && (
                            <Tab 
                              label={
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  {labelForType('SLI')} ({codebundle.slis.length})
                                  <Tooltip 
                                    title="A Monitor is a Task that runs on a schedule, continuously, in the background. It emits a numeric 0-1 health value used to track service health and performance over time."
                                    arrow
                                  >
                                    <InfoIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                                  </Tooltip>
                                </Box>
                              }
                            />
                          )}
                        </Tabs>
                      </Box>
                    )}
                    
                    {/* TaskSet panel */}
                    {codebundle.tasks && codebundle.tasks.length > 0 && (!hasSliTab || tasksTab === 0) && (
                      <Box>
                        {codebundle.tasks.map((raw, index) => {
                          const task: any = typeof raw === 'string' ? { name: raw } : (raw as any) || {};
                          const taskName: string = task.name || task.title || 'Unnamed Task';
                          const taskTitle: string = task.title || taskName;
                          const taskDoc: string | undefined = task.description || task.doc;
                          const readOnly = task.readOnly;
                          const accessChip = readOnly === false ? 'read-write' : readOnly === true ? 'read-only' : null;
                          const inputs = task.inputs && typeof task.inputs === 'object' ? Object.entries(task.inputs) : [];
                          const outputs = task.outputs && typeof task.outputs === 'object' ? Object.entries(task.outputs) : [];
                          const effects: string[] = Array.isArray(task.effects) ? task.effects : [];
                          const permissions: string[] = Array.isArray(task.permissions) ? task.permissions : [];
                          const showEffects = effects.length > 0 && (readOnly === false || task.destructive);
                          const hasDetails = inputs.length > 0 || outputs.length > 0 || showEffects || permissions.length > 0;

                          return (
                            <Paper key={index} variant="outlined" sx={{ p: 2.5, mb: 2, borderRadius: 2 }}>
                              {/* Header row */}
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: taskDoc ? 1 : 0 }}>
                                <Typography sx={{ fontWeight: 600, fontSize: '1rem', color: 'text.primary' }}>
                                  {taskTitle}
                                </Typography>
                                {taskTitle !== taskName && (
                                  <Chip
                                    label={taskName}
                                    size="small"
                                    variant="outlined"
                                    sx={{ height: 22, fontSize: '0.75rem', ...monospace }}
                                  />
                                )}
                                <Box sx={{ flexGrow: 1 }} />
                                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                  {accessChip && (
                                    <Chip
                                      label={accessChip}
                                      size="small"
                                      color={accessChip === 'read-write' ? 'warning' : 'success'}
                                      variant="outlined"
                                      sx={{ fontSize: '0.75rem', height: 22, fontWeight: 600 }}
                                    />
                                  )}
                                  {task.destructive && (
                                    <Chip label="destructive" size="small" color="error" variant="outlined" sx={{ fontSize: '0.75rem', height: 22, fontWeight: 600 }} />
                                  )}
                                  {task.dryRun && (
                                    <Chip label="dry-run" size="small" color="info" variant="outlined" sx={{ fontSize: '0.75rem', height: 22, fontWeight: 600 }} />
                                  )}
                                  {task.timeout && (
                                    <Chip label={`timeout ${task.timeout}`} size="small" variant="outlined" sx={{ fontSize: '0.75rem', height: 22 }} />
                                  )}
                                </Box>
                              </Box>

                              {taskDoc && (
                                <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.6, mt: 0.5 }}>
                                  {taskDoc}
                                </Typography>
                              )}

                              {hasDetails && (
                                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                                  {inputs.length > 0 && (
                                    <MetaSection label="Inputs">
                                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                        {inputs.map(([name, spec]: [string, any]) => (
                                          <Box key={name} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
                                            <Typography component="span" variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 600, ...monospace }}>
                                              {name}
                                            </Typography>
                                            <Typography component="span" variant="caption" color="text.secondary">
                                              ({spec?.type || 'string'}{spec?.default !== undefined && spec?.default !== null ? `, default ${String(spec.default)}` : ''})
                                            </Typography>
                                            {spec?.description && (
                                              <Typography component="span" variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
                                                {spec.description}
                                              </Typography>
                                            )}
                                          </Box>
                                        ))}
                                      </Box>
                                    </MetaSection>
                                  )}

                                  {outputs.length > 0 && (
                                    <MetaSection label="Outputs">
                                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                        {outputs.map(([name, spec]: [string, any]) => (
                                          <Box key={name} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
                                            <Typography component="span" variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 600, ...monospace }}>
                                              {name}
                                            </Typography>
                                            {spec?.description && (
                                              <Typography component="span" variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
                                                {spec.description}
                                              </Typography>
                                            )}
                                          </Box>
                                        ))}
                                      </Box>
                                    </MetaSection>
                                  )}

                                  {showEffects && (
                                    <MetaSection label="Side Effects">
                                      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                                        {effects.map((effect, effectIndex) => (
                                          <Typography component="li" key={effectIndex} variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem', mb: 0.25 }}>
                                            {effect}
                                          </Typography>
                                        ))}
                                      </Box>
                                    </MetaSection>
                                  )}

                                  {permissions.length > 0 && (
                                    <MetaSection label="Permissions">
                                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {permissions.map((perm, permIndex) => (
                                          <Chip
                                            key={permIndex}
                                            label={perm}
                                            size="small"
                                            variant="outlined"
                                            sx={{ height: 22, fontSize: '0.7rem', ...monospace }}
                                          />
                                        ))}
                                      </Box>
                                    </MetaSection>
                                  )}
                                </Box>
                              )}
                            </Paper>
                          );
                        })}
                      </Box>
                    )}
                    
                    {/* SLI panel */}
                    {codebundle.slis && codebundle.slis.length > 0 && tasksTab === (codebundle.tasks && codebundle.tasks.length > 0 ? 1 : 0) && (
                      <Box>
                        <List disablePadding>
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
                      </Box>
                    )}
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No Tasks defined for this Skill.
                  </Typography>
                )}
              </CardContent>
            )}
            
            {/* Variables Tab */}
            {mainTab === 2 && (
              <CardContent>
                {codebundle.user_variables && codebundle.user_variables.length > 0 ? (
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      These variables can be overridden or tuned as needed:
                    </Typography>
                    <TableContainer component={Paper} variant="outlined">
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 600 }}>Variable</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Scope</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Default</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {codebundle.user_variables.map((variable, index) => {
                            const defaultDisplay =
                              variable.default !== null && variable.default !== undefined && variable.default !== ''
                                ? String(variable.default)
                                : (variable.example || '—');
                            return (
                              <TableRow key={index} hover>
                                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                                  {variable.name}
                                </TableCell>
                                <TableCell sx={{ fontSize: '0.8125rem', color: 'text.secondary' }}>
                                  {variable.type || 'string'}
                                </TableCell>
                                <TableCell sx={{ fontSize: '0.875rem' }}>
                                  {variable.scope
                                    ? `${variable.scope}${variable.task ? ` \u00b7 ${variable.task}` : ''}`
                                    : '-'}
                                </TableCell>
                                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: 'text.secondary' }}>
                                  {defaultDisplay}
                                </TableCell>
                                <TableCell sx={{ fontSize: '0.875rem' }}>
                                  {variable.description || '—'}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                ) : (
                  <Box sx={{ mt: 4, p: 3, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <InfoIcon sx={{ fontSize: '1.2rem', color: 'info.main', mt: 0.25 }} />
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                          No User Variables Documented
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          This Skill may not require user-configured variables, or they have not been extracted yet. 
                          Check the source code on GitHub for the complete configuration requirements.
                        </Typography>
                        {codebundle.codecollection?.git_url && (
                          <Button
                            variant="outlined"
                            size="small"
                            startIcon={<GitHubIcon />}
                            href={codebundle.runbook_source_url || `${codebundle.codecollection.git_url}/tree/${(codebundle.codecollection as any).git_ref || 'main'}/codebundles/${codebundle.slug}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            sx={{ mt: 2, textTransform: 'none' }}
                          >
                            View Source on GitHub
                          </Button>
                        )}
                      </Box>
                    </Box>
                  </Box>
                )}
              </CardContent>
            )}
            
            {/* Security Tab */}
            {mainTab === 3 && (
              <CardContent>
                <Typography variant="h6" sx={{ mb: 3, fontWeight: 600 }}>
                  Security & Access Requirements
                </Typography>
                
                {/* Access Level */}
                {codebundle.access_level && codebundle.access_level !== 'unknown' && (
                  <Box sx={{ mb: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <SecurityIcon sx={{ fontSize: '1.2rem', color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        Access Level
                      </Typography>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                      <Chip 
                        label={codebundle.access_level.toUpperCase()} 
                        size="small"
                        color={
                          codebundle.access_level === 'read-only' ? 'success' :
                          codebundle.access_level === 'read-write' ? 'warning' : 'default'
                        }
                        sx={{ fontWeight: 600, fontSize: '0.75rem' }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {codebundle.access_level === 'read-only' 
                        ? 'This Skill requires read-only access to resources. It will not make changes to your infrastructure.'
                        : codebundle.access_level === 'read-write'
                        ? 'This Skill requires read-write access and may modify resources in your infrastructure.'
                        : 'Access level requirements for this Skill.'}
                    </Typography>
                  </Box>
                )}
                
                {/* IAM Requirements */}
                {iamRequirements.length > 0 && (
                  <Box sx={{ mb: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <ShieldIcon sx={{ fontSize: '1.2rem', color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        IAM Requirements
                      </Typography>
                      <Chip 
                        label={`${iamRequirements.length} permission${iamRequirements.length !== 1 ? 's' : ''}`} 
                        size="small" 
                        color="primary"
                        sx={{ ml: 1 }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      The following IAM permissions are required to execute this Skill:
                    </Typography>
                    <Box 
                      component="ul" 
                      sx={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        gap: 0.5, 
                        pl: 2,
                        m: 0,
                        listStyleType: 'disc'
                      }}
                    >
                      {iamRequirements.map((req, index) => (
                        <Box 
                          component="li" 
                          key={index}
                          sx={{ pl: 0.5 }}
                        >
                          <Typography 
                            variant="body2" 
                            sx={{ 
                              fontFamily: 'monospace', 
                              fontSize: '0.875rem',
                              wordBreak: 'break-all'
                            }}
                          >
                            {req}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                )}
                
                {/* Additional Security Information */}
                <Box sx={{ mt: 4, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                    <InfoIcon sx={{ fontSize: '1rem', color: 'info.main', mt: 0.25 }} />
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                        Security Best Practices
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Always follow the principle of least privilege when granting IAM permissions. 
                        Review these requirements with your security team before deployment.
                      </Typography>
                    </Box>
                  </Box>
                </Box>
                
                {!codebundle.access_level && iamRequirements.length === 0 && (
                  <Alert severity="info">
                    No specific security requirements have been documented for this Skill.
                  </Alert>
                )}
              </CardContent>
            )}
            
            {/* Updates Tab */}
            {mainTab === 4 && (
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Version History
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {/* Latest Update */}
                  <Box sx={{ pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Chip 
                        label="Current" 
                        size="small" 
                        color="primary"
                        sx={{ fontWeight: 600 }}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {new Date(codebundle.git_updated_at || codebundle.updated_at).toLocaleDateString('en-US', { 
                          year: 'numeric', 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      <strong>Tasks:</strong> {totalTools} Task{totalTools !== 1 ? 's' : ''}
                      {codebundle.tasks && codebundle.tasks.length > 0 && ` (${codebundle.tasks.length} ${labelForType('TaskSet', codebundle.tasks.length !== 1)})`}
                      {codebundle.slis && codebundle.slis.length > 0 && ` + ${codebundle.slis.length} ${labelForType('SLI', codebundle.slis.length !== 1)}`}
                    </Typography>
                    {codebundle.configuration_type?.platform && codebundle.configuration_type.platform !== 'Unknown' && (
                      <Typography variant="body2">
                        <strong>Platform:</strong> {codebundle.configuration_type.platform}
                      </Typography>
                    )}
                  </Box>

                  {/* Git Information */}
                  {codebundle.codecollection?.git_url && (
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                        Source Repository
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        View the complete change history and commit log on GitHub.
                      </Typography>
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<GitHubIcon />}
                        href={codebundle.runbook_source_url
                          ? `${codebundle.runbook_source_url}/commits`
                          : `${codebundle.codecollection.git_url}/commits/${(codebundle.codecollection as any).git_ref || 'main'}/codebundles/${codebundle.slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ textTransform: 'none' }}
                      >
                        View Commit History
                      </Button>
                    </Box>
                  )}
                </Box>
              </CardContent>
            )}
          </Card>

          {/* Enhanced Task Details */}
          {codebundle.ai_enhanced_metadata?.enhanced_tasks && 
           codebundle.ai_enhanced_metadata.enhanced_tasks.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <AutoAwesomeIcon sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Enhanced Task Details ({codebundle.ai_enhanced_metadata.enhanced_tasks.length})
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {codebundle.ai_enhanced_metadata.enhanced_tasks.map((task, index) => (
                    <Card key={index} variant="outlined">
                      <CardContent sx={{ p: 2 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                          {task.name}
                        </Typography>
                        
                        {task.ai_purpose && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                              Purpose:
                            </Typography>
                            <Typography variant="body2">
                              {task.ai_purpose}
                            </Typography>
                          </Box>
                        )}
                        
                        {task.ai_function && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                              Function:
                            </Typography>
                            <Typography variant="body2">
                              {task.ai_function}
                            </Typography>
                          </Box>
                        )}
                        
                        {task.ai_requirements && task.ai_requirements.length > 0 && (
                          <Box sx={{ mb: 1 }}>
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
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
                            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
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
              </CardContent>
            </Card>
          )}
        </Box>

      </Box>
    </Container>
  );
};

export default SkillDetail;