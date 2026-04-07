import { useState, useEffect, useCallback, type SyntheticEvent } from 'react'
import {
  Box,
  Typography,
  Paper,
  Chip,
  TextField,
  InputAdornment,
  CircularProgress,
  Alert,
  Collapse,
  Divider,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  IconButton,
  Checkbox,
  Stepper,
  Step,
  StepLabel,
  Slide,
  type StepIconProps,
} from '@mui/material'
import {
  Search,
  ExpandMore,
  ExpandLess,
  Engineering,
  ElectricalServices,
  Speed,
  CheckCircle,
  Close,
  Lock,
  ArrowForward,
} from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { useEquipment } from '@/store'
import type { Train, Equipment } from '@/store/types'
import { WORKFLOW_STEPS } from '@/constants/workflow'

// ── Constants ─────────────────────────────────────────────────────────────────

const EQUIPMENT_TYPE_ICON: Record<string, React.ReactNode> = {
  'Gas Turbine': <Speed fontSize="small" />,
  Generator: <ElectricalServices fontSize="small" />,
  'Steam Turbine': <Engineering fontSize="small" />,
}

const EQUIPMENT_TYPE_COLOR: Record<
  Equipment['equipmentType'],
  'primary' | 'secondary' | 'default'
> = {
  'Gas Turbine': 'primary',
  Generator: 'secondary',
  'Steam Turbine': 'default',
}

const MILESTONE_OPTIONS = ['18-month', '12-month', '6-month'] as const
type Milestone = (typeof MILESTONE_OPTIONS)[number]

// ── Workflow Stepper ──────────────────────────────────────────────────────────

/**
 * Custom step icon that shows a Lock on the "AI Chat" step when it is future-
 * locked (i.e. the user has not yet completed the assessment).
 */
function WorkflowStepIcon(props: StepIconProps & { lockable?: boolean; activeStep: number }) {
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

interface AssessmentStepperProps {
  activeStep: number
}

function AssessmentStepper({ activeStep }: AssessmentStepperProps) {
  return (
    <Paper variant="outlined" sx={{ px: 3, py: 2, mb: 3 }}>
      <Typography variant="overline" color="text.secondary" display="block" sx={{ mb: 1.5, letterSpacing: 1.2 }}>
        Assessment Workflow
      </Typography>
      <Stepper activeStep={activeStep} alternativeLabel connector={<></>}>
        {WORKFLOW_STEPS.map((step, i) => (
          <Step key={step.label} completed={activeStep > i}>
            <StepLabel
              StepIconComponent={(p) => (
                <WorkflowStepIcon {...p} lockable={step.lockable} activeStep={activeStep} />
              )}
              sx={{
                '& .MuiStepLabel-label': {
                  fontSize: '0.75rem',
                  mt: 0.5,
                  color: activeStep === i ? 'primary.main' : activeStep > i ? 'success.main' : 'text.disabled',
                  fontWeight: activeStep === i ? 700 : 400,
                },
                '& .MuiStepLabel-labelContainer .MuiTypography-caption': {
                  display: 'block',
                },
              }}
            >
              {step.label}
              <Typography variant="caption" color="text.disabled" display="block" sx={{ mt: 0.25 }}>
                {step.description}
              </Typography>
            </StepLabel>
          </Step>
        ))}
      </Stepper>
    </Paper>
  )
}

// ── Equipment Row ─────────────────────────────────────────────────────────────

interface EquipmentRowProps {
  equipment: Equipment
  checked: boolean
  onToggle: (eq: Equipment, checked: boolean) => void
}

function EquipmentRow({ equipment, checked, onToggle }: EquipmentRowProps) {
  const handleClick = (e: SyntheticEvent) => {
    e.stopPropagation()
    onToggle(equipment, !checked)
  }

  return (
    <Box
      onClick={handleClick}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        py: 1.5,
        px: 2,
        borderRadius: 1,
        cursor: 'pointer',
        bgcolor: checked ? 'primary.50' : 'background.default',
        border: '1.5px solid',
        borderColor: checked ? 'primary.main' : 'transparent',
        '&:hover': {
          bgcolor: checked ? 'primary.50' : 'action.hover',
          borderColor: checked ? 'primary.main' : 'divider',
        },
        '&:not(:last-child)': { mb: 1 },
        transition: 'all 0.15s',
      }}
    >
      <Checkbox
        checked={checked}
        size="small"
        color="primary"
        onClick={(e) => e.stopPropagation()}
        onChange={(_, c) => onToggle(equipment, c)}
        sx={{ p: 0.25 }}
      />
      <Box sx={{ color: checked ? 'primary.main' : 'text.secondary', display: 'flex', alignItems: 'center' }}>
        {EQUIPMENT_TYPE_ICON[equipment.equipmentType] ?? <Engineering fontSize="small" />}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          fontWeight={700}
          noWrap
          sx={{ fontFamily: 'monospace', color: checked ? 'primary.main' : 'text.primary' }}
        >
          {equipment.serialNumber}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {equipment.equipmentType} · {equipment.model} · {equipment.totalEOH?.toLocaleString('en-US') ?? '—'} EOH ·{' '}
          {equipment.totalStarts?.toLocaleString('en-US') ?? '—'} starts
        </Typography>
      </Box>
      <Chip
        label={equipment.equipmentCode}
        size="small"
        variant="outlined"
        color={checked ? 'primary' : 'default'}
        sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}
      />
    </Box>
  )
}

// ── Unit Card ─────────────────────────────────────────────────────────────────

interface UnitCardProps {
  unit: Train
  selectedEquipments: Map<string, Equipment>
  onToggle: (eq: Equipment, checked: boolean) => void
}

function UnitCard({ unit, selectedEquipments, onToggle }: UnitCardProps) {
  const [expanded, setExpanded] = useState(false)

  const checkedInUnit = unit.equipment.filter((eq) => selectedEquipments.has(eq.serialNumber))
  const hasSelection = checkedInUnit.length > 0

  return (
    <Paper
      variant="outlined"
      sx={{
        mb: 2,
        overflow: 'hidden',
        borderColor: hasSelection ? 'primary.light' : 'divider',
        transition: 'border-color 0.15s',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: 3,
          py: 2,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'action.hover' },
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5, flexWrap: 'wrap' }}>
            <Typography variant="h6" fontWeight={600}>{unit.trainName}</Typography>
            {unit.trainType && (
              <Chip label={unit.trainType} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
            )}
            {hasSelection && (
              <Chip
                label="selected"
                size="small"
                color="primary"
                sx={{ fontWeight: 600 }}
              />
            )}
          </Box>
          <Stack direction="row" spacing={3} flexWrap="wrap">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Engineering sx={{ fontSize: 14, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">{unit.site}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              {unit.equipment.length} component{unit.equipment.length !== 1 ? 's' : ''}
            </Typography>
          </Stack>
        </Box>

        <IconButton size="small" sx={{ ml: 1 }}>
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <Divider />
        <Box sx={{ px: 3, py: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
            Select one component for the assessment
          </Typography>
          {unit.equipment.map((eq) => (
            <EquipmentRow
              key={eq.serialNumber}
              equipment={eq}
              checked={selectedEquipments.has(eq.serialNumber)}
              onToggle={onToggle}
            />
          ))}
        </Box>
      </Collapse>
    </Paper>
  )
}

// ── ESN Result Card ───────────────────────────────────────────────────────────

interface EsnResultCardProps {
  equipment: Equipment
  checked: boolean
  onToggle: (eq: Equipment, checked: boolean) => void
  onDismiss: () => void
}

function EsnResultCard({ equipment, checked, onToggle, onDismiss }: EsnResultCardProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        mb: 3,
        overflow: 'hidden',
        border: '1.5px solid',
        borderColor: checked ? 'primary.main' : 'primary.light',
      }}
    >
      <Box
        sx={{
          px: 3,
          py: 1.5,
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <CheckCircle fontSize="small" />
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          ESN Match — {equipment.serialNumber}
        </Typography>
        <IconButton size="small" onClick={onDismiss} sx={{ color: 'inherit' }}>
          <Close fontSize="small" />
        </IconButton>
      </Box>

      <Box sx={{ px: 3, py: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 2 }}>
          <Box sx={{ color: 'primary.main', pt: 0.25 }}>
            {EQUIPMENT_TYPE_ICON[equipment.equipmentType] ?? <Engineering />}
          </Box>
          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
              <Chip label={equipment.equipmentType} size="small" color={EQUIPMENT_TYPE_COLOR[equipment.equipmentType]} />
              <Chip label={equipment.model} size="small" variant="outlined" />
              <Chip label={equipment.equipmentCode} size="small" variant="outlined" sx={{ fontFamily: 'monospace' }} />
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 1.5 }}>
              {[
                { label: 'Site', value: equipment.site },
                {
                  label: 'Comm. Op.',
                  value: new Date(equipment.commercialOpDate).toLocaleDateString('en-US', {
                    month: 'short',
                    year: 'numeric',
                  }),
                },
                { label: 'EOH', value: equipment.totalEOH?.toLocaleString('en-US') ?? '—' },
                { label: 'Starts', value: equipment.totalStarts?.toLocaleString('en-US') ?? '—' },
                ...(equipment.coolingType ? [{ label: 'Cooling', value: equipment.coolingType }] : []),
              ].map(({ label, value }) => (
                <Box key={label}>
                  <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                  <Typography variant="body2" fontWeight={600}>{value}</Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        <Divider sx={{ mb: 2 }} />

        <Stack direction="row" spacing={1.5} alignItems="center">
          <Checkbox
            checked={checked}
            onChange={(_, c) => onToggle(equipment, c)}
            size="small"
            color="primary"
          />
          <Typography variant="body2" color="text.secondary">
            {checked ? 'Added to selection — set milestone in bar below' : 'Select for assessment'}
          </Typography>
        </Stack>
      </Box>
    </Paper>
  )
}

// ── Selection Action Bar ──────────────────────────────────────────────────────

interface SelectionActionBarProps {
  selectedEquipments: Map<string, Equipment>
  milestone: Milestone
  onMilestoneChange: (m: Milestone) => void
  onDeselect: (esn: string) => void
  onBeginAssessment: () => void
}

function SelectionActionBar({
  selectedEquipments,
  milestone,
  onMilestoneChange,
  onDeselect,
  onBeginAssessment,
}: SelectionActionBarProps) {
  const count = selectedEquipments.size
  const show = count > 0
  const selectedEquipment = Array.from(selectedEquipments.values())[0]

  return (
    <Slide direction="up" in={show} mountOnEnter unmountOnExit>
      <Paper
        elevation={8}
        sx={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 1200,
          borderTop: '2px solid',
          borderColor: 'primary.main',
          borderRadius: 0,
        }}
      >
        <Box
          sx={{
            px: { xs: 2, sm: 4 },
            py: 2,
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            alignItems: { xs: 'flex-start', sm: 'center' },
            maxWidth: '100%',
          }}
        >
          {/* Count + selected preview */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.75 }}>
              {count} component{count !== 1 ? 's' : ''} selected for assessment
            </Typography>
            {selectedEquipment && (
              <Chip
                label={selectedEquipment.serialNumber}
                color="primary"
                variant="outlined"
                onDelete={() => onDeselect(selectedEquipment.serialNumber)}
                sx={{
                  height: 40,
                  '& .MuiChip-label': {
                    pl: 2,
                    pr: 1.25,
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    lineHeight: 1,
                  },
                  '& .MuiChip-deleteIcon': {
                    mr: 1.25,
                    ml: 0,
                  },
                }}
              />
            )}
          </Box>

          {/* Milestone + CTA */}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center" flexShrink={0}>
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Review Period</InputLabel>
              <Select
                value={milestone}
                label="Review Period"
                onChange={(e) => onMilestoneChange(e.target.value)}
              >
                {MILESTONE_OPTIONS.map((m) => (
                  <MenuItem key={m} value={m}>
                    {m} milestone
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              size="large"
              endIcon={<ArrowForward />}
              onClick={onBeginAssessment}
              sx={{ whiteSpace: 'nowrap', px: 3 }}
            >
              Begin Assessment
            </Button>
          </Stack>
        </Box>
      </Paper>
    </Slide>
  )
}

// ── Units Page ────────────────────────────────────────────────────────────────

/**
 * UnitsPage — Step 1 of the Reliability Engineer assessment workflow.
 *
 * • Browse/search trains and select equipment via checkboxes.
 * • ESN lookup (Enter key) adds found equipment directly to the selection.
 * • Global milestone picker + "Begin Assessment" in the sticky action bar.
 * • Horizontal workflow stepper shows the full 4-step journey with AI Chat
 *   locked until an assessment is completed.
 */
const UnitsPage = () => {
  const navigate = useNavigate()

  const { trains, error, loadTrains, searchEquipment, selectedEquipment, clearSelection } =
    useEquipment()

  const [searchText, setSearchText] = useState('')
  const [esnLoading, setEsnLoading] = useState(false)
  const [esnNotFound, setEsnNotFound] = useState(false)
  const [hasLoaded, setHasLoaded] = useState(false)

  // Selection state
  const [selectedEquipments, setSelectedEquipments] = useState<Map<string, Equipment>>(new Map())
  const [milestone, setMilestone] = useState<Milestone>('18-month')

  // Load all trains once on mount — filtering is done client-side so typing
  // in the search box never triggers an additional API call.
  useEffect(() => {
    void loadTrains('all').finally(() => setHasLoaded(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Clear ESN banner when search text changes
  useEffect(() => {
    if (selectedEquipment || esnNotFound) {
      clearSelection()
      setEsnNotFound(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText])

  const handleSearchKey = async (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter' || !searchText.trim()) return
    setEsnLoading(true)
    setEsnNotFound(false)
    try {
      const result = await searchEquipment(searchText.trim().toUpperCase())
      if ((result as { error?: unknown }).error) setEsnNotFound(true)
    } catch {
      setEsnNotFound(true)
    } finally {
      setEsnLoading(false)
    }
  }

  const handleToggleEquipment = useCallback((eq: Equipment, checked: boolean) => {
    setSelectedEquipments((prev) => {
      const next = new Map(prev)
      if (checked) {
        next.clear()
        next.set(eq.serialNumber, eq)
      } else next.delete(eq.serialNumber)
      return next
    })
  }, [])

  const handleDeselect = useCallback((esn: string) => {
    setSelectedEquipments((prev) => {
      const next = new Map(prev)
      next.delete(esn)
      return next
    })
  }, [])

  const handleDismissEsn = () => {
    clearSelection()
    setEsnNotFound(false)
  }

  const handleBeginAssessment = useCallback(() => {
    const first = Array.from(selectedEquipments.values())[0]
    if (!first) return
    void navigate(`/unit?esn=${encodeURIComponent(first.serialNumber)}&review_period=${milestone}`)
  }, [selectedEquipments, milestone, navigate])

  const hasSelection = selectedEquipments.size > 0

  return (
    // Extra bottom padding so content isn't hidden behind the action bar
    <Box sx={{ pb: hasSelection ? 14 : 0 }}>

      {/* ── Page Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" fontWeight={700} gutterBottom>
          Units
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Select equipment below to start a reliability assessment.
          Enter an ESN and press Enter to look up a specific component.
        </Typography>
      </Box>

      {/* ── Workflow Stepper (step 0 active) */}
      <AssessmentStepper activeStep={0} />

      {/* ── Search Bar */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Search by unit name, site, or ESN — press Enter for ESN lookup"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onKeyDown={(e) => { void handleSearchKey(e) }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  {esnLoading ? (
                    <CircularProgress size={16} />
                  ) : (
                    <Search fontSize="small" />
                  )}
                </InputAdornment>
              ),
              endAdornment: searchText ? (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => {
                      setSearchText('')
                      handleDismissEsn()
                    }}
                  >
                    <Close fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ) : undefined,
            },
          }}
        />
      </Paper>

      {/* ── ESN not-found notice */}
      {esnNotFound && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={handleDismissEsn}>
          No equipment found for ESN <strong>{searchText.trim().toUpperCase()}</strong>.
        </Alert>
      )}

      {/* ── ESN match result */}
      {selectedEquipment && (
        <EsnResultCard
          equipment={selectedEquipment}
          checked={selectedEquipments.has(selectedEquipment.serialNumber)}
          onToggle={handleToggleEquipment}
          onDismiss={handleDismissEsn}
        />
      )}

      {/* ── Unit list loading */}
      {!hasLoaded && (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {hasLoaded && !error && (
        <>
          {trains.length === 0 ? (
            <Paper variant="outlined" sx={{ py: 6, textAlign: 'center' }}>
              <Typography color="text.secondary">No units found.</Typography>
            </Paper>
          ) : (
            <>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  {trains.length} unit{trains.length !== 1 ? 's' : ''} found
                </Typography>
              </Stack>
              {trains.map((unit) => (
                <UnitCard
                  key={unit.id}
                  unit={unit}
                  selectedEquipments={selectedEquipments}
                  onToggle={handleToggleEquipment}
                />
              ))}
            </>
          )}
        </>
      )}

      {/* ── Sticky Selection Action Bar */}
      <SelectionActionBar
        selectedEquipments={selectedEquipments}
        milestone={milestone}
        onMilestoneChange={setMilestone}
        onDeselect={handleDeselect}
        onBeginAssessment={handleBeginAssessment}
      />
    </Box>
  )
}

export default UnitsPage
