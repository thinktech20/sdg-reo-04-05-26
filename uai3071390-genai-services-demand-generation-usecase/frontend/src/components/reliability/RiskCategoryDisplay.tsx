import { useMemo, useState } from 'react'
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import { ArrowDownward, ArrowUpward, ExpandMore, ImportExport } from '@mui/icons-material'
import type { RiskCategory, RiskCondition } from '@/store/types'
import RiskConditionRow from './RiskConditionRow'
import RiskTableControls, {
  type RiskFilterValue,
  type StatusFilterValue,
} from './RiskTableControls'

interface RiskCategoryDisplayProps {
  category: RiskCategory
  assessmentId: string
  savedRows: Record<string, string>
  editable: boolean
}

/**
 * Risk Category Display - Step 4 & 5
 * 
 * Displays a collapsible risk category with conditions table
 * Allows editing of individual conditions (Step 5)
 */
const RiskCategoryDisplay = ({
  category,
  assessmentId,
  savedRows,
  editable,
}: RiskCategoryDisplayProps) => {
  const [expanded, setExpanded] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [riskFilter, setRiskFilter] = useState<RiskFilterValue>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('all')
  const [sortBy, setSortBy] = useState<'condition' | 'category' | 'riskLevel' | 'status'>(
    'riskLevel'
  )
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  const getRiskColor = (risk: string) => {
    const riskColorMap: Record<string, 'error' | 'warning' | 'success'> = {
      heavy: 'error',
      high: 'error',
      medium: 'warning',
      light: 'success',
      low: 'success',
    }
    return riskColorMap[risk.toLowerCase()] || 'default'
  }

  const getStatusColor = (status: string) => {
    const statusColorMap: Record<string, 'success' | 'warning' | 'info'> = {
      complete: 'success',
      'data-needed': 'warning',
      'in-progress': 'info',
    }
    return statusColorMap[status.toLowerCase()] || 'default'
  }

  const filteredAndSortedConditions = useMemo(() => {
    const searchValue = searchQuery.trim().toLowerCase()
    const riskOrder: Record<string, number> = { Low: 1, Medium: 2, High: 3 }
    const statusOrder: Record<string, number> = {
      complete: 1,
      'in-progress': 2,
      'data-needed': 3,
    }
    const sortAccessor: Record<typeof sortBy, (condition: RiskCondition) => string | number> = {
      condition: (c) => (c.issueName || c.condition).toLowerCase(),
      category: (condition) => condition.category.toLowerCase(),
      riskLevel: (condition) => riskOrder[condition.riskLevel] ?? Number.MAX_SAFE_INTEGER,
      status: (condition) =>
        statusOrder[condition.status.toLowerCase()] ?? Number.MAX_SAFE_INTEGER,
    }

    return category.conditions
      .filter((condition) => {
        const matchesRisk = riskFilter === 'all' || condition.riskLevel === riskFilter
        const matchesStatus = statusFilter === 'all' || condition.status === statusFilter
        const matchesSearch =
          searchValue.length === 0 ||
          [
            condition.findingId,
            condition.category,
            condition.issueName,
            condition.condition,
            condition.threshold,
            condition.actualValue,
            condition.evidence,
          ].some((value) => value.toLowerCase().includes(searchValue))

        return matchesRisk && matchesStatus && matchesSearch
      })
      .sort((leftCondition, rightCondition) => {
        const left = sortAccessor[sortBy](leftCondition)
        const right = sortAccessor[sortBy](rightCondition)
        const comparison =
          typeof left === 'number' && typeof right === 'number'
            ? left - right
            : String(left).localeCompare(String(right))
        return sortDirection === 'asc' ? comparison : comparison * -1
      })
  }, [category.conditions, riskFilter, searchQuery, sortBy, sortDirection, statusFilter])

  const handleResetControls = () => {
    setSearchQuery('')
    setRiskFilter('all')
    setStatusFilter('all')
    setSortBy('riskLevel')
    setSortDirection('desc')
  }

  const handleSortClick = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortDirection((currentDirection) => (currentDirection === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortBy(field)
    setSortDirection('asc')
  }

  const getSortIcon = (field: typeof sortBy) => {
    if (sortBy !== field) {
      return <ImportExport fontSize="small" />
    }
    if (sortDirection === 'asc') {
      return <ArrowDownward fontSize="small" />
    }
    return <ArrowUpward fontSize="small" />
  }

  const renderSortableHeader = (
    label: string,
    field: typeof sortBy,
    width: number
  ) => (
    <TableCell
      width={width}
      onClick={() => handleSortClick(field)}
      data-testid={`sort-header-${field}`}
      sx={{
        cursor: 'pointer',
        userSelect: 'none',
        borderBottom: '3px solid transparent',
        transition: 'border-color 0.15s ease-in-out',
        '&:hover': {
          borderBottomColor: 'divider',
        },
      }}
    >
      <Box
        component="span"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.5,
          whiteSpace: 'nowrap',
          lineHeight: 1.2,
        }}
      >
        {label}
        {getSortIcon(field)}
      </Box>
    </TableCell>
  )

  // Count conditions by risk level
  const riskCounts = {
    high: category.conditions.filter((c) => c.riskLevel === 'High').length,
    medium: category.conditions.filter((c) => c.riskLevel === 'Medium').length,
    low: category.conditions.filter((c) => c.riskLevel === 'Low').length,
  }

  return (
    <Accordion
      expanded={expanded}
      onChange={() => setExpanded(!expanded)}
      sx={{ mb: 2 }}
      elevation={3}
    >
      <AccordionSummary
        expandIcon={<ExpandMore />}
        sx={{
          bgcolor: 'grey.50',
          '&:hover': { bgcolor: 'grey.100' },
        }}
      >
        <Box flex={1} display="flex" alignItems="center" justifyContent="space-between" pr={2}>
          <Box>
            <Typography variant="h6">{category.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              Component: {category.component} • Process Doc: {category.processDocument}
            </Typography>
          </Box>
          
          <Box display="flex" gap={1} alignItems="center">
            <Chip
              label={`Overall: ${category.overallRisk}`}
              color={getRiskColor(category.overallRisk)}
              size="small"
            />
            <Chip
              label={`${riskCounts.high}H ${riskCounts.medium}M ${riskCounts.low}L`}
              size="small"
              variant="outlined"
            />
          </Box>
        </Box>
      </AccordionSummary>

      <AccordionDetails sx={{ p: 0 }}>
        {/* Category Description */}
        <Box sx={{ p: 2, bgcolor: 'grey.50', borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="body2" color="text.secondary">
            {category.description}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mt={1}>
            Reliability Model: {category.reliabilityModelRef}
          </Typography>
        </Box>

        {/* Conditions Table */}
        <RiskTableControls
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          riskFilter={riskFilter}
          onRiskFilterChange={setRiskFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          onResetControls={handleResetControls}
        />
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'grey.100' }}>
                {renderSortableHeader('Issue', 'condition', 220)}
                {renderSortableHeader('Category', 'category', 120)}
                <TableCell sx={{ minWidth: 220 }}>Condition</TableCell>
                <TableCell width="120">Actual Value</TableCell>
                {renderSortableHeader('Risk Level', 'riskLevel', 100)}
                {renderSortableHeader('Status', 'status', 100)}
                <TableCell>Evidence & Justification</TableCell>
                {editable && <TableCell width="120">Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredAndSortedConditions.length > 0 ? (
                filteredAndSortedConditions.map((condition) => (
                  <RiskConditionRow
                    key={condition.findingId}
                    condition={condition}
                    assessmentId={assessmentId}
                    savedTimestamp={savedRows[condition.findingId]}
                    editable={editable}
                    getRiskColor={getRiskColor}
                    getStatusColor={getStatusColor}
                  />
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={editable ? 8 : 7}>
                    <Typography variant="body2" color="text.secondary">
                      No conditions match selected filters.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Summary Footer */}
        <Box sx={{ p: 2, bgcolor: 'grey.50', borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary">
            Showing: {filteredAndSortedConditions.length} of {category.conditions.length} | High
            Risk: {riskCounts.high} | Medium Risk: {riskCounts.medium} | Low Risk: {riskCounts.low}
          </Typography>
        </Box>
      </AccordionDetails>
    </Accordion>
  )
}

export default RiskCategoryDisplay
