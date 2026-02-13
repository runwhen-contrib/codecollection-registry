import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Divider
} from '@mui/material';
import {
  Login as LoginIcon,
  Google as GoogleIcon
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const { login, isAuthenticated, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const success = await login(email, password);
      if (success) {
        const from = (location.state as any)?.from?.pathname || '/';
        navigate(from, { replace: true });
      } else {
        setError('Invalid email or password');
      }
    } catch (err) {
      setError('Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    setIsLoading(true);
    
    try {
      if (loginWithGoogle) {
        await loginWithGoogle();
      } else {
        setError('Google login not yet implemented');
      }
    } catch (err) {
      setError('Google login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8, mb: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <LoginIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
          
          <Typography variant="h4" component="h1" gutterBottom>
            Sign In
          </Typography>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, textAlign: 'center' }}>
            Access to admin and task management features requires authentication
          </Typography>

          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              sx={{ mb: 2 }}
            />
            
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              sx={{ mb: 3 }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading}
              sx={{ mb: 2, py: 1.5 }}
              startIcon={isLoading ? <CircularProgress size={20} /> : <LoginIcon />}
            >
              {isLoading ? 'Signing In...' : 'Sign In'}
            </Button>
          </Box>

          <Divider sx={{ width: '100%', my: 2 }}>
            <Typography variant="body2" color="text.secondary">
              OR
            </Typography>
          </Divider>

          <Button
            fullWidth
            variant="outlined"
            onClick={handleGoogleLogin}
            disabled={isLoading}
            sx={{ py: 1.5 }}
            startIcon={<GoogleIcon />}
          >
            Continue with Google
          </Button>
        </Box>
      </Paper>
    </Container>
  );
};

export default Login;
