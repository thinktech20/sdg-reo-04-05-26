/**
 * Assessments Slice
 * Manages risk assessments, analysis, and findings
 */

import { createSlice, createAsyncThunk, createSelector, type PayloadAction } from '@reduxjs/toolkit'
import type {
  AssessmentState,
  Assessment,
  ApiError,
  CreateAssessmentRequest,
  RunAnalysisRequest,
  NarrativeRequest,
  FeedbackRequest,
  JobStatus,
} from '../types'
import { API_BASE } from '../api'

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const getAuthHeader = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

const normalizeAssessment = (
  raw: Assessment & { esn?: string; status?: string; assessmentId?: string; esin_id?: string }
): Assessment => {
  const rawData = raw as Partial<Assessment> & {
    esn?: string
    status?: string
    assessmentId?: string
    esin_id?: string
  }

  return {
    reliabilityStatus: 'not-started',
    outageStatus: 'not-started',
    reliabilityFindings: [],
    outageFindings: [],
    reliabilityChat: [],
    outageChat: [],
    uploadedDocs: [],
    ...rawData,
    id: raw.id || raw.assessmentId || '',
    reviewPeriod: raw.reviewPeriod || raw.milestone,
    serialNumber: raw.serialNumber || raw.esin_id || raw.esn || '',
    createdAt: raw.createdAt,
    updatedAt: raw.updatedAt,
  }
}

// ============================================================================
// ASYNC THUNKS
// ============================================================================

/**
 * Create or get existing assessment
 */
export const createAssessment = createAsyncThunk<
  Assessment,
  CreateAssessmentRequest,
  { rejectValue: ApiError }
>(
  'assessments/createAssessment',
  async (request, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(request),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as {
        assessment: Assessment & { esn?: string; status?: string; assessmentId?: string; esin_id?: string }
      }
      return normalizeAssessment(data.assessment)
    } catch {
      return rejectWithValue({ error: 'Failed to create assessment' })
    }
  },
)

/**
 * Fetch assessment by ID
 */
export const fetchAssessment = createAsyncThunk<
  Assessment,
  string,
  { rejectValue: ApiError }
>(
  'assessments/fetchAssessment',
  async (id, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${id}`, {
        headers: getAuthHeader(),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as {
        assessment: Assessment & { esn?: string; status?: string; assessmentId?: string; esin_id?: string }
      }
      return normalizeAssessment(data.assessment)
    } catch {
      return rejectWithValue({ error: 'Failed to fetch assessment' })
    }
  },
)

/**
 * Run analysis — single entry point for both personas.
 * The orchestrator routes internally based on `persona`:
 *   RE (Reliability Engineer) → risk evaluation
 *   OE (Outage Engineer)      → event history
 * Returns 202 Accepted; caller should poll /status until COMPLETE.
 */
export const runAnalysis = createAsyncThunk<
  { id: string; workflowId: string; workflowStatus: string },
  { id: string; request: RunAnalysisRequest },
  { rejectValue: ApiError }
>(
  'assessments/runAnalysis',
  async ({ id, request }, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${id}/analyze/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(request),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      // Data-service returns 202 — poll /status for result
      // workflowId comes from the request if supplied (e.g. RE_NARRATIVE for regeneration)
      // otherwise the backend defaults it to {persona}_DEFAULT.
      const workflowId = request.workflowId ?? `${request.persona}_DEFAULT`
      return { id, workflowId, workflowStatus: 'PENDING' }
    } catch {
      return rejectWithValue({ error: 'Failed to run analysis' })
    }
  },
)

/**
 * Poll analysis job status (single shot — call repeatedly from useAssessmentPolling hook).
 * Polls GET /api/assessments/{id}/status?workflowId={workflowId} (single-shot).
 */
export const pollAnalysisStatus = createAsyncThunk<
  JobStatus,
  { id: string; workflowId: string },
  { rejectValue: ApiError }
>(
  'assessments/pollAnalysisStatus',
  async ({ id, workflowId }, { rejectWithValue, signal }) => {
    try {
      const response = await fetch(
        `${API_BASE}/assessments/${id}/status?workflowId=${workflowId}`,
        { headers: getAuthHeader(), signal },
      )

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const data = (await response.json()) as JobStatus
      return data
    } catch {
      return rejectWithValue({ error: 'Failed to poll analysis status' })
    }
  },
)

/**
 * Trigger narrative generation (Step 6 / A2) — called after user submits feedback.
 * Returns 202 Accepted; caller should poll /status?workflowId=RE_NARRATIVE or OE_NARRATIVE until COMPLETED.
 */
/**
 * Re-export alias: narrative regeneration uses the same /analyze/run endpoint,
 * with workflowId={persona}_NARRATIVE in the payload so the backend routes it
 * through the narrative pipeline instead of the default risk-eval pipeline.
 */
export const runNarrative = createAsyncThunk<
  { id: string; workflowId: string; workflowStatus: string },
  { id: string; request: NarrativeRequest },
  { rejectValue: ApiError }
>(
  'assessments/runNarrative',
  async ({ id, request }, { rejectWithValue, signal }) => {
    try {
      const workflowId = `${request.persona.toUpperCase()}_NARRATIVE`
      const response = await fetch(`${API_BASE}/assessments/${id}/analyze/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ ...request, workflowId }),
        signal,
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      return { id, workflowId, workflowStatus: 'PENDING' }
    } catch {
      return rejectWithValue({ error: 'Failed to trigger narrative generation' })
    }
  },
)

/**
 * Update reliability findings
 */
export const updateReliability = createAsyncThunk<
  Assessment,
  { id: string; data: unknown },
  { rejectValue: ApiError }
>(
  'assessments/updateReliability',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${id}/reliability`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const result = (await response.json()) as { assessment: Assessment }
      return result.assessment
    } catch {
      return rejectWithValue({ error: 'Failed to update reliability' })
    }
  },
)

/**
 * Update outage findings
 */
export const updateOutage = createAsyncThunk<
  Assessment,
  { id: string; data: unknown },
  { rejectValue: ApiError }
>(
  'assessments/updateOutage',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${id}/outage`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      const result = (await response.json()) as { assessment: Assessment }
      return result.assessment
    } catch {
      return rejectWithValue({ error: 'Failed to update outage' })
    }
  },
)

/**
 * Submit feedback for a finding
 */
export const submitFeedback = createAsyncThunk<
  { findingId: string; feedback: FeedbackRequest },
  { assessmentId: string; findingId: string; feedback: FeedbackRequest },
  { rejectValue: ApiError }
>(
  'assessments/submitFeedback',
  async ({ assessmentId, findingId, feedback }, { rejectWithValue }) => {
    try {
      const response = await fetch(
        `${API_BASE}/assessments/${assessmentId}/findings/${findingId}/feedback`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
          },
          body: JSON.stringify(feedback),
        },
      )

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      await response.json()
      return { findingId, feedback }
    } catch {
      return rejectWithValue({ error: 'Failed to submit feedback' })
    }
  },
)

/**
 * Export assessment to PDF
 */
export const exportPDF = createAsyncThunk<
  Blob,
  string,
  { rejectValue: ApiError }
>(
  'assessments/exportPDF',
  async (id, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${id}/export/pdf`, {
        headers: getAuthHeader(),
      })

      if (!response.ok) {
        const error = (await response.json()) as ApiError
        return rejectWithValue(error)
      }

      return await response.blob()
    } catch {
      return rejectWithValue({ error: 'Failed to export PDF' })
    }
  },
)

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: AssessmentState = {
  assessments: {},
  currentAssessment: null,
  loading: false,
  analyzing: false,
  error: null,
  analyzeJobs: {},
}

// ============================================================================
// SLICE
// ============================================================================

const assessmentsSlice = createSlice({
  name: 'assessments',
  initialState,
  reducers: {
    /**
     * Set current assessment
     */
    setCurrentAssessment: (state, action: PayloadAction<Assessment | null>) => {
      state.currentAssessment = action.payload
    },
    
    /**
     * Clear current assessment
     */
    clearCurrentAssessment: (state) => {
      state.currentAssessment = null
    },
    
    /**
     * Clear error
     */
    clearError: (state) => {
      state.error = null
    },
    
    /**
     * Update assessment locally (optimistic update)
     */
    updateAssessmentLocal: (state, action: PayloadAction<{ id: string; data: Partial<Assessment> }>) => {
      const { id, data } = action.payload
      if (state.assessments[id]) {
        state.assessments[id] = { ...state.assessments[id], ...data }
      }
      if (state.currentAssessment?.id === id) {
        state.currentAssessment = { ...state.currentAssessment, ...data }
      }
    },
  },
  extraReducers: (builder) => {
    // Create assessment
    builder
      .addCase(createAssessment.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(createAssessment.fulfilled, (state, action: PayloadAction<Assessment>) => {
        state.loading = false
        const assessment = action.payload
        state.assessments[assessment.id] = assessment
        state.currentAssessment = assessment
        state.error = null
      })
      .addCase(createAssessment.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to create assessment'
      })

    // Fetch assessment
    builder
      .addCase(fetchAssessment.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchAssessment.fulfilled, (state, action: PayloadAction<Assessment>) => {
        state.loading = false
        const assessment = action.payload
        state.assessments[assessment.id] = assessment
        state.currentAssessment = assessment
        state.error = null
      })
      .addCase(fetchAssessment.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload?.error || 'Failed to fetch assessment'
      })

    // Run analysis (single thunk for all personas)
    builder
      .addCase(runAnalysis.pending, (state) => {
        state.analyzing = true
        state.error = null
      })
      .addCase(runAnalysis.fulfilled, (state, action) => {
        state.analyzing = false
        const { id, workflowId, workflowStatus } = action.payload

        if (!state.analyzeJobs[id]) state.analyzeJobs[id] = {}
        state.analyzeJobs[id][workflowId] = {
          assessmentId: id,
          workflowId,
          workflowStatus,
        }

        state.error = null
      })
      .addCase(runAnalysis.rejected, (state, action) => {
        state.analyzing = false
        state.error = action.payload?.error || 'Analysis failed'
      })

    // Poll analysis status
    builder
      .addCase(pollAnalysisStatus.fulfilled, (state, action) => {
        const job = action.payload
        const { assessmentId, workflowId } = job

        if (!state.analyzeJobs[assessmentId]) state.analyzeJobs[assessmentId] = {}
        state.analyzeJobs[assessmentId][workflowId] = job
      })

    // Run narrative (trigger A2 post-feedback)
    builder
      .addCase(runNarrative.pending, (state) => {
        state.analyzing = true
        state.error = null
      })
      .addCase(runNarrative.fulfilled, (state, action) => {
        state.analyzing = false
        const { id, workflowId, workflowStatus } = action.payload

        if (!state.analyzeJobs[id]) state.analyzeJobs[id] = {}
        state.analyzeJobs[id][workflowId] = {
          assessmentId: id,
          workflowId,
          workflowStatus,
        }

        state.error = null
      })
      .addCase(runNarrative.rejected, (state, action) => {
        state.analyzing = false
        state.error = action.payload?.error || 'Narrative generation failed'
      })

    // Update reliability
    builder
      .addCase(updateReliability.fulfilled, (state, action: PayloadAction<Assessment>) => {
        const assessment = action.payload
        state.assessments[assessment.id] = assessment
        if (state.currentAssessment?.id === assessment.id) {
          state.currentAssessment = assessment
        }
      })

    // Update outage
    builder
      .addCase(updateOutage.fulfilled, (state, action: PayloadAction<Assessment>) => {
        const assessment = action.payload
        state.assessments[assessment.id] = assessment
        if (state.currentAssessment?.id === assessment.id) {
          state.currentAssessment = assessment
        }
      })

    // Submit feedback
    builder
      .addCase(submitFeedback.fulfilled, (state, action) => {
        const { findingId } = action.payload
        const now = new Date().toISOString()

        if (state.currentAssessment) {
          state.currentAssessment.savedRows = {
            ...(state.currentAssessment.savedRows ?? {}),
            [findingId]: now,
          }
          const currentId = state.currentAssessment.id
          const existing = currentId ? state.assessments[currentId] : undefined
          if (currentId && existing) {
            state.assessments[currentId] = {
              ...existing,
              savedRows: {
                ...(existing.savedRows ?? {}),
                [findingId]: now,
              },
            }
          }
        }
      })
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const {
  setCurrentAssessment,
  clearCurrentAssessment,
  clearError,
  updateAssessmentLocal,
} = assessmentsSlice.actions

export default assessmentsSlice.reducer

// Selectors
export const selectAssessments = (state: { assessments: AssessmentState }) => 
  state.assessments
const selectAssessmentsMap = (state: { assessments: AssessmentState }) =>
  state.assessments.assessments
export const selectAllAssessments = createSelector(
  [selectAssessmentsMap],
  (assessmentsMap) => Object.values(assessmentsMap)
)
export const selectCurrentAssessment = (state: { assessments: AssessmentState }) => 
  state.assessments.currentAssessment
export const selectAssessmentById = (id: string) => 
  (state: { assessments: AssessmentState }) => state.assessments.assessments[id]
export const selectAssessmentsLoading = (state: { assessments: AssessmentState }) => 
  state.assessments.loading
export const selectAnalyzing = (state: { assessments: AssessmentState }) => 
  state.assessments.analyzing
export const selectAssessmentsError = (state: { assessments: AssessmentState }) => 
  state.assessments.error
export const selectAnalyzeJob = (id: string, workflowId: string) =>
  (state: { assessments: AssessmentState }): JobStatus | undefined =>
    state.assessments.analyzeJobs[id]?.[workflowId]
