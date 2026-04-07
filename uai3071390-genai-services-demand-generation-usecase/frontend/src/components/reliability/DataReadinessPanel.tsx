import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import {
  Box,
  Typography,
  Paper,
  LinearProgress,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Stack,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import {
  ArrowForward,
  Storage,
  Article,
  Build,
  History,
  ModelTraining,
  FolderOpen,
  Info,
  ExpandMore,
} from '@mui/icons-material'
import type { Assessment } from '@/store/types'
import { useAppDispatch, useAppSelector } from '@/store'
import {
  fetchDataReadiness,
  fetchERCases,
  fetchFSRReports,
  fetchOutageHistory,
  selectERCases,
  selectFSRReports,
  selectOutageHistory,
  selectERCasesPagination,
  selectFSRReportsPagination,
  selectOutageHistoryPagination,
  selectDataReadiness,
  selectDocumentsLoading,
} from '@/store/slices/documentsSlice'
import {
  CASE_SOURCE_IDS,
  type CaseSourceId,
} from './dataReadinessUtils'

interface DataReadinessPanelProps {
  assessment: Assessment | null
  esn?: string
  /** Called when the user applies or clears the date filter. */
  onFiltersApplied?: (dateFrom: string, dateTo: string) => void
  /** Called whenever the set of checked data sources changes. */
  onDataTypesSelected?: (types: string[]) => void
}

interface DataSource {
  id: string
  name: string
  nativelyAvailable: boolean
  count?: number
  description: string
  icon: React.ReactNode
}

interface UploadedFile {
  id: string
  name: string
  category: string
  size: number
  uploadedAt: string
}

interface PreviewRecord {
  id: string
  sourceId: CaseSourceId
  date: string
  caseId?: string
  description?: string
  closeNotes?: string
  caseSummary?: string
  title?: string
  outage?: string
  outageSummary?: string
}

const BASE_SOURCES: Omit<DataSource, 'nativelyAvailable' | 'icon'>[] = [
  {
    id: 'install-base',
    name: 'Install Base Data',
    count: undefined,
    description: 'Unit metadata, COD, EOH, starts, configuration',
  },
  {
    id: 'er-cases',
    name: 'ER Cases',
    count: undefined,
    description: 'Engineering Review cases with severity classifications',
  },
  {
    id: 'fsr-reports',
    name: 'FSR Reports',
    count: undefined,
    description: 'Field Service Reports with test results and findings',
  },
  {
    id: 'outage-history',
    name: 'Outage History',
    count: undefined,
    description: 'Past outage events and component-level findings',
  },
  {
    id: 'rel-models',
    name: 'Reliability Models',
    count: undefined,
    description: 'GE Vernova reliability models and risk thresholds',
  },
]

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  'install-base': <Storage fontSize="small" />,
  'er-cases': <Article fontSize="small" />,
  'fsr-reports': <Build fontSize="small" />,
  'outage-history': <History fontSize="small" />,
  'rel-models': <ModelTraining fontSize="small" />,
  uploaded: <FolderOpen fontSize="small" />,
}

const INITIAL_AVAILABILITY: Record<string, boolean> = {
  'install-base': true,
  'er-cases': true,
  'fsr-reports': true,
  'outage-history': false,
  'rel-models': true,
}

const READINESS_KEY_MAP: Record<string, string> = {
  'install-base': 'ibatData',
  'er-cases': 'erCases',
  'fsr-reports': 'fsrReports',
  'outage-history': 'outageHistory',
  'rel-models': 'prismData',
}

/**
 * Data Readiness Panel - Step 2
 *
 * Shows all available data sources and preview tables used in review.
 *
 * The backend payload and selected-data state are preserved, but selection and
 * date-range controls are intentionally hidden in this UX variant.
 *
 * Uploaded documents automatically appear as an additional row.
 */
const DataReadinessPanel = ({ assessment, esn: esnProp, onDataTypesSelected }: DataReadinessPanelProps) => {
  const dispatch = useAppDispatch()
  const esn = esnProp ?? assessment?.serialNumber ?? ''
  const uploadedFiles: UploadedFile[] = assessment?.uploadedDocs ?? []

  // Date filter values are preserved for payload compatibility, but controls are hidden.
  const [appliedStart] = useState('')
  const [appliedEnd] = useState('')

  const [expandedPreviews, setExpandedPreviews] = useState<Set<string>>(new Set())
  // Track which case sources have already been fetched (to avoid re-fetching)
  const [fetchedSources, setFetchedSources] = useState<Set<string>>(new Set())
  // Track which case sources are currently loading
  const [loadingSources, setLoadingSources] = useState<Set<string>>(new Set())

  const fetchReadiness = useCallback((startDate?: string, endDate?: string) => {
    if (!esn) return
    void dispatch(fetchDataReadiness({ esn, startDate, endDate }))
    // Reset fetched-detail tracking when readiness is re-fetched
    setFetchedSources(new Set())
  }, [esn, dispatch])

  // Initial load — fetch data readiness summary (counts only)
  useEffect(() => {
    fetchReadiness()
  }, [fetchReadiness])

  const docsLoading = useAppSelector(selectDocumentsLoading)
  const dataReadiness = useAppSelector(selectDataReadiness(esn))
  const erCases = useAppSelector(selectERCases(esn))
  const fsrReports = useAppSelector(selectFSRReports(esn))
  const outageHistory = useAppSelector(selectOutageHistory(esn))
  const erPagination = useAppSelector(selectERCasesPagination(esn))
  const fsrPagination = useAppSelector(selectFSRReportsPagination(esn))
  const outagePagination = useAppSelector(selectOutageHistoryPagination(esn))

  // Track which sources are loading more (next page)
  const [loadingMore, setLoadingMore] = useState<Set<string>>(new Set())
  const tableContainerRefs = useRef<Record<string, HTMLDivElement | null>>({})

  const getPagination = useCallback((sourceId: string) => {
    if (sourceId === 'er-cases') return erPagination
    if (sourceId === 'fsr-reports') return fsrPagination
    if (sourceId === 'outage-history') return outagePagination
    return null
  }, [erPagination, fsrPagination, outagePagination])

  const handleLoadMore = useCallback((sourceId: string) => {
    const pagination = getPagination(sourceId)
    if (!pagination || !pagination.hasMore || loadingMore.has(sourceId) || !esn) return

    const nextPage = pagination.page + 1
    const dateArgs = { esn, startDate: appliedStart || undefined, endDate: appliedEnd || undefined, page: nextPage }

    setLoadingMore((prev) => new Set(prev).add(sourceId))

    let promise: Promise<unknown> | undefined
    if (sourceId === 'er-cases') promise = dispatch(fetchERCases(dateArgs))
    if (sourceId === 'fsr-reports') promise = dispatch(fetchFSRReports(dateArgs))
    if (sourceId === 'outage-history') promise = dispatch(fetchOutageHistory(dateArgs))

    if (promise) {
      void promise.finally(() => {
        setLoadingMore((prev) => {
          const next = new Set(prev)
          next.delete(sourceId)
          return next
        })
      })
    }
  }, [getPagination, loadingMore, esn, appliedStart, appliedEnd, dispatch])

  const handleTableScroll = useCallback((sourceId: string) => (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    if (nearBottom) {
      handleLoadMore(sourceId)
    }
  }, [handleLoadMore])

  // Auto-load next page when the table content doesn't overflow the container
  useEffect(() => {
    for (const sourceId of expandedPreviews) {
      const pagination = getPagination(sourceId)
      if (!pagination?.hasMore || loadingMore.has(sourceId)) continue
      const container = tableContainerRefs.current[sourceId]
      if (container && container.scrollHeight <= container.clientHeight) {
        handleLoadMore(sourceId)
      }
    }
  }, [expandedPreviews, getPagination, loadingMore, handleLoadMore, erCases, fsrReports, outageHistory])

  // Checked state: default = natively available sources + uploaded (if any)
  const [checked] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    BASE_SOURCES.forEach((s) => {
      if (INITIAL_AVAILABILITY[s.id]) initial.add(s.id)
    })
    return initial
  })

  // Notify parent whenever checked sources change
  useEffect(() => {
    onDataTypesSelected?.([...checked])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checked])

  // Build preview records from already-fetched detail data
  const previewData = useMemo<Record<CaseSourceId, PreviewRecord[]>>(() => ({
    'er-cases': erCases.map((c) => ({
      id: c.erNumber,
      sourceId: 'er-cases' as const,
      caseId: c.erNumber,
      description: c.description ?? c.title,
      closeNotes: c.resolution ?? (c.status === 'Closed' ? 'Closed without additional notes.' : 'Resolution pending.'),
      date: c.dateReported,
      caseSummary: c.summary ?? c.description ?? '',
    })),
    'fsr-reports': fsrReports.map((r) => ({
      id: r.reportId,
      sourceId: 'fsr-reports' as const,
      title: r.title,
      date: r.outageDate ?? r.dateCompleted ?? '',
      outage: r.outageType ?? 'Planned',
      outageSummary: r.findings || r.recommendation || '',
    })),
    'outage-history': outageHistory.map((e) => ({
      id: e.outageId,
      sourceId: 'outage-history' as const,
      title: `${e.outageType} outage work scope`,
      date: e.startDate,
      outage: e.outageId,
      outageSummary: e.workPerformed?.length
        ? `Outage ${e.startDate}–${e.endDate || '—'} (${e.duration} days). Work: ${e.workPerformed.join(', ')}.`
        : `${e.outageType} outage starting ${e.startDate}.`,
    })),
  }), [erCases, fsrReports, outageHistory])

  // Build the full source list (base + uploaded row when files exist)
  const dataSources: DataSource[] = useMemo(() => {
    const ds = dataReadiness?.dataSources

    const base: DataSource[] = BASE_SOURCES.map((s) => {
      const key = READINESS_KEY_MAP[s.id]
      const src = key ? (ds as Record<string, { available: boolean; count?: number }> | undefined)?.[key] : undefined
      const isCaseSource = CASE_SOURCE_IDS.has(s.id)

      return {
        ...s,
        count: isCaseSource && src ? (src.count ?? 0) : s.count,
        nativelyAvailable: src ? src.available : Boolean(INITIAL_AVAILABILITY[s.id]),
        icon: SOURCE_ICONS[s.id],
      }
    })

    if (uploadedFiles.length > 0) {
      base.push({
        id: 'uploaded',
        name: 'Uploaded Documents',
        nativelyAvailable: true,
        count: uploadedFiles.length,
        description: 'User-provided documents and test results',
        icon: SOURCE_ICONS['uploaded'],
      })
    }

    return base
  }, [dataReadiness, uploadedFiles.length])

  const handleTogglePreview = (sourceId: string, isExpanded: boolean) => {
    setExpandedPreviews((prev) => {
      const next = new Set(prev)
      if (isExpanded) next.add(sourceId)
      else next.delete(sourceId)
      return next
    })

    // Lazy-load detail data when accordion is expanded
    if (isExpanded && esn && !fetchedSources.has(sourceId)) {
      const dateArgs = { esn, startDate: appliedStart || undefined, endDate: appliedEnd || undefined }
      setLoadingSources((prev) => new Set(prev).add(sourceId))
      let promise: Promise<unknown> | undefined
      if (sourceId === 'er-cases') promise = dispatch(fetchERCases(dateArgs))
      if (sourceId === 'fsr-reports') promise = dispatch(fetchFSRReports(dateArgs))
      if (sourceId === 'outage-history') promise = dispatch(fetchOutageHistory(dateArgs))
      if (promise) {
        void promise.finally(() => {
          setLoadingSources((prev) => {
            const next = new Set(prev)
            next.delete(sourceId)
            return next
          })
        })
      }
      setFetchedSources((prev) => new Set(prev).add(sourceId))
    }
  }

  const checkedCount = checked.size
  const canProceed = checkedCount >= 1

  return (
    <Box id="data-readiness-section">
      <Paper elevation={1} sx={{ p: 3, mb: 3, bgcolor: 'primary.50', position: 'relative', overflow: 'hidden' }}>
        {docsLoading && (
          <LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0 }} />
        )}
        <Typography variant="h6" gutterBottom>
          Step 2: Data Readiness Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Review the available data sources for this unit. Source selection and date-range
          filtering are managed automatically in this view.
        </Typography>
      </Paper>

      <Paper elevation={2} sx={{ mb: 3 }}>
        <Box px={3} pt={2.5} pb={1} display="flex" alignItems="center" gap={1}>
          <Typography variant="h6" sx={{ flex: 1 }}>
            Data Sources
          </Typography>
          <Tooltip title="Data sources available for this assessment review.">
            <Info sx={{ fontSize: 18, color: 'text.secondary', cursor: 'help' }} />
          </Tooltip>
        </Box>

        <List disablePadding>
          {!dataReadiness && docsLoading ? (
            <Box px={3} py={3}>
              <LinearProgress />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Loading data source availability…
              </Typography>
            </Box>
          ) : (
            dataSources.map((source, idx) => {
            const isChecked = checked.has(source.id)
            const isUnavailable = !source.nativelyAvailable
            const isCaseSource = CASE_SOURCE_IDS.has(source.id)
            const isPreviewExpanded = expandedPreviews.has(source.id)
            const isERCaseSource = source.id === 'er-cases'
            const previewRecords =
              isCaseSource && isPreviewExpanded
                ? previewData[source.id as CaseSourceId]
                : []
            const isDisabled =
              isUnavailable && source.count === 0 && source.id !== 'uploaded'

            const rowContent = (
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <ListItemIcon
                  sx={{
                    minWidth: 36,
                    color: isChecked ? 'primary.main' : 'text.secondary',
                    mt: 0,
                    alignSelf: 'center',
                  }}
                >
                  {source.icon}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                      <Typography
                        variant="body2"
                        fontWeight={isChecked ? 700 : 400}
                        sx={{ color: isChecked ? 'text.primary' : 'text.secondary' }}
                      >
                        {source.name}
                      </Typography>
                      {source.count !== undefined && (
                        <Chip
                          label={`${source.count} ${source.count === 1 ? 'item' : 'items'}`}
                          size="small"
                          variant="outlined"
                          color={isChecked ? 'primary' : 'default'}
                          sx={{ fontSize: '0.7rem', height: 20 }}
                        />
                      )}
                      {isUnavailable && (
                        <Chip
                          label="not available"
                          size="small"
                          color="default"
                          sx={{ fontSize: '0.65rem', height: 20, opacity: 0.7 }}
                        />
                      )}
                    </Box>
                  }
                  secondary={source.description}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </Box>
            )

            return (
              <Box key={source.id} data-testid={`data-source-${source.id}`}>
                {idx > 0 && <Divider component="li" />}
                {isCaseSource ? (
                  <Accordion
                    disableGutters
                    elevation={0}
                    expanded={isPreviewExpanded}
                    onChange={(_, expanded) => handleTogglePreview(source.id, expanded)}
                    disabled={isDisabled}
                    sx={{
                      bgcolor: isChecked ? 'action.selected' : 'transparent',
                      transition: 'background-color 0.15s',
                      opacity: isUnavailable && !isChecked ? 0.5 : 1,
                      border: 0,
                      borderRadius: 0,
                      boxShadow: 'none',
                      '&::before': { display: 'none' },
                      '&.MuiAccordion-root': {
                        borderRadius: 0,
                      },
                    }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMore />}
                      data-testid={`data-source-row-${source.id}`}
                      aria-disabled={isDisabled ? 'true' : undefined}
                      sx={{
                        px: 3,
                        py: 0.5,
                        '& .MuiAccordionSummary-content': {
                          alignItems: 'center',
                          margin: '8px 0',
                        },
                      }}
                      aria-controls={`${source.id}-preview-content`}
                      id={`${source.id}-preview-header`}
                    >
                      {rowContent}
                    </AccordionSummary>
                    <AccordionDetails sx={{ px: 3, pb: 2, pt: 0 }}>
                      {loadingSources.has(source.id) ? (
                        <LinearProgress />
                      ) : previewRecords.length === 0 ? (
                        <Typography variant="caption" color="text.secondary">
                          No case previews available.
                        </Typography>
                      ) : (
                        <TableContainer
                          ref={(el) => { tableContainerRefs.current[source.id] = el }}
                          component={Paper}
                          variant="outlined"
                          onScroll={handleTableScroll(source.id)}
                          sx={{
                            maxHeight: 400,
                            overflowY: 'scroll',
                            bgcolor: 'common.white',
                            borderColor: 'divider',
                            '& .MuiTableCell-root': {
                              bgcolor: 'common.white',
                              borderColor: 'divider',
                            },
                          }}
                        >
                          <Table size="small" stickyHeader aria-label={`${source.name} case previews`}>
                            <TableHead>
                              <TableRow>
                                {isERCaseSource ? (
                                  <>
                                    <TableCell>Case ID</TableCell>
                                    <TableCell>Description</TableCell>
                                    <TableCell>Close Notes</TableCell>
                                    <TableCell>Date</TableCell>
                                    <TableCell>Case Summary</TableCell>
                                  </>
                                ) : (
                                  <>
                                    <TableCell>Title</TableCell>
                                    <TableCell>Date</TableCell>
                                    <TableCell>Outage</TableCell>
                                    <TableCell>Outage Summary</TableCell>
                                  </>
                                )}
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {previewRecords.map((record) => (
                                <TableRow key={record.id}>
                                  {isERCaseSource ? (
                                    <>
                                      <TableCell>{record.caseId}</TableCell>
                                      <TableCell>{record.description}</TableCell>
                                      <TableCell>{record.closeNotes}</TableCell>
                                      <TableCell>{record.date}</TableCell>
                                      <TableCell>{record.caseSummary}</TableCell>
                                    </>
                                  ) : (
                                    <>
                                      <TableCell>{record.title}</TableCell>
                                      <TableCell>{record.date}</TableCell>
                                      <TableCell>{record.outage}</TableCell>
                                      <TableCell>{record.outageSummary}</TableCell>
                                    </>
                                  )}
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                          {loadingMore.has(source.id) && (
                            <Box py={1}>
                              <LinearProgress />
                            </Box>
                          )}
                        </TableContainer>
                      )}
                    </AccordionDetails>
                  </Accordion>
                ) : (
                  <ListItem
                    disablePadding
                    sx={{
                      bgcolor: isChecked ? 'action.selected' : 'transparent',
                      transition: 'background-color 0.15s',
                    }}
                  >
                    <Box
                      data-testid={`data-source-row-${source.id}`}
                      sx={{ px: 3, py: 1.5, width: '100%', opacity: isDisabled ? 0.5 : 1 }}
                    >
                      {rowContent}
                    </Box>
                  </ListItem>
                )}
              </Box>
            )
            })
          )}
        </List>
      </Paper>

      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="body2" color={canProceed ? 'text.secondary' : 'error.main'}>
          {canProceed
            ? `${checkedCount} data source${checkedCount !== 1 ? 's' : ''} ready for analysis`
            : 'Select at least one data source to continue'}
        </Typography>
        <Button
          variant="contained"
          size="large"
          endIcon={<ArrowForward />}
          disabled={!canProceed}
          onClick={() => {
            const el = document.getElementById('risk-analysis-section')
            el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
        >
          Continue to Analysis
        </Button>
      </Stack>
    </Box>
  )
}

export default DataReadinessPanel
