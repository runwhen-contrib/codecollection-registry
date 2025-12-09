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
} from '@mui/material';
import { Link } from 'react-router-dom';
import { apiService, CodeCollection, CodeBundle } from '../services/api';

const Home: React.FC = () => {
  const [collections, setCollections] = useState<CodeCollection[]>([]);
  const [codebundles, setCodebundles] = useState<CodeBundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        console.log('Fetching data from API...');
        const [collectionsData, codebundlesData] = await Promise.all([
          apiService.getCodeCollections(),
          apiService.getCodeBundles({ limit: 6 }).then(response => response.codebundles),
        ]);
        console.log('Collections data:', collectionsData);
        console.log('Codebundles data:', codebundlesData);
        setCollections(collectionsData);
        setCodebundles(codebundlesData);
      } catch (err) {
        console.error('Detailed error:', err);
        setError(`Failed to load data: ${err}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const categories = [
    { name: 'KUBERNETES', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/kubernetes-icon-color.svg' },
    { name: 'GKE', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/gcp/google_kubernetes_engine/google_kubernetes_engine.svg' },
    { name: 'AKS', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/azure/containers/10023-icon-service-Kubernetes-Services.svg' },
    { name: 'EKS', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/amazon-eks.svg' },
    { name: 'OPENSHIFT', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/OpenShift-LogoType.svg' },
    { name: 'GCP', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/google-cloud-platform.svg' },
    { name: 'AWS', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Amazon_Web_Services_Logo.svg' },
    { name: 'CLOUDWATCH', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/aws/cloudwatch.svg' },
    { name: 'HTTP', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/code_blocks.svg' },
    { name: 'GITHUB', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/github-mark.svg' },
  ];

  const communityResources = [
    {
      title: 'Share an awesome command',
      icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/share.svg',
      link: 'https://github.com/runwhen-contrib/runwhen-local/issues/new?assignees=stewartshea&labels=runwhen-local%2Cawesome-command-contribution&projects=&template=awesome-command-contribution.yaml&title=%5Bawesome-command-contribution%5D+',
    },
    {
      title: 'Join the (Paid) RunWhen Authors Program',
      icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/code_blocks.svg',
      link: 'https://docs.runwhen.com/public/v/runwhen-authors',
    },
    {
      title: 'Request help from the community',
      icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/help_center.svg',
      link: 'https://github.com/runwhen-contrib/runwhen-local/issues/new?assignees=stewartshea&labels=runwhen-local%2Cnew-command-request&projects=&template=commands-wanted.yaml&title=%5Bnew-command-request%5D+',
    },
    {
      title: 'Connect on Slack',
      icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/slack_black.svg',
      link: 'https://runwhen.slack.com/join/shared_invite/zt-1l7t3tdzl-IzB8gXDsWtHkT8C5nufm2A#/shared-invite/email',
    },
  ];

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
        <Typography variant="body2" sx={{ textAlign: 'center', mt: 2 }}>
          Loading data from API... (Check console for details)
        </Typography>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
        <Typography variant="body2" sx={{ mt: 2 }}>
          Collections: {collections.length}, Codebundles: {codebundles.length}
        </Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Debug Info */}
      <Box sx={{ mb: 2, p: 2, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
        <Typography variant="body2">
          Debug: Collections: {collections.length}, Codebundles: {codebundles.length}, Loading: {loading.toString()}, Error: {error || 'None'}
        </Typography>
      </Box>
      

      {/* Top Codebundle Categories */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h2" sx={{ mb: 2 }}>
          Top CodeBundle Categories
        </Typography>
        <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {categories.map((category) => (
            <Box key={category.name} sx={{ flex: '0 0 calc(50% - 8px)', '@media (min-width: 600px)': { flex: '0 0 calc(25% - 12px)' } }}>
              <Card
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 120,
                  textAlign: 'center',
                  '&:hover': {
                    boxShadow: 4,
                  },
                }}
              >
                <CardActionArea
                  component={Link}
                  to={`/categories/${category.name.toLowerCase()}`}
                  sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
                >
                  <Box
                    component="img"
                    src={category.icon}
                    alt={`${category.name} icon`}
                    sx={{
                      width: 80,
                      height: 80,
                      mb: 1,
                      borderRadius: 1,
                      padding: 1,
                    }}
                  />
                  <Typography variant="body1" fontWeight="bold">
                    {category.name}
                  </Typography>
                </CardActionArea>
              </Card>
            </Box>
          ))}
          <Box sx={{ flex: '0 0 calc(50% - 8px)', '@media (min-width: 600px)': { flex: '0 0 calc(25% - 12px)' } }}>
            <Card
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 120,
                textAlign: 'center',
                '&:hover': {
                  boxShadow: 4,
                },
              }}
            >
              <CardActionArea
                component={Link}
                to="/categories"
                sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
              >
                <Typography variant="body1" fontWeight="bold">
                  Browse All Categories
                </Typography>
              </CardActionArea>
            </Card>
          </Box>
        </Box>
      </Box>

      {/* Two Column Layout */}
      <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', lg: 'row' } }}>
        {/* Featured CodeCollections */}
        <Box sx={{ flex: 1 }}>
          <Typography variant="h2" sx={{ mb: 2 }}>
            Featured CodeCollections
          </Typography>
          <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {collections.map((collection) => (
              <Box key={collection.id} sx={{ flex: '0 0 calc(100% - 8px)', '@media (min-width: 600px)': { flex: '0 0 calc(50% - 12px)' } }}>
                <Card
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    minHeight: 80,
                    '&:hover': {
                      boxShadow: 4,
                    },
                  }}
                >
                  <CardActionArea
                    component={Link}
                    to={`/collections/${collection.slug}`}
                    sx={{ p: 2, display: 'flex', alignItems: 'center' }}
                  >
                    <Box
                      component="img"
                      src={collection.owner_icon || 'https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg'}
                      alt="Icon"
                      sx={{
                        width: 50,
                        height: 50,
                        mr: 2,
                        borderRadius: 1.5,
                        padding: 1,
                      }}
                    />
                    <Box>
                      <Typography variant="h6" fontWeight="bold">
                        {collection.name}
                      </Typography>
                    </Box>
                  </CardActionArea>
                </Card>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Community Resources */}
        <Box sx={{ flex: 1 }}>
          <Typography variant="h2" sx={{ mb: 2 }}>
            Community Resources
          </Typography>
          <Box sx={{ width: '100%', height: '2px', backgroundColor: '#e0e0e0', mb: 3 }} />
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {communityResources.map((resource, index) => (
              <Box key={index}>
                <Card
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    minHeight: 80,
                    '&:hover': {
                      boxShadow: 4,
                    },
                  }}
                >
                  <CardActionArea
                    href={resource.link}
                    target="_blank"
                    rel="noopener"
                    sx={{ p: 2, display: 'flex', alignItems: 'center' }}
                  >
                    <Box
                      component="img"
                      src={resource.icon}
                      alt="Icon"
                      sx={{
                        width: 50,
                        height: 50,
                        mr: 2,
                        borderRadius: 1.5,
                        padding: 1,
                      }}
                    />
                    <Box>
                      <Typography variant="h6" fontWeight="bold">
                        {resource.title}
                      </Typography>
                    </Box>
                  </CardActionArea>
                </Card>
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default Home;