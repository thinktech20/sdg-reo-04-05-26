import { AppBar, Box, IconButton, Toolbar, Typography } from '@mui/material'
import Brightness4Icon from '@mui/icons-material/Brightness4'
import Brightness7Icon from '@mui/icons-material/Brightness7'
import { useThemeMode } from '@/theme'

type Props = {
  drawerWidth: number
  headerHeight: number
}

/**
 * Header component
 * Top application bar with title and theme toggle
 */
export default function Header({ drawerWidth, headerHeight }: Props) {
  const { mode, toggleTheme } = useThemeMode()
  const isDarkMode = mode === 'dark'

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        height: `${headerHeight}px`,
        justifyContent: 'center',
        bgcolor: isDarkMode ? '#25262b' : '#ffffff',
        border: 'none',
        borderBottom: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : '#e5e5e5'}`,
        ml: { md: `${drawerWidth}px` },
        width: { md: `calc(100% - ${drawerWidth}px)` },
        transition: 'all 0.3s ease',
        borderRadius: 0,
      }}
    >
      <Toolbar
        sx={{ minHeight: `${headerHeight}px`, display: 'flex', justifyContent: 'space-between' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'left', gap: 0, flexDirection: 'column' }}>
            <Typography variant="h4" sx={{ fontWeight: 600, fontSize: '1.2rem', color: 'text.primary' }}>
              Unit Risk Agent
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 400, fontSize: '0.7rem', color: 'text.secondary' }}>
              Outage Planning Intelligence System
            </Typography>
          </Box>
        </Box>

        <IconButton
          onClick={toggleTheme}
          sx={{
            color: 'text.primary',
            '&:hover': {
              bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)',
            },
          }}
          aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDarkMode ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>
      </Toolbar>
    </AppBar>
  )
}
