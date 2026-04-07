import { useRef, useState } from 'react'
import {
  TableRow,
  TableCell,
  Chip,
  IconButton,
  TextField,
  Select,
  MenuItem,
  Box,
  Tooltip,
  FormControl,
  InputLabel,
  Popover,
  Typography,
} from '@mui/material'
import { Save, Cancel, CheckCircle, ThumbUp, ThumbDown, CheckCircleOutline } from '@mui/icons-material'
import type { RiskCondition } from '@/store/types'
import { useAppDispatch } from '@/store'
import { submitFeedback } from '@/store/slices/assessmentsSlice'

interface RiskConditionRowProps {
  condition: RiskCondition
  assessmentId: string
  savedTimestamp?: string
  editable: boolean
  getRiskColor: (risk: string) => 'error' | 'warning' | 'success' | 'default'
  getStatusColor: (status: string) => 'error' | 'warning' | 'success' | 'info' | 'default'
}

// ── Citation chips: primary inline + "+N more" popover ────────────────────────

function CitationChips({ condition }: { condition: RiskCondition }) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const extra = condition.additionalCitations ?? []
  const label = `${condition.dataSource} · ${condition.primaryCitation}`

  return (
    <Box display="flex" alignItems="center" gap={0.5} mt={0.5} flexWrap="wrap">
      <Tooltip title={`Source: ${condition.dataSource} | ${condition.primaryCitation}`}>
        <Chip
          label={label}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.7rem', maxWidth: 260 }}
        />
      </Tooltip>
      {extra.length > 0 && (
        <>
          <Chip
            label={`+${extra.length} more`}
            size="small"
            variant="outlined"
            color="default"
            onClick={(e) => setAnchorEl(e.currentTarget)}
            sx={{ fontSize: '0.7rem', cursor: 'pointer' }}
          />
          <Popover
            open={Boolean(anchorEl)}
            anchorEl={anchorEl}
            onClose={() => setAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          >
            <Box sx={{ p: 2, maxWidth: 360 }}>
              <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                All citations
              </Typography>
              <Box display="flex" flexDirection="column" gap={0.5}>
                <Typography variant="body2" sx={{ fontSize: '0.78rem' }}>
                  1. {condition.primaryCitation}
                </Typography>
                {extra.map((c, i) => (
                  <Typography key={i} variant="body2" sx={{ fontSize: '0.78rem' }}>
                    {i + 2}. {c}
                  </Typography>
                ))}
              </Box>
            </Box>
          </Popover>
        </>
      )}
    </Box>
  )
}

// ── Main row component ─────────────────────────────────────────────────────────

/**
 * Risk Condition Row - Step 5 Editing
 * 
 * Individual condition row with edit functionality
 * Allows editing risk level, status, and evidence
 */
const RiskConditionRow = ({
  condition,
  assessmentId,
  savedTimestamp,
  editable,
  getRiskColor,
  getStatusColor,
}: RiskConditionRowProps) => {
  const dispatch = useAppDispatch()
  const [showFeedbackSaved, setShowFeedbackSaved] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(condition.feedback ?? null)
  const [feedbackReason, setFeedbackReason] = useState(condition.comments ?? '')
  const [feedbackRiskLevel, setFeedbackRiskLevel] = useState<'' | 'High' | 'Medium' | 'Low'>(
    (condition.feedbackType as '' | 'High' | 'Medium' | 'Low') ?? ''
  )
  const [negativeFeedbackAnchorEl, setNegativeFeedbackAnchorEl] = useState<HTMLElement | null>(
    null
  )
  const [savingFeedback, setSavingFeedback] = useState(false)
  const savingInFlight = useRef(false)
  // Tracks whether down feedback has been saved in this session (or came from props).
  // Once true, cancel/escape must not revert the thumbs-down visual state.
  const hasSavedDown = useRef(condition.feedback === 'down')
  // Last successfully-saved values — used to repopulate the popover on reopen
  // before Redux has propagated the updated condition props.
  const lastSavedRiskLevel = useRef<'' | 'High' | 'Medium' | 'Low'>(
    (condition.feedbackType as '' | 'High' | 'Medium' | 'Low') ?? ''
  )
  const lastSavedReason = useRef(condition.comments ?? '')
  const feedbackReasonInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null)
  const isNegativeFeedbackSaveDisabled = savingFeedback || feedbackRiskLevel === ''

  const handleFeedbackRiskLevelChange = (value: '' | 'High' | 'Medium' | 'Low') => {
    setFeedbackRiskLevel(value)
    setTimeout(() => {
      feedbackReasonInputRef.current?.focus()
    }, 0)
  }

  const handleFeedbackReasonKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || isNegativeFeedbackSaveDisabled) {
      return
    }
    event.preventDefault()
    void handleSaveFeedback('down')
  }

  const handleFeedbackClick = (
    selectedFeedback: 'up' | 'down',
    anchorEl?: HTMLElement | null
  ) => {
    if (selectedFeedback === 'down') {
      setFeedback('down')
      // Restore from last-saved refs so the popover shows what was saved
      // even if Redux hasn't propagated the updated condition props yet.
      setFeedbackRiskLevel(lastSavedRiskLevel.current)
      setFeedbackReason(lastSavedReason.current)
      setNegativeFeedbackAnchorEl(anchorEl ?? null)
      return
    }

    setFeedback('up')
    setNegativeFeedbackAnchorEl(null)
    setFeedbackReason('')
    void handleSaveFeedback('up')
  }

  const handleSaveFeedback = async (selectedFeedback: 'up' | 'down') => {
    if (savingInFlight.current) return
    savingInFlight.current = true
    setSavingFeedback(true)
    try {
      const IS_DOWN = selectedFeedback === 'down'
      await dispatch(
        submitFeedback({
          assessmentId,
          findingId: condition.findingId,
          feedback: {
            feedback: selectedFeedback,
            comments: IS_DOWN ? feedbackReason : '',
            ...(IS_DOWN ? { feedbackType: feedbackRiskLevel as 'High' | 'Medium' | 'Low' } : {}),
          },
        })
      ).unwrap()
      if(IS_DOWN) {
        hasSavedDown.current = true
        lastSavedRiskLevel.current = feedbackRiskLevel
        lastSavedReason.current = feedbackReason
        setShowFeedbackSaved(true)
        setTimeout(() => setShowFeedbackSaved(false), 2000)
      }
      if (selectedFeedback === 'down') {
        setNegativeFeedbackAnchorEl(null)
      }
    } catch (error) {
      console.error('Failed to save feedback:', error)
    } finally {
      savingInFlight.current = false
      setSavingFeedback(false)
    }
  }

  const handleCancelNegativeFeedback = () => {
    setNegativeFeedbackAnchorEl(null)
    // Restore from last-saved refs, not stale condition props.
    setFeedbackRiskLevel(lastSavedRiskLevel.current)
    setFeedbackReason(lastSavedReason.current)
    // Only revert the thumb visual if down has never been saved — once saved it's
    // permanent (no API undo exists) so the button must stay highlighted.
    if (!hasSavedDown.current) {
      setFeedback(condition.feedback ?? null)
    }
  }

  return (
    <TableRow
      sx={{
        '&:hover': { bgcolor: 'grey.50' },
        bgcolor: 'inherit',
      }}
    >
      {/* Issue name (Finding ID in tooltip) */}
      <TableCell>
        <Tooltip title={`Finding ID: ${condition.findingId}`}>
          <span style={{ fontSize: '0.875rem' }}>{condition.issueName || condition.condition}</span>
        </Tooltip>
      </TableCell>

      {/* Category */}
      <TableCell>
        <Tooltip title={condition.category}>
          <span style={{ fontSize: '0.875rem' }}>{condition.category}</span>
        </Tooltip>
      </TableCell>

      {/* Condition */}
      <TableCell>
        <Tooltip title={condition.condition}>
          <span
            style={{
              fontSize: '0.875rem',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {condition.condition}
          </span>
        </Tooltip>
      </TableCell>

      {/* Actual Value */}
      <TableCell>
        <strong>{condition.actualValue}</strong>
      </TableCell>

      {/* Risk Level */}
      <TableCell>
        <Box display="flex" flexDirection="column" gap={0.5} alignItems="flex-start">
          <Chip
            label={condition.riskLevel}
            color={getRiskColor(condition.riskLevel)}
            size="small"
          />
          {feedback === 'down' && feedbackRiskLevel && (
            <Tooltip
              title={
                feedbackReason
                  ? `Corrected by reviewer — Comment: ${feedbackReason}`
                  : 'Corrected by reviewer'
              }
            >
              <Chip
                label={`Corrected: ${feedbackRiskLevel}`}
                color={getRiskColor(feedbackRiskLevel)}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.7rem' }}
              />
            </Tooltip>
          )}
        </Box>
      </TableCell>

      {/* Status */}
      <TableCell>
        <Chip
          label={condition.status.replace('-', ' ').toUpperCase()}
          color={getStatusColor(condition.status)}
          size="small"
        />
      </TableCell>

      {/* Evidence & Justification */}
      <TableCell>
        <Box>
          <Tooltip title={condition.justification}>
            <span style={{ fontSize: '0.875rem', display: 'block' }}>
              {condition.evidence}
            </span>
          </Tooltip>
          {condition.comments && (
            <span
              style={{
                fontSize: '0.75rem',
                color: 'text.secondary',
                fontStyle: 'italic',
                display: 'block',
                marginTop: '4px',
              }}
            >
              Note: {condition.comments}
            </span>
          )}
          <CitationChips condition={condition} />
        </Box>
      </TableCell>

      {/* Actions */}
      {editable && (
        <TableCell>
          <Box display="flex" gap={0.5} alignItems="center">
            <Tooltip title={feedback === 'down' ? 'Negative feedback already saved' : 'Mark feedback as helpful'}>
              <span>
                <IconButton
                  size="small"
                  color={feedback === 'up' ? 'success' : 'primary'}
                  aria-label="Thumbs up feedback"
                  onClick={() => {
                    void handleFeedbackClick('up')
                  }}
                  disabled={savingFeedback || feedback === 'down'}
                >
                  <ThumbUp fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Mark feedback as not helpful">
              {showFeedbackSaved ? (
                <Box
                  sx={{
                    width: 30,
                    height: 30,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <CheckCircleOutline
                    fontSize="small"
                    color="success"
                    aria-label="Negative feedback saved"
                  />
                </Box>
              ) : (
                <IconButton
                  size="small"
                  color={feedback === 'down' ? 'error' : 'primary'}
                  aria-label="Thumbs down feedback"
                  onClick={(event) => handleFeedbackClick('down', event.currentTarget)}
                  disabled={savingFeedback}
                >
                  <ThumbDown fontSize="small" />
                </IconButton>
              )}
            </Tooltip>
            {savedTimestamp && (
              <Tooltip
                title={`Last saved: ${new Date(savedTimestamp).toLocaleString()}`}
              >
                <CheckCircle fontSize="small" sx={{ color: 'grey.400' }} />
              </Tooltip>
            )}
          </Box>
        </TableCell>
      )}
      <Popover
        open={feedback === 'down' && Boolean(negativeFeedbackAnchorEl)}
        anchorEl={negativeFeedbackAnchorEl}
        onClose={handleCancelNegativeFeedback}
        transitionDuration={0}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <Box sx={{ width: 320, p: 2 }}>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
            Feedback for {condition.findingId}
          </Typography>
          <FormControl size="small" fullWidth required sx={{ mb: 1 }}>
            <InputLabel id={`feedback-risk-level-label-${condition.findingId}`}>Risk Level</InputLabel>
            <Select
              labelId={`feedback-risk-level-label-${condition.findingId}`}
              value={feedbackRiskLevel}
              label="Risk Level"
              onChange={(event) =>
                handleFeedbackRiskLevelChange(event.target.value as '' | 'High' | 'Medium' | 'Low')
              }
            >
              <MenuItem value="High">High</MenuItem>
              <MenuItem value="Medium">Medium</MenuItem>
              <MenuItem value="Low">Low</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            multiline
            minRows={3}
            fullWidth
            label="Reason"
            placeholder="Add reason for negative feedback..."
            value={feedbackReason}
            onChange={(event) => setFeedbackReason(event.target.value)}
            onKeyDown={handleFeedbackReasonKeyDown}
            inputRef={feedbackReasonInputRef}
          />
          <Box display="flex" justifyContent="flex-end" gap={0.5} mt={1}>
            <Tooltip title="Save feedback">
              <span>
                <IconButton
                  size="small"
                  color="primary"
                  aria-label="Save negative feedback"
                  onClick={() => {
                    void handleSaveFeedback('down')
                  }}
                  disabled={isNegativeFeedbackSaveDisabled}
                >
                  <Save fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Cancel negative feedback">
              <IconButton
                size="small"
                color="default"
                aria-label="Cancel negative feedback"
                onClick={handleCancelNegativeFeedback}
                disabled={savingFeedback}
              >
                <Cancel fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Popover>
    </TableRow>
  )
}

export default RiskConditionRow
