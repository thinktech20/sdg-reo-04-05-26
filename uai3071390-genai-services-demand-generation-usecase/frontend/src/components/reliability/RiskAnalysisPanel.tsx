import { useState } from 'react'
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  AlertTitle,
  Stepper,
  Step,
  StepLabel,
  LinearProgress,
  Chip,
  Divider,
} from '@mui/material'
import {
  PlayArrow,
  Engineering,
  CheckCircle,
  RadioButtonChecked,
  CheckCircleOutline,
  ErrorOutline,
  Refresh,
} from '@mui/icons-material'
import type { Assessment, JobStatus } from '@/store/types'
import { useAppDispatch } from '@/store'
import { createAssessment, runAnalysis, pollAnalysisStatus, fetchAssessment } from '@/store/slices/assessmentsSlice'
import RiskCategoryDisplay from './RiskCategoryDisplay'

interface RiskAnalysisPanelProps {
  assessment: Assessment | null
  esn: string
  reviewPeriod: string
  equipmentType?: string
  dataTypes?: string[]
  dateFrom?: string
  dateTo?: string
}

const analysisSteps = [
  'Querying ER Cases',
  'Analyzing FSR Reports',
  'Applying Reliability Models',
  'Interpreting Risk Combinations',
  'Generating Findings',
]

/** Human-readable labels for orchestrator pipeline node names. */
const NODE_LABELS: Record<string, string> = {
  risk_eval: 'Risk Evaluation',
  narrative: 'Narrative Summary',
  event_history: 'Event History',
  finalize: 'Finalizing Results',
  starting: 'Starting…',
}

function elapsedLabel(startedAt: string, completedAt?: string): string {
  const start = new Date(startedAt).getTime()
  const end = completedAt ? new Date(completedAt).getTime() : Date.now()
  const secs = Math.round((end - start) / 1000)
  return secs >= 60 ? `${Math.floor(secs / 60)}m ${secs % 60}s` : `${secs}s`
}

/**
 * Risk Analysis Panel - Steps 3-5
 *
 * Step 3: Trigger AI analysis with optional human-in-loop
 * Step 4: Display risk assessment table
 * Step 5: Allow user feedback editing (handled in RiskCategoryDisplay)
 */
const RiskAnalysisPanel = ({ assessment, esn, reviewPeriod, equipmentType, dataTypes, dateFrom, dateTo }: RiskAnalysisPanelProps) => {
  const dispatch = useAppDispatch()
  const [analyzing, setAnalyzing] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [currentJobStatus, setCurrentJobStatus] = useState<JobStatus | null>(null)
  const [failureMessage, setFailureMessage] = useState<string | null>(null)

  const hasAnalysis = assessment?.reliabilityRiskCategories !== undefined
  const riskCategoryCount = assessment?.reliabilityRiskCategories
    ? Object.keys(assessment.reliabilityRiskCategories).length
    : 0
  const hasRiskCategories = riskCategoryCount > 0

  /**
   * After the analyze endpoint returns 202 PENDING, poll /status until
   * the job is COMPLETE or FAILED.
   *
   * This poll loop is intentionally non-expiring so long-running workflows
   * continue showing progress without timing out in the UI.
   */
  const pollUntilComplete = async (assessmentId: string) => {
    const INTERVAL_MS = 5000
    let pollCount = 0

    for (;;) {
      pollCount += 1
      await new Promise((r) => setTimeout(r, INTERVAL_MS))
      try {
        const result = await dispatch(
          pollAnalysisStatus({ id: assessmentId, workflowId: 'RE_DEFAULT' })
        ).unwrap()
        setCurrentJobStatus(result)

        if (result.workflowStatus === 'COMPLETED') {
          // RE_DEFAULT pipeline runs risk eval + narrative in one workflow.
          // fetchAssessment will return both riskCategories and narrativeSummary.
          await dispatch(fetchAssessment(assessmentId))
          break
        }
        if (result.workflowStatus === 'FAILED') {
          setFailureMessage(result.errorMessage ?? 'The analysis pipeline reported a failure.')
          break
        }
      } catch (err) {
        // Keep spinner alive for long-lived jobs even across transient network issues.
        if (pollCount % 12 === 0) {
          console.warn(`Poll attempt ${pollCount} failed (continuing):`, err)
        }
      }
    }
    setAnalyzing(false)
  }

  const handleRunAnalysis = async () => {
    try {
      // Create assessment on first run if one doesn't exist yet
      let assessmentId = assessment?.id
      if (!assessmentId) {
        const newAssessment = await dispatch(
          createAssessment({ esn, persona: 'RE', workflowId: 'RE_DEFAULT', reviewPeriod, equipmentType, dataTypes, dateFrom, dateTo })
        ).unwrap()
        assessmentId = newAssessment.id
      }

      const job = await dispatch(
        runAnalysis({
          id: assessmentId,
          request: {
            persona: 'RE',
            workflowId: 'RE_DEFAULT',
            equipmentType: equipmentType ?? 'Generator',
            reviewPeriod,
            unitNumber: assessment?.unitNumber,
            dataTypes,
            dateFrom,
            dateTo,
          },
        })
      ).unwrap()
      // If job is async (PENDING), poll until COMPLETE
      if (job.workflowStatus === 'PENDING' || job.workflowStatus === 'IN_QUEUE') {
        await pollUntilComplete(assessmentId)
      } else {
        setAnalyzing(false)
      }
    } catch (err) {
      console.error('Analysis failed:', err)
      // Redux rejectWithValue payloads are plain objects {error: string}, not Error instances.
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'error' in err
          ? String((err as { error: unknown }).error)
          : 'Failed to start the analysis. Please try again.'
      setFailureMessage(msg)
      setAnalyzing(false)
    }
  }

  // Handle analysis start — kick off the API call immediately; run the
  // animated fake stepper separately so it never blocks or races with the
  // real polling loop (calling async code inside a React state-updater
  // function causes StrictMode double-invocation bugs).
  const handleStartAnalysis = () => {
    setAnalyzing(true)
    setCurrentStep(0)
    setCurrentJobStatus(null)
    setFailureMessage(null)

    // Purely cosmetic fake stepper — advances independently of the API
    let step = 0
    const stepInterval = setInterval(() => {
      step++
      if (step < analysisSteps.length) {
        setCurrentStep(step)
      } else {
        clearInterval(stepInterval)
      }
    }, 800)

    // Start the real API sequence immediately (does not depend on stepper)
    void handleRunAnalysis()
  }

  return (
    <Box id="risk-analysis-section">
      {/* Section Header */}
      <Paper elevation={1} sx={{ p: 3, mb: 3, bgcolor: 'primary.50' }}>
        <Typography variant="h6" gutterBottom>
          Steps 3-5: Risk Assessment & Analysis
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Run AI-powered risk analysis to identify conditions requiring attention. You can review
          and provide feedback on each finding.
        </Typography>
      </Paper>

      {/* Analysis Failed */}
      {!analyzing && failureMessage && (
        <Paper
          elevation={2}
          sx={{
            p: 4,
            mb: 3,
            border: 1,
            borderColor: 'error.main',
            bgcolor: 'error.50',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 2 }}>
            <ErrorOutline color="error" sx={{ fontSize: 36, flexShrink: 0, mt: 0.5 }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6" color="error.main" gutterBottom>
                Analysis Failed
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {failureMessage}
              </Typography>

              {/* Show which nodes ran before the failure */}
              {currentJobStatus?.nodeTimings && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, mb: 2 }}>
                  {Object.entries(currentJobStatus.nodeTimings).map(([name, timing]) => (
                    <Box key={name} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {timing.completedAt
                        ? <CheckCircleOutline fontSize="small" color="success" />
                        : <ErrorOutline fontSize="small" color="error" />}
                      <Typography variant="body2" sx={{ flex: 1 }}>
                        {NODE_LABELS[name] ?? name}
                      </Typography>
                      <Chip
                        label={
                          timing.completedAt
                            ? elapsedLabel(timing.startedAt, timing.completedAt)
                            : 'Interrupted'
                        }
                        size="small"
                        variant="outlined"
                        color={timing.completedAt ? 'success' : 'error'}
                      />
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          </Box>
          <Box display="flex" justifyContent="flex-end">
            <Button
              variant="contained"
              color="error"
              startIcon={<Refresh />}
              onClick={handleStartAnalysis}
            >
              Retry Analysis
            </Button>
          </Box>
        </Paper>
      )}

      {/* Analysis Control */}
      {!hasAnalysis && !analyzing && !failureMessage && (
        <Paper elevation={2} sx={{ p: 4, mb: 3, textAlign: 'center' }}>
          <Engineering sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Ready to Start Risk Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            This will analyze available data sources and generate a comprehensive risk assessment
            table with findings across all risk categories.
          </Typography>
          <Button
            variant="contained"
            size="large"
            startIcon={<PlayArrow />}
            onClick={handleStartAnalysis}
            disabled={analyzing}
          >
            Run AI Risk Analysis
          </Button>
        </Paper>
      )}

      {/* Analysis Progress */}
      {analyzing && (
        <Paper elevation={2} sx={{ p: 4, mb: 3 }}>
          <Typography variant="h6" gutterBottom textAlign="center">
            Analyzing Risk Assessment…
          </Typography>
          <Box sx={{ width: '100%', mb: 3 }}>
            <LinearProgress />
          </Box>

          {/* Real node-level progress (available when backend returns activeNode) */}
          {currentJobStatus?.nodeTimings || currentJobStatus?.activeNode ? (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>
                Pipeline progress
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {/* Completed nodes */}
                {currentJobStatus.nodeTimings &&
                  Object.entries(currentJobStatus.nodeTimings)
                    .filter(([, t]) => t.completedAt)
                    .map(([name, timing]) => (
                      <Box key={name} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CheckCircleOutline fontSize="small" color="success" />
                        <Typography variant="body2" sx={{ flex: 1 }}>
                          {NODE_LABELS[name] ?? name}
                        </Typography>
                        <Chip
                          label={elapsedLabel(timing.startedAt, timing.completedAt)}
                          size="small"
                          variant="outlined"
                          color="success"
                        />
                      </Box>
                    ))}

                {/* Divider between completed and active */}
                {currentJobStatus.nodeTimings &&
                  Object.values(currentJobStatus.nodeTimings).some((t) => t.completedAt) &&
                  currentJobStatus.activeNode && (
                    <Divider sx={{ my: 0.5 }} />
                  )}

                {/* Active node */}
                {currentJobStatus.activeNode && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <RadioButtonChecked fontSize="small" color="primary" sx={{ animation: 'pulse 1.5s infinite' }} />
                    <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
                      {NODE_LABELS[currentJobStatus.activeNode] ?? currentJobStatus.activeNode}
                    </Typography>
                    <Chip
                      label={(() => {
                        const activeNode = currentJobStatus.activeNode
                        const timing = currentJobStatus.nodeTimings?.[activeNode]
                        return timing?.startedAt
                          ? `${elapsedLabel(timing.startedAt)}…`
                          : 'Running…'
                      })()}
                      size="small"
                      color="primary"
                    />
                  </Box>
                )}
              </Box>
            </Box>
          ) : (
            /* Fallback animated stepper when no real node data yet */
            <Stepper activeStep={currentStep} alternativeLabel>
              {analysisSteps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          )}
        </Paper>
      )}

      {/* Risk Assessment Results */}
      {hasAnalysis && !analyzing && (
        <Box>
          {hasRiskCategories ? (
            <Alert severity="success" sx={{ mb: 3 }} icon={<CheckCircle />}>
              <AlertTitle>Analysis Complete</AlertTitle>
              Risk assessment table generated successfully. Review findings below and provide
              feedback as needed.
            </Alert>
          ) : (
            <Alert severity="warning" sx={{ mb: 3 }}>
              <AlertTitle>No Risk Findings Returned</AlertTitle>
              The analysis workflow completed, but no risk findings were returned for this run.
              No synthetic data is shown. Please verify data-source availability and retry.
            </Alert>
          )}

          {/* Risk Categories */}
          {hasRiskCategories && assessment.reliabilityRiskCategories && (
            <Box>
              {Object.entries(assessment.reliabilityRiskCategories).map(
                ([categoryId, category]) => (
                  <RiskCategoryDisplay
                    key={categoryId}
                    category={category}
                    assessmentId={assessment.id}
                    savedRows={assessment.savedRows || {}}
                    editable={true}
                  />
                )
              )}
            </Box>
          )}

          {/* Feedback info — points user to Narrative panel */}
          <Alert severity="info" sx={{ mt: 3 }}>
            Narrative generation is a separate step now. Submit feedback on all finding rows above,
            then use <strong>Generate Narrative Summary</strong> in Step 6.
          </Alert>

          {/* Re-run risk table (separate from narrative regeneration) */}
          <Box display="flex" justifyContent="center" mt={2}>
            <Button
              variant="text"
              size="small"
              startIcon={<Refresh />}
              onClick={handleStartAnalysis}
              sx={{ color: 'text.secondary' }}
            >
              Re-run risk analysis from scratch
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  )
}

export default RiskAnalysisPanel
