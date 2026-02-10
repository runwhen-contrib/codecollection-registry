import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#5282f1',
      light: '#7a9ff4',
      dark: '#3a5cb8',
    },
    secondary: {
      main: '#f8ad4b',
      light: '#fac273',
      dark: '#e69538',
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
    fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '2.5rem',
      fontWeight: 700,
      color: '#858484',
    },
    h2: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '2rem',
      fontWeight: 600,
      color: '#858484',
    },
    h3: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.5rem',
      fontWeight: 600,
      color: '#858484',
    },
    h4: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.25rem',
      fontWeight: 600,
      color: '#858484',
    },
    h5: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      fontSize: '1.125rem',
      fontWeight: 600,
      color: '#858484',
    },
    h6: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
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
          backgroundColor: '#5282f1',
          color: '#ffffff',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
          fontSize: '0.875rem',
          color: '#858484',
        },
        head: {
          fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
          fontWeight: 600,
          color: '#3f3f3f',
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