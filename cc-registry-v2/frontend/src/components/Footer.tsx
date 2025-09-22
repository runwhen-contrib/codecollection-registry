import React from 'react';
import { Box, Typography, Link, Container } from '@mui/material';
import GitHubIcon from '@mui/icons-material/GitHub';
import SlackIcon from '@mui/icons-material/Message';

const Footer: React.FC = () => {
  return (
    <Box
      sx={{
        backgroundColor: '#2f80ed',
        color: 'white',
        padding: 3,
        marginTop: 'auto',
      }}
    >
      <Container maxWidth="lg">
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-around',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <GitHubIcon />
            <Link
              href="https://github.com/runwhen-contrib/codecollection-registry"
              target="_blank"
              rel="noopener"
              sx={{ color: 'white', textDecoration: 'none' }}
            >
              GitHub
            </Link>
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SlackIcon />
            <Link
              href="https://runwhen.slack.com"
              target="_blank"
              rel="noopener"
              sx={{ color: 'white', textDecoration: 'none' }}
            >
              Slack
            </Link>
          </Box>
          
          <Typography variant="body2" sx={{ color: 'white' }}>
            © 2024 RunWhen Inc. All rights reserved.
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};

export default Footer;