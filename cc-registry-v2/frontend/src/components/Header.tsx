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
  Divider,
} from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Menu as MenuIcon,
  KeyboardArrowDown as ArrowDownIcon,
  MoreVert as MoreVertIcon,
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
  const [linksMenuAnchor, setLinksMenuAnchor] = React.useState<null | HTMLElement>(null);

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

  const handleLinksMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setLinksMenuAnchor(event.currentTarget);
  };

  const handleLinksMenuClose = () => {
    setLinksMenuAnchor(null);
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

  const isBrowseActive = ['/collections', '/codebundles', '/all-tasks'].some(
    path => location.pathname.startsWith(path)
  );

  return (
    <AppBar position="static" sx={{ backgroundColor: '#5282f1' }}>
      <Toolbar>
        <Box
          component={Link}
          to="/"
          sx={{
            display: 'flex',
            alignItems: 'center',
            textDecoration: 'none',
            gap: 2,
          }}
        >
          <Box
            component="img"
            src="/assets/white_runwhen_logo_transparent_bg.png"
            alt="RunWhen Logo"
            sx={{
              height: 40,
              width: 'auto',
            }}
          />
          <Typography
            variant="h6"
            sx={{
              color: 'white',
              fontWeight: 'bold',
            }}
          >
            CodeCollection Registry
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, marginLeft: 'auto' }}>
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 1 }}>
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
                CodeCollections
              </MenuItem>
              <MenuItem onClick={() => handleMenuNavigate('/codebundles')}>
                CodeBundles
              </MenuItem>
              <MenuItem onClick={() => handleMenuNavigate('/all-tasks')}>
                All Tasks
              </MenuItem>
            </Menu>

            {/* Links Dropdown */}
            <Button
              color="inherit"
              onClick={handleLinksMenuOpen}
              endIcon={<ArrowDownIcon />}
              sx={{
                color: 'white',
              }}
            >
              Links
            </Button>
            <Menu
              anchorEl={linksMenuAnchor}
              open={Boolean(linksMenuAnchor)}
              onClose={handleLinksMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
              }}
            >
              <MenuItem
                component="a"
                href="https://www.runwhen.com"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleLinksMenuClose}
              >
                Website
              </MenuItem>
              <MenuItem
                component="a"
                href="https://docs.runwhen.com"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleLinksMenuClose}
              >
                Documentation
              </MenuItem>
              <MenuItem
                component="a"
                href="https://github.com/runwhen-contrib"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleLinksMenuClose}
              >
                GitHub
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
              Registry Chat
            </Button>

            <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.3)', height: 20, mx: 1, alignSelf: 'center' }} />
            
            <Button
              component="a"
              href="https://docs.runwhen.com/public/live-demos"
              target="_blank"
              rel="noopener noreferrer"
              color="inherit"
              sx={{
                color: 'white',
                fontWeight: 'normal',
              }}
            >
              Login
            </Button>
          </Box>
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
              Config Builder
              {itemCount > 0 && (
                <Typography variant="caption" sx={{ ml: 1, color: 'primary.main' }}>
                  ({itemCount})
                </Typography>
              )}
            </MenuItem>
            <Divider />
            {!isAuthenticated && (
              <MenuItem onClick={() => handleMenuNavigate('/login')}>
                Admin Login
              </MenuItem>
            )}
            {isAuthenticated && (
              <>
                <MenuItem onClick={() => handleMenuNavigate('/admin')}>
                  Admin Panel
                </MenuItem>
                <MenuItem onClick={() => handleMenuNavigate('/chat-debug')}>
                  Chat Debug
                </MenuItem>
                <MenuItem onClick={() => handleMenuNavigate('/tasks')}>
                  Task Manager
                </MenuItem>
              </>
            )}
          </Menu>
          
          {/* User Menu (when authenticated) */}
          {isAuthenticated && (
            <>
              <Button
                color="inherit"
                onClick={handleUserMenuOpen}
                endIcon={<ArrowDownIcon />}
                sx={{
                  ml: 1,
                  color: 'white',
                }}
              >
                {user?.name || 'Account'}
              </Button>
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
