import React, { useState, useEffect } from 'react';
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
  TextField,
  Switch,
  FormControlLabel,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
} from '@mui/material';
import Editor from '@monaco-editor/react';
import {
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ContentCopy as ContentCopyIcon,
  GitHub as GitHubIcon,
  Clear as ClearIcon,
  DynamicForm as DynamicFormIcon,
  Code as CodeIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  PlayArrow as PlayArrowIcon,
  ArrowForward as ArrowForwardIcon,
  ArrowBack as ArrowBackIcon,
  Workspaces as WorkspaceIcon,
  Build as BuildIcon,
} from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { useCart } from '../contexts/CartContext';
import { apiService, HelmChart, HelmChartVersion, HelmChartTemplate } from '../services/api';
import WorkspaceBuilder from './WorkspaceBuilder';

interface HelmValues {
  // Chart Version Selection
  selectedChartVersion: string;
  
  // Global Settings
  workspaceName: string;
  platformType: string;
  platformArch: string;
  
  // Proxy Configuration
  proxyEnabled: boolean;
  proxyHost: string;
  proxyPort: string;
  proxyUsername: string;
  proxyPassword: string;
  httpProxy: string;
  httpsProxy: string;
  noProxy: string;
  
  // Proxy CA Configuration
  proxyCAEnabled: boolean;
  proxyCASecretName: string;
  proxyCAKey: string;
  
  // Registry Configuration
  registryEnabled: boolean;
  registryUrl: string;
  registryUsername: string;
  registryPassword: string;
  registryEmail: string;
  imagePullSecrets: boolean;
  registryOverride: string;
  
  // RunWhen Local Configuration
  runwhenLocalEnabled: boolean;
  runwhenLocalImage: string;
  runwhenLocalTag: string;
  clusterName: string;
  inClusterAuth: boolean;
  discoveryInterval: number;
  uploadEnabled: boolean;
  uploadMergeMode: string;
  terminalDisabled: boolean;
  debugLogs: boolean;
  
  // Upload Info Configuration
  uploadInfoEnabled: boolean;
  uploadInfoSecretName: string;
  uploadInfoSecretKey: string;
  
  // Workspace Info Configuration
  defaultLocation: string;
  workspaceOwnerEmail: string;
  defaultLOD: string;
  
  // Service Account Configuration
  serviceAccountCreate: boolean;
  serviceAccountName: string;
  clusterRoleViewEnabled: boolean;
  advancedClusterRoleEnabled: boolean;
  
  // Runner Configuration
  runnerEnabled: boolean;
  runnerImage: string;
  runnerTag: string;
  runnerLogLevel: string;
  runnerDebugLogs: boolean;
  runnerControlAddr: string;
  runnerMetricsUrl: string;
  
  // Code Collections
  codeCollections: Array<{
    repoURL: string;
    tag?: string;
    branch?: string;
    ref?: string;
    workerReplicas: number;
    name?: string;
  }>;
  
  // Security Context
  containerSecurityContextEnabled: boolean;
  allowPrivilegeEscalation: boolean;
  readOnlyRootFilesystem: boolean;
  
  // Resources
  resources: {
    requests: {
      cpu: string;
      memory: string;
    };
    limits: {
      cpu: string;
      memory: string;
    };
  };
  
  // Scheduling
  nodeSelector: Record<string, string>;
  tolerations: Array<{
    key: string;
    operator: string;
    value?: string;
    effect: string;
  }>;
  affinity: Record<string, any>;
  
  // Ingress Configuration
  ingressEnabled: boolean;
  ingressClassName: string;
  ingressHost: string;
  ingressTLSEnabled: boolean;
  ingressTLSSecretName: string;
}

const ConfigBuilder: React.FC = () => {
  const { items, removeFromCart, clearCart, getRepositoryConfigs } = useCart();
  const repositoryConfigs = getRepositoryConfigs();
  const [showYamlEditor, setShowYamlEditor] = useState(true);
  const [wizardStep, setWizardStep] = useState(0);
  const [wizardStarted, setWizardStarted] = useState(false);
  const [selectedWizard, setSelectedWizard] = useState<'helm' | 'workspace' | null>(null);
  
  // Helm chart version management
  const [helmChart, setHelmChart] = useState<HelmChart | null>(null);
  const [helmChartVersions, setHelmChartVersions] = useState<HelmChartVersion[]>([]);
  const [selectedChartVersion, setSelectedChartVersion] = useState<HelmChartVersion | null>(null);
  const [chartTemplates, setChartTemplates] = useState<HelmChartTemplate[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [helmValues, setHelmValues] = useState<HelmValues>({
    // Chart Version Selection
    selectedChartVersion: '',
    
    // Global Settings
    workspaceName: '',
    platformType: 'kubernetes',
    platformArch: 'amd64',
    
    // Proxy Configuration
    proxyEnabled: false,
    proxyHost: '',
    proxyPort: '8080',
    proxyUsername: '',
    proxyPassword: '',
    httpProxy: '',
    httpsProxy: '',
    noProxy: '127.0.0.1,localhost,$($KUBERNETES_SERVICE_HOST)',
    
    // Proxy CA Configuration
    proxyCAEnabled: false,
    proxyCASecretName: '',
    proxyCAKey: 'ca.crt',
    
    // Registry Configuration
    registryEnabled: false,
    registryUrl: '',
    registryUsername: '',
    registryPassword: '',
    registryEmail: '',
    imagePullSecrets: false,
    registryOverride: '',
    
    // RunWhen Local Configuration
    runwhenLocalEnabled: true,
    runwhenLocalImage: '',
    runwhenLocalTag: 'latest',
    clusterName: 'default',
    inClusterAuth: true,
    discoveryInterval: 14400,
    uploadEnabled: false,
    uploadMergeMode: 'keep-uploaded',
    terminalDisabled: true,
    debugLogs: false,
    
    // Upload Info Configuration
    uploadInfoEnabled: false,
    uploadInfoSecretName: 'uploadinfo',
    uploadInfoSecretKey: 'uploadInfo.yaml',
    
    // Workspace Info Configuration
    defaultLocation: 'none',
    workspaceOwnerEmail: 'tester@my-company.com',
    defaultLOD: 'detailed',
    
    // Service Account Configuration
    serviceAccountCreate: true,
    serviceAccountName: 'runwhen-local',
    clusterRoleViewEnabled: true,
    advancedClusterRoleEnabled: false,
    
    // Runner Configuration
    runnerEnabled: true,
    runnerImage: '',
    runnerTag: '',
    runnerLogLevel: 'info',
    runnerDebugLogs: true,
    runnerControlAddr: 'https://runner.beta.runwhen.com',
    runnerMetricsUrl: 'https://runner-cortex-tenant.beta.runwhen.com/push',
    
    // Code Collections
    codeCollections: [
      {
        repoURL: 'https://github.com/runwhen-contrib/rw-cli-codecollection',
        branch: 'main',
        workerReplicas: 4
      }
    ],
    
    // Security Context
    containerSecurityContextEnabled: true,
    allowPrivilegeEscalation: false,
    readOnlyRootFilesystem: false,
    
    // Resources
    resources: {
      requests: {
        cpu: '100m',
        memory: '128Mi',
      },
      limits: {
        cpu: '1',
        memory: '1024Mi',
      },
    },
    
    // Scheduling
    nodeSelector: {},
    tolerations: [],
    affinity: {},
    
    // Ingress Configuration
    ingressEnabled: false,
    ingressClassName: '',
    ingressHost: 'chart-example.local',
    ingressTLSEnabled: false,
    ingressTLSSecretName: 'chart-example-tls',
  });

  // Load helm chart versions on component mount
  useEffect(() => {
    const loadHelmChartVersions = async () => {
      setLoadingVersions(true);
      setVersionError(null);
      
      try {
        // Load the runwhen-local chart and its versions
        const chartData = await apiService.getHelmChart('runwhen-local');
        setHelmChart(chartData);
        setHelmChartVersions(chartData.versions || []);
        
        // Set the latest version as default
        const latestVersion = chartData.versions?.find(v => v.is_latest) || chartData.versions?.[0];
        if (latestVersion) {
          setSelectedChartVersion(latestVersion);
          setHelmValues(prev => ({
            ...prev,
            selectedChartVersion: latestVersion.version
          }));
          
          // Load templates for the latest version
          try {
            const templates = await apiService.getHelmChartTemplates('runwhen-local', latestVersion.version);
            setChartTemplates(templates);
          } catch (error) {
            console.warn('Could not load chart templates:', error);
          }
        }
      } catch (error) {
        console.error('Error loading helm chart versions:', error);
        setVersionError('Failed to load helm chart versions. Using default configuration.');
        // Continue with default values
      } finally {
        setLoadingVersions(false);
      }
    };

    loadHelmChartVersions();
  }, []);

  // Handle version selection change
  const handleVersionChange = async (versionString: string) => {
    const version = helmChartVersions.find(v => v.version === versionString);
    if (!version) return;

    setSelectedChartVersion(version);
    setHelmValues(prev => ({
      ...prev,
      selectedChartVersion: versionString
    }));

    // Load version-specific data
    try {
      const versionData = await apiService.getHelmChartVersion('runwhen-local', versionString);
      
      // Update helm values with defaults from this version
      if (versionData.default_values) {
        setHelmValues(prev => ({
          ...prev,
          ...mergeDefaultValues(prev, versionData.default_values)
        }));
      }

      // Load templates for this version
      const templates = await apiService.getHelmChartTemplates('runwhen-local', versionString);
      setChartTemplates(templates);
    } catch (error) {
      console.error('Error loading version data:', error);
    }
  };

  // Helper function to merge default values without overriding user changes
  const mergeDefaultValues = (currentValues: HelmValues, defaultValues: any): Partial<HelmValues> => {
    const updates: Partial<HelmValues> = {};
    
    // Only update values that are still at their initial state
    if (!currentValues.runwhenLocalImage && defaultValues.runwhenLocal?.image?.repository) {
      updates.runwhenLocalImage = defaultValues.runwhenLocal.image.repository;
    }
    if (currentValues.runwhenLocalTag === 'latest' && defaultValues.runwhenLocal?.image?.tag) {
      updates.runwhenLocalTag = defaultValues.runwhenLocal.image.tag;
    }
    
    return updates;
  };

  const handleCopyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // Could add a toast notification here
  };

  const handleDownload = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const updateHelmValues = (field: string, value: any) => {
    setHelmValues(prev => {
      const keys = field.split('.');
      const newValues = { ...prev };
      let current: any = newValues;
      
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      return newValues;
    });
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

  const generateHelmValues = (): string => {
    const values: any = {};

    // Global Settings
    values.workspaceName = helmValues.workspaceName || 'workspace-name';
    values.platformType = helmValues.platformType;
    values.platformArch = helmValues.platformArch;

    // Image Pull Secrets
    if (helmValues.imagePullSecrets) {
      values.imagePullSecrets = [{ name: 'registry-secret' }];
    } else {
      values.imagePullSecrets = [];
    }

    // Registry Override
    if (helmValues.registryOverride) {
      values.registryOverride = helmValues.registryOverride;
    }

    // Proxy Configuration
    if (helmValues.proxyEnabled) {
      values.proxy = {
        enabled: true,
        httpProxy: helmValues.httpProxy || `http://${helmValues.proxyHost}:${helmValues.proxyPort}`,
        httpsProxy: helmValues.httpsProxy || `http://${helmValues.proxyHost}:${helmValues.proxyPort}`,
        noProxy: helmValues.noProxy,
      };
    } else {
      values.proxy = { enabled: false };
    }

    // Proxy CA Configuration
    if (helmValues.proxyCAEnabled && helmValues.proxyCASecretName) {
      values.proxyCA = {
        secretName: helmValues.proxyCASecretName,
        key: helmValues.proxyCAKey,
      };
    }

    // Container Security Context
    if (helmValues.containerSecurityContextEnabled) {
      values.containerSecurityContext = {
        allowPrivilegeEscalation: helmValues.allowPrivilegeEscalation,
        capabilities: { drop: ['all'] },
        readOnlyRootFilesystem: helmValues.readOnlyRootFilesystem,
        seccompProfile: { type: 'RuntimeDefault' },
      };
    }

    // Node Selector
    if (Object.keys(helmValues.nodeSelector).length > 0) {
      values.nodeSelector = helmValues.nodeSelector;
    }

    // Tolerations
    if (helmValues.tolerations.length > 0) {
      values.tolerations = helmValues.tolerations;
    }

    // Affinity
    if (Object.keys(helmValues.affinity).length > 0) {
      values.affinity = helmValues.affinity;
    }

    // RunWhen Local Configuration
    if (helmValues.runwhenLocalEnabled) {
      values.runwhenLocal = {
        enabled: true,
        image: {
          registry: helmValues.runwhenLocalImage ? helmValues.runwhenLocalImage.split('/')[0] : '',
          repository: helmValues.runwhenLocalImage ? helmValues.runwhenLocalImage.split('/').slice(1).join('/') : '',
          tag: helmValues.runwhenLocalTag,
          pullPolicy: 'Always',
        },
        clusterName: helmValues.clusterName,
        discoveryKubeconfig: {
          inClusterAuth: {
            enabled: helmValues.inClusterAuth,
            createKubeconfigSecret: helmValues.inClusterAuth,
          },
        },
        autoRun: {
          discoveryInterval: helmValues.discoveryInterval,
          uploadEnabled: helmValues.uploadEnabled,
          uploadMergeMode: helmValues.uploadMergeMode,
        },
        terminal: {
          disabled: helmValues.terminalDisabled,
        },
        debugLogs: helmValues.debugLogs,
        serviceAccount: {
          create: helmValues.serviceAccountCreate,
          name: helmValues.serviceAccountName,
        },
        serviceAccountRoles: {
          clusterRoleView: {
            enabled: helmValues.clusterRoleViewEnabled,
          },
          advancedClusterRole: {
            enabled: helmValues.advancedClusterRoleEnabled,
          },
        },
        resources: {
          default: helmValues.resources,
        },
        workspaceInfo: {
          configMap: {
            create: true,
            name: 'workspace-builder',
            data: {
              defaultLocation: helmValues.defaultLocation,
              workspaceOwnerEmail: helmValues.workspaceOwnerEmail,
              defaultLOD: helmValues.defaultLOD,
              cloudConfig: {
                kubernetes: {
                  inClusterAuth: helmValues.inClusterAuth,
                },
              },
              codeCollections: [],
              taskTagExclusions: ['access:read-write'],
              custom: {
                kubeconfig_secret_name: 'k8s:file@secret/kubeconfig:kubeconfig',
                kubernetes_distribution_binary: 'kubectl',
                cloud_provider: 'none',
                gcp_project_id: 'none',
                gcp_ops_suite_sa: 'none',
                aws_access_key_id: 'AWS_ACCESS_KEY_ID',
                aws_secret_access_key: 'AWS_SECRET_ACCESS_KEY',
              },
            },
          },
        },
      };

      // Upload Info Configuration
      if (helmValues.uploadInfoEnabled) {
        values.runwhenLocal.uploadInfo = {
          secretProvided: {
            enabled: true,
            secretName: helmValues.uploadInfoSecretName,
            secretKey: helmValues.uploadInfoSecretKey,
            secretPath: helmValues.uploadInfoSecretKey,
          },
        };
      }

      // Ingress Configuration
      if (helmValues.ingressEnabled) {
        values.runwhenLocal.ingress = {
          enabled: true,
          className: helmValues.ingressClassName,
          hosts: [
            {
              host: helmValues.ingressHost,
              paths: [{ path: '/', pathType: 'Prefix' }],
            },
          ],
        };

        if (helmValues.ingressTLSEnabled) {
          values.runwhenLocal.ingress.tls = [
            {
              secretName: helmValues.ingressTLSSecretName,
              hosts: [helmValues.ingressHost],
            },
          ];
        }
      }
    }

    // Runner Configuration
    if (helmValues.runnerEnabled) {
      values.runner = {
        enabled: true,
        log: {
          level: helmValues.runnerLogLevel,
          format: 'console',
        },
        debugLogs: helmValues.runnerDebugLogs,
        controlAddr: helmValues.runnerControlAddr,
        metrics: {
          url: helmValues.runnerMetricsUrl,
        },
        codeCollections: helmValues.codeCollections,
        configMap: {
          create: true,
          name: 'runner-config',
          apiVersion: 'config.runwhen.com/v1',
          kind: 'RunnerConfig',
          raw: {},
        },
        resources: {
          default: {
            requests: { cpu: '50m', memory: '64Mi' },
            limits: { cpu: '600m', memory: '256Mi' },
          },
        },
        runEnvironment: {
          deployment: {
            resources: {
              default: {
                requests: { cpu: '100m', memory: '512Mi' },
                limits: { cpu: '1', memory: '1024Mi' },
              },
            },
          },
          pod: {
            runAsJob: false,
            resources: {
              default: {
                requests: { cpu: '50m', memory: '128Mi' },
                limits: { cpu: '1', memory: '512Mi' },
              },
            },
          },
          secretsProvided: {},
          blockedSecrets: [],
        },
      };

      if (helmValues.runnerImage) {
        values.runner.image = {
          registry: helmValues.runnerImage.split('/')[0],
          repository: helmValues.runnerImage.split('/').slice(1).join('/'),
          tag: helmValues.runnerTag,
        };
      }
    }

    // Convert to proper YAML format
    const convertToYaml = (obj: any, indent: number = 0): string => {
      const spaces = '  '.repeat(indent);
      let yaml = '';
      
      for (const [key, value] of Object.entries(obj)) {
        if (value === null || value === undefined) {
          continue;
        }
        
        if (typeof value === 'object' && !Array.isArray(value)) {
          yaml += `${spaces}${key}:\n`;
          yaml += convertToYaml(value, indent + 1);
        } else if (Array.isArray(value)) {
          if (value.length === 0) {
            yaml += `${spaces}${key}: []\n`;
          } else {
            yaml += `${spaces}${key}:\n`;
            value.forEach(item => {
              if (typeof item === 'object') {
                yaml += `${spaces}  -\n`;
                yaml += convertToYaml(item, indent + 2);
              } else {
                let itemValue;
                if (typeof item === 'string') {
                  itemValue = `"${item}"`;
                } else if (typeof item === 'boolean') {
                  itemValue = item.toString();
                } else {
                  itemValue = item;
                }
                yaml += `${spaces}  - ${itemValue}\n`;
              }
            });
          }
        } else {
          let yamlValue;
          if (typeof value === 'string') {
            yamlValue = `"${value}"`;
          } else if (typeof value === 'boolean') {
            yamlValue = value.toString();
          } else {
            yamlValue = value;
          }
          yaml += `${spaces}${key}: ${yamlValue}\n`;
        }
      }
      
      return yaml;
    };

    const yamlString = convertToYaml(values);

    return `# RunWhen Local Helm Chart Values
# Generated by CodeCollection Registry Configuration Builder
# Chart Version: ${helmValues.selectedChartVersion || 'latest'}
# Generated at: ${new Date().toISOString()}
# This file is client-side only and not stored

${yamlString}`;
  };

  // Show wizard selection if no wizard is selected yet
  if (!selectedWizard) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <DynamicFormIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Configuration Builder
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 6, maxWidth: 800, mx: 'auto' }}>
            Choose your configuration approach: Create a complete Helm deployment configuration 
            or build a simple workspace configuration file.
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 4, maxWidth: 1000, mx: 'auto' }}>
            {/* Helm Configuration Wizard */}
            <Card sx={{ flex: 1, cursor: 'pointer', '&:hover': { boxShadow: 6 } }} onClick={() => setSelectedWizard('helm')}>
              <CardContent sx={{ p: 4, textAlign: 'center' }}>
                <BuildIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
                <Typography variant="h5" gutterBottom>
                  Helm Configuration Wizard
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                  Complete Helm deployment configuration including networking, security, resources, and advanced settings.
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 }}>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Full values.yaml generation
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Version-aware configuration
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Network & security settings
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Resource limits & scheduling
                  </Typography>
                </Box>
                <Button variant="contained" fullWidth>
                  Start Helm Wizard
                </Button>
              </CardContent>
            </Card>

            {/* Workspace Builder */}
            <Card sx={{ flex: 1, cursor: 'pointer', '&:hover': { boxShadow: 6 } }} onClick={() => setSelectedWizard('workspace')}>
              <CardContent sx={{ p: 4, textAlign: 'center' }}>
                <WorkspaceIcon sx={{ fontSize: 48, color: 'secondary.main', mb: 2 }} />
                <Typography variant="h5" gutterBottom>
                  Workspace Builder
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                  Simple workspace configuration focusing on basic settings and code collections.
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 }}>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ workspaceInfo.yaml generation
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Quick & simple setup
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Workspace & location settings
                  </Typography>
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    ✅ Code collection management
                  </Typography>
                </Box>
                <Button variant="outlined" fullWidth>
                  Start Workspace Builder
                </Button>
              </CardContent>
            </Card>
          </Box>

          {items.length === 0 && (
            <Box sx={{ mt: 6 }}>
              <Alert severity="info" sx={{ maxWidth: 600, mx: 'auto' }}>
                <Typography variant="body2">
                  <strong>No CodeBundles selected:</strong> You can still create configurations, 
                  but consider browsing and adding CodeBundles to your cart for a more complete setup.
                </Typography>
              </Alert>
              <Button
                component={Link}
                to="/codebundles"
                variant="text"
                sx={{ mt: 2 }}
                startIcon={<CodeIcon />}
              >
                Browse CodeBundles
              </Button>
            </Box>
          )}
        </Box>
      </Container>
    );
  }

  // Show WorkspaceBuilder if workspace wizard is selected
  if (selectedWizard === 'workspace') {
    return <WorkspaceBuilder />;
  }

  // Continue with Helm wizard if helm is selected
  if (items.length === 0 && !wizardStarted && selectedWizard === 'helm') {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <DynamicFormIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h4" gutterBottom color="text.secondary">
            Helm Configuration Wizard
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
            Add some CodeBundles to your cart to get started with Helm configuration generation.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="outlined"
              onClick={() => setSelectedWizard(null)}
              startIcon={<ArrowBackIcon />}
            >
              Back to Wizard Selection
            </Button>
            <Button
              component={Link}
              to="/codebundles"
              variant="contained"
              size="large"
              startIcon={<CodeIcon />}
            >
              Browse CodeBundles
            </Button>
            <Button
              variant="contained"
              size="large"
              startIcon={<PlayArrowIcon />}
              onClick={() => setWizardStarted(true)}
            >
              Start Helm Wizard
            </Button>
          </Box>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          <strong>Privacy Notice:</strong> This configuration builder runs entirely in your browser. 
          No data is stored on our servers. All generated configurations remain on your device.
        </Typography>
      </Alert>

      {/* Helm Chart Version Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Helm Chart Configuration
          </Typography>
          
          {versionError && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {versionError}
            </Alert>
          )}
          
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 200 }}>
              <InputLabel>Chart Version</InputLabel>
              <Select
                value={helmValues.selectedChartVersion}
                label="Chart Version"
                onChange={(e) => handleVersionChange(e.target.value)}
                disabled={loadingVersions || helmChartVersions.length === 0}
              >
                {helmChartVersions.map((version) => (
                  <MenuItem key={version.id} value={version.version}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                      <Typography>{version.version}</Typography>
                      {version.is_latest && (
                        <Chip label="Latest" size="small" color="primary" />
                      )}
                      {version.is_prerelease && (
                        <Chip label="Pre-release" size="small" color="warning" />
                      )}
                      {version.is_deprecated && (
                        <Chip label="Deprecated" size="small" color="error" />
                      )}
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            {loadingVersions && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={20} />
                <Typography variant="body2" color="text.secondary">
                  Loading versions...
                </Typography>
              </Box>
            )}
            
            {selectedChartVersion && (
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {selectedChartVersion.app_version && (
                  <Chip 
                    label={`App: ${selectedChartVersion.app_version}`} 
                    size="small" 
                    variant="outlined" 
                  />
                )}
                {selectedChartVersion.created_date && (
                  <Chip 
                    label={`Released: ${new Date(selectedChartVersion.created_date).toLocaleDateString()}`} 
                    size="small" 
                    variant="outlined" 
                  />
                )}
              </Box>
            )}
          </Box>
          
          {/* Configuration Templates */}
          {chartTemplates.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="subtitle2" gutterBottom>
                Quick Start Templates
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {chartTemplates.map((template) => (
                  <Button
                    key={template.id}
                    variant={template.is_default ? "contained" : "outlined"}
                    size="small"
                    onClick={() => {
                      // Apply template values
                      setHelmValues(prev => ({
                        ...prev,
                        ...template.template_values
                      }));
                    }}
                  >
                    {template.name}
                  </Button>
                ))}
              </Box>
            </Box>
          )}
          
          {selectedChartVersion?.description && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              {selectedChartVersion.description}
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Wizard Step Navigation */}
      {(wizardStarted || items.length > 0) && selectedWizard === 'helm' && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <DynamicFormIcon color="primary" />
                <Typography variant="h6">
                  Helm Configuration Wizard
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Step {wizardStep + 1} of 9
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {wizardStep === 0 && (
                  <Button
                    variant="text"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => setSelectedWizard(null)}
                  >
                    Back to Wizard Selection
                  </Button>
                )}
                {wizardStep > 0 && (
                  <Button
                    variant="outlined"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => setWizardStep(Math.max(0, wizardStep - 1))}
                  >
                    Previous
                  </Button>
                )}
                {wizardStep < 8 && (
                  <Button
                    variant="contained"
                    endIcon={wizardStep === 7 ? <SettingsIcon /> : <ArrowForwardIcon />}
                    onClick={() => setWizardStep(Math.min(8, wizardStep + 1))}
                  >
                    {wizardStep === 7 ? 'Generate Configuration' : 'Next'}
                  </Button>
                )}
                {wizardStep === 8 && (
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<DownloadIcon />}
                    onClick={() => handleDownload(generateHelmValues(), 'values.yaml')}
                  >
                    Download & Finish
                  </Button>
                )}
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((step) => (
                  <Box
                    key={step}
                    sx={{
                      flex: 1,
                      height: 4,
                      backgroundColor: step <= wizardStep ? 'primary.main' : 'grey.300',
                      borderRadius: 2,
                    }}
                  />
                ))}
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {items.length > 0 && selectedWizard === 'helm' && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mb: 3 }}>
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
      )}

      {/* Wizard Step Content */}
      {(wizardStarted || items.length > 0) && selectedWizard === 'helm' && (
        <>
          {wizardStep === 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 1: Workspace Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure your RunWhen workspace settings
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                  <Box sx={{ width: { xs: '100%', md: '50%' } }}>
                    <TextField
                      fullWidth
                      label="Workspace Name"
                      value={helmValues.workspaceName}
                      onChange={(e) => updateHelmValues('workspaceName', e.target.value)}
                      placeholder="my-workspace"
                      helperText="Name of your RunWhen workspace"
                    />
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 1 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 2: Network Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure proxy settings if needed
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                  <Box>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={helmValues.proxyEnabled}
                          onChange={(e) => updateHelmValues('proxyEnabled', e.target.checked)}
                        />
                      }
                      label="Enable Proxy"
                    />
                  </Box>
                  {helmValues.proxyEnabled && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Proxy Host"
                            value={helmValues.proxyHost}
                            onChange={(e) => updateHelmValues('proxyHost', e.target.value)}
                            placeholder="proxy.company.com"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Proxy Port"
                            value={helmValues.proxyPort}
                            onChange={(e) => updateHelmValues('proxyPort', e.target.value)}
                            placeholder="8080"
                          />
                        </Box>
                      </Box>
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="HTTP Proxy URL (Optional)"
                            value={helmValues.httpProxy}
                            onChange={(e) => updateHelmValues('httpProxy', e.target.value)}
                            placeholder="http://proxy.company.com:8080"
                            helperText="Full HTTP proxy URL (overrides host:port)"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="HTTPS Proxy URL (Optional)"
                            value={helmValues.httpsProxy}
                            onChange={(e) => updateHelmValues('httpsProxy', e.target.value)}
                            placeholder="http://proxy.company.com:8080"
                            helperText="Full HTTPS proxy URL (overrides host:port)"
                          />
                        </Box>
                      </Box>
                      <Box>
                        <TextField
                          fullWidth
                          label="No Proxy"
                          value={helmValues.noProxy}
                          onChange={(e) => updateHelmValues('noProxy', e.target.value)}
                          placeholder="127.0.0.1,localhost,$($KUBERNETES_SERVICE_HOST)"
                          helperText="Comma-separated list of hosts to bypass proxy"
                        />
                      </Box>
                      <Box>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={helmValues.proxyCAEnabled}
                              onChange={(e) => updateHelmValues('proxyCAEnabled', e.target.checked)}
                            />
                          }
                          label="Configure Proxy CA Certificate"
                        />
                      </Box>
                      {helmValues.proxyCAEnabled && (
                        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                          <Box sx={{ flex: 1 }}>
                            <TextField
                              fullWidth
                              label="Proxy CA Secret Name"
                              value={helmValues.proxyCASecretName}
                              onChange={(e) => updateHelmValues('proxyCASecretName', e.target.value)}
                              placeholder="proxy-ca-secret"
                              helperText="Name of the secret containing the proxy CA certificate"
                            />
                          </Box>
                          <Box sx={{ flex: 1 }}>
                            <TextField
                              fullWidth
                              label="CA Certificate Key"
                              value={helmValues.proxyCAKey}
                              onChange={(e) => updateHelmValues('proxyCAKey', e.target.value)}
                              placeholder="ca.crt"
                              helperText="Key within the secret containing the CA certificate"
                            />
                          </Box>
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 2 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 3: Registry Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure private registry settings if needed
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                  <Box>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={helmValues.registryEnabled}
                          onChange={(e) => updateHelmValues('registryEnabled', e.target.checked)}
                        />
                      }
                      label="Enable Private Registry"
                    />
                  </Box>
                  {helmValues.registryEnabled && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <Box>
                        <TextField
                          fullWidth
                          label="Registry URL"
                          value={helmValues.registryUrl}
                          onChange={(e) => updateHelmValues('registryUrl', e.target.value)}
                          placeholder="registry.company.com"
                          helperText="Private container registry URL"
                        />
                      </Box>
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Registry Username"
                            value={helmValues.registryUsername}
                            onChange={(e) => updateHelmValues('registryUsername', e.target.value)}
                            placeholder="username"
                            helperText="Username for registry authentication"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Registry Password"
                            type="password"
                            value={helmValues.registryPassword}
                            onChange={(e) => updateHelmValues('registryPassword', e.target.value)}
                            placeholder="password"
                            helperText="Password for registry authentication"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Registry Email"
                            type="email"
                            value={helmValues.registryEmail}
                            onChange={(e) => updateHelmValues('registryEmail', e.target.value)}
                            placeholder="user@company.com"
                            helperText="Email for registry authentication"
                          />
                        </Box>
                      </Box>
                      <Box>
                        <TextField
                          fullWidth
                          label="Registry Override (Optional)"
                          value={helmValues.registryOverride}
                          onChange={(e) => updateHelmValues('registryOverride', e.target.value)}
                          placeholder="registry.company.com"
                          helperText="Override registry for all images (useful for air-gapped environments)"
                          sx={{ width: { xs: '100%', md: '50%' } }}
                        />
                      </Box>
                      <Box>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={helmValues.imagePullSecrets}
                              onChange={(e) => updateHelmValues('imagePullSecrets', e.target.checked)}
                            />
                          }
                          label="Create Image Pull Secrets"
                        />
                      </Box>
                    </Box>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 3 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 4: Platform & Architecture
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure platform-specific settings for your deployment environment
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                    <Box sx={{ flex: 1 }}>
                      <TextField
                        fullWidth
                        select
                        label="Platform Type"
                        value={helmValues.platformType}
                        onChange={(e) => updateHelmValues('platformType', e.target.value)}
                        helperText="Select your Kubernetes platform type"
                        SelectProps={{ native: true }}
                      >
                        <option value="kubernetes">Standard Kubernetes</option>
                        <option value="EKS_Fargate">AWS EKS Fargate</option>
                      </TextField>
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <TextField
                        fullWidth
                        select
                        label="Platform Architecture"
                        value={helmValues.platformArch}
                        onChange={(e) => updateHelmValues('platformArch', e.target.value)}
                        helperText="Select your platform architecture"
                        SelectProps={{ native: true }}
                      >
                        <option value="amd64">AMD64 (x86_64)</option>
                        <option value="arm64">ARM64</option>
                      </TextField>
                    </Box>
                  </Box>
                  
                  <Box>
                    <TextField
                      fullWidth
                      label="Cluster Name"
                      value={helmValues.clusterName}
                      onChange={(e) => updateHelmValues('clusterName', e.target.value)}
                      placeholder="default"
                      helperText="Name identifier for your cluster"
                      sx={{ width: { xs: '100%', md: '50%' } }}
                    />
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 4 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 5: Security & Service Accounts
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure security contexts and service account permissions
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Service Account Configuration
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.serviceAccountCreate}
                            onChange={(e) => updateHelmValues('serviceAccountCreate', e.target.checked)}
                          />
                        }
                        label="Create Service Account"
                      />
                      {helmValues.serviceAccountCreate && (
                        <TextField
                          fullWidth
                          label="Service Account Name"
                          value={helmValues.serviceAccountName}
                          onChange={(e) => updateHelmValues('serviceAccountName', e.target.value)}
                          placeholder="runwhen-local"
                          sx={{ width: { xs: '100%', md: '50%' } }}
                        />
                      )}
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.clusterRoleViewEnabled}
                            onChange={(e) => updateHelmValues('clusterRoleViewEnabled', e.target.checked)}
                          />
                        }
                        label="Enable Cluster Role View (Recommended)"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.advancedClusterRoleEnabled}
                            onChange={(e) => updateHelmValues('advancedClusterRoleEnabled', e.target.checked)}
                          />
                        }
                        label="Enable Advanced Cluster Role (Additional Permissions)"
                      />
                    </Box>
                  </Box>
                  
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Container Security Context
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.containerSecurityContextEnabled}
                            onChange={(e) => updateHelmValues('containerSecurityContextEnabled', e.target.checked)}
                          />
                        }
                        label="Enable Security Context (Recommended)"
                      />
                      {helmValues.containerSecurityContextEnabled && (
                        <>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={!helmValues.allowPrivilegeEscalation}
                                onChange={(e) => updateHelmValues('allowPrivilegeEscalation', !e.target.checked)}
                              />
                            }
                            label="Prevent Privilege Escalation"
                          />
                          <FormControlLabel
                            control={
                              <Switch
                                checked={helmValues.readOnlyRootFilesystem}
                                onChange={(e) => updateHelmValues('readOnlyRootFilesystem', e.target.checked)}
                              />
                            }
                            label="Read-Only Root Filesystem"
                          />
                        </>
                      )}
                    </Box>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 5 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 6: RunWhen Platform Integration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure integration with RunWhen Platform for workspace upload and management
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <Box>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={helmValues.uploadEnabled}
                          onChange={(e) => updateHelmValues('uploadEnabled', e.target.checked)}
                        />
                      }
                      label="Enable Automatic Upload to RunWhen Platform"
                    />
                  </Box>
                  
                  {helmValues.uploadEnabled && (
                    <>
                      <Box>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={helmValues.uploadInfoEnabled}
                              onChange={(e) => updateHelmValues('uploadInfoEnabled', e.target.checked)}
                            />
                          }
                          label="Use Upload Info Secret"
                        />
                      </Box>
                      
                      {helmValues.uploadInfoEnabled && (
                        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                          <Box sx={{ flex: 1 }}>
                            <TextField
                              fullWidth
                              label="Upload Info Secret Name"
                              value={helmValues.uploadInfoSecretName}
                              onChange={(e) => updateHelmValues('uploadInfoSecretName', e.target.value)}
                              placeholder="uploadinfo"
                              helperText="Name of the Kubernetes secret containing upload configuration"
                            />
                          </Box>
                          <Box sx={{ flex: 1 }}>
                            <TextField
                              fullWidth
                              label="Upload Info Secret Key"
                              value={helmValues.uploadInfoSecretKey}
                              onChange={(e) => updateHelmValues('uploadInfoSecretKey', e.target.value)}
                              placeholder="uploadInfo.yaml"
                              helperText="Key within the secret containing the upload info"
                            />
                          </Box>
                        </Box>
                      )}
                      
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            select
                            label="Upload Merge Mode"
                            value={helmValues.uploadMergeMode}
                            onChange={(e) => updateHelmValues('uploadMergeMode', e.target.value)}
                            helperText="How to handle conflicts during upload"
                            SelectProps={{ native: true }}
                          >
                            <option value="keep-uploaded">Keep Uploaded (Overwrite Existing)</option>
                            <option value="keep-existing">Keep Existing (Skip Conflicts)</option>
                          </TextField>
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Discovery Interval (seconds)"
                            type="number"
                            value={helmValues.discoveryInterval}
                            onChange={(e) => updateHelmValues('discoveryInterval', parseInt(e.target.value))}
                            placeholder="14400"
                            helperText="How often to run discovery (4 hours = 14400 seconds)"
                          />
                        </Box>
                      </Box>
                      
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Default Location"
                            value={helmValues.defaultLocation}
                            onChange={(e) => updateHelmValues('defaultLocation', e.target.value)}
                            placeholder="none"
                            helperText="Default location identifier for RunWhen Platform"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Workspace Owner Email"
                            type="email"
                            value={helmValues.workspaceOwnerEmail}
                            onChange={(e) => updateHelmValues('workspaceOwnerEmail', e.target.value)}
                            placeholder="admin@company.com"
                            helperText="Email address of the workspace owner"
                          />
                        </Box>
                      </Box>
                      
                      <Box sx={{ width: { xs: '100%', md: '50%' } }}>
                        <TextField
                          fullWidth
                          select
                          label="Default Level of Detail"
                          value={helmValues.defaultLOD}
                          onChange={(e) => updateHelmValues('defaultLOD', e.target.value)}
                          helperText="Default detail level for discovery"
                          SelectProps={{ native: true }}
                        >
                          <option value="none">None</option>
                          <option value="basic">Basic</option>
                          <option value="detailed">Detailed</option>
                        </TextField>
                      </Box>
                    </>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 6 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 7: Runner Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure the RunWhen Runner for executing tasks and SLIs
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <Box>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={helmValues.runnerEnabled}
                          onChange={(e) => updateHelmValues('runnerEnabled', e.target.checked)}
                        />
                      }
                      label="Enable RunWhen Runner"
                    />
                  </Box>
                  
                  {helmValues.runnerEnabled && (
                    <>
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            select
                            label="Log Level"
                            value={helmValues.runnerLogLevel}
                            onChange={(e) => updateHelmValues('runnerLogLevel', e.target.value)}
                            SelectProps={{ native: true }}
                          >
                            <option value="debug">Debug</option>
                            <option value="info">Info</option>
                            <option value="warn">Warning</option>
                            <option value="error">Error</option>
                          </TextField>
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={helmValues.runnerDebugLogs}
                                onChange={(e) => updateHelmValues('runnerDebugLogs', e.target.checked)}
                              />
                            }
                            label="Enable Debug Logs"
                          />
                        </Box>
                      </Box>
                      
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Control Address"
                            value={helmValues.runnerControlAddr}
                            onChange={(e) => updateHelmValues('runnerControlAddr', e.target.value)}
                            placeholder="https://runner.beta.runwhen.com"
                            helperText="RunWhen Platform runner control endpoint"
                          />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <TextField
                            fullWidth
                            label="Metrics URL"
                            value={helmValues.runnerMetricsUrl}
                            onChange={(e) => updateHelmValues('runnerMetricsUrl', e.target.value)}
                            placeholder="https://runner-cortex-tenant.beta.runwhen.com/push"
                            helperText="Metrics ingestion endpoint"
                          />
                        </Box>
                      </Box>
                    </>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 7 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 8: Resource Configuration & Advanced Settings
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Configure resource limits, ingress, and advanced deployment settings
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Resource Configuration
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2" gutterBottom>
                          Resource Requests
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <TextField
                            fullWidth
                            label="CPU Request"
                            value={helmValues.resources.requests.cpu}
                            onChange={(e) => updateHelmValues('resources.requests.cpu', e.target.value)}
                            placeholder="100m"
                            size="small"
                          />
                          <TextField
                            fullWidth
                            label="Memory Request"
                            value={helmValues.resources.requests.memory}
                            onChange={(e) => updateHelmValues('resources.requests.memory', e.target.value)}
                            placeholder="128Mi"
                            size="small"
                          />
                        </Box>
                      </Box>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2" gutterBottom>
                          Resource Limits
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <TextField
                            fullWidth
                            label="CPU Limit"
                            value={helmValues.resources.limits.cpu}
                            onChange={(e) => updateHelmValues('resources.limits.cpu', e.target.value)}
                            placeholder="1"
                            size="small"
                          />
                          <TextField
                            fullWidth
                            label="Memory Limit"
                            value={helmValues.resources.limits.memory}
                            onChange={(e) => updateHelmValues('resources.limits.memory', e.target.value)}
                            placeholder="1024Mi"
                            size="small"
                          />
                        </Box>
                      </Box>
                    </Box>
                  </Box>
                  
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Ingress Configuration
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.ingressEnabled}
                            onChange={(e) => updateHelmValues('ingressEnabled', e.target.checked)}
                          />
                        }
                        label="Enable Ingress"
                      />
                      {helmValues.ingressEnabled && (
                        <>
                          <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                            <TextField
                              fullWidth
                              label="Ingress Class Name"
                              value={helmValues.ingressClassName}
                              onChange={(e) => updateHelmValues('ingressClassName', e.target.value)}
                              placeholder="nginx"
                              helperText="Ingress controller class name"
                            />
                            <TextField
                              fullWidth
                              label="Host"
                              value={helmValues.ingressHost}
                              onChange={(e) => updateHelmValues('ingressHost', e.target.value)}
                              placeholder="runwhen.example.com"
                              helperText="Hostname for accessing RunWhen Local"
                            />
                          </Box>
                          <Box>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={helmValues.ingressTLSEnabled}
                                  onChange={(e) => updateHelmValues('ingressTLSEnabled', e.target.checked)}
                                />
                              }
                              label="Enable TLS"
                            />
                            {helmValues.ingressTLSEnabled && (
                              <TextField
                                fullWidth
                                label="TLS Secret Name"
                                value={helmValues.ingressTLSSecretName}
                                onChange={(e) => updateHelmValues('ingressTLSSecretName', e.target.value)}
                                placeholder="runwhen-tls"
                                helperText="Name of the TLS certificate secret"
                                sx={{ mt: 1, width: { xs: '100%', md: '50%' } }}
                              />
                            )}
                          </Box>
                        </>
                      )}
                    </Box>
                  </Box>
                  
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Additional Settings
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={!helmValues.terminalDisabled}
                            onChange={(e) => updateHelmValues('terminalDisabled', !e.target.checked)}
                          />
                        }
                        label="Enable In-Browser Terminal (Security Risk - Not Recommended for Production)"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={helmValues.debugLogs}
                            onChange={(e) => updateHelmValues('debugLogs', e.target.checked)}
                          />
                        }
                        label="Enable Debug Logging"
                      />
                    </Box>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}

          {wizardStep === 8 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  Step 9: Generated Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Your Helm values.yaml file is ready! Copy or download it to deploy RunWhen Local.
                </Typography>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <SettingsIcon color="primary" />
                    <Typography variant="h6">
                      values.yaml for Helm Chart v{helmValues.selectedChartVersion || 'latest'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<ContentCopyIcon />}
                      onClick={() => handleCopyToClipboard(generateHelmValues())}
                    >
                      Copy values.yaml
                    </Button>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<DownloadIcon />}
                      onClick={() => handleDownload(generateHelmValues(), 'values.yaml')}
                    >
                      Download
                    </Button>
                  </Box>
                </Box>

                <Alert severity="success" sx={{ mb: 3 }}>
                  <Typography variant="body2">
                    <strong>Configuration Complete!</strong> Your values.yaml file has been generated based on your selections. 
                    Use this file with the RunWhen Local Helm chart to deploy your troubleshooting platform.
                  </Typography>
                </Alert>

                <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                  <Editor
                    height="400px"
                    defaultLanguage="yaml"
                    value={generateHelmValues()}
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

                <Box sx={{ mt: 3, p: 2, backgroundColor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Next Steps:
                  </Typography>
                  <Typography variant="body2" component="div">
                    1. Save the values.yaml file to your local machine<br/>
                    2. Add the RunWhen Helm repository: <code>helm repo add runwhen-contrib https://runwhen-contrib.github.io/helm-charts</code><br/>
                    3. Install RunWhen Local: <code>helm install runwhen-local runwhen-contrib/runwhen-local -f values.yaml</code><br/>
                    4. Monitor the deployment: <code>kubectl get pods -l app.kubernetes.io/name=runwhen-local</code>
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {items.length > 0 && selectedWizard === null && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Repository Configuration */}
          <Box>
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
                            {item.codebundle.configuration_type?.has_generation_rules && (
                              <Chip 
                                label={item.codebundle.configuration_type.platform?.toUpperCase() || 'AUTO'} 
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
          <Box>
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
                  Auto-Discovered CodeBundles
                </Typography>
                <Typography variant="body1">
                  {items.filter(item => item.codebundle.configuration_type?.has_generation_rules).length} of {items.length}
                </Typography>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Platforms
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {Array.from(new Set(
                    items
                      .filter(item => item.codebundle.configuration_type?.platform)
                      .map(item => item.codebundle.configuration_type!.platform!)
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

        {/* Helm Chart Configuration */}
        <Box sx={{ mt: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                RunWhen Local Helm Chart Configuration
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure your RunWhen Local deployment with custom values for workspace, proxy, registry, and resources.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {/* Workspace Configuration */}
                <Box>
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6">Workspace Configuration</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                        <Box sx={{ width: { xs: '100%', md: '50%' } }}>
                          <TextField
                            fullWidth
                            label="Workspace Name"
                            value={helmValues.workspaceName}
                            onChange={(e) => updateHelmValues('workspaceName', e.target.value)}
                            placeholder="my-workspace"
                            helperText="Name of your RunWhen workspace"
                          />
                        </Box>
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>

                {/* Proxy Configuration */}
                <Box>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6">Proxy Configuration</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                        <Box>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={helmValues.proxyEnabled}
                                onChange={(e) => updateHelmValues('proxyEnabled', e.target.checked)}
                              />
                            }
                            label="Enable Proxy"
                          />
                        </Box>
                        {helmValues.proxyEnabled && (
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Proxy Host"
                                  value={helmValues.proxyHost}
                                  onChange={(e) => updateHelmValues('proxyHost', e.target.value)}
                                  placeholder="proxy.company.com"
                                />
                              </Box>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Proxy Port"
                                  value={helmValues.proxyPort}
                                  onChange={(e) => updateHelmValues('proxyPort', e.target.value)}
                                  placeholder="8080"
                                />
                              </Box>
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Proxy Username (Optional)"
                                  value={helmValues.proxyUsername}
                                  onChange={(e) => updateHelmValues('proxyUsername', e.target.value)}
                                  placeholder="username"
                                />
                              </Box>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Proxy Password (Optional)"
                                  type="password"
                                  value={helmValues.proxyPassword}
                                  onChange={(e) => updateHelmValues('proxyPassword', e.target.value)}
                                  placeholder="password"
                                />
                              </Box>
                            </Box>
                          </Box>
                        )}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>

                {/* Registry Configuration */}
                <Box>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6">Registry Configuration</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
                        <Box>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={helmValues.registryEnabled}
                                onChange={(e) => updateHelmValues('registryEnabled', e.target.checked)}
                              />
                            }
                            label="Enable Private Registry"
                          />
                        </Box>
                        {helmValues.registryEnabled && (
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Box>
                              <TextField
                                fullWidth
                                label="Registry URL"
                                value={helmValues.registryUrl}
                                onChange={(e) => updateHelmValues('registryUrl', e.target.value)}
                                placeholder="registry.company.com"
                                helperText="Private container registry URL"
                              />
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Registry Username"
                                  value={helmValues.registryUsername}
                                  onChange={(e) => updateHelmValues('registryUsername', e.target.value)}
                                  placeholder="username"
                                />
                              </Box>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Registry Password"
                                  type="password"
                                  value={helmValues.registryPassword}
                                  onChange={(e) => updateHelmValues('registryPassword', e.target.value)}
                                  placeholder="password"
                                />
                              </Box>
                              <Box sx={{ flex: 1 }}>
                                <TextField
                                  fullWidth
                                  label="Registry Email"
                                  value={helmValues.registryEmail}
                                  onChange={(e) => updateHelmValues('registryEmail', e.target.value)}
                                  placeholder="user@company.com"
                                />
                              </Box>
                            </Box>
                            <Box>
                              <FormControlLabel
                                control={
                                  <Switch
                                    checked={helmValues.imagePullSecrets}
                                    onChange={(e) => updateHelmValues('imagePullSecrets', e.target.checked)}
                                  />
                                }
                                label="Create Image Pull Secrets"
                              />
                            </Box>
                          </Box>
                        )}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>

                {/* Resource Configuration */}
                <Box>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6">Resource Configuration</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3, width: '100%' }}>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Resource Requests
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Box sx={{ flex: 1 }}>
                              <TextField
                                fullWidth
                                label="CPU Request"
                                value={helmValues.resources.requests.cpu}
                                onChange={(e) => updateHelmValues('resources.requests.cpu', e.target.value)}
                                placeholder="100m"
                                size="small"
                              />
                            </Box>
                            <Box sx={{ flex: 1 }}>
                              <TextField
                                fullWidth
                                label="Memory Request"
                                value={helmValues.resources.requests.memory}
                                onChange={(e) => updateHelmValues('resources.requests.memory', e.target.value)}
                                placeholder="128Mi"
                                size="small"
                              />
                            </Box>
                          </Box>
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Resource Limits
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Box sx={{ flex: 1 }}>
                              <TextField
                                fullWidth
                                label="CPU Limit"
                                value={helmValues.resources.limits.cpu}
                                onChange={(e) => updateHelmValues('resources.limits.cpu', e.target.value)}
                                placeholder="500m"
                                size="small"
                              />
                            </Box>
                            <Box sx={{ flex: 1 }}>
                              <TextField
                                fullWidth
                                label="Memory Limit"
                                value={helmValues.resources.limits.memory}
                                onChange={(e) => updateHelmValues('resources.limits.memory', e.target.value)}
                                placeholder="512Mi"
                                size="small"
                              />
                            </Box>
                          </Box>
                        </Box>
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Helm Values YAML - Only show when wizard is started and helm is selected */}
        {(wizardStarted || items.length > 0) && selectedWizard === 'helm' && (
          <Box sx={{ mt: 4 }}>
            <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SettingsIcon />
                  <Typography variant="h5">
                    RunWhen Local values.yaml
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<ContentCopyIcon />}
                    onClick={() => handleCopyToClipboard(generateHelmValues())}
                  >
                    Copy values.yaml
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<DownloadIcon />}
                    onClick={() => handleDownload(generateHelmValues(), 'values.yaml')}
                  >
                    Download
                  </Button>
                </Box>
              </Box>
              
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                This values.yaml file can be used with the RunWhen Local Helm chart for deployment.
              </Typography>

              <Paper 
                variant="outlined" 
                sx={{ 
                  p: 2, 
                  backgroundColor: 'action.hover',
                  maxHeight: '300px',
                  overflow: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '0.875rem'
                }}
              >
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {generateHelmValues()}
                </pre>
              </Paper>
            </CardContent>
          </Card>
        </Box>
        )}

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
      </Box>
      )}
    </Container>
  );
};

export default ConfigBuilder;
