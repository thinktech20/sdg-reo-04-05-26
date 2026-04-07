import {
  Drawer,
  Box,
  List,
  ListItemButton,
  ListItemText,
  IconButton,
  Avatar,
  Typography,
} from '@mui/material'
import { Link, useLocation } from 'react-router-dom'
import DashboardIcon from '@mui/icons-material/Dashboard'
import AssessmentIcon from '@mui/icons-material/Assessment'
import KeyboardArrowLeftIcon from '@mui/icons-material/KeyboardArrowLeft'
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined'
import { useTheme } from '@mui/material/styles'

type Props = {
  drawerWidth: number
  drawerWidthCollapsed: number
  headerHeight: number
  collapsed: boolean
  onToggle: () => void
}

export default function SideNav({
  drawerWidth,
  drawerWidthCollapsed,
  headerHeight,
  collapsed,
  onToggle,
}: Props) {
  const location = useLocation()
  const theme = useTheme()
  const currentDrawerWidth = collapsed ? drawerWidthCollapsed : drawerWidth

  const sidebarBg = theme.palette.mode === 'dark' ? '#005e60' : '#6AA1A3'

  const items = [
    { label: 'Dashboard', to: '/', icon: <DashboardIcon sx={{ fontSize: 20 }} /> },
    { label: 'Units', to: '/units', icon: <AssessmentIcon sx={{ fontSize: 20 }} /> },
  ]

  return (
    <Drawer
      variant="permanent"
      open
      sx={{
        display: { xs: 'none', md: 'block' },
        width: currentDrawerWidth,
        flexShrink: 0,
        transition: 'width 0.3s ease',
        ['& .MuiDrawer-paper']: {
          width: currentDrawerWidth,
          boxSizing: 'border-box',
          background: sidebarBg,
          borderRight: 'none',
          height: '100vh',
          transition: 'width 0.3s ease',
          overflow: 'hidden',
        },
      }}
    >
      {/* Logo Section */}
      <Box
        sx={{
          px: collapsed ? 0 : 2,
          py: 1.5,
          height: `${headerHeight}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          bgcolor: sidebarBg,
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
        }}
        onClick={onToggle}
      >
        <Box
          component="img"
          src={`/${collapsed ? 'gev-logo-mini.svg' : 'gev-logo.svg'}`}
          alt="GE Vernova"
          sx={{
            width: collapsed ? '40%' : '75%',
            height: 48,
            objectFit: 'contain',
            filter: 'brightness(0) invert(1)',
            transition: 'all 0.3s ease',
          }}
        />
        <IconButton
          size="small"
          sx={{
            color: 'white',
            display: collapsed ? 'none' : 'flex',
          }}
        >
          <KeyboardArrowLeftIcon sx={{ fontSize: 20 }} />
        </IconButton>
      </Box>

      {/* Navigation Items */}
      <Box sx={{ px: 2, pt: 2, flexGrow: 1, overflow: 'auto' }}>
        <List dense>
          {items.map((item) => {
            const selected = location.pathname === item.to
            return (
              <ListItemButton
                key={item.to}
                component={Link}
                to={item.to}
                selected={selected}
                sx={{
                  borderRadius: 2,
                  mb: 0.5,
                  color: 'rgba(255, 255, 255, 0.9)',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  px: collapsed ? 1 : 2,
                  '&.Mui-selected': {
                    bgcolor: 'rgba(255, 255, 255, 0.15)',
                    color: 'white',
                    '&:hover': {
                      bgcolor: 'rgba(255, 255, 255, 0.2)',
                    },
                  },
                  '&:hover': {
                    bgcolor: 'rgba(255, 255, 255, 0.1)',
                  },
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    width: '100%',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                  }}
                >
                  {item.icon}
                  {!collapsed && (
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{
                        fontSize: '0.875rem',
                        fontWeight: selected ? 600 : 400,
                      }}
                    />
                  )}
                </Box>
              </ListItemButton>
            )
          })}
        </List>
      </Box>

      {/* Bottom Section - User Profile and Settings */}
      <Box
        sx={{
          px: 2,
          py: 2,
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          mt: 'auto',
        }}
      >
        {!collapsed ? (
          <>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                mb: 1,
                cursor: 'pointer',
                p: 1,
                borderRadius: 2,
                '&:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.05)',
                },
              }}
            >
              <Avatar sx={{ bgcolor: 'text.secondary' }}>D</Avatar>
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <Typography
                  variant="body2"
                  sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}
                >
                  User Name
                </Typography>
                <Typography
                  variant="caption"
                  sx={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.75rem' }}
                >
                  user@example.com
                </Typography>
                {/* <Chip label="Reliability Engineer" variant="outlined" /> */}
              </Box>
            </Box>
            <ListItemButton
              sx={{
                borderRadius: 2,
                color: 'rgba(255, 255, 255, 0.9)',
                py: 1,
                '&:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <SettingsOutlinedIcon sx={{ fontSize: 20 }} />
                <ListItemText
                  primary="Settings"
                  primaryTypographyProps={{
                    fontSize: '0.875rem',
                  }}
                />
              </Box>
            </ListItemButton>
          </>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'text.secondary' }}>D</Avatar>
            <IconButton
              size="small"
              sx={{
                color: 'rgba(255, 255, 255, 0.9)',
                '&:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                },
              }}
            >
              <SettingsOutlinedIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Box>
        )}
      </Box>
    </Drawer>
  )
}
