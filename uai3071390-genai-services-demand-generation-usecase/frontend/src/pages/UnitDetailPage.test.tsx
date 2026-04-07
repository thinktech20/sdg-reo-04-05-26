import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import UnitDetailPage from './UnitDetailPage'

type AssessmentsState = {
  currentAssessment: { reliabilityStatus: string } | null
  loading: boolean
  error: string | null
}

type EquipmentState = {
  selectedEquipment: {
    serialNumber?: string
    model: string
    site: string
    totalEOH?: number
    totalStarts?: number
  } | null
  error?: string | null
}

const mockDispatch = vi.fn(() => ({
  unwrap: vi.fn().mockResolvedValue(undefined),
}))
const mockNavigate = vi.fn()
const mockUseAssessments = vi.fn<() => AssessmentsState>()
const mockUseEquipment = vi.fn<() => EquipmentState>()
const mockSearchParams = new URLSearchParams('esn=GT12345&review_period=12-month')

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams],
  }
})

vi.mock('@/store', () => ({
  useAppDispatch: () => mockDispatch,
  useAssessments: () => mockUseAssessments(),
  useEquipment: () => mockUseEquipment(),
}))

vi.mock('@/store/slices/assessmentsSlice', () => ({
  clearCurrentAssessment: vi.fn(() => ({ type: 'assessments/clearCurrentAssessment' })),
  clearError: vi.fn(() => ({ type: 'assessments/clearError' })),
  createAssessment: vi.fn((payload) => ({ type: 'createAssessment', payload })),
  fetchAssessment: vi.fn((payload) => ({ type: 'fetchAssessment', payload })),
}))

vi.mock('@/components/reliability/DataReadinessPanel', () => ({ default: () => <div>Data Readiness Panel</div> }))
vi.mock('@/components/reliability/RiskAnalysisPanel', () => ({ default: () => <div>Risk Analysis Panel</div> }))
vi.mock('@/components/reliability/NarrativeSummaryPanel', () => ({ default: () => <div>Narrative Summary Panel</div> }))
vi.mock('@/components/reliability/ReliabilityChatPanel', () => ({ default: () => <div>Reliability Chat Panel</div> }))

describe('UnitDetailPage', () => {
  beforeEach(() => {
    mockDispatch.mockClear()
    mockNavigate.mockClear()
    mockUseAssessments.mockReset()
    mockUseEquipment.mockReset()
  })

  it('renders numeric fields using en-US grouping', () => {
    mockUseAssessments.mockReturnValue({
      currentAssessment: {
        reliabilityStatus: 'in-progress',
      },
      loading: false,
      error: null,
    })
    mockUseEquipment.mockReturnValue({
      selectedEquipment: {
        serialNumber: 'GT12345',
        model: 'GEN-7FH2',
        site: 'Demo Site',
        totalEOH: 95000,
        totalStarts: 1250,
      },
      error: null,
    })

    render(<UnitDetailPage />)

    expect(screen.getByText('95,000')).toBeInTheDocument()
    expect(screen.getByText('1,250')).toBeInTheDocument()
    expect(screen.getByText('12-month')).toBeInTheDocument()
    expect(screen.getByText('Data Readiness Panel')).toBeInTheDocument()
  })
})
