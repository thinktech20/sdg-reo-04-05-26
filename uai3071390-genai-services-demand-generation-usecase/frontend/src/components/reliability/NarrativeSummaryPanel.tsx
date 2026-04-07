import { useMemo, useState } from 'react'
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  AlertTitle,
  Chip,
  Divider,
  Snackbar,
  LinearProgress,
} from '@mui/material'
import { Description, ContentCopy, AutoAwesome, Refresh } from '@mui/icons-material'
import type { Assessment } from '@/store/types'
import { useAppDispatch } from '@/store'
import { runAnalysis, pollAnalysisStatus, fetchAssessment } from '@/store/slices/assessmentsSlice'

interface NarrativeSummaryPanelProps {
  assessment: Assessment | null
  assessmentId?: string
}

interface NarrativeSection {
  title: string
  content: string
}

const parseNarrativeSections = (summaryText: string): NarrativeSection[] => {
  const trimmedText = summaryText.trim()
  if (!trimmedText.startsWith('{') || !trimmedText.endsWith('}')) {
    return []
  }

  try {
    const parsedSummary = JSON.parse(trimmedText) as Record<string, unknown>
    if (Array.isArray(parsedSummary) || typeof parsedSummary !== 'object' || parsedSummary === null) {
      return []
    }

    return Object.entries(parsedSummary)
      .map(([title, value]) => {
        if (value === undefined || value === null) {
          return null
        }

        let content = ''
        if (typeof value === 'string') {
          content = value
        } else if (Array.isArray(value)) {
          content = value.map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).join('\n')
        } else if (typeof value === 'object') {
          content = JSON.stringify(value, null, 2)
        } else if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
          content = value.toString()
        } else {
          return null
        }

        if (!content.trim()) {
          return null
        }

        return { title, content }
      })
      .filter((section): section is NarrativeSection => section !== null)
  } catch {
    return []
  }
}

const buildCopySummary = (summaryText: string, sections: NarrativeSection[]): string => {
  if (sections.length === 0) {
    return summaryText
  }

  return sections.map((section) => `${section.title}\n${section.content}`).join('\n\n')
}

const copyTextWithFallback = async (text: string): Promise<void> => {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Fall back to textarea copy for browsers that block clipboard API.
    }
  }

  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.setAttribute('readonly', '')
  textArea.style.position = 'fixed'
  textArea.style.left = '-9999px'
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()

  const copied = document.execCommand('copy')
  document.body.removeChild(textArea)

  if (!copied) {
    throw new Error('Clipboard copy failed')
  }
}

/**
 * Narrative Summary Panel - Step 6
 * 
 * Displays auto-generated narrative summary from AI
 */
const NarrativeSummaryPanel = ({ assessment, assessmentId }: NarrativeSummaryPanelProps) => {
  const dispatch = useAppDispatch()
  const [copyFeedback, setCopyFeedback] = useState<{
    severity: 'success' | 'error'
    message: string
  } | null>(null)
  const [regenerating, setRegenerating] = useState(false)

  const hasAnalysis = assessment?.reliabilityRiskCategories !== undefined
  const hasNarrative = assessment?.narrativeSummary !== undefined && assessment?.narrativeSummary !== ''
  const allFindingIds = Object.values(assessment?.reliabilityRiskCategories ?? {}).flatMap(
    (category) => category.conditions.map((condition) => condition.findingId)
  )
  const submittedFeedbackRows = assessment?.savedRows ?? {}
  const hasRows = allFindingIds.length > 0
  const allRowsHaveFeedback = hasRows && allFindingIds.every((id) => Boolean(submittedFeedbackRows[id]))
  const reviewedRows = allFindingIds.filter((id) => Boolean(submittedFeedbackRows[id])).length
  const pendingRows = Math.max(allFindingIds.length - reviewedRows, 0)
  const canGenerateNarrative = hasAnalysis && allRowsHaveFeedback
  const summaryText = assessment?.narrativeSummary ?? ''
  const narrativeSections = useMemo(() => parseNarrativeSections(summaryText), [summaryText])
  const hasStructuredNarrative = narrativeSections.length > 0

  const handleRegenerateNarrative = async () => {
    const id = assessmentId ?? assessment?.id
    if (!id) return
    setRegenerating(true)
    try {
      const job = await dispatch(
        runAnalysis({ id, request: { persona: 'RE', workflowId: 'RE_NARRATIVE' } })
      ).unwrap()
      if (job.workflowStatus === 'PENDING' || job.workflowStatus === 'IN_QUEUE') {
        const MAX_POLLS = 60
        const INTERVAL_MS = 5000
        let errors = 0
        for (let i = 0; i < MAX_POLLS; i++) {
          await new Promise((r) => setTimeout(r, INTERVAL_MS))
          try {
            const result = await dispatch(
              pollAnalysisStatus({ id, workflowId: job.workflowId })
            ).unwrap()
            errors = 0
            if (result.workflowStatus === 'COMPLETED' || result.workflowStatus === 'FAILED') break
          } catch {
            if (++errors >= 5) break
          }
        }
        await dispatch(fetchAssessment(id))
      }
    } catch (err) {
      console.warn('Narrative regeneration failed:', err)
    } finally {
      setRegenerating(false)
    }
  }

  const handleCopySummary = async () => {
    if (!summaryText) {
      setCopyFeedback({ severity: 'error', message: 'No summary content available to copy.' })
      return
    }

    try {
      const copyPayload = buildCopySummary(summaryText, narrativeSections)
      await copyTextWithFallback(copyPayload)
      setCopyFeedback({ severity: 'success', message: 'Executive summary copied to clipboard.' })
    } catch {
      setCopyFeedback({
        severity: 'error',
        message: 'Copy failed. Please check browser clipboard permissions and try again.',
      })
    }
  }

  return (
    <Box>
      {/* Section Header */}
      <Paper elevation={1} sx={{ p: 3, mb: 3, bgcolor: 'primary.50' }}>
        <Typography variant="h6" gutterBottom>
          Step 6: Narrative Summary
        </Typography>
        <Typography variant="body2" color="text.secondary">
          AI-generated executive summary synthesizing risk findings, user feedback, and
          recommendations.
        </Typography>
      </Paper>

      {/* No Analysis Warning */}
      {!hasAnalysis && (
        <Alert severity="info" icon={<Description />}>
          <AlertTitle>Narrative Not Available</AlertTitle>
          Complete the risk analysis (Step 3) first. After that, submit feedback on all findings,
          then generate the narrative summary from this panel.
        </Alert>
      )}

      {hasAnalysis && !allRowsHaveFeedback && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <AlertTitle>Feedback Required Before Narrative</AlertTitle>
          Narrative generation stays locked until review is complete for all output-table rows.
          {hasRows && (
            <> Currently reviewed: {reviewedRows} / {allFindingIds.length}. Remaining: {pendingRows}.</>
          )}
        </Alert>
      )}

      {/* Generating / pending state — analysis done but narrative not yet arrived */}
      {hasAnalysis && !hasNarrative && !regenerating && (
        <Paper elevation={2} sx={{ p: 3 }}>
          <Box display="flex" alignItems="center" gap={2} mb={2}>
            <AutoAwesome color="primary" />
            <Typography variant="body1" fontWeight={500}>Narrative Summary Not Generated Yet</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {canGenerateNarrative
              ? 'All finding rows have feedback. Generate the narrative summary now.'
              : 'Review must be completed for every output-table finding row before narrative generation can start.'}
          </Typography>
          {!canGenerateNarrative && (
            <Paper variant="outlined" sx={{ mt: 2, p: 2, bgcolor: 'warning.50', borderColor: 'warning.main' }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Waiting For Review Completion
              </Typography>
              <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
                <Chip size="small" label={`Reviewed ${reviewedRows} / ${allFindingIds.length}`} color="warning" />
                {pendingRows > 0 && (
                  <Chip size="small" label={`${pendingRows} rows remaining`} variant="outlined" color="warning" />
                )}
              </Box>
            </Paper>
          )}
          {(assessmentId ?? assessment?.id) && (
            <Box mt={2} display="flex" gap={1}>
              {!canGenerateNarrative && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    const section = document.getElementById('risk-analysis-section')
                    section?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}
                >
                  Go to Output Table Review
                </Button>
              )}
              <Button
                startIcon={<Refresh />}
                variant="outlined"
                size="small"
                onClick={() => {
                  const id = assessmentId ?? assessment?.id
                  if (id) void dispatch(fetchAssessment(id))
                }}
              >
                Check again
              </Button>
              <Button
                startIcon={<AutoAwesome />}
                variant="text"
                size="small"
                disabled={!canGenerateNarrative}
                onClick={() => { void handleRegenerateNarrative() }}
              >
                Generate Narrative Summary
              </Button>
            </Box>
          )}
        </Paper>
      )}

      {/* Narrative Display */}
      {hasAnalysis && (hasNarrative || regenerating) && (
        <Paper elevation={2} sx={{ p: 3 }}>
          {/* Action Bar */}
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box display="flex" gap={1} alignItems="center">
              <Description color="primary" />
              <Typography variant="h6">Executive Summary</Typography>
              {hasNarrative && (
                <Chip label="AI Generated" size="small" color="primary" variant="outlined" />
              )}
            </Box>
            <Box display="flex" gap={1}>
              {(assessmentId ?? assessment?.id) && (
                <Button
                  startIcon={<AutoAwesome />}
                  variant="outlined"
                  size="small"
                  disabled={regenerating || !canGenerateNarrative}
                  onClick={() => { void handleRegenerateNarrative() }}
                >
                  {regenerating ? 'Generating…' : 'Generate Narrative Summary'}
                </Button>
              )}
              <Button
                startIcon={<ContentCopy />}
                variant="outlined"
                size="small"
                disabled={!hasNarrative}
                onClick={() => { void handleCopySummary() }}
              >
                Copy
              </Button>
            </Box>
          </Box>

          {regenerating && <LinearProgress sx={{ mb: 2 }} />}

          <Divider sx={{ mb: 2 }} />

          {/* Narrative Content */}
          {hasNarrative && (
            hasStructuredNarrative ? (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '1fr',
                  gap: 2,
                }}
              >
                {narrativeSections.map((section) => (
                  <Paper
                    key={section.title}
                    variant="outlined"
                    sx={{
                      width: '100%',
                      p: 2,
                      borderRadius: 1.5,
                      bgcolor: 'background.paper',
                    }}
                  >
                    <Typography
                      variant="overline"
                      sx={{
                        color: 'primary.main',
                        fontWeight: 700,
                        letterSpacing: 0.4,
                      }}
                    >
                      {section.title}
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        mt: 0.5,
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.7,
                      }}
                    >
                      {section.content}
                    </Typography>
                  </Paper>
                ))}
              </Box>
            ) : (
              <Box
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  lineHeight: 1.8,
                  bgcolor: 'grey.50',
                  p: 3,
                  borderRadius: 1,
                  border: 1,
                  borderColor: 'divider',
                }}
              >
                {assessment.narrativeSummary}
              </Box>
            )
          )}

          {/* Info Footer */}
          <Alert severity="info" sx={{ mt: 2 }}>
            <AlertTitle>About This Summary</AlertTitle>
            This narrative was generated based on the risk assessment table, your feedback, and
            GE Vernova process standards. It includes:
            <ul style={{ marginTop: '8px', marginBottom: 0 }}>
              <li>Critical risk combinations identified through pattern analysis</li>
              <li>Prioritized findings with GE process document references</li>
              <li>Actionable recommendations aligned with reliability models</li>
              <li>Data quality notes highlighting gaps for follow-up</li>
            </ul>
          </Alert>
        </Paper>
      )}
      <Snackbar
        open={copyFeedback !== null}
        autoHideDuration={3000}
        onClose={() => setCopyFeedback(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setCopyFeedback(null)}
          severity={copyFeedback?.severity ?? 'success'}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {copyFeedback?.message ?? ''}
        </Alert>
      </Snackbar>
    </Box>
  )
}

export default NarrativeSummaryPanel
