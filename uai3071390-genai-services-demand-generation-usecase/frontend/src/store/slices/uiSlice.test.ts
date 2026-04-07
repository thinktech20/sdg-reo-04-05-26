/**
 * UI Slice Tests
 */

import { describe, it, expect, beforeEach } from 'vitest'
import uiReducer, {
  toggleTheme,
  setTheme,
  toggleSidebar,
  collapseSidebar,
  expandSidebar,
  openSidebarDrawer,
  closeSidebarDrawer,
  selectUI,
  selectTheme,
  selectIsDarkMode,
  selectSidebarCollapsed,
  selectSidebarOpen,
} from './uiSlice'
import { createTestStore } from '@/test/utils'
import type { UIState } from '../types'

describe('uiSlice', () => {
  let initialState: UIState

  beforeEach(() => {
    initialState = {
      theme: 'light',
      sidebarCollapsed: false,
      sidebarOpen: false,
    }
    localStorage.clear()
  })

  describe('reducers', () => {
    it('should return initial state', () => {
      expect(uiReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle toggleTheme from light to dark', () => {
      const state = uiReducer(initialState, toggleTheme())
      expect(state.theme).toBe('dark')
      expect(localStorage.getItem('theme')).toBe('dark')
    })

    it('should handle toggleTheme from dark to light', () => {
      const darkState = { ...initialState, theme: 'dark' as const }
      const state = uiReducer(darkState, toggleTheme())
      expect(state.theme).toBe('light')
      expect(localStorage.getItem('theme')).toBe('light')
    })

    it('should handle setTheme to dark', () => {
      const state = uiReducer(initialState, setTheme('dark'))
      expect(state.theme).toBe('dark')
      expect(localStorage.getItem('theme')).toBe('dark')
    })

    it('should handle setTheme to light', () => {
      const state = uiReducer(initialState, setTheme('light'))
      expect(state.theme).toBe('light')
      expect(localStorage.getItem('theme')).toBe('light')
    })

    it('should handle setTheme to light (alternative test)', () => {
      const darkState = { ...initialState, theme: 'dark' as const }
      const state = uiReducer(darkState, setTheme('light'))
      expect(state.theme).toBe('light')
      expect(localStorage.getItem('theme')).toBe('light')
    })

    it('should handle setTheme to dark (alternative test)', () => {
      const state = uiReducer(initialState, setTheme('dark'))
      expect(state.theme).toBe('dark')
      expect(localStorage.getItem('theme')).toBe('dark')
    })

    it('should handle toggleSidebar from expanded to collapsed', () => {
      const state = uiReducer(initialState, toggleSidebar())
      expect(state.sidebarCollapsed).toBe(true)
      expect(localStorage.getItem('sidebarCollapsed')).toBe('true')
    })

    it('should handle toggleSidebar from collapsed to expanded', () => {
      const collapsedState = { ...initialState, sidebarCollapsed: true }
      const state = uiReducer(collapsedState, toggleSidebar())
      expect(state.sidebarCollapsed).toBe(false)
      expect(localStorage.getItem('sidebarCollapsed')).toBe('false')
    })

    it('should handle collapseSidebar', () => {
      const state = uiReducer(initialState, collapseSidebar())
      expect(state.sidebarCollapsed).toBe(true)
      expect(localStorage.getItem('sidebarCollapsed')).toBe('true')
    })

    it('should handle expandSidebar', () => {
      const collapsedState = { ...initialState, sidebarCollapsed: true }
      const state = uiReducer(collapsedState, expandSidebar())
      expect(state.sidebarCollapsed).toBe(false)
      expect(localStorage.getItem('sidebarCollapsed')).toBe('false')
    })

    it('should handle openSidebarDrawer', () => {
      const state = uiReducer(initialState, openSidebarDrawer())
      expect(state.sidebarOpen).toBe(true)
    })

    it('should handle closeSidebarDrawer', () => {
      const openState = { ...initialState, sidebarOpen: true }
      const state = uiReducer(openState, closeSidebarDrawer())
      expect(state.sidebarOpen).toBe(false)
    })
  })

  describe('initial state from localStorage', () => {
    it('should persist dark theme to localStorage', () => {
      localStorage.clear()
      const state = uiReducer(initialState, setTheme('dark'))
      expect(state.theme).toBe('dark')
      expect(localStorage.getItem('theme')).toBe('dark')
    })

    it('should persist sidebar collapsed state to localStorage', () => {
      localStorage.clear()
      const state = uiReducer(initialState, collapseSidebar())
      expect(state.sidebarCollapsed).toBe(true)
      expect(localStorage.getItem('sidebarCollapsed')).toBe('true')
    })

    it('should use default theme when localStorage has invalid value', () => {
      localStorage.setItem('theme', 'invalid')
      const freshState = uiReducer(undefined, { type: 'unknown' })
      expect(freshState.theme).toBe('light')
    })
  })

  describe('selectors', () => {
    it('selectUI should return UI state', () => {
      const store = createTestStore({ ui: initialState })
      expect(selectUI(store.getState())).toEqual(initialState)
    })

    it('selectTheme should return current theme', () => {
      const store = createTestStore({ ui: { ...initialState, theme: 'dark' } })
      expect(selectTheme(store.getState())).toBe('dark')
    })

    it('selectIsDarkMode should return true for dark theme', () => {
      const store = createTestStore({ ui: { ...initialState, theme: 'dark' } })
      expect(selectIsDarkMode(store.getState())).toBe(true)
    })

    it('selectIsDarkMode should return false for light theme', () => {
      const store = createTestStore({ ui: { ...initialState, theme: 'light' } })
      expect(selectIsDarkMode(store.getState())).toBe(false)
    })

    it('selectSidebarCollapsed should return sidebar collapsed state', () => {
      const store = createTestStore({ ui: { ...initialState, sidebarCollapsed: true } })
      expect(selectSidebarCollapsed(store.getState())).toBe(true)
    })

    it('selectSidebarOpen should return sidebar open state', () => {
      const store = createTestStore({ ui: { ...initialState, sidebarOpen: true } })
      expect(selectSidebarOpen(store.getState())).toBe(true)
    })
  })
})
