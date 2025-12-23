import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Avatar,
  Divider,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Menu as MenuIcon,
  MoreVert as MoreVertIcon,
  Login as LoginIcon,
  Logout as LogoutIcon,
  Person as PersonIcon,
  Build as BuildIcon,
  List as ListIcon,
  KeyboardArrowDown as ArrowDownIcon,
  Folder as FolderIcon,
  Extension as ExtensionIcon,
  Category as CategoryIcon,
} from '@mui/icons-material';
import { useCart } from '../contexts/CartContext';
import { useAuth } from '../contexts/AuthContext';

const Header: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { itemCount } = useCart();
  const { isAuthenticated, user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [moreMenuAnchor, setMoreMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [browseMenuAnchor, setBrowseMenuAnchor] = React.useState<null | HTMLElement>(null);

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setAnchorEl(null);
  };

  const handleMoreMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMoreMenuAnchor(event.currentTarget);
  };

  const handleMoreMenuClose = () => {
    setMoreMenuAnchor(null);
  };

  const handleBrowseMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setBrowseMenuAnchor(event.currentTarget);
  };

  const handleBrowseMenuClose = () => {
    setBrowseMenuAnchor(null);
  };

  const handleLogout = () => {
    logout();
    handleUserMenuClose();
    navigate('/');
  };

  const handleMenuNavigate = (path: string) => {
    navigate(path);
    handleMoreMenuClose();
    handleBrowseMenuClose();
  };

  const isBrowseActive = ['/collections', '/codebundles', '/categories'].some(
    path => location.pathname.startsWith(path)
  );

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
          
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 1 }}>
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
              to="/all-tasks"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/all-tasks' ? 'bold' : 'normal',
              }}
            >
              All Tasks
            </Button>
            
            {/* Browse Dropdown */}
            <Button
              color="inherit"
              onClick={handleBrowseMenuOpen}
              endIcon={<ArrowDownIcon />}
              sx={{
                color: 'white',
                fontWeight: isBrowseActive ? 'bold' : 'normal',
              }}
            >
              Browse
            </Button>
            <Menu
              anchorEl={browseMenuAnchor}
              open={Boolean(browseMenuAnchor)}
              onClose={handleBrowseMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
              }}
            >
              <MenuItem onClick={() => handleMenuNavigate('/collections')}>
                <ListItemIcon>
                  <FolderIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>CodeCollections</ListItemText>
              </MenuItem>
              <MenuItem onClick={() => handleMenuNavigate('/codebundles')}>
                <ListItemIcon>
                  <ExtensionIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>CodeBundles</ListItemText>
              </MenuItem>
              <MenuItem onClick={() => handleMenuNavigate('/categories')}>
                <ListItemIcon>
                  <CategoryIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Categories</ListItemText>
              </MenuItem>
            </Menu>

            <Button
              component={Link}
              to="/chat"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: location.pathname === '/chat' ? 'bold' : 'normal',
              }}
            >
              RunWhen Assistant
            </Button>
            
            {isAuthenticated && (
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
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {/* More Menu - Hidden features */}
          <IconButton
            color="inherit"
            onClick={handleMoreMenuOpen}
            sx={{
              opacity: 0.7,
              '&:hover': {
                opacity: 1,
                backgroundColor: 'rgba(255,255,255,0.1)',
              }
            }}
          >
            <MoreVertIcon />
          </IconButton>
          <Menu
            anchorEl={moreMenuAnchor}
            open={Boolean(moreMenuAnchor)}
            onClose={handleMoreMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
          >
            <MenuItem onClick={() => handleMenuNavigate('/config-builder')}>
              <ListItemIcon>
                <BuildIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Config Builder</ListItemText>
              {itemCount > 0 && (
                <Typography variant="caption" sx={{ ml: 1, color: 'primary.main' }}>
                  ({itemCount})
                </Typography>
              )}
            </MenuItem>
            <Divider />
            {!isAuthenticated && (
              <MenuItem onClick={() => handleMenuNavigate('/login')}>
                <ListItemIcon>
                  <LoginIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Login</ListItemText>
              </MenuItem>
            )}
            {isAuthenticated && (
              <MenuItem onClick={() => handleMenuNavigate('/tasks')}>
                <ListItemIcon>
                  <ListIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Task Manager</ListItemText>
              </MenuItem>
            )}
          </Menu>
          
          {/* User Menu (when authenticated) */}
          {isAuthenticated && (
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
