import { createTheme, PaletteMode } from '@mui/material';

export const getTheme = (mode: PaletteMode) => {
  const isLight = mode === 'light';

  return createTheme({
    palette: {
      mode,
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
        default: isLight ? '#ffffff' : '#121212',
        paper: isLight ? '#ffffff' : '#1e1e1e',
      },
      text: {
        primary: isLight ? '#3f3f3f' : '#e0e0e0',
        secondary: isLight ? '#858484' : '#a0a0a0',
      },
      divider: isLight ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)',
    },
    typography: {
      fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '2.5rem',
        fontWeight: 700,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      h2: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '2rem',
        fontWeight: 600,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      h3: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.5rem',
        fontWeight: 600,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      h4: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.25rem',
        fontWeight: 600,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      h5: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.125rem',
        fontWeight: 600,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      h6: {
        fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1rem',
        fontWeight: 600,
        color: isLight ? '#858484' : '#e0e0e0',
      },
      body1: {
        fontSize: '1rem',
        color: isLight ? '#858484' : '#c0c0c0',
      },
      body2: {
        fontSize: '0.875rem',
        color: isLight ? '#858484' : '#c0c0c0',
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
          root: ({ theme }) => ({
            borderRadius: '4px',
            boxShadow: theme.palette.mode === 'light'
              ? '0 2px 4px rgba(0, 0, 0, 0.1)'
              : '0 2px 4px rgba(0, 0, 0, 0.4)',
            backgroundColor: theme.palette.background.paper,
          }),
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: theme.palette.mode === 'light' ? '#5282f1' : '#1a1a2e',
            color: '#ffffff',
          }),
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
            fontSize: '0.875rem',
            color: isLight ? '#858484' : '#c0c0c0',
          },
          head: {
            fontFamily: '"Raleway", "Roboto", "Helvetica", "Arial", sans-serif',
            fontWeight: 600,
            color: isLight ? '#3f3f3f' : '#e0e0e0',
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
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: 'none', // Remove MUI's default dark mode paper gradient
          }),
        },
      },
    },
  });
};

// Default export for backward compatibility
const theme = getTheme('light');
export default theme;
