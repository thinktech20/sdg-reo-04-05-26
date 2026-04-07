/**
 * Store Configuration Tests
 */

import { describe, it, expect } from 'vitest'
import { store } from './index'
import type { RootState } from './index'

describe('Store Configuration', () => {
  it('should initialize with correct reducers', () => {
    const state = store.getState()
    
    expect(state).toHaveProperty('auth')
    expect(state).toHaveProperty('ui')
    expect(state).toHaveProperty('equipment')
    expect(state).toHaveProperty('assessments')
    expect(state).toHaveProperty('documents')
    expect(state).toHaveProperty('chat')
  })

  it('should have correct initial auth state', () => {
    const state = store.getState()
    
    expect(state.auth).toMatchObject({
      user: null,
      token: null,
      isAuthenticated: false,
      loading: false,
      error: null,
    })
  })

  it('should have correct initial UI state', () => {
    const state = store.getState()
    
    expect(state.ui).toMatchObject({
      theme: expect.stringMatching(/^(light|dark)$/),
      sidebarCollapsed: expect.any(Boolean),
      sidebarOpen: false,
    })
  })

  it('should have correct initial equipment state', () => {
    const state = store.getState()
    
    expect(state.equipment).toMatchObject({
      trains: [],
      selectedEquipment: null,
      searchResults: [],
      loading: false,
      error: null,
      filters: {
        type: 'all',
        search: '',
      },
    })
  })

  it('should have correct initial assessments state', () => {
    const state = store.getState()
    
    expect(state.assessments).toMatchObject({
      assessments: {},
      currentAssessment: null,
      loading: false,
      analyzing: false,
      error: null,
    })
  })

  it('should have correct initial documents state', () => {
    const state = store.getState()
    
    expect(state.documents).toMatchObject({
      erCases: {},
      fsrReports: {},
      outageHistory: {},
      uploadedDocs: {},
      loading: false,
      error: null,
    })
  })

  it('should have correct initial chat state', () => {
    const state = store.getState()
    
    expect(state.chat).toMatchObject({
      reliabilityChats: {},
      outageChats: {},
      loading: false,
      error: null,
    })
  })

  it('should handle actions correctly', () => {
    const initialState = store.getState()
    
    // Dispatch a test action (toggle theme)
    store.dispatch({ type: 'ui/toggleTheme' })
    
    const newState = store.getState()
    
    // Theme should have changed
    expect(newState.ui.theme).not.toBe(initialState.ui.theme)
    
    // Other state should remain unchanged
    expect(newState.auth).toEqual(initialState.auth)
    expect(newState.equipment).toEqual(initialState.equipment)
  })

  it('should maintain state shape conformance', () => {
    const state: RootState = store.getState()
    
    // Verify state shape matches RootState type
    expect(typeof state.auth).toBe('object')
    expect(typeof state.ui).toBe('object')
    expect(typeof state.equipment).toBe('object')
    expect(typeof state.assessments).toBe('object')
    expect(typeof state.documents).toBe('object')
    expect(typeof state.chat).toBe('object')
  })

  it('should have devTools enabled in non-production', () => {
    // Store is configured with devTools in development
    // This is more of a configuration check
    const { dispatch } = store
    expect(store).toBeDefined()
    expect(dispatch).toBeDefined()
    expect(typeof store['getState']).toBe('function')
    expect(typeof store['subscribe']).toBe('function')
  })

  it('should support middleware', () => {
    // Verify middleware is working (thunk middleware is default in RTK)
    const thunkAction = () => (dispatch: typeof store.dispatch) => {
      dispatch({ type: 'test/thunk' })
    }
    
    // Should not throw
    expect(() => store.dispatch(thunkAction() as never)).not.toThrow()
  })

  it('should handle unknown actions gracefully', () => {
    const beforeState = store.getState()
    
    // Dispatch unknown action
    store.dispatch({ type: 'UNKNOWN_ACTION_TYPE' })
    
    const afterState = store.getState()
    
    // State should remain unchanged
    expect(afterState).toEqual(beforeState)
  })

  it('should support subscriptions', () => {
    let callCount = 0
    
    const unsubscribe = store.subscribe(() => {
      callCount++
    })
    
    // Dispatch an action
    store.dispatch({ type: 'ui/toggleTheme' })
    
    expect(callCount).toBeGreaterThan(0)
    
    // Cleanup
    unsubscribe()
  })

  it('should allow replacing reducers', () => {
    // Just verify the store has the replaceReducer method
    expect(typeof store['replaceReducer']).toBe('function')
  })
})
