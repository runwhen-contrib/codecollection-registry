import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useAuth, hasRole } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
  allowedDomains?: string[];
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredRole,
  allowedDomains = ['runwhen.com'] // Default allowed domain
}) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          minHeight: '50vh',
          gap: 2
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary">
          Checking authentication...
        </Typography>
      </Box>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role requirement
  if (requiredRole && !hasRole(user, requiredRole)) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom>
          Access Denied
        </Typography>
        <Typography variant="body1" color="text.secondary">
          You don't have the required permissions to access this page.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Required role: {requiredRole}
        </Typography>
      </Box>
    );
  }

  // Check domain requirement (for future use)
  if (allowedDomains.length > 0 && user?.domain && !allowedDomains.includes(user.domain)) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom>
          Domain Not Allowed
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Your domain ({user.domain}) is not authorized to access this application.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Allowed domains: {allowedDomains.join(', ')}
        </Typography>
      </Box>
    );
  }

  // Render protected content
  return <>{children}</>;
};

export default ProtectedRoute;
