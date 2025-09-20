import React from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActionArea,
} from '@mui/material';
import { Link } from 'react-router-dom';

const Categories: React.FC = () => {
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
    { name: 'DOCKER', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/docker.svg' },
    { name: 'TERRAFORM', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/terraform.svg' },
    { name: 'ANSIBLE', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/ansible.svg' },
    { name: 'PROMETHEUS', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/prometheus.svg' },
    { name: 'GRAFANA', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/grafana.svg' },
    { name: 'ELASTICSEARCH', icon: 'https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/elasticsearch.svg' },
  ];

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h1" sx={{ mb: 4 }}>
        Categories
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {categories.map((category) => (
          <Box key={category.name} sx={{ flex: '0 0 calc(50% - 12px)', '@media (min-width: 600px)': { flex: '0 0 calc(33.333% - 16px)' }, '@media (min-width: 900px)': { flex: '0 0 calc(25% - 18px)' } }}>
            <Card
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 150,
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
                    mb: 2,
                    borderRadius: 1,
                    padding: 1,
                  }}
                />
                <Typography variant="h6" fontWeight="bold">
                  {category.name}
                </Typography>
              </CardActionArea>
            </Card>
            </Box>
          ))}
        </Box>
    </Container>
  );
};

export default Categories;