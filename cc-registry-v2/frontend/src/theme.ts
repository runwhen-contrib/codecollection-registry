import { createTheme, PaletteMode } from '@mui/material';

export const getTheme = (mode: PaletteMode) => {
  const isLight = mode === 'light';

  // Aligned with /workspaces/docs src/styles/custom.css (RunWhen Starlight theme)
  const docsPrimary = '#2F80ED';
  const docsPrimaryLight = '#90cdf4';
  const docsPrimaryDark = '#1a365d';
  const docsGray1 = isLight ? '#2d3748' : '#cbd5e1';
  const docsGray2 = isLight ? '#4a5568' : '#94a3b8';
  const docsGray5 = isLight ? '#e2e8f0' : '#64748b';
  const docsGray6 = isLight ? '#f7fafc' : '#334155';
  const docsGray7 = isLight ? '#ffffff' : '#0f172a';

  return createTheme({
    palette: {
      mode,
      primary: {
        main: docsPrimary,
        light: docsPrimaryLight,
        dark: docsPrimaryDark,
      },
      secondary: {
        main: '#faa629',
        light: '#f6ad37',
        dark: '#e69538',
      },
      background: {
        default: docsGray7,
        paper: isLight ? docsGray7 : '#1e293b',
      },
      text: {
        primary: isLight ? '#1a202c' : '#e2e8f0',
        secondary: isLight ? docsGray2 : docsGray2,
      },
      divider: isLight ? docsGray5 : 'rgba(255, 255, 255, 0.12)',
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '2.5rem',
        fontWeight: 700,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      h2: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '2rem',
        fontWeight: 600,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      h3: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.5rem',
        fontWeight: 600,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      h4: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.25rem',
        fontWeight: 600,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      h5: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1.125rem',
        fontWeight: 600,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      h6: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        fontSize: '1rem',
        fontWeight: 600,
        color: isLight ? '#1a202c' : '#e2e8f0',
      },
      body1: {
        fontSize: '0.875rem',
        color: isLight ? docsGray2 : '#cbd5e1',
      },
      body2: {
        fontSize: '0.8125rem',
        color: isLight ? docsGray2 : '#94a3b8',
      },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: 6,
            fontWeight: 600,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderRadius: 8,
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
            backgroundColor: theme.palette.mode === 'light' ? theme.palette.primary.main : '#0f172a',
            color: '#ffffff',
          }),
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
            fontSize: '0.875rem',
            color: isLight ? docsGray2 : '#94a3b8',
          },
          head: {
            fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
            fontWeight: 600,
            color: isLight ? '#1a202c' : '#e2e8f0',
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
