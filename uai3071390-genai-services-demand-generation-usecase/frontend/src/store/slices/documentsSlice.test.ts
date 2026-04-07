/**
 * Documents Slice Tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import documentsReducer, {
  fetchERCases,
  fetchFSRReports,
  fetchOutageHistory,
  fetchUploadedDocuments,
  uploadDocument,
  fetchAllDocuments,
  clearError,
  clearDocuments,
  clearAllDocuments,
  selectDocuments,
  selectERCases,
  selectFSRReports,
  selectOutageHistory,
  selectUploadedDocs,
  selectDocumentsLoading,
  selectDocumentsError,
} from './documentsSlice'
import { createTestStore, createMockERCase, createMockFSRReport, createMockOutageEvent, createMockUploadedDocument } from '@/test/utils'
import type { DocumentState, PaginatedList } from '../types'

// Mock fetch
const mockFetch = vi.fn()

const createPaginatedList = <T>(items: T[], page = 1, hasMore = false): PaginatedList<T> => ({
  items,
  page,
  hasMore,
})

describe('documentsSlice', () => {
  let initialState: DocumentState

  beforeEach(() => {
    initialState = {
      erCases: {},
      fsrReports: {},
      outageHistory: {},
      uploadedDocs: {},
      dataReadiness: {},
      loading: false,
      error: null,
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
      expect(documentsReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle clearError', () => {
      const stateWithError = { ...initialState, error: 'Test error' }
      const state = documentsReducer(stateWithError, clearError())
      expect(state.error).toBeNull()
    })

    it('should handle clearDocuments for specific ESN', () => {
      const stateWithDocs = {
        ...initialState,
        erCases: { 'GT12345': createPaginatedList([createMockERCase()]) },
        fsrReports: { 'GT12345': createPaginatedList([createMockFSRReport()]) },
        outageHistory: { 'GT12345': createPaginatedList([createMockOutageEvent()]) },
        uploadedDocs: { 'GT12345': [] },
      }
      const state = documentsReducer(stateWithDocs, clearDocuments('GT12345'))
      
      expect(state.erCases['GT12345']).toBeUndefined()
      expect(state.fsrReports['GT12345']).toBeUndefined()
      expect(state.outageHistory['GT12345']).toBeUndefined()
      expect(state.uploadedDocs['GT12345']).toBeUndefined()
    })

    it('should handle clearAllDocuments', () => {
      const stateWithDocs = {
        ...initialState,
        erCases: { 'GT12345': createPaginatedList([createMockERCase()]) },
        fsrReports: { 'GT67890': createPaginatedList([createMockFSRReport()]) },
        outageHistory: { 'GT11111': createPaginatedList([createMockOutageEvent()]) },
        uploadedDocs: { 'GT22222': [] },
      }
      const state = documentsReducer(stateWithDocs, clearAllDocuments())
      
      expect(state.erCases).toEqual({})
      expect(state.fsrReports).toEqual({})
      expect(state.outageHistory).toEqual({})
      expect(state.uploadedDocs).toEqual({})
    })
  })

  describe('async thunks', () => {
    describe('fetchERCases', () => {
      it('should fetch ER cases successfully', async () => {
        const mockCases = [createMockERCase(), createMockERCase({ erNumber: 'ER-2025-002' })]

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ erCases: mockCases }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchERCases({ esn: 'GT12345' }))
        
        const state = store.getState().documents
        expect(state.loading).toBe(false)
        expect(state.erCases['GT12345']).toEqual(createPaginatedList(mockCases))
        expect(state.error).toBeNull()
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed to fetch' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchERCases({ esn: 'GT12345' }))
        
        const state = store.getState().documents
        expect(state.error).toBeTruthy()
      })
    })

    describe('fetchFSRReports', () => {
      it('should fetch FSR reports successfully', async () => {
        const mockReports = [createMockFSRReport()]

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ fsrReports: mockReports }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchFSRReports({ esn: 'GT12345' }))
        
        const state = store.getState().documents
        expect(state.fsrReports['GT12345']).toEqual(createPaginatedList(mockReports))
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchFSRReports({ esn: 'GT12345' }))
        
        expect(store.getState().documents.error).toBeTruthy()
      })
    })

    describe('fetchOutageHistory', () => {
      it('should fetch outage history successfully', async () => {
        const mockHistory = [createMockOutageEvent()]

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ outageHistory: mockHistory }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchOutageHistory({ esn: 'GT12345' }))
        
        const state = store.getState().documents
        expect(state.outageHistory['GT12345']).toEqual(createPaginatedList(mockHistory))
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchOutageHistory({ esn: 'GT12345' }))
        
        expect(store.getState().documents.error).toBeTruthy()
      })
    })

    describe('fetchUploadedDocuments', () => {
      it('should fetch uploaded documents successfully', async () => {
        const mockDocs = [createMockUploadedDocument()]

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ documents: mockDocs }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchUploadedDocuments('GT12345'))
        
        const state = store.getState().documents
        expect(state.uploadedDocs['GT12345']).toEqual(mockDocs)
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchUploadedDocuments('GT12345'))
        
        expect(store.getState().documents.error).toBeTruthy()
      })
    })

    describe('uploadDocument', () => {
      it('should upload document successfully', async () => {
        const mockDoc = createMockUploadedDocument({ id: '1', name: 'test.pdf', uploadedAt: '2026-01-01' })
        const mockFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ document: mockDoc }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(uploadDocument({ 
          esn: 'GT12345', 
          file: mockFile, 
          category: 'maintenance' 
        }))
        
        const state = store.getState().documents
        expect(state.uploadedDocs['GT12345']).toEqual([mockDoc])
      })

      it('should append to existing documents', async () => {
        const existingDoc = createMockUploadedDocument({ id: '1', name: 'existing.pdf', uploadedAt: '2026-01-01' })
        const newDoc = createMockUploadedDocument({ id: '2', name: 'new.pdf', uploadedAt: '2026-01-02' })
        const mockFile = new File(['content'], 'new.pdf', { type: 'application/pdf' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ document: newDoc }),
        } as unknown as Response)

        const store = createTestStore({
          documents: {
            ...initialState,
            uploadedDocs: { 'GT12345': [existingDoc] },
          },
        })

        await store.dispatch(uploadDocument({ 
          esn: 'GT12345', 
          file: mockFile, 
          category: 'maintenance' 
        }))
        
        const state = store.getState().documents
        expect(state.uploadedDocs['GT12345']).toHaveLength(2)
        expect(state.uploadedDocs['GT12345']).toContainEqual(newDoc)
      })

      it('should handle upload failure', async () => {
        const mockFile = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Upload failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(uploadDocument({ 
          esn: 'GT12345', 
          file: mockFile, 
          category: 'maintenance' 
        }))
        
        expect(store.getState().documents.error).toBeTruthy()
      })
    })

    describe('fetchAllDocuments', () => {
      it('should fetch all document types successfully', async () => {
        const mockCases = [createMockERCase()]
        const mockReports = [createMockFSRReport()]
        const mockHistory = [createMockOutageEvent()]
        const mockDocs = [createMockUploadedDocument()]

        mockFetch
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ erCases: mockCases }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ fsrReports: mockReports }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ outageHistory: mockHistory }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ documents: mockDocs }),
          } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchAllDocuments('GT12345'))
        
        const state = store.getState().documents
        expect(state.erCases['GT12345']).toEqual(createPaginatedList(mockCases))
        expect(state.fsrReports['GT12345']).toEqual(createPaginatedList(mockReports))
        expect(state.outageHistory['GT12345']).toEqual(createPaginatedList(mockHistory))
        expect(state.uploadedDocs['GT12345']).toEqual(mockDocs)
      })

      it('should handle partial failures gracefully', async () => {
        mockFetch
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ erCases: [] }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: false,
            json: () => ({ error: 'Failed' }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ outageHistory: [] }),
          } as unknown as Response)
          .mockResolvedValueOnce({
            ok: true,
            json: () => ({ documents: [] }),
          } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchAllDocuments('GT12345'))
        
        // Should still get data from successful requests
        expect(store.getState().documents.erCases['GT12345']).toEqual(createPaginatedList([]))
      })
    })
  })

  describe('selectors', () => {
    it('selectDocuments should return documents state', () => {
      const store = createTestStore({ documents: initialState })
      expect(selectDocuments(store.getState())).toEqual(initialState)
    })

    it('selectERCases should return ER cases for ESN', () => {
      const cases = [createMockERCase()]
      const store = createTestStore({
        documents: { ...initialState, erCases: { 'GT12345': createPaginatedList(cases) } },
      })
      expect(selectERCases('GT12345')(store.getState())).toEqual(cases)
    })

    it('selectERCases should return empty array when no cases', () => {
      const store = createTestStore({ documents: initialState })
      expect(selectERCases('GT12345')(store.getState())).toEqual([])
    })

    it('selectFSRReports should return FSR reports for ESN', () => {
      const reports = [createMockFSRReport()]
      const store = createTestStore({
        documents: { ...initialState, fsrReports: { 'GT12345': createPaginatedList(reports) } },
      })
      expect(selectFSRReports('GT12345')(store.getState())).toEqual(reports)
    })

    it('selectOutageHistory should return outage history for ESN', () => {
      const history = [createMockOutageEvent()]
      const store = createTestStore({
        documents: { ...initialState, outageHistory: { 'GT12345': createPaginatedList(history) } },
      })
      expect(selectOutageHistory('GT12345')(store.getState())).toEqual(history)
    })

    it('selectUploadedDocs should return uploaded documents for ESN', () => {
      const docs = [createMockUploadedDocument({ id: '1', name: 'test.pdf', uploadedAt: '2026-01-01' })]
      const store = createTestStore({
        documents: { ...initialState, uploadedDocs: { 'GT12345': docs } },
      })
      expect(selectUploadedDocs('GT12345')(store.getState())).toEqual(docs)
    })

    it('selectDocumentsLoading should return loading state', () => {
      const store = createTestStore({ documents: { ...initialState, loading: true } })
      expect(selectDocumentsLoading(store.getState())).toBe(true)
    })

    it('selectDocumentsError should return error', () => {
      const store = createTestStore({ documents: { ...initialState, error: 'Test error' } })
      expect(selectDocumentsError(store.getState())).toBe('Test error')
    })
  })
})
