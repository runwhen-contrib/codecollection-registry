import React from 'react';
import { Box, Typography, Link, Container, SvgIcon } from '@mui/material';
import GitHubIcon from '@mui/icons-material/GitHub';

// Custom Slack icon using official Slack logo SVG path
const SlackIcon: React.FC<{ fontSize?: 'small' | 'medium' | 'large' | 'inherit' }> = ({ fontSize = 'medium' }) => (
  <SvgIcon fontSize={fontSize} viewBox="0 0 24 24">
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.124 2.521a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.52 2.521h-2.522V8.834zm-1.271 0a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.521-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.312zm-2.521 10.124a2.528 2.528 0 0 1 2.521 2.522A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.52v-2.522h2.521zm0-1.271a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.521h6.312A2.528 2.528 0 0 1 24 15.165a2.528 2.528 0 0 1-2.52 2.521h-6.314z" />
  </SvgIcon>
);

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
            © 2025 RunWhen Inc. All rights reserved.
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};

export default Footer;
