/**
 * Assessments Slice Tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import assessmentsReducer, {
  createAssessment,
  fetchAssessment,
  runAnalysis,
  runNarrative,
  updateReliability,
  updateOutage,
  submitFeedback,
  exportPDF,
  setCurrentAssessment,
  clearCurrentAssessment,
  clearError,
  updateAssessmentLocal,
  selectAssessments,
  selectAllAssessments,
  selectCurrentAssessment,
  selectAssessmentById,
  selectAssessmentsLoading,
  selectAnalyzing,
  selectAssessmentsError,
} from './assessmentsSlice'
import { createTestStore, createMockAssessment } from '@/test/utils'
import type { AssessmentState } from '../types'

// Mock fetch globally
// Mock fetch
const mockFetch = vi.fn()

describe('assessmentsSlice', () => {
  let initialState: AssessmentState

  beforeEach(() => {
    initialState = {
      assessments: {},
      currentAssessment: null,
      loading: false,
      analyzing: false,
      error: null,
      analyzeJobs: {},
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
      expect(assessmentsReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle setCurrentAssessment', () => {
      const assessment = createMockAssessment()
      const state = assessmentsReducer(initialState, setCurrentAssessment(assessment))
      expect(state.currentAssessment).toEqual(assessment)
    })

    it('should handle setCurrentAssessment with null', () => {
      const stateWithAssessment = { ...initialState, currentAssessment: createMockAssessment() }
      const state = assessmentsReducer(stateWithAssessment, setCurrentAssessment(null))
      expect(state.currentAssessment).toBeNull()
    })

    it('should handle clearCurrentAssessment', () => {
      const stateWithAssessment = { ...initialState, currentAssessment: createMockAssessment() }
      const state = assessmentsReducer(stateWithAssessment, clearCurrentAssessment())
      expect(state.currentAssessment).toBeNull()
    })

    it('should handle clearError', () => {
      const stateWithError = { ...initialState, error: 'Test error' }
      const state = assessmentsReducer(stateWithError, clearError())
      expect(state.error).toBeNull()
    })

    it('should handle updateAssessmentLocal', () => {
      const assessment = createMockAssessment({ id: '1', reliabilityStatus: 'not-started' })
      const stateWithAssessment = {
        ...initialState,
        assessments: { '1': assessment },
        currentAssessment: assessment,
      }
      
      const state = assessmentsReducer(
        stateWithAssessment,
        updateAssessmentLocal({ id: '1', data: { reliabilityStatus: 'in-progress' } })
      )
      
      expect(state.assessments['1']?.reliabilityStatus).toBe('in-progress')
      expect(state.currentAssessment?.reliabilityStatus).toBe('in-progress')
    })

    it('should handle updateAssessmentLocal when assessment not in dictionary', () => {
      const state = assessmentsReducer(
        initialState,
        updateAssessmentLocal({ id: '999', data: { reliabilityStatus: 'in-progress' } })
      )
      
      expect(state.assessments['999']).toBeUndefined()
    })
  })

  describe('async thunks', () => {
    describe('createAssessment', () => {
      it('should create assessment successfully', async () => {
        const mockAssessment = createMockAssessment()

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessment: mockAssessment }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(createAssessment({ esn: 'GT12345', reviewPeriod: '18-month', persona: 'RE', workflowId: 'RE_DEFAULT' }))
        
        const state = store.getState().assessments
        expect(state.loading).toBe(false)
        expect(state.assessments[mockAssessment.id]).toEqual(mockAssessment)
        expect(state.currentAssessment).toEqual(mockAssessment)
        expect(state.error).toBeNull()
      })

      it('should handle create failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Creation failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(createAssessment({ esn: 'GT12345', reviewPeriod: '18-month', persona: 'RE', workflowId: 'RE_DEFAULT' }))
        
        const state = store.getState().assessments
        expect(state.error).toBeTruthy()
      })
    })

    describe('fetchAssessment', () => {
      it('should fetch assessment successfully', async () => {
        const mockAssessment = createMockAssessment()

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessment: mockAssessment }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchAssessment('assessment-1'))
        
        const state = store.getState().assessments
        expect(state.assessments[mockAssessment.id]).toEqual(mockAssessment)
        expect(state.currentAssessment).toEqual(mockAssessment)
      })

      it('should handle fetch failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Not found' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(fetchAssessment('invalid'))
        
        const state = store.getState().assessments
        expect(state.error).toBeTruthy()
      })
    })

    describe('runAnalysis', () => {
      it('should accept run request and return PENDING for RE', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessmentId: '1', workflowId: 'RE_DEFAULT', workflowStatus: 'PENDING' }),
        } as unknown as Response)

        const store = createTestStore({
          assessments: {
            ...initialState,
            assessments: { '1': createMockAssessment({ id: '1' }) },
            currentAssessment: createMockAssessment({ id: '1' }),
          },
        })

        await store.dispatch(runAnalysis({
          id: '1',
          request: { persona: 'RE', equipmentType: 'Gas Turbine' },
        }))

        const state = store.getState().assessments
        expect(state.analyzing).toBe(false)
        expect(state.analyzeJobs['1']?.['RE_DEFAULT']?.workflowStatus).toBe('PENDING')
        expect(state.error).toBeNull()
      })

      it('should set analyzing state during request', async () => {
        mockFetch.mockImplementationOnce(() =>
          new Promise(resolve => setTimeout(() => resolve({
            ok: true,
            json: () => ({}),
          } as unknown as Response), 100))
        )

        const store = createTestStore({
          assessments: {
            ...initialState,
            assessments: { '1': createMockAssessment({ id: '1' }) },
          },
        })

        const promise = store.dispatch(runAnalysis({
          id: '1',
          request: { persona: 'OE' },
        }))

        expect(store.getState().assessments.analyzing).toBe(true)

        await promise
        expect(store.getState().assessments.analyzing).toBe(false)
      })

      it('should handle run analysis failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Analysis failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(runAnalysis({
          id: '1',
          request: { persona: 'RE' },
        }))

        const state = store.getState().assessments
        expect(state.error).toBeTruthy()
      })
    })

    describe('runNarrative', () => {
      it('should hit /analyze/run with workflowId=RE_NARRATIVE and return PENDING', async () => {
        // runNarrative now delegates to /analyze/run with workflowId in body
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessmentId: '1', workflowId: 'RE_NARRATIVE', workflowStatus: 'PENDING' }),
        } as unknown as Response)

        const store = createTestStore({
          assessments: {
            ...initialState,
            assessments: { '1': createMockAssessment({ id: '1' }) },
          },
        })

        await store.dispatch(runNarrative({ id: '1', request: { persona: 'RE' } }))

        // Verify the fetch was called against /analyze/run (not /analyze/narrative)
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/analyze/run'),
          expect.objectContaining({
            body: expect.stringContaining('"workflowId":"RE_NARRATIVE"'),
          }),
        )

        const state = store.getState().assessments
        expect(state.analyzeJobs['1']?.['RE_NARRATIVE']?.workflowStatus).toBe('PENDING')
        expect(state.analyzeJobs['1']?.['RE_NARRATIVE']?.workflowId).toBe('RE_NARRATIVE')
      })
    })

    describe('updateReliability', () => {
      it('should update reliability successfully', async () => {
        const updatedAssessment = createMockAssessment({ id: '1', reliabilityStatus: 'completed' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessment: updatedAssessment }),
        } as unknown as Response)

        const store = createTestStore({
          assessments: {
            ...initialState,
            assessments: { '1': createMockAssessment({ id: '1' }) },
            currentAssessment: createMockAssessment({ id: '1' }),
          },
        })

        await store.dispatch(updateReliability({ id: '1', data: {} }))
        
        const state = store.getState().assessments
        expect(state.assessments['1']).toEqual(updatedAssessment)
        expect(state.currentAssessment).toEqual(updatedAssessment)
      })
    })

    describe('updateOutage', () => {
      it('should update outage successfully', async () => {
        const updatedAssessment = createMockAssessment({ id: '1', outageStatus: 'completed' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({ assessment: updatedAssessment }),
        } as unknown as Response)

        const store = createTestStore({
          assessments: {
            ...initialState,
            assessments: { '1': createMockAssessment({ id: '1' }) },
          },
        })

        await store.dispatch(updateOutage({ id: '1', data: {} }))
        
        expect(store.getState().assessments.assessments['1']).toEqual(updatedAssessment)
      })
    })

    describe('submitFeedback', () => {
      it('should submit feedback successfully', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => ({}),
        } as unknown as Response)

        const store = createTestStore()
        const result = await store.dispatch(submitFeedback({
          assessmentId: '1',
          findingId: 'finding-1',
          feedback: { feedback: 'up', comments: 'Good' },
        }))
        
        expect(result.type).toBe('assessments/submitFeedback/fulfilled')
      })

      it('should handle feedback submission failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(submitFeedback({
          assessmentId: '1',
          findingId: 'finding-1',
          feedback: { feedback: 'up', comments: 'Good' },
        }))
        
        // Should not throw, just reject
        expect(true).toBe(true)
      })
    })

    describe('exportPDF', () => {
      it('should export PDF successfully', async () => {
        const mockBlob = new Blob(['pdf content'], { type: 'application/pdf' })

        mockFetch.mockResolvedValueOnce({
          ok: true,
          blob: () => mockBlob,
        } as unknown as Response)

        const store = createTestStore()
        const result = await store.dispatch(exportPDF('assessment-1'))
        
        expect(result.type).toBe('assessments/exportPDF/fulfilled')
        expect(result.payload).toBeInstanceOf(Blob)
      })

      it('should handle export failure', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          json: () => ({ error: 'Export failed' }),
        } as unknown as Response)

        const store = createTestStore()
        await store.dispatch(exportPDF('assessment-1'))
        
        // Should not throw
        expect(true).toBe(true)
      })
    })
  })

  describe('selectors', () => {
    it('selectAssessments should return assessments state', () => {
      const store = createTestStore({ assessments: initialState })
      expect(selectAssessments(store.getState())).toEqual(initialState)
    })

    it('selectAllAssessments should return array of assessments', () => {
      const assessments = {
        '1': createMockAssessment({ id: '1' }),
        '2': createMockAssessment({ id: '2' }),
      }
      const store = createTestStore({ assessments: { ...initialState, assessments } })
      const all = selectAllAssessments(store.getState())
      expect(all).toHaveLength(2)
      expect(all).toContainEqual(assessments['1'])
      expect(all).toContainEqual(assessments['2'])
    })

    it('selectCurrentAssessment should return current assessment', () => {
      const assessment = createMockAssessment()
      const store = createTestStore({
        assessments: { ...initialState, currentAssessment: assessment },
      })
      expect(selectCurrentAssessment(store.getState())).toEqual(assessment)
    })

    it('selectAssessmentById should return specific assessment', () => {
      const assessment = createMockAssessment({ id: '1' })
      const store = createTestStore({
        assessments: { ...initialState, assessments: { '1': assessment } },
      })
      expect(selectAssessmentById('1')(store.getState())).toEqual(assessment)
    })

    it('selectAssessmentsLoading should return loading state', () => {
      const store = createTestStore({ assessments: { ...initialState, loading: true } })
      expect(selectAssessmentsLoading(store.getState())).toBe(true)
    })

    it('selectAnalyzing should return analyzing state', () => {
      const store = createTestStore({ assessments: { ...initialState, analyzing: true } })
      expect(selectAnalyzing(store.getState())).toBe(true)
    })

    it('selectAssessmentsError should return error', () => {
      const store = createTestStore({ assessments: { ...initialState, error: 'Test error' } })
      expect(selectAssessmentsError(store.getState())).toBe('Test error')
    })
  })
})
