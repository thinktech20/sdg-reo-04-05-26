/**
 * Equipment Slice Tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import equipmentReducer, {
  fetchTrains,
  searchEquipment,
  setSelectedEquipment,
  clearSelectedEquipment,
  setTypeFilter,
  setSearchQuery,
  clearFilters,
  clearError,
  clearSearchResults,
  selectEquipment,
  selectTrains,
  selectSelectedEquipment,
  selectSearchResults,
  selectEquipmentLoading,
  selectEquipmentError,
  selectEquipmentFilters,
  selectFilteredTrains,
} from './equipmentSlice'
import { createTestStore, createMockEquipment, createMockTrain } from '@/test/utils'
import type { EquipmentState } from '../types'

// Mock fetch globally
// Mock fetch
const mockFetch = vi.fn()

describe('equipmentSlice', () => {
  let initialState: EquipmentState

  beforeEach(() => {
    initialState = {
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
    mockFetch.mockClear()
    vi.stubGlobal('fetch', mockFetch)
  })

  afterEach(() => {
    mockFetch.mockReset()
    vi.unstubAllGlobals()
  })

  describe('reducers', () => {
    it('should return initial state', () => {
      expect(equipmentReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle setSelectedEquipment', () => {
      const equipment = createMockEquipment()
      const state = equipmentReducer(initialState, setSelectedEquipment(equipment))
      expect(state.selectedEquipment).toEqual(equipment)
    })

    it('should handle setSelectedEquipment with null', () => {
      const stateWithEquipment = { ...initialState, selectedEquipment: createMockEquipment() }
      const state = equipmentReducer(stateWithEquipment, setSelectedEquipment(null))
      expect(state.selectedEquipment).toBeNull()
    })

    it('should handle clearSelectedEquipment', () => {
      const stateWithEquipment = { ...initialState, selectedEquipment: createMockEquipment() }
      const state = equipmentReducer(stateWithEquipment, clearSelectedEquipment())
      expect(state.selectedEquipment).toBeNull()
    })

    it('should handle setTypeFilter', () => {
      const state = equipmentReducer(initialState, setTypeFilter('Gas Turbine'))
      expect(state.filters.type).toBe('Gas Turbine')
    })

    it('should handle setSearchQuery', () => {
      const state = equipmentReducer(initialState, setSearchQuery('GT12345'))
      expect(state.filters.search).toBe('GT12345')
    })

    it('should handle clearFilters', () => {
      const stateWithFilters = {
        ...initialState,
        filters: { type: 'Gas Turbine', search: 'GT12345' },
      }
      const state = equipmentReducer(stateWithFilters, clearFilters())
      expect(state.filters).toEqual({ type: 'all', search: '' })
    })

    it('should handle clearError', () => {
      const stateWithError = { ...initialState, error: 'Test error' }
      const state = equipmentReducer(stateWithError, clearError())
      expect(state.error).toBeNull()
    })

    it('should handle clearSearchResults', () => {
      const stateWithResults = { ...initialState, searchResults: [createMockEquipment()] }
      const state = equipmentReducer(stateWithResults, clearSearchResults())
      expect(state.searchResults).toEqual([])
    })
  })

  describe('async thunks', () => {
    describe('fetchTrains', () => {
      it('should fetch trains successfully', async () => {
        const mockTrains = [createMockTrain(), createMockTrain({ id: '2', trainName: 'Unit 2' })]

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ units: mockTrains }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchTrains({}))
        
        const state = store.getState().equipment
        expect(state.loading).toBe(false)
        expect(state.trains).toEqual(mockTrains)
        expect(state.error).toBeNull()
      })

      it('should apply type filter in request', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ trains: [] }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchTrains({ filterType: 'Gas Turbine' }))
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringMatching(/filter_type=Gas(\+|%20)Turbine/),
          expect.any(Object)
        )
      })

      it('should apply search filter in request', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ trains: [] }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchTrains({ search: 'GT12345' }))
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringMatching(/search=GT12345/),
          expect.any(Object)
        )
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed to fetch' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchTrains({}))
        
        const state = store.getState().equipment
        expect(state.loading).toBe(false)
        expect(state.error).toBeTruthy()
      })

      it('should handle network error', async () => {
        mockFetch.mockRejectedValueOnce(new Error('Network error'))

        const store = createTestStore()
        await store.dispatch(fetchTrains({}))
        
        const state = store.getState().equipment
        expect(state.error).toBe('Failed to fetch trains')
      })

      it('should set loading state during fetch', async () => {
        mockFetch.mockImplementationOnce(() => 
          new Promise(resolve => setTimeout(() => resolve({
            ok: true,
            json: () => ({ trains: [] }),
          } as unknown as Response), 100))
        )

        const store = createTestStore()
        const promise = store.dispatch(fetchTrains({}))
        
        expect(store.getState().equipment.loading).toBe(true)
        
        await promise
        expect(store.getState().equipment.loading).toBe(false)
      })
    })

    describe('searchEquipment', () => {
      it('should search equipment successfully', async () => {
        const mockEquipment = createMockEquipment({ serialNumber: 'GT12345' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ equipment: mockEquipment }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(searchEquipment('GT12345'))
        
        const state = store.getState().equipment
        expect(state.loading).toBe(false)
        expect(state.selectedEquipment).toEqual(mockEquipment)
        expect(state.searchResults).toEqual([mockEquipment])
        expect(state.error).toBeNull()
      })

      it('should handle search failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Equipment not found' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(searchEquipment('INVALID'))
        
        const state = store.getState().equipment
        expect(state.loading).toBe(false)
        expect(state.selectedEquipment).toBeNull()
        expect(state.error).toBe('Equipment not found')
      })

      it('should encode ESN in URL', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ equipment: createMockEquipment() }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(searchEquipment('GT 12345'))
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringMatching(/esn=GT(%20|\+)12345/),
          expect.any(Object)
        )
      })
    })
  })

  describe('selectors', () => {
    it('selectEquipment should return equipment state', () => {
      const store = createTestStore({ equipment: initialState })
      expect(selectEquipment(store.getState())).toEqual(initialState)
    })

    it('selectTrains should return trains array', () => {
      const trains = [createMockTrain()]
      const store = createTestStore({ equipment: { ...initialState, trains } })
      expect(selectTrains(store.getState())).toEqual(trains)
    })

    it('selectSelectedEquipment should return selected equipment', () => {
      const equipment = createMockEquipment()
      const store = createTestStore({ equipment: { ...initialState, selectedEquipment: equipment } })
      expect(selectSelectedEquipment(store.getState())).toEqual(equipment)
    })

    it('selectSearchResults should return search results', () => {
      const results = [createMockEquipment()]
      const store = createTestStore({ equipment: { ...initialState, searchResults: results } })
      expect(selectSearchResults(store.getState())).toEqual(results)
    })

    it('selectEquipmentLoading should return loading state', () => {
      const store = createTestStore({ equipment: { ...initialState, loading: true } })
      expect(selectEquipmentLoading(store.getState())).toBe(true)
    })

    it('selectEquipmentError should return error', () => {
      const store = createTestStore({ equipment: { ...initialState, error: 'Test error' } })
      expect(selectEquipmentError(store.getState())).toBe('Test error')
    })

    it('selectEquipmentFilters should return filters', () => {
      const filters = { type: 'Gas Turbine', search: 'GT12345' }
      const store = createTestStore({ equipment: { ...initialState, filters } })
      expect(selectEquipmentFilters(store.getState())).toEqual(filters)
    })

    describe('selectFilteredTrains', () => {
      it('should return all trains when no filters applied', () => {
        const trains = [createMockTrain(), createMockTrain({ id: '2' })]
        const store = createTestStore({ equipment: { ...initialState, trains } })
        expect(selectFilteredTrains(store.getState())).toEqual(trains)
      })

      it('should filter trains by search query (train name)', () => {
        const trains = [
          createMockTrain({ trainName: 'Moss Landing Unit 1', site: 'California' }),
          createMockTrain({ id: '2', trainName: 'Alamitos Unit 2', site: 'Texas' }),
        ]
        const store = createTestStore({
          equipment: { ...initialState, trains, filters: { type: 'all', search: 'Moss' } },
        })
        const filtered = selectFilteredTrains(store.getState())
        expect(filtered).toHaveLength(1)
        expect(filtered[0]!.trainName).toBe('Moss Landing Unit 1')
      })

      it('should filter trains by search query (site)', () => {
        const trains = [
          createMockTrain({ site: 'California' }),
          createMockTrain({ id: '2', site: 'Texas' }),
        ]
        const store = createTestStore({
          equipment: { ...initialState, trains, filters: { type: 'all', search: 'California' } },
        })
        const filtered = selectFilteredTrains(store.getState())
        expect(filtered).toHaveLength(1)
        expect(filtered[0]!.site).toBe('California')
      })

      it('should filter trains by search query (equipment serial)', () => {
        const trains = [
          createMockTrain({ equipment: [createMockEquipment({ serialNumber: 'GT12345' })] }),
          createMockTrain({ id: '2', equipment: [createMockEquipment({ serialNumber: 'GT67890' })] }),
        ]
        const store = createTestStore({
          equipment: { ...initialState, trains, filters: { type: 'all', search: 'GT123' } },
        })
        const filtered = selectFilteredTrains(store.getState())
        expect(filtered).toHaveLength(1)
        expect(filtered[0]!.equipment[0]!.serialNumber).toBe('GT12345')
      })

      it('should be case-insensitive', () => {
        const trains = [createMockTrain({ trainName: 'Moss Landing' })]
        const store = createTestStore({
          equipment: { ...initialState, trains, filters: { type: 'all', search: 'moss' } },
        })
        expect(selectFilteredTrains(store.getState())).toHaveLength(1)
      })
    })
  })
})
