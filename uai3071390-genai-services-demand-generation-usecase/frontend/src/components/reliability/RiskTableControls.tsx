import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material'

export type RiskFilterValue = 'all' | 'High' | 'Medium' | 'Low'
export type StatusFilterValue = 'all' | 'complete' | 'data-needed' | 'in-progress'

interface RiskTableControlsProps {
  searchQuery: string
  onSearchQueryChange: (value: string) => void
  riskFilter: RiskFilterValue
  onRiskFilterChange: (value: RiskFilterValue) => void
  statusFilter: StatusFilterValue
  onStatusFilterChange: (value: StatusFilterValue) => void
  onResetControls: () => void
}

const RiskTableControls = ({
  searchQuery,
  onSearchQueryChange,
  riskFilter,
  onRiskFilterChange,
  statusFilter,
  onStatusFilterChange,
  onResetControls,
}: RiskTableControlsProps) => {
  return (
    <Box
      sx={{
        p: 2,
        display: 'flex',
        gap: 1.5,
        flexWrap: 'wrap',
        alignItems: 'center',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <TextField
        size="small"
        label="Search…"
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        sx={{ minWidth: 220 }}
      />

      <FormControl size="small" sx={{ minWidth: 150 }}>
        <InputLabel id="risk-filter-label">Risk Level</InputLabel>
        <Select
          labelId="risk-filter-label"
          value={riskFilter}
          label="Risk Level"
          onChange={(event) => onRiskFilterChange(event.target.value as RiskFilterValue)}
        >
          <MenuItem value="all">All Risk Levels</MenuItem>
          <MenuItem value="High">High</MenuItem>
          <MenuItem value="Medium">Medium</MenuItem>
          <MenuItem value="Low">Low</MenuItem>
        </Select>
      </FormControl>

      <FormControl size="small" sx={{ minWidth: 160 }}>
        <InputLabel id="status-filter-label">Status</InputLabel>
        <Select
          labelId="status-filter-label"
          value={statusFilter}
          label="Status"
          onChange={(event) => onStatusFilterChange(event.target.value as StatusFilterValue)}
        >
          <MenuItem value="all">All Statuses</MenuItem>
          <MenuItem value="complete">Complete</MenuItem>
          <MenuItem value="in-progress">In Progress</MenuItem>
          <MenuItem value="data-needed">Data Needed</MenuItem>
        </Select>
      </FormControl>

      <Button
        size="small"
        variant="outlined"
        onClick={onResetControls}
        aria-label="Reset sort and filter controls"
      >
        Reset
      </Button>
    </Box>
  )
}

export default RiskTableControls
