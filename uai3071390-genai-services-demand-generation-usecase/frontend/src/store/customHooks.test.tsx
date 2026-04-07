/**
 * Tests for Custom Redux Hooks
 * 
 * These tests verify that the custom hooks provide the correct interface
 * and properly wrap Redux operations. Full integration testing is covered
 * by slice tests.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import type { ReactNode } from 'react'

import {
  useAuth,
  useUI,
  useEquipment,
  useAssessments,
  useDocuments,
  useChat,
  useAssessmentDetail,
} from './customHooks'

import authReducer from './slices/authSlice'
import uiReducer from './slices/uiSlice'
import equipmentReducer from './slices/equipmentSlice'
import assessmentsReducer from './slices/assessmentsSlice'
import documentsReducer from './slices/documentsSlice'
import chatReducer from './slices/chatSlice'

import { createMockUser } from '@/test/utils'
import type { RootState } from './index'

// Helper type for partial nested objects
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]
}

// Mock fetch
let mockFetch: ReturnType<typeof vi.fn>

beforeEach(() => {
  mockFetch = vi.fn()
  vi.stubGlobal('fetch', mockFetch)
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// Helper to create test store
const createTestStore = (preloadedState?: DeepPartial<RootState>) => {
  return configureStore({
    reducer: {
      auth: authReducer,
      ui: uiReducer,
      equipment: equipmentReducer,
      assessments: assessmentsReducer,
      documents: documentsReducer,
      chat: chatReducer,
    },
    preloadedState: preloadedState as RootState,
  })
}

// Helper to create wrapper with store
const createWrapper = (store: ReturnType<typeof createTestStore>) => {
  return ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  )
}

// ============================================================================
// AUTH HOOKS TESTS
// ============================================================================

describe('useAuth', () => {
  it('should provide auth state and actions', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('user')
    expect(result.current).toHaveProperty('isAuthenticated')
    expect(result.current).toHaveProperty('loading')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('isAdmin')
    
    // Verify action methods
    expect(result.current).toHaveProperty('login')
    expect(result.current).toHaveProperty('logout')
    expect(result.current).toHaveProperty('refreshUser')
    expect(result.current).toHaveProperty('restoreSession')
    expect(result.current).toHaveProperty('clearError')
    
    // Verify types
    expect(typeof result.current.login).toBe('function')
    expect(typeof result.current.logout).toBe('function')
  })

  it('should reflect authenticated state', () => {
    const mockUser = createMockUser()
    const store = createTestStore({
      auth: {
        user: mockUser,
        token: 'test-token',
        isAuthenticated: true,
        loading: false,
        error: null,
      },
    })

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(store),
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(mockUser)
  })
})

// ============================================================================
// UI HOOKS TESTS
// ============================================================================

describe('useUI', () => {
  it('should provide UI state and actions', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useUI(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('theme')
    expect(result.current).toHaveProperty('isDarkMode')
    expect(result.current).toHaveProperty('sidebarCollapsed')
    
    // Verify action methods
    expect(result.current).toHaveProperty('toggleTheme')
    expect(result.current).toHaveProperty('setLightMode')
    expect(result.current).toHaveProperty('setDarkMode')
    expect(result.current).toHaveProperty('toggleSidebar')
    expect(result.current).toHaveProperty('collapseSidebar')
    expect(result.current).toHaveProperty('expandSidebar')
    
    // Verify types
    expect(typeof result.current.toggleTheme).toBe('function')
    expect(typeof result.current.toggleSidebar).toBe('function')
  })

  it('should toggle theme', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useUI(), {
      wrapper: createWrapper(store),
    })

    const initialTheme = result.current.theme

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.theme).not.toBe(initialTheme)
  })

  it('should toggle sidebar', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useUI(), {
      wrapper: createWrapper(store),
    })

    const initialCollapsed = result.current.sidebarCollapsed

    act(() => {
      result.current.toggleSidebar()
    })

    expect(result.current.sidebarCollapsed).toBe(!initialCollapsed)
  })
})

// ============================================================================
// EQUIPMENT HOOKS TESTS
// ============================================================================

describe('useEquipment', () => {
  it('should provide equipment state and actions', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useEquipment(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('trains')
    expect(result.current).toHaveProperty('selectedEquipment')
    expect(result.current).toHaveProperty('loading')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('filters')
    
    // Verify action methods
    expect(result.current).toHaveProperty('loadTrains')
    expect(result.current).toHaveProperty('searchEquipment')
    expect(result.current).toHaveProperty('selectEquipment')
    expect(result.current).toHaveProperty('clearSelection')
    expect(result.current).toHaveProperty('setTypeFilter')
    expect(result.current).toHaveProperty('setSearchQuery')
    expect(result.current).toHaveProperty('clearFilters')
    
    // Verify types
    expect(typeof result.current.loadTrains).toBe('function')
    expect(typeof result.current.searchEquipment).toBe('function')
    expect(Array.isArray(result.current.trains)).toBe(true)
  })
})

// ============================================================================
// ASSESSMENTS HOOKS TESTS
// ============================================================================

describe('useAssessments', () => {
  it('should provide assessments state and actions', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useAssessments(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('currentAssessment')
    expect(result.current).toHaveProperty('allAssessments')
    expect(result.current).toHaveProperty('loading')
    expect(result.current).toHaveProperty('analyzing')
    expect(result.current).toHaveProperty('error')
    
    // Verify action methods
    expect(result.current).toHaveProperty('createAssessment')
    expect(result.current).toHaveProperty('fetchAssessment')
    expect(result.current).toHaveProperty('runAnalysis')
    expect(result.current).toHaveProperty('updateReliability')
    expect(result.current).toHaveProperty('updateOutage')
    expect(result.current).toHaveProperty('submitFeedback')
    expect(result.current).toHaveProperty('exportPDF')
    expect(result.current).toHaveProperty('setCurrentAssessment')
    expect(result.current).toHaveProperty('clearCurrentAssessment')
    
    // Verify types
    expect(typeof result.current.createAssessment).toBe('function')
    expect(typeof result.current.runAnalysis).toBe('function')
  })
})

// ============================================================================
// DOCUMENTS HOOKS TESTS
// ============================================================================

describe('useDocuments', () => {
  it('should provide documents state and actions without ESN', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useDocuments(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('erCases')
    expect(result.current).toHaveProperty('fsrReports')
    expect(result.current).toHaveProperty('outageHistory')
    expect(result.current).toHaveProperty('uploadedDocs')
    expect(result.current).toHaveProperty('loading')
    
    // Verify action methods
    expect(result.current).toHaveProperty('fetchERCases')
    expect(result.current).toHaveProperty('fetchFSRReports')
    expect(result.current).toHaveProperty('fetchOutageHistory')
    expect(result.current).toHaveProperty('fetchUploadedDocuments')
    expect(result.current).toHaveProperty('uploadDocument')
    expect(result.current).toHaveProperty('fetchAllDocuments')
    
    // Verify types
    expect(typeof result.current.fetchERCases).toBe('function')
    expect(typeof result.current.uploadDocument).toBe('function')
  })

  it('should accept ESN parameter', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useDocuments('GT12345'), {
      wrapper: createWrapper(store),
    })

    expect(result.current).toHaveProperty('erCases')
    expect(result.current).toHaveProperty('fetchERCases')
  })
})

// ============================================================================
// CHAT HOOKS TESTS
// ============================================================================

describe('useChat', () => {
  it('should provide chat state and actions without assessmentId', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useChat(), {
      wrapper: createWrapper(store),
    })

    // Verify state properties
    expect(result.current).toHaveProperty('reliabilityChat')
    expect(result.current).toHaveProperty('outageChat')
    expect(result.current).toHaveProperty('hasReliabilityChat')
    expect(result.current).toHaveProperty('hasOutageChat')
    expect(result.current).toHaveProperty('loading')
    
    // Verify action methods
    expect(result.current).toHaveProperty('clearReliabilityChat')
    expect(result.current).toHaveProperty('clearOutageChat')
    
    // Verify types
    expect(typeof result.current.clearReliabilityChat).toBe('function')
  })

  it('should accept assessmentId parameter', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useChat('assessment-1'), {
      wrapper: createWrapper(store),
    })

    expect(result.current).toHaveProperty('reliabilityChat')
    expect(result.current).toHaveProperty('clearReliabilityChat')
  })
})

// ============================================================================
// COMBINED HOOKS TESTS
// ============================================================================

describe('useAssessmentDetail', () => {
  it('should combine assessment, chat, and documents hooks', () => {
    const store = createTestStore()
    const { result } = renderHook(() => useAssessmentDetail('assessment-1'), {
      wrapper: createWrapper(store),
    })

    // Should have assessment properties
    expect(result.current).toHaveProperty('currentAssessment')
    expect(result.current).toHaveProperty('createAssessment')
    
    // Should have chat properties
    expect(result.current).toHaveProperty('reliabilityChat')
    expect(result.current).toHaveProperty('clearReliabilityChat')
    
    // Should have documents properties
    expect(result.current).toHaveProperty('erCases')
    expect(result.current).toHaveProperty('fetchERCases')
    
    // Verify combined interface
    expect(typeof result.current.createAssessment).toBe('function')
    expect(typeof result.current.clearReliabilityChat).toBe('function')
    expect(typeof result.current.fetchERCases).toBe('function')
  })
})
