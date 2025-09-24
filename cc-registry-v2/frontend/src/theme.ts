import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#2f80ed',
      light: '#5a9eff',
      dark: '#1e5bb8',
    },
    secondary: {
      main: '#faa629',
      light: '#ffb84d',
      dark: '#e69500',
    },
    background: {
      default: '#ffffff',
      paper: '#ffffff',
    },
    text: {
      primary: '#3f3f3f',
      secondary: '#858484',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '2.5rem',
      fontWeight: 700,
      color: '#858484',
    },
    h2: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '2rem',
      fontWeight: 600,
      color: '#858484',
    },
    h3: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.5rem',
      fontWeight: 600,
      color: '#858484',
    },
    h4: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.25rem',
      fontWeight: 600,
      color: '#858484',
    },
    h5: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.125rem',
      fontWeight: 600,
      color: '#858484',
    },
    h6: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1rem',
      fontWeight: 600,
      color: '#858484',
    },
    body1: {
      fontSize: '1rem',
      color: '#858484',
    },
    body2: {
      fontSize: '0.875rem',
      color: '#858484',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '4px',
          fontWeight: 600,
        },
        contained: {
          backgroundColor: '#ffffff',
          color: '#2f80ed',
          '&:hover': {
            backgroundColor: '#faa629',
            color: '#ffffff',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: '4px',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
          backgroundColor: '#ffffff',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#2f80ed',
          color: '#ffffff',
        },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: {
          '&:visited': {
            color: 'inherit',
          },
        },
      },
    },
  },
});

export default theme;