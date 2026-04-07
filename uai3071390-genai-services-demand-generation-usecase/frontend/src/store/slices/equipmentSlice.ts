/**
 * Equipment Slice
 * Manages trains, equipment, and search functionality
 */

import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type { EquipmentState, Train, Equipment, ApiError } from '../types'
import { API_BASE } from '../api'

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const getAuthHeader = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

// ============================================================================
// ASYNC THUNKS
// ============================================================================

/**
 * Fetch all trains with optional filtering
 */
export const fetchTrains = createAsyncThunk<
  Train[],
  { filterType?: string; search?: string },
  { rejectValue: ApiError }
>(
  'equipment/fetchTrains',
  async ({ filterType = 'all', search = '' }, { rejectWithValue, signal }) => {
    try {
      const params = new URLSearchParams()
      if (filterType !== 'all') params.append('filter_type', filterType)
      if (search) params.append('search', search)

      const response = await fetch(`${API_BASE}/units?${params.toString()}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { units: Train[] }
      return data.units
    } catch {
      return rejectWithValue({ error: 'Failed to fetch trains' })
    }
  },
)

/**
 * Search for equipment by ESN
 */
export const searchEquipment = createAsyncThunk<
  Equipment,
  string,
  { rejectValue: ApiError }
>(
  'equipment/searchEquipment',
  async (esn, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(`${API_BASE}/equipment/search?esn=${encodeURIComponent(esn)}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { equipment: Equipment }
      return data.equipment
    } catch {
      return rejectWithValue({ error: 'Failed to search equipment' })
    }
  },
)

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: EquipmentState = {
  trains: [],
  selectedEquipment: null,
  searchResults: [],
  loading: false,
  trainsLoading: false,
  error: null,
  filters: {
    type: 'all',
    search: '',
  },
}

// ============================================================================
// SLICE
// ============================================================================

const equipmentSlice = createSlice({
  name: 'equipment',
  initialState,
  reducers: {
    /**
     * Set selected equipment
     */
    setSelectedEquipment: (state, action: PayloadAction<Equipment | null>) => {
      state.selectedEquipment = action.payload
    },
    
    /**
     * Clear selected equipment
     */
    clearSelectedEquipment: (state) => {
      state.selectedEquipment = null
    },
    
    /**
     * Set equipment type filter
     */
    setTypeFilter: (state, action: PayloadAction<string>) => {
      state.filters.type = action.payload
    },
    
    /**
     * Set search query
     */
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.filters.search = action.payload
    },
    
    /**
     * Clear filters
     */
    clearFilters: (state) => {
      state.filters = {
        type: 'all',
        search: '',
      }
    },
    
    /**
     * Clear error
     */
    clearError: (state) => {
      state.error = null
    },
    
    /**
     * Clear search results
     */
    clearSearchResults: (state) => {
      state.searchResults = []
    },
  },
  extraReducers: (builder) => {
    // Fetch trains
    builder
      .addCase(fetchTrains.pending, (state) => {
        state.loading = true
        state.trainsLoading = true
        state.error = null
      })
      .addCase(fetchTrains.fulfilled, (state, action: PayloadAction<Train[]>) => {
        state.loading = false
        state.trainsLoading = false
        state.trains = action.payload
        state.error = null
      })
      .addCase(fetchTrains.rejected, (state, action) => {
        state.loading = false
        state.trainsLoading = false
        state.error = action.payload?.error || 'Failed to fetch trains'
      })

    // Search equipment
    builder
      .addCase(searchEquipment.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(searchEquipment.fulfilled, (state, action: PayloadAction<Equipment>) => {
        state.loading = false
        state.selectedEquipment = action.payload
        state.searchResults = [action.payload]
        state.error = null
      })
      .addCase(searchEquipment.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Equipment not found'
        state.selectedEquipment = null
      })
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const {
  setSelectedEquipment,
  clearSelectedEquipment,
  setTypeFilter,
  setSearchQuery,
  clearFilters,
  clearError,
  clearSearchResults,
} = equipmentSlice.actions

export default equipmentSlice.reducer

// Selectors
export const selectEquipment = (state: { equipment: EquipmentState }) => state.equipment
export const selectTrains = (state: { equipment: EquipmentState }) => state.equipment.trains
export const selectSelectedEquipment = (state: { equipment: EquipmentState }) => 
  state.equipment.selectedEquipment
export const selectSearchResults = (state: { equipment: EquipmentState }) => 
  state.equipment.searchResults
export const selectEquipmentLoading = (state: { equipment: EquipmentState }) => 
  state.equipment.loading
export const selectTrainsLoading = (state: { equipment: EquipmentState }) =>
  state.equipment.trainsLoading
export const selectEquipmentError = (state: { equipment: EquipmentState }) => 
  state.equipment.error
export const selectEquipmentFilters = (state: { equipment: EquipmentState }) => 
  state.equipment.filters

// Derived selectors
export const selectFilteredTrains = (state: { equipment: EquipmentState }) => {
  const { trains, filters } = state.equipment
  
  if (filters.type === 'all' && !filters.search) {
    return trains
  }
  
  return trains.filter(train => {
    // Type filter is handled by API, but keeping this for client-side filtering if needed
    const matchesType = filters.type === 'all' || 
      train.equipment.some(eq => eq.equipmentType === filters.type)
    
    const matchesSearch = !filters.search ||
      train.trainName.toLowerCase().includes(filters.search.toLowerCase()) ||
      train.site.toLowerCase().includes(filters.search.toLowerCase()) ||
      train.equipment.some(eq => 
        eq.serialNumber.toLowerCase().includes(filters.search.toLowerCase()),
      )
    
    return matchesType && matchesSearch
  })
}
