/**
 * useAssessmentPolling
 *
 * Polls GET /api/assessments/{id}/status?jobType={jobType} at a fixed interval
 * and dispatches `pollAnalysisStatus` until the job reaches COMPLETE or FAILED.
 *
 * Usage:
 *   useAssessmentPolling({ assessmentId: 'asmt_abc123', jobType: 'reliability', enabled: true })
 *
 * The hook:
 *  - Does nothing when `enabled` is false or job is already COMPLETE/FAILED
 *  - Polls every POLL_INTERVAL_MS milliseconds
 *  - Clears the interval automatically on unmount or when the job finishes
 *  - Dispatches to Redux so the result is accessible via selectAnalyzeJob()
 */

import { useEffect, useRef } from 'react'
import { useAppDispatch, useAppSelector } from '../store'
import { pollAnalysisStatus, selectAnalyzeJob } from '../store/slices/assessmentsSlice'

const POLL_INTERVAL_MS = 3_000

export interface UseAssessmentPollingProps {
  assessmentId: string
  jobType: 'reliability' | 'outage'
  /** Set to true after submitting an analysis job (202 response received). */
  enabled: boolean
}

/** Map human-readable job type to the workflowId used by pollAnalysisStatus. */
const WORKFLOW_ID_MAP = { reliability: 'RE_DEFAULT', outage: 'OE_DEFAULT' } as const
type WorkflowId = 'RE_DEFAULT' | 'OE_DEFAULT'

export function useAssessmentPolling({
  assessmentId,
  jobType,
  enabled,
}: UseAssessmentPollingProps): void {
  const dispatch = useAppDispatch()
  const workflowId: WorkflowId = WORKFLOW_ID_MAP[jobType]
  const jobStatus = useAppSelector(selectAnalyzeJob(assessmentId, workflowId))
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isTerminal = jobStatus?.workflowStatus === 'COMPLETED' || jobStatus?.workflowStatus === 'FAILED'

  useEffect(() => {
    if (!enabled || isTerminal || !assessmentId) {
      return
    }

    // Poll immediately on mount / when enabled flips true
    void dispatch(pollAnalysisStatus({ id: assessmentId, workflowId }))

    intervalRef.current = setInterval(() => {
      void dispatch(pollAnalysisStatus({ id: assessmentId, workflowId }))
    }, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  // Disable exhaustive-deps: intentionally re-run only when enabled/terminal/ids change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, isTerminal, assessmentId, jobType])
}
