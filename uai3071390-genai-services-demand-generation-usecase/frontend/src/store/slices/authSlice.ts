/**
 * Auth Slice
 * Manages authentication state, login, logout, and user session
 * Migrated from sdg-risk-analyser-archive
 */

import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type { AuthState, User, LoginRequest, LoginResponse, ApiError } from '../types'
import { API_BASE } from '../api'

// ============================================================================
// ASYNC THUNKS
// ============================================================================

/**
 * Login user with SSO
 */
export const login = createAsyncThunk<LoginResponse, LoginRequest, { rejectValue: ApiError }>(
  'auth/login',
  async (credentials, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as LoginResponse
      
      // Store token in localStorage
      localStorage.setItem('auth_token', data.token)
      localStorage.setItem('user', JSON.stringify(data.user))
      
      return data
    } catch {
      return rejectWithValue({ error: 'Network error occurred' })
    }
  },
)

/**
 * Fetch current user profile
 */
export const fetchCurrentUser = createAsyncThunk<User, void, { rejectValue: ApiError }>(
  'auth/fetchCurrentUser',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token')
      if (!token) {
        return rejectWithValue({ error: 'No token found' })
      }

      const response = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      return (await response.json()) as User
    } catch {
      return rejectWithValue({ error: 'Network error occurred' })
    }
  },
)

/**
 * Logout user
 */
export const logout = createAsyncThunk<void, void, { rejectValue: ApiError }>(
  'auth/logout',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token')
      
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        })
      }

      // Clear localStorage regardless of API response
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
    } catch {
      // Even if API fails, clear local storage
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
      return rejectWithValue({ error: 'Logout failed' })
    }
  },
)

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
  loading: false,
  error: null,
}

// ============================================================================
// SLICE
// ============================================================================

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null
    },
    
    restoreSession: (state) => {
      const token = localStorage.getItem('auth_token')
      const userStr = localStorage.getItem('user')
      
      if (token && userStr) {
        try {
          state.token = token
          state.user = JSON.parse(userStr) as User
          state.isAuthenticated = true
        } catch {
          // Invalid stored data, clear it
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user')
          state.token = null
          state.user = null
          state.isAuthenticated = false
        }
      }
    },
  },
  extraReducers: (builder) => {
    // Login
    builder
      .addCase(login.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(login.fulfilled, (state, action: PayloadAction<LoginResponse>) => {
        state.loading = false
        state.user = action.payload.user
        state.token = action.payload.token
        state.isAuthenticated = true
        state.error = null
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Login failed'
        state.isAuthenticated = false
      })

    // Fetch current user
    builder
      .addCase(fetchCurrentUser.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action: PayloadAction<User>) => {
        state.loading = false
        state.user = action.payload
        state.isAuthenticated = true
        state.error = null
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch user'
        state.isAuthenticated = false
        state.user = null
        state.token = null
        localStorage.removeItem('auth_token')
        localStorage.removeItem('user')
      })

    // Logout
    builder
      .addCase(logout.pending, (state) => {
        state.loading = true
      })
      .addCase(logout.fulfilled, (state) => {
        state.loading = false
        state.user = null
        state.token = null
        state.isAuthenticated = false
        state.error = null
      })
      .addCase(logout.rejected, (state) => {
        state.loading = false
        state.user = null
        state.token = null
        state.isAuthenticated = false
        state.error = null
      })
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const { clearError, restoreSession } = authSlice.actions
export default authSlice.reducer

// Selectors
export const selectAuth = (state: { auth: AuthState }) => state.auth
export const selectCurrentUser = (state: { auth: AuthState }) => state.auth.user
export const selectIsAuthenticated = (state: { auth: AuthState }) => state.auth.isAuthenticated
export const selectAuthLoading = (state: { auth: AuthState }) => state.auth.loading
export const selectAuthError = (state: { auth: AuthState }) => state.auth.error
export const selectUserRole = (state: { auth: AuthState }) => state.auth.user?.role
export const selectUserAccessLevel = (state: { auth: AuthState }) => state.auth.user?.accessLevel
export const selectIsAdmin = (state: { auth: AuthState }) => 
  state.auth.user?.accessLevel === 'super'
