/**
 * Documents Slice
 * Manages ER cases, FSR reports, outage history, and uploaded documents
 */

import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import type {
  DocumentState,
  ERCase,
  FSRReport,
  OutageEvent,
  UploadedDocument,
  ApiError,
  DataReadiness
} from '../types'
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

const DEFAULT_PAGE_SIZE = 20

/**
 * Fetch ER cases for equipment
 */
export const fetchERCases = createAsyncThunk<
  { esn: string; erCases: ERCase[]; page: number; pageSize: number },
  { esn: string; startDate?: string; endDate?: string; page?: number; pageSize?: number },
  { rejectValue: ApiError }
>(
  'documents/fetchERCases',
  async ({ esn, startDate, endDate, page = 1, pageSize = DEFAULT_PAGE_SIZE }, { rejectWithValue, signal }) => {
    try {
      const params = new URLSearchParams()
      if (startDate) params.append('startDate', startDate)
      if (endDate) params.append('endDate', endDate)
      params.append('page', String(page))
      params.append('pageSize', String(pageSize))
      const qs = `?${params.toString()}`
      const response = await fetch(`${API_BASE}/equipment/${esn}/er-cases${qs}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { erCases: ERCase[] }
      return { esn, erCases: data.erCases, page, pageSize }
    } catch {
      return rejectWithValue({ error: 'Failed to fetch ER cases' })
    }
  },
)

/**
 * Fetch FSR reports for equipment
 */
export const fetchFSRReports = createAsyncThunk<
  { esn: string; fsrReports: FSRReport[]; page: number; pageSize: number },
  { esn: string; startDate?: string; endDate?: string; page?: number; pageSize?: number },
  { rejectValue: ApiError }
>(
  'documents/fetchFSRReports',
  async ({ esn, startDate, endDate, page = 1, pageSize = DEFAULT_PAGE_SIZE }, { rejectWithValue, signal }) => {
    try {
      const params = new URLSearchParams()
      if (startDate) params.append('startDate', startDate)
      if (endDate) params.append('endDate', endDate)
      params.append('page', String(page))
      params.append('pageSize', String(pageSize))
      const qs = `?${params.toString()}`
      const response = await fetch(`${API_BASE}/equipment/${esn}/fsr-reports${qs}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { fsrReports: FSRReport[] }
      return { esn, fsrReports: data.fsrReports, page, pageSize }
    } catch {
      return rejectWithValue({ error: 'Failed to fetch FSR reports' })
    }
  },
)

/**
 * Fetch outage history for equipment
 */
export const fetchOutageHistory = createAsyncThunk<
  { esn: string; outageHistory: OutageEvent[]; page: number; pageSize: number },
  { esn: string; startDate?: string; endDate?: string; page?: number; pageSize?: number },
  { rejectValue: ApiError }
>(
  'documents/fetchOutageHistory',
  async ({ esn, startDate, endDate, page = 1, pageSize = DEFAULT_PAGE_SIZE }, { rejectWithValue, signal }) => {
    try {
      const params = new URLSearchParams()
      if (startDate) params.append('startDate', startDate)
      if (endDate) params.append('endDate', endDate)
      params.append('page', String(page))
      params.append('pageSize', String(pageSize))
      const qs = `?${params.toString()}`
      const response = await fetch(`${API_BASE}/equipment/${esn}/outage-history${qs}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { outageHistory: OutageEvent[] }
      return { esn, outageHistory: data.outageHistory, page, pageSize }
    } catch {
      return rejectWithValue({ error: 'Failed to fetch outage history' })
    }
  },
)

/**
 * Fetch uploaded documents for equipment
 */
export const fetchUploadedDocuments = createAsyncThunk<
  { esn: string; documents: UploadedDocument[] },
  string,
  { rejectValue: ApiError }
>(
  'documents/fetchUploadedDocuments',
  async (esn, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(`${API_BASE}/equipment/${esn}/documents`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { documents: UploadedDocument[] }
      return { esn, documents: data.documents }
    } catch {
      return rejectWithValue({ error: 'Failed to fetch uploaded documents' })
    }
  },
)

/**
 * Upload document
 */
export const uploadDocument = createAsyncThunk<
  { esn: string; document: UploadedDocument },
  { esn: string; file: File; category: string },
  { rejectValue: ApiError }
>(
  'documents/uploadDocument',
  async ({ esn, file, category }, { rejectWithValue }) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('category', category)

      const response = await fetch(`${API_BASE}/equipment/${esn}/documents`, {
        method: 'POST',
        headers: getAuthHeader(),
        body: formData,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as { document: UploadedDocument }
      return { esn, document: data.document }
    } catch {
      return rejectWithValue({ error: 'Failed to upload document' })
    }
  },
)

/**
 * Fetch data readiness summary for equipment (ER + PRISM + IBAT in one call)
 */
export const fetchDataReadiness = createAsyncThunk<
  { esn: string; dataReadiness: DataReadiness },
  { esn: string; startDate?: string; endDate?: string },
  { rejectValue: ApiError }
>(
  'documents/fetchDataReadiness',
  async ({ esn, startDate, endDate }, { rejectWithValue, signal }) => {
    try {
      const params = new URLSearchParams()
      if (startDate) params.append('from_date', startDate)
      if (endDate) params.append('to_date', endDate)
      const qs = params.toString() ? `?${params.toString()}` : ''
      const response = await fetch(`${API_BASE}/equipment/${esn}/data-readiness${qs}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as DataReadiness
      return { esn, dataReadiness: data }
    } catch {
      return rejectWithValue({ error: 'Failed to fetch data readiness' })
    }
  },
)

/**
 * Fetch all documents for equipment (convenience method)
 */
export const fetchAllDocuments = createAsyncThunk<
  void,
  string,
  { rejectValue: ApiError }
>(
  'documents/fetchAllDocuments',
  async (esn, { dispatch, rejectWithValue }) => {
    try {
      await Promise.all([
        dispatch(fetchERCases({ esn })),
        dispatch(fetchFSRReports({ esn })),
        dispatch(fetchOutageHistory({ esn })),
        dispatch(fetchUploadedDocuments(esn)),
      ])
    } catch {
      return rejectWithValue({ error: 'Failed to fetch documents' })
    }
  },
)

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: DocumentState = {
  erCases: {},
  fsrReports: {},
  outageHistory: {},
  uploadedDocs: {},
  dataReadiness: {},
  loading: false,
  error: null,
}

// ============================================================================
// SLICE
// ============================================================================

const documentsSlice = createSlice({
  name: 'documents',
  initialState,
  reducers: {
    /**
     * Clear error
     */
    clearError: (state) => {
      state.error = null
    },
    
    /**
     * Clear documents for specific ESN
     */
    clearDocuments: (state, action: PayloadAction<string>) => {
      const esn = action.payload
      delete state.erCases[esn]
      delete state.fsrReports[esn]
      delete state.outageHistory[esn]
      delete state.uploadedDocs[esn]
      delete state.dataReadiness[esn]
    },
    
    /**
     * Clear all documents
     */
    clearAllDocuments: (state) => {
      state.erCases = {}
      state.fsrReports = {}
      state.outageHistory = {}
      state.uploadedDocs = {}
      state.dataReadiness = {}
    },
  },
  extraReducers: (builder) => {
    // Fetch data readiness
    builder
      .addCase(fetchDataReadiness.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchDataReadiness.fulfilled, (state, action) => {
        state.loading = false
        const { esn, dataReadiness } = action.payload
        state.dataReadiness[esn] = dataReadiness
        state.error = null
      })
      .addCase(fetchDataReadiness.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch data readiness'
      })

    // Fetch ER cases
    builder
      .addCase(fetchERCases.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchERCases.fulfilled, (state, action) => {
        state.loading = false
        const { esn, erCases, page, pageSize } = action.payload
        const existing = state.erCases[esn]
        if (page === 1 || !existing) {
          state.erCases[esn] = { items: erCases, page, hasMore: erCases.length >= pageSize }
        } else {
          existing.items = [...existing.items, ...erCases]
          existing.page = page
          existing.hasMore = erCases.length >= pageSize
        }
        state.error = null
      })
      .addCase(fetchERCases.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch ER cases'
      })

    // Fetch FSR reports
    builder
      .addCase(fetchFSRReports.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchFSRReports.fulfilled, (state, action) => {
        state.loading = false
        const { esn, fsrReports, page, pageSize } = action.payload
        const existing = state.fsrReports[esn]
        if (page === 1 || !existing) {
          state.fsrReports[esn] = { items: fsrReports, page, hasMore: fsrReports.length >= pageSize }
        } else {
          existing.items = [...existing.items, ...fsrReports]
          existing.page = page
          existing.hasMore = fsrReports.length >= pageSize
        }
        state.error = null
      })
      .addCase(fetchFSRReports.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch FSR reports'
      })

    // Fetch outage history
    builder
      .addCase(fetchOutageHistory.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchOutageHistory.fulfilled, (state, action) => {
        state.loading = false
        const { esn, outageHistory, page, pageSize } = action.payload
        const existing = state.outageHistory[esn]
        if (page === 1 || !existing) {
          state.outageHistory[esn] = { items: outageHistory, page, hasMore: outageHistory.length >= pageSize }
        } else {
          existing.items = [...existing.items, ...outageHistory]
          existing.page = page
          existing.hasMore = outageHistory.length >= pageSize
        }
        state.error = null
      })
      .addCase(fetchOutageHistory.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch outage history'
      })

    // Fetch uploaded documents
    builder
      .addCase(fetchUploadedDocuments.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchUploadedDocuments.fulfilled, (state, action) => {
        state.loading = false
        const { esn, documents } = action.payload
        state.uploadedDocs[esn] = documents
        state.error = null
      })
      .addCase(fetchUploadedDocuments.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch uploaded documents'
      })

    // Upload document
    builder
      .addCase(uploadDocument.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(uploadDocument.fulfilled, (state, action) => {
        state.loading = false
        const { esn, document } = action.payload
        if (!state.uploadedDocs[esn]) {
          state.uploadedDocs[esn] = []
        }
        state.uploadedDocs[esn].push(document)
        state.error = null
      })
      .addCase(uploadDocument.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to upload document'
      })

    // Fetch all documents
    builder
      .addCase(fetchAllDocuments.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchAllDocuments.fulfilled, (state) => {
        state.loading = false
        state.error = null
      })
      .addCase(fetchAllDocuments.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch documents'
      })
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const {
  clearError,
  clearDocuments,
  clearAllDocuments,
} = documentsSlice.actions

export default documentsSlice.reducer

const EMPTY_ER_CASES: ERCase[] = []
const EMPTY_FSR_REPORTS: FSRReport[] = []
const EMPTY_OUTAGE_HISTORY: OutageEvent[] = []
const EMPTY_UPLOADED_DOCS: UploadedDocument[] = []

// Selectors
export const selectDocuments = (state: { documents: DocumentState }) => state.documents
export const selectERCases = (esn: string) => 
  (state: { documents: DocumentState }) => state.documents.erCases[esn]?.items ?? EMPTY_ER_CASES
export const selectERCasesPagination = (esn: string) =>
  (state: { documents: DocumentState }) => state.documents.erCases[esn] ?? null
export const selectFSRReports = (esn: string) => 
  (state: { documents: DocumentState }) => state.documents.fsrReports[esn]?.items ?? EMPTY_FSR_REPORTS
export const selectFSRReportsPagination = (esn: string) =>
  (state: { documents: DocumentState }) => state.documents.fsrReports[esn] ?? null
export const selectOutageHistory = (esn: string) => 
  (state: { documents: DocumentState }) => state.documents.outageHistory[esn]?.items ?? EMPTY_OUTAGE_HISTORY
export const selectOutageHistoryPagination = (esn: string) =>
  (state: { documents: DocumentState }) => state.documents.outageHistory[esn] ?? null
export const selectUploadedDocs = (esn: string) => 
  (state: { documents: DocumentState }) => state.documents.uploadedDocs[esn] ?? EMPTY_UPLOADED_DOCS
export const selectDataReadiness = (esn: string) =>
  (state: { documents: DocumentState }) => state.documents.dataReadiness[esn] ?? null
export const selectDocumentsLoading = (state: { documents: DocumentState }) => 
  state.documents.loading
export const selectDocumentsError = (state: { documents: DocumentState }) => 
  state.documents.error
