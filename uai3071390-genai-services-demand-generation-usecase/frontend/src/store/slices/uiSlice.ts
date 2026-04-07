/**
 * UI Slice
 * Manages UI state including theme, sidebar, and other UI preferences
 * Migrated from sdg-risk-analyser-archive
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { UIState } from '../types'

// ============================================================================
// INITIAL STATE
// ============================================================================

const getInitialTheme = (): 'light' | 'dark' => {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') {
    return stored
  }
  
  // Check system preference
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  
  return 'light'
}

const initialState: UIState = {
  theme: getInitialTheme(),
  sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === 'true',
  sidebarOpen: false, // For mobile drawer
}

// ============================================================================
// SLICE
// ============================================================================

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleTheme: (state) => {
      state.theme = state.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('theme', state.theme)
    },
    
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload
      localStorage.setItem('theme', state.theme)
    },
    
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed
      localStorage.setItem('sidebarCollapsed', String(state.sidebarCollapsed))
    },
    
    collapseSidebar: (state) => {
      state.sidebarCollapsed = true
      localStorage.setItem('sidebarCollapsed', 'true')
    },
    
    expandSidebar: (state) => {
      state.sidebarCollapsed = false
      localStorage.setItem('sidebarCollapsed', 'false')
    },
    
    openSidebarDrawer: (state) => {
      state.sidebarOpen = true
    },
    
    closeSidebarDrawer: (state) => {
      state.sidebarOpen = false
    },
    
    toggleSidebarDrawer: (state) => {
      state.sidebarOpen = !state.sidebarOpen
    },
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const {
  toggleTheme,
  setTheme,
  toggleSidebar,
  collapseSidebar,
  expandSidebar,
  openSidebarDrawer,
  closeSidebarDrawer,
  toggleSidebarDrawer,
} = uiSlice.actions

export default uiSlice.reducer

// Selectors
export const selectUI = (state: { ui: UIState }) => state.ui
export const selectTheme = (state: { ui: UIState }) => state.ui.theme
export const selectIsDarkMode = (state: { ui: UIState }) => state.ui.theme === 'dark'
export const selectSidebarCollapsed = (state: { ui: UIState }) => state.ui.sidebarCollapsed
export const selectSidebarOpen = (state: { ui: UIState }) => state.ui.sidebarOpen
