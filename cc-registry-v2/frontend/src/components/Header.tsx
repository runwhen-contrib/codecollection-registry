import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  Badge,
  Menu,
  MenuItem,
  Avatar,
  Divider,
} from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Search as SearchIcon,
  Menu as MenuIcon,
  DynamicForm as DynamicFormIcon,
  Login as LoginIcon,
  Logout as LogoutIcon,
  Person as PersonIcon,
} from '@mui/icons-material';
import { useCart } from '../contexts/CartContext';
import { useAuth } from '../contexts/AuthContext';

const Header: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { itemCount } = useCart();
  const { isAuthenticated, user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleUserMenuClose();
    navigate('/');
  };

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
              to="/all-tasks"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/all-tasks' ? 'bold' : 'normal',
              }}
            >
              All Tasks
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
              to="/config-builder"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/config-builder' ? 'bold' : 'normal',
              }}
            >
              Config Builder
            </Button>
            {isAuthenticated && (
              <>
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
              </>
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton 
            color="inherit"
            component={Link}
            to="/config-builder"
            sx={{
              '&:hover': {
                backgroundColor: 'rgba(255,255,255,0.1)',
              }
            }}
          >
            <Badge badgeContent={itemCount} color="error">
              <DynamicFormIcon />
            </Badge>
          </IconButton>
          <IconButton color="inherit">
            <SearchIcon />
          </IconButton>
          
          {/* Authentication Section */}
          {isAuthenticated ? (
            <>
              <IconButton
                color="inherit"
                onClick={handleUserMenuOpen}
                sx={{ ml: 1 }}
              >
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'rgba(255,255,255,0.2)' }}>
                  <PersonIcon />
                </Avatar>
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleUserMenuClose}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
              >
                <MenuItem disabled>
                  <Box>
                    <Typography variant="body2" fontWeight="bold">
                      {user?.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {user?.email}
                    </Typography>
                  </Box>
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>
                  <LogoutIcon sx={{ mr: 1 }} />
                  Logout
                </MenuItem>
              </Menu>
            </>
          ) : (
            <Button
              component={Link}
              to="/login"
              color="inherit"
              startIcon={<LoginIcon />}
              sx={{
                color: 'white',
                border: '1px solid rgba(255,255,255,0.3)',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.1)',
                }
              }}
            >
              Login
            </Button>
          )}
          
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