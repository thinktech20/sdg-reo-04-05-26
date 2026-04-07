import { createTheme } from '@mui/material/styles'
import { type PaletteMode } from '@mui/material'

// TypeScript module augmentation for custom theme properties
declare module '@mui/material/styles' {
  interface Theme {
    customColors: {
      userBubble: string
      aiBubble: string
      cardBackground: string
      inputBackground: string
      shadow: string
      neutral: string
      avatar: string
      activeOutline: string
      textHover: string
    }
  }
  interface ThemeOptions {
    customColors?: {
      userBubble?: string
      aiBubble?: string
      cardBackground?: string
      inputBackground?: string
      shadow?: string
      neutral?: string
      avatar?: string
      activeOutline?: string
      textHover?: string
    }
  }
}

const AVATAR_LIGHT = '#6AA1A3'
const AVATAR_DARK = '#2f7c7e'

const PRIMARY_MAIN = '#005E60' // evergreen
const PRIMARY_LIGHT = '#468a8c'
const PRIMARY_DARK = '#003F41' // dark evergreen

const SECONDARY_MAIN = AVATAR_LIGHT
const SECONDARY_LIGHT = '#8db7b9'
const SECONDARY_DARK = AVATAR_DARK

const SKY = '#5fb7ff'
const NIGHT = '#212121'
const DAY = '#fff'

// GE Vernova inspired color palette with softer backgrounds
const GE_EVERGREEN_400 = 'rgba(150, 189, 189, 1)'
const GE_EVERGREEN_50 = '#EBF2F4' // Very light evergreen tint (light mode)
const SOFT_GRAY = '#F8FAFC'
const WARM_WHITE = '#FEFEFE'

// Dark mode colors
const DARK_BG_DEFAULT = NIGHT
const DARK_BG_PAPER = '#242A3F'
const DARK_BG_ELEVATED = '#242B3D'
const DARK_EVERGREEN = 'rgba(69, 138, 138, 1)'

const DIVIDER_LIGHT = '#dbdddd'
const DIVIDER_DARK = '#3d486f'

const TRANSITION = 'all 0.2s ease'

// Helper functions to get colors based on mode
export const getCustomColors = (mode: PaletteMode) => ({
  userBubble: mode === 'light' ? GE_EVERGREEN_400 : DARK_EVERGREEN,
  aiBubble: mode === 'light' ? GE_EVERGREEN_50 : DARK_BG_ELEVATED,
  cardBackground: mode === 'light' ? GE_EVERGREEN_50 : DARK_BG_ELEVATED,
  inputBackground: mode === 'light' ? WARM_WHITE : DARK_BG_PAPER,
  shadow: mode === 'light' ? 'rgba(0, 0, 0, 0.10)' : 'rgba(255, 255, 255, 0.10)',
  neutral: mode === 'light' ? DIVIDER_LIGHT : DIVIDER_DARK,
  avatar: mode === 'light' ? AVATAR_LIGHT : AVATAR_DARK,
  activeOutline: SKY,
  textHover: mode === 'light' ? NIGHT : SKY,
})

const createAppTheme = (mode: PaletteMode = 'light') => {
  const textPrimary = mode === 'light' ? PRIMARY_MAIN : '#FFFFFF'
  const textSecondary = mode === 'light' ? '#468a8c' : '#99bec0'

  return createTheme({
    cssVariables: true,
    customColors: getCustomColors(mode),
    breakpoints: {
      values: {
        xs: 0,
        sm: 600,
        md: 900,
        lg: 1200,
        xl: 1536,
      },
    },
    palette: {
      mode,
      primary: {
        main: PRIMARY_MAIN,
        light: PRIMARY_LIGHT,
        dark: PRIMARY_DARK,
        contrastText: '#ffffff',
      },
      secondary: {
        main: SECONDARY_MAIN,
        light: SECONDARY_LIGHT,
        dark: SECONDARY_DARK,
        contrastText: '#000',
      },
      background: {
        default: mode === 'light' ? DAY : DARK_BG_DEFAULT,
        paper: mode === 'light' ? GE_EVERGREEN_50 : DARK_BG_PAPER,
      },
      text: {
        primary: textPrimary,
        secondary: textSecondary,
      },
      divider: mode === 'light' ? DIVIDER_LIGHT : DIVIDER_DARK,
      action: {
        hover: 'rgba(0, 0, 0, 0)',
        selected: 'rgba(0, 0, 0, 0)',
      },
      success: {
        main: '#10B981',
        light: '#CCFFCC',
        dark: '#059669',
      },
      warning: {
        main: '#F59E0B',
        light: '#ffe6b2',
        dark: '#D97706',
      },
      error: {
        main: '#EF4444',
        light: '#FFCCCC',
        dark: '#DC2626',
      },
      info: {
        main: SKY,
        light: SKY,
        dark: SKY,
      },
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontWeight: 700,
        fontSize: '2.5rem',
        lineHeight: 1.2,
      },
      h2: {
        fontWeight: 700,
        fontSize: '2rem',
        lineHeight: 1.3,
      },
      h3: {
        fontWeight: 600,
        fontSize: '1.75rem',
        lineHeight: 1.3,
      },
      h4: {
        fontWeight: 600,
        fontSize: '1.5rem',
        lineHeight: 1.4,
      },
      h5: {
        fontWeight: 600,
        fontSize: '1.25rem',
        lineHeight: 1.4,
      },
      h6: {
        fontWeight: 600,
        fontSize: '1.125rem',
        lineHeight: 1.4,
      },
      body1: {
        fontSize: '1rem',
        lineHeight: 1.6,
      },
      body2: {
        fontSize: '0.875rem',
        lineHeight: 1.5,
      },
      button: {
        textTransform: 'none',
        fontWeight: 500,
      },
    },
    shape: {
      borderRadius: 12,
    },
    components: {
      MuiAvatar: {
        styleOverrides: {
          root: {
            color: DAY,
            backgroundColor: mode === 'light' ? AVATAR_LIGHT : AVATAR_DARK,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            color: textPrimary,
            textTransform: 'none',
            fontWeight: 400,
            boxShadow: 'none',
            outline: '2px solid transparent',
            transition: TRANSITION,
            '&:hover': {
              boxShadow: 'none',
            },
            '&.MuiButton-contained': {
              color: DAY,
              '&:not(.Mui-disabled)': {
                backgroundColor: PRIMARY_MAIN,
              },
              '&:hover': {
                outlineColor: SKY,
              },
            },
            '&.MuiButton-outlined': {
              color: mode === 'dark' ? DAY : undefined,
              border: `1px solid ${PRIMARY_LIGHT}`,
              '&:hover': {
                borderColor: 'transparent',
                outlineColor: SKY,
              },
              '&.Mui-disabled': {
                borderColor: mode === 'light' ? DIVIDER_LIGHT : DIVIDER_DARK,
              },
            },
            '&.MuiButton-text': {
              '&:hover': {
                backgroundColor: 'transparent',
                outlineColor: 'none',
              },
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            '&.MuiChip-filled.MuiChip-colorDefault': {
              color: DAY,
              backgroundColor: mode === 'light' ? AVATAR_LIGHT : AVATAR_DARK,
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            outline: '2px solid transparent',
            '&:hover': {
              outlineColor: SKY,
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: mode === 'light' ? GE_EVERGREEN_50 : DARK_BG_PAPER,
            cursor: 'pointer',
            boxShadow: 'none',
            border: `1px solid ${mode === 'light' ? DIVIDER_LIGHT : DIVIDER_DARK}`,
            outline: '2px solid transparent',
            '&:hover': {
              borderColor: 'transparent',
              outlineColor: SKY,
            },
            transition: TRANSITION,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            cursor: 'pointer',
            border: '2px solid transparent',
            borderRadius: '8px',
            paddingTop: 2,
            paddingRight: 12,
            paddingLeft: 12,
            paddingBottom: 2,
            minHeight: 32,
            '&.Mui-selected': {
              borderColor: mode === 'dark' ? SECONDARY_DARK : SECONDARY_LIGHT,
              backgroundColor: 'none',
            },
            '&:hover': {
              borderColor: SKY,
              backgroundColor: 'none',
            },
          },
        },
      },
      MuiListItemText: {
        styleOverrides: {
          primary: {
            fontSize: '0.8rem',
            noWrap: true,
          },
          secondary: {
            fontSize: '0.7rem',
            color: PRIMARY_LIGHT,
          },
        },
      },
      MuiListSubheader: {
        styleOverrides: {
          root: {
            fontSize: '0.75rem',
            textTransform: 'uppercase',
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: mode === 'light' ? `1px solid ${DIVIDER_LIGHT}` : 'none',
            boxShadow: 'none',
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? SOFT_GRAY : DARK_BG_DEFAULT,
            '& .MuiOutlinedInput-root': {
              borderRadius: 8,
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: SKY,
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderColor: SKY,
                borderWidth: 2,
              },
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: {
            backgroundColor: SKY,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            '& .MuiOutlinedInput-root': {
              backgroundColor: mode === 'light' ? SOFT_GRAY : DARK_BG_DEFAULT,
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderWidth: 2,
                borderColor: SKY,
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                border: `2px solid ${SKY}`,
              },
            },
            '& .MuiOutlinedInput-notchedOutline': {
              border: `1px solid ${mode === 'light' ? DIVIDER_LIGHT : DIVIDER_DARK}`,
            },
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            minHeight: 48,
          },
        },
      },
    },
  })
}

export default createAppTheme
