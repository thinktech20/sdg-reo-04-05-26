import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Box from '@mui/material/Box'

import Header from './Header'
import SideNav from './SideNav'

const DRAWER_WIDTH = 260
const DRAWER_WIDTH_COLLAPSED = 72
const HEADER_HEIGHT = 64

/**
 * Base layout component
 * Provides the main application structure with header, sidebar, and content area
 */
export default function BaseLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const currentDrawerWidth = sidebarCollapsed ? DRAWER_WIDTH_COLLAPSED : DRAWER_WIDTH

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => !prev)
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Header drawerWidth={currentDrawerWidth} headerHeight={HEADER_HEIGHT} />
      <SideNav
        drawerWidth={DRAWER_WIDTH}
        drawerWidthCollapsed={DRAWER_WIDTH_COLLAPSED}
        headerHeight={HEADER_HEIGHT}
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
      />

      <Box
        component="main"
        sx={{
            flexGrow: 1,
            p: 4,
            mt: `${HEADER_HEIGHT}px`,
            transition: 'margin-left 0.3s ease',
        }}
      >
        <Box sx={{ maxWidth: '100%', mx: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}

