/**
 * Auth Slice Tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import authReducer, {
  login,
  logout,
  fetchCurrentUser,
  clearError,
  restoreSession,
  selectAuth,
  selectCurrentUser,
  selectIsAuthenticated,
  selectAuthLoading,
  selectAuthError,
  selectUserRole,
  selectUserAccessLevel,
  selectIsAdmin,
} from './authSlice'
import { createTestStore, createMockUser } from '@/test/utils'
import type { AuthState } from '../types'

// Mock fetch
const mockFetch = vi.fn()

describe('authSlice', () => {
  let initialState: AuthState

  beforeEach(() => {
    initialState = {
      user: null,
      token: null,
      isAuthenticated: false,
      loading: false,
      error: null,
    }
    localStorage.clear()
    mockFetch.mockClear()
    vi.stubGlobal('fetch', mockFetch)
  })

  afterEach(() => {
    mockFetch.mockReset()
    vi.unstubAllGlobals()
  })

  describe('reducers', () => {
    it('should return initial state', () => {
      expect(authReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle clearError', () => {
      const stateWithError = { ...initialState, error: 'Test error' }
      expect(authReducer(stateWithError, clearError())).toEqual({
        ...stateWithError,
        error: null,
      })
    })

    it('should handle restoreSession with valid token and user', () => {
      const user = createMockUser()
      const token = 'test-token'
      
      localStorage.setItem('auth_token', token)
      localStorage.setItem('user', JSON.stringify(user))
      
      const nextState = authReducer(initialState, restoreSession())
      
      expect(nextState.user).toEqual(user)
      expect(nextState.token).toEqual(token)
      expect(nextState.isAuthenticated).toBe(true)
    })

    it('should handle restoreSession with no token', () => {
      const nextState = authReducer(initialState, restoreSession())
      
      expect(nextState.user).toBeNull()
      expect(nextState.token).toBeNull()
      expect(nextState.isAuthenticated).toBe(false)
    })

    it('should handle restoreSession with invalid user JSON', () => {
      localStorage.setItem('auth_token', 'test-token')
      localStorage.setItem('user', 'invalid-json')
      
      const nextState = authReducer(initialState, restoreSession())
      
      expect(nextState.user).toBeNull()
      expect(nextState.token).toBeNull()
      expect(nextState.isAuthenticated).toBe(false)
    })
  })

  describe('async thunks', () => {
    describe('login', () => {
      it('should handle successful login', async () => {
        const mockUser = createMockUser()
        const mockToken = 'test-token'

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ user: mockUser, token: mockToken }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(login({ sso: 'demo' }))
        
        const state = store.getState().auth
        expect(state.loading).toBe(false)
        expect(state.user).toEqual(mockUser)
        expect(state.token).toBe(mockToken)
        expect(state.isAuthenticated).toBe(true)
        expect(state.error).toBeNull()
      })

      it('should save token and user to localStorage on success', async () => {
        const mockUser = createMockUser()
        const mockToken = 'test-token'

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ user: mockUser, token: mockToken }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(login({ sso: 'demo' }))
        
        const savedToken = localStorage.getItem('auth_token')
        const savedUser = localStorage.getItem('user')
        
        expect(savedToken).toBe(mockToken)
        expect(savedUser).toBe(JSON.stringify(mockUser))
      })

      it('should handle login failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Invalid credentials' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(login({ sso: 'invalid' }))
        
        const state = store.getState().auth
        expect(state.loading).toBe(false)
        expect(state.user).toBeNull()
        expect(state.token).toBeNull()
        expect(state.isAuthenticated).toBe(false)
        expect(state.error).toBeTruthy()
      })

      it('should handle network error', async () => {
        mockFetch.mockRejectedValueOnce(new Error('Network error'))

        const store = createTestStore()
        await store.dispatch(login({ sso: 'demo' }))
        
        const state = store.getState().auth
        expect(state.loading).toBe(false)
        expect(state.error).toBeTruthy()
        expect(state.isAuthenticated).toBe(false)
      })

      it('should set loading state during login', async () => {
        mockFetch.mockImplementationOnce(() => 
          new Promise(resolve => setTimeout(() => resolve({
            ok: true,
            json: () => ({ user: createMockUser(), token: 'token' }),
          } as unknown as Response), 100))
        )

        const store = createTestStore()
        const promise = store.dispatch(login({ sso: 'demo' }))
        
        // Check loading state immediately
        expect(store.getState().auth.loading).toBe(true)
        
        await promise
        expect(store.getState().auth.loading).toBe(false)
      })
    })

    describe('fetchCurrentUser', () => {
      it('should fetch current user successfully', async () => {
        const mockUser = createMockUser()
        localStorage.setItem('auth_token', 'test-token')

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => mockUser,
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchCurrentUser())
        
        const state = store.getState().auth
        expect(state.user).toEqual(mockUser)
        expect(state.error).toBeNull()
      })

      it('should handle fetch failure', async () => {
        localStorage.setItem('auth_token', 'test-token')
        
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Unauthorized' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchCurrentUser())
        
        const state = store.getState().auth
        expect(state.error).toBeTruthy()
      })
    })

    describe('logout', () => {
      it('should clear state and localStorage', async () => {
        const mockUser = createMockUser()
        localStorage.setItem('auth_token', 'test-token')
        localStorage.setItem('user', JSON.stringify(mockUser))

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({}),
        } as unknown as Response)

        const store = createTestStore({
          auth: {
            user: mockUser,
            token: 'test-token',
            isAuthenticated: true,
            loading: false,
            error: null,
          },
        })
        
        await store.dispatch(logout())
        
        const state = store.getState().auth
        expect(state.user).toBeNull()
        expect(state.token).toBeNull()
        expect(state.isAuthenticated).toBe(false)
        expect(localStorage.getItem('auth_token')).toBeNull()
        expect(localStorage.getItem('user')).toBeNull()
      })

      it('should handle logout even if API call fails', async () => {
        mockFetch.mockRejectedValueOnce(new Error('Network error'))

        const store = createTestStore({
          auth: {
            user: createMockUser(),
            token: 'test-token',
            isAuthenticated: true,
            loading: false,
            error: null,
          },
        })
        
        await store.dispatch(logout())
        
        const state = store.getState().auth
        expect(state.user).toBeNull()
        expect(state.isAuthenticated).toBe(false)
      })
    })
  })

  describe('selectors', () => {
    it('selectAuth should return auth state', () => {
      const store = createTestStore({ auth: initialState })
      expect(selectAuth(store.getState())).toEqual(initialState)
    })

    it('selectCurrentUser should return current user', () => {
      const user = createMockUser()
      const store = createTestStore({ auth: { ...initialState, user } })
      expect(selectCurrentUser(store.getState())).toEqual(user)
    })

    it('selectIsAuthenticated should return authentication status', () => {
      const store = createTestStore({ auth: { ...initialState, isAuthenticated: true } })
      expect(selectIsAuthenticated(store.getState())).toBe(true)
    })

    it('selectAuthLoading should return loading state', () => {
      const store = createTestStore({ auth: { ...initialState, loading: true } })
      expect(selectAuthLoading(store.getState())).toBe(true)
    })

    it('selectAuthError should return error', () => {
      const store = createTestStore({ auth: { ...initialState, error: 'Test error' } })
      expect(selectAuthError(store.getState())).toBe('Test error')
    })

    it('selectUserRole should return user role', () => {
      const user = createMockUser({ role: 'admin' })
      const store = createTestStore({ auth: { ...initialState, user } })
      expect(selectUserRole(store.getState())).toBe('admin')
    })

    it('selectUserRole should return undefined for no user', () => {
      const store = createTestStore({ auth: initialState })
      expect(selectUserRole(store.getState())).toBeUndefined()
    })

    it('selectUserAccessLevel should return access level', () => {
      const user = createMockUser({ accessLevel: 'super' })
      const store = createTestStore({ auth: { ...initialState, user } })
      expect(selectUserAccessLevel(store.getState())).toBe('super')
    })

    it('selectIsAdmin should return true for super access level users', () => {
      const user = createMockUser({ accessLevel: 'super' })
      const store = createTestStore({ auth: { ...initialState, user } })
      expect(selectIsAdmin(store.getState())).toBe(true)
    })

    it('selectIsAdmin should return false for non-admin users', () => {
      const user = createMockUser({ role: 'reliability' })
      const store = createTestStore({ auth: { ...initialState, user } })
      expect(selectIsAdmin(store.getState())).toBe(false)
    })

    it('selectIsAdmin should return false when no user', () => {
      const store = createTestStore({ auth: initialState })
      expect(selectIsAdmin(store.getState())).toBe(false)
    })
  })
})
