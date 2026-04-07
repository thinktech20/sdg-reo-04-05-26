import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Paper,
  Chip,
  Divider,
  Alert,
  AlertTitle,
  CircularProgress,
  LinearProgress,
  Skeleton,
  Grid,
  Stepper,
  Step,
  StepLabel,
  type StepIconProps,
} from '@mui/material'
import { Engineering, CalendarMonth, Speed, PowerSettingsNew, CheckCircle, Lock, LockOutlined } from '@mui/icons-material'
import { WORKFLOW_STEPS } from '@/constants/workflow'
import { useAppDispatch, useAssessments, useEquipment } from '@/store'
import { clearCurrentAssessment, clearError, fetchAssessment } from '@/store/slices/assessmentsSlice'
import { searchEquipment } from '@/store/slices/equipmentSlice'
import DataReadinessPanel from '@/components/reliability/DataReadinessPanel'
import RiskAnalysisPanel from '@/components/reliability/RiskAnalysisPanel'
import NarrativeSummaryPanel from '@/components/reliability/NarrativeSummaryPanel'
import ReliabilityChatPanel from '@/components/reliability/ReliabilityChatPanel'

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Maps assessment status → active step index (0-based) */
function getActiveStep(assessment?: { reliabilityStatus?: string; reliabilityRiskCategories?: unknown } | null): number {
  if (assessment?.reliabilityStatus === 'completed') return 3
  // Risk analysis has run — step 2 (Run Assessment) is complete, step 3 (AI Chat) is active
  if (assessment?.reliabilityRiskCategories) return 3
  if (assessment?.reliabilityStatus === 'in-progress') return 2
  return 1
}

// ── Workflow step icon (with Lock for locked future steps) ────────────────────

function DetailStepIcon(props: StepIconProps & { lockable?: boolean; activeStep: number }) {
  const { active, completed, icon, lockable, activeStep } = props
  const stepIndex = Number(icon) - 1

  if (lockable && stepIndex > activeStep && !completed) {
    return (
      <Box
        sx={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'action.disabledBackground',
        }}
      >
        <Lock sx={{ fontSize: 16, color: 'text.disabled' }} />
      </Box>
    )
  }

  return (
    <Box
      sx={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: completed ? 'success.main' : active ? 'primary.main' : 'action.disabledBackground',
        color: completed || active ? 'white' : 'text.disabled',
        fontSize: 14,
        fontWeight: 700,
        transition: 'all 0.2s',
      }}
    >
      {completed ? <CheckCircle sx={{ fontSize: 18 }} /> : icon}
    </Box>
  )
}

/**
 * Unit Detail Page - Reliability Engineer Workflow
 * 
 * This page implements the complete RE workflow (Steps 2-6, 8):
 * - Step 2: Data Readiness Review
 * - Step 3-4: AI Risk Analysis & Display
 * - Step 5: Feedback Editing
 * - Step 6: Narrative Summary
 * - Step 8: Q&A Chat
 * 
 * Note: Step 1 (Unit Search) redirects here with esn & review_period params
 *       Step 7 (Event History) is OE-only and not included
 */
const UnitDetailPage = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  
  const esn = searchParams.get('esn')
  const reviewPeriod = searchParams.get('review_period') || '18-month'
  const [appliedDateFilter, setAppliedDateFilter] = useState({ dateFrom: '', dateTo: '' })
  const [selectedDataTypes, setSelectedDataTypes] = useState<string[]>([])
  
  const { currentAssessment, loading } = useAssessments()
  const { selectedEquipment, loading: equipmentLoading, error: equipmentError } = useEquipment()

  // Clear stale assessment data when moving to a new ESN so the page renders
  // fresh rather than showing the previous unit's findings and narrative.
  useEffect(() => {
    dispatch(clearCurrentAssessment())
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [esn])

  // Fetch equipment details on mount if not already loaded (e.g. direct URL navigation)
  useEffect(() => {
    if (!esn || (selectedEquipment && selectedEquipment.serialNumber === esn)) return
    const promise = dispatch(searchEquipment(esn))
    return () => { promise.abort() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [esn])

  // Only load an existing assessment if an explicit assessment_id is provided in the URL
  // (i.e. navigating back from the KB / assessments list). Fresh arrivals from search
  // have no assessment yet — creation is deferred until the user triggers analysis.
  useEffect(() => {
    if (!esn) {
      void navigate('/')
      return
    }

    const assessmentId = searchParams.get('assessment_id')
    if (!assessmentId) return

    const promise = dispatch(fetchAssessment(assessmentId))
    promise.unwrap().catch(() => { dispatch(clearError()) })
    return () => { promise.abort() }
  }, [esn, searchParams, dispatch, navigate])

  // Loading state — only show a full-page spinner when explicitly fetching an
  // existing assessment by URL (assessment_id param). Assessment *creation* is
  // triggered from within RiskAnalysisPanel and must not unmount this page
  // (which would reset the panel's local `analyzing` state and lose the loader).
  const isFetchingExisting = loading && !currentAssessment && !!searchParams.get('assessment_id')
  if (isFetchingExisting) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    )
  }

  // No ESN provided
  if (!esn) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          <AlertTitle>No Equipment Selected</AlertTitle>
          Please search and select a unit from the home page.
        </Alert>
      </Box>
    )
  }

  const equipmentData = {
    serialNumber: esn,
    model: selectedEquipment?.model ?? null,
    type: selectedEquipment?.equipmentType ?? null,
    site: selectedEquipment?.site ?? null,
    cod: selectedEquipment?.commercialOpDate ?? null,
    eoh: selectedEquipment?.totalEOH ?? null,
    starts: selectedEquipment?.totalStarts ?? null,
  }

  /** Show skeletons from the very first render until equipment for this ESN is in Redux.
   *  Covers three cases:
   *   1. Initial navigation: selectedEquipment is null → serialNumber !== esn
   *   2. The dispatch is in-flight (equipmentLoading is true)
   *   3. A different ESN is still in Redux while the new one loads
   *  Suppressed when there is a hard error (no point spinning forever). */
  const headerLoading = (equipmentLoading || selectedEquipment?.serialNumber !== esn) && !equipmentError

  return (
    <Box sx={{ p: 3 }}>
      {/* Page Header with Unit Information */}
      <Paper elevation={2} sx={{ p: 3, mb: 3, overflow: 'hidden', position: 'relative' }}>
        {headerLoading && (
          <LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0 }} />
        )}
        <Grid container spacing={3} alignItems="center">
          <Grid size={{ xs: 12, md: 6 }}>
            <Box display="flex" alignItems="center" gap={2} mb={1}>
              <Engineering sx={{ fontSize: 32, color: 'primary.main' }} />
              <Typography variant="h4" component="h1">
                {equipmentData.serialNumber}
              </Typography>
              {headerLoading ? (
                <Skeleton variant="rounded" width={90} height={24} />
              ) : equipmentData.type ? (
                <Chip label={equipmentData.type} color="primary" size="small" />
              ) : null}
            </Box>
            {headerLoading ? (
              <Skeleton variant="text" width={280} sx={{ fontSize: '1rem' }} />
            ) : (
              <Typography variant="body1" color="text.secondary">
                Model: {equipmentData.model ?? '—'} • Site: {equipmentData.site ?? '—'}
              </Typography>
            )}
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box textAlign="center">
                  <CalendarMonth sx={{ color: 'text.secondary', mb: 0.5 }} />
                  <Typography variant="caption" color="text.secondary" display="block">
                    COD
                  </Typography>
                  {headerLoading ? (
                    <Skeleton variant="text" width={72} sx={{ mx: 'auto' }} />
                  ) : (
                    <Typography variant="body2" fontWeight="medium">
                      {equipmentData.cod ?? '—'}
                    </Typography>
                  )}
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box textAlign="center">
                  <Speed sx={{ color: 'text.secondary', mb: 0.5 }} />
                  <Typography variant="caption" color="text.secondary" display="block">
                    EOH
                  </Typography>
                  {headerLoading ? (
                    <Skeleton variant="text" width={72} sx={{ mx: 'auto' }} />
                  ) : (
                    <Typography variant="body2" fontWeight="medium">
                      {equipmentData.eoh != null ? equipmentData.eoh.toLocaleString('en-US') : '—'}
                    </Typography>
                  )}
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box textAlign="center">
                  <PowerSettingsNew sx={{ color: 'text.secondary', mb: 0.5 }} />
                  <Typography variant="caption" color="text.secondary" display="block">
                    Starts
                  </Typography>
                  {headerLoading ? (
                    <Skeleton variant="text" width={72} sx={{ mx: 'auto' }} />
                  ) : (
                    <Typography variant="body2" fontWeight="medium">
                      {equipmentData.starts != null ? equipmentData.starts.toLocaleString('en-US') : '—'}
                    </Typography>
                  )}
                </Box>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box textAlign="center">
                  <CalendarMonth sx={{ color: 'text.secondary', mb: 0.5 }} />
                  <Typography variant="caption" color="text.secondary" display="block">
                    Milestone
                  </Typography>
                  <Typography variant="body2" fontWeight="medium">
                    {reviewPeriod}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Grid>
        </Grid>

        {/* Status Badge */}
        {currentAssessment && (
          <Box mt={2} pt={2} borderTop={1} borderColor="divider">
            <Box display="flex" gap={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Status:
              </Typography>
              <Chip
                label={(currentAssessment.reliabilityStatus ?? 'not-started').replace('-', ' ').toUpperCase()}
                color={
                  currentAssessment.reliabilityStatus === 'completed'
                    ? 'success'
                    : currentAssessment.reliabilityStatus === 'in-progress'
                    ? 'warning'
                    : 'default'
                }
                size="small"
              />
            </Box>
          </Box>
        )}

        {/* Workflow Stepper */}
        <Box mt={3} pt={2} borderTop={1} borderColor="divider">
          <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 1.2 }}>
            Assessment Workflow
          </Typography>
          <Stepper
            activeStep={getActiveStep(currentAssessment)}
            alternativeLabel
            connector={<></>}
            sx={{ mt: 1.5 }}
          >
            {WORKFLOW_STEPS.map((step, i) => {
              const active = getActiveStep(currentAssessment)
              return (
                <Step key={step.label} completed={active > i}>
                  <StepLabel
                    StepIconComponent={(p) => (
                      <DetailStepIcon {...p} lockable={step.lockable} activeStep={active} />
                    )}
                    sx={{
                      '& .MuiStepLabel-label': {
                        fontSize: '0.75rem',
                        mt: 0.5,
                        color:
                          active === i
                            ? 'primary.main'
                            : active > i
                              ? 'success.main'
                              : 'text.disabled',
                        fontWeight: active === i ? 700 : 400,
                      },
                    }}
                  >
                    {step.label}
                    <Typography variant="caption" color="text.disabled" display="block" sx={{ mt: 0.25 }}>
                      {step.description}
                    </Typography>
                  </StepLabel>
                </Step>
              )
            })}
          </Stepper>
        </Box>
      </Paper>

      {/* Reliability Engineer Workflow Title */}
      <Box mb={3}>
        <Typography variant="h5" gutterBottom>
          Reliability Engineering Assessment
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Complete the workflow below to generate risk assessment and recommendations
        </Typography>
      </Box>

      {/* Step 2: Data Readiness */}
      <DataReadinessPanel
        assessment={currentAssessment}
        esn={esn}
        onFiltersApplied={(dateFrom, dateTo) => setAppliedDateFilter({ dateFrom, dateTo })}
        onDataTypesSelected={setSelectedDataTypes}
      />

      <Divider sx={{ my: 4 }} />

      {/* Steps 3-5: Risk Analysis & Feedback */}
      <RiskAnalysisPanel
        assessment={currentAssessment}
        esn={esn}
        reviewPeriod={reviewPeriod}
        equipmentType={selectedEquipment?.equipmentType}
        dataTypes={selectedDataTypes}
        dateFrom={appliedDateFilter.dateFrom || undefined}
        dateTo={appliedDateFilter.dateTo || undefined}
      />

      <Divider sx={{ my: 4 }} />

      {/* Step 6: Narrative Summary */}
      <NarrativeSummaryPanel assessment={currentAssessment} assessmentId={currentAssessment?.id} />

      <Divider sx={{ my: 4 }} />

      {/* Step 4: Q&A Chat — locked until assessment is complete */}
      {currentAssessment?.reliabilityStatus === 'completed' ? (
        <ReliabilityChatPanel assessment={currentAssessment} />
      ) : (
        <Paper
          variant="outlined"
          sx={{
            p: 6,
            textAlign: 'center',
            bgcolor: 'action.disabledBackground',
            borderStyle: 'dashed',
          }}
        >
          <LockOutlined sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.disabled" gutterBottom>
            AI Chat — Locked
          </Typography>
          <Typography variant="body2" color="text.disabled">
            Complete the Risk Assessment above to unlock Q&amp;A with the AI agent.
          </Typography>
        </Paper>
      )}
    </Box>
  )
}

export default UnitDetailPage
