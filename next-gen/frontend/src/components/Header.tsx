import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
} from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import MenuIcon from '@mui/icons-material/Menu';

const Header: React.FC = () => {
  const location = useLocation();

  return (
    <AppBar position="static" sx={{ backgroundColor: '#2f80ed' }}>
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <Typography
            variant="h6"
            component={Link}
            to="/"
            sx={{
              color: 'white',
              textDecoration: 'none',
              fontWeight: 'bold',
              marginRight: 4,
            }}
          >
            CodeCollection Registry
          </Typography>
          
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 2 }}>
            <Button
              component={Link}
              to="/"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/' ? 'bold' : 'normal',
              }}
            >
              Home
            </Button>
            <Button
              component={Link}
              to="/collections"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/collections' ? 'bold' : 'normal',
              }}
            >
              Collections
            </Button>
            <Button
              component={Link}
              to="/codebundles"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/codebundles' ? 'bold' : 'normal',
              }}
            >
              CodeBundles
            </Button>
            <Button
              component={Link}
              to="/categories"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/categories' ? 'bold' : 'normal',
              }}
            >
              Categories
            </Button>
            <Button
              component={Link}
              to="/admin"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/admin' ? 'bold' : 'normal',
                backgroundColor: 'rgba(255,255,255,0.1)',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.2)',
                }
              }}
            >
              Admin
            </Button>
            <Button
              component={Link}
              to="/tasks"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/tasks' ? 'bold' : 'normal',
                backgroundColor: 'rgba(255,255,255,0.1)',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.2)',
                }
              }}
            >
              Tasks
            </Button>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton color="inherit">
            <SearchIcon />
          </IconButton>
          <IconButton
            color="inherit"
            sx={{ display: { xs: 'block', md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;