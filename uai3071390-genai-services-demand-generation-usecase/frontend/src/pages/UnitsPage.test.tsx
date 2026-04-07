import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import UnitsPage from './UnitsPage'
import type { Equipment, Train } from '@/store/types'

type UseEquipmentState = {
  trains: Train[]
  loading: boolean
  error: string | null
  loadTrains: (filterType: 'all' | 'Major' | 'Minor', searchText?: string) => unknown
  searchEquipment: (esn: string) => Promise<unknown>
  selectedEquipment: Equipment | null
  clearSelection: () => void
}

const mockNavigate = vi.fn()
const mockUseEquipment = vi.fn<() => UseEquipmentState>()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('@/store', () => ({
  useEquipment: () => mockUseEquipment(),
}))

const makeEquipment = (overrides: Partial<Equipment> = {}): Equipment => ({
  serialNumber: 'GT1001',
  equipmentType: 'Gas Turbine',
  equipmentCode: 'GT-001',
  model: '7FA',
  site: 'Plant West',
  commercialOpDate: '2020-01-01',
  totalEOH: 50000,
  totalStarts: 1000,
  ...overrides,
})

const makeTrain = (overrides: Partial<Train> = {}): Train => ({
  id: 'train-1',
  trainName: 'Unit 1',
  site: 'Plant West',
  trainType: 'Combined Cycle',
  outageId: 'OUT-1',
  outageType: 'Major',
  startDate: '2026-03-01',
  endDate: '2026-03-15',
  equipment: [makeEquipment()],
  ...overrides,
})

const renderPage = () =>
  render(
    <MemoryRouter>
      <UnitsPage />
    </MemoryRouter>
  )

describe('UnitsPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockUseEquipment.mockReset()
  })

  it('loads units with search only and does not show outage filters', async () => {
    const loadTrains = vi.fn().mockResolvedValue(undefined)
    mockUseEquipment.mockReturnValue({
      trains: [makeTrain()],
      loading: false,
      error: null,
      loadTrains,
      searchEquipment: vi.fn(),
      selectedEquipment: null,
      clearSelection: vi.fn(),
    })

    renderPage()

    await waitFor(() => {
      expect(loadTrains).toHaveBeenCalledWith('all')
    })

    expect(screen.queryByText('All')).not.toBeInTheDocument()
    expect(screen.queryByText('Major')).not.toBeInTheDocument()
    expect(screen.queryByText('Minor')).not.toBeInTheDocument()
    expect(screen.queryByText('OUT-1')).not.toBeInTheDocument()
  })

  it('supports single selection, ESN chip preview, formatted values and chip remove action', async () => {
    const loadTrains = vi.fn().mockResolvedValue(undefined)
    const firstEquipment = makeEquipment({ serialNumber: 'GT1001', totalEOH: 50000, totalStarts: 1000 })
    const secondEquipment = makeEquipment({
      serialNumber: 'GT2002',
      equipmentCode: 'GT-002',
      totalEOH: 120000,
      totalStarts: 2450,
    })

    mockUseEquipment.mockReturnValue({
      trains: [makeTrain({ equipment: [firstEquipment, secondEquipment] })],
      loading: false,
      error: null,
      loadTrains,
      searchEquipment: vi.fn(),
      selectedEquipment: null,
      clearSelection: vi.fn(),
    })

    renderPage()

    await waitFor(() => screen.getByText('Unit 1'))
    fireEvent.click(screen.getByText('Unit 1'))
    expect(screen.getByText(/1,000 starts/i)).toBeInTheDocument()

    fireEvent.click(screen.getByText('GT1001'))

    const secondCheckbox = screen.getAllByRole('checkbox')[1]!

    expect(screen.getByRole('button', { name: 'GT1001' })).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
    expect(screen.getByText('selected')).toBeInTheDocument()

    fireEvent.click(secondCheckbox)

    await waitFor(() => {
      const updated = screen.getAllByRole('checkbox')
      expect(updated[0]).not.toBeChecked()
      expect(updated[1]).toBeChecked()
    })

    const previewChip = screen.getByRole('button', { name: 'GT2002' })

    expect(screen.getAllByRole('checkbox')[1]).toBeChecked()

    fireEvent.click(within(previewChip).getByTestId('CancelIcon'))
    expect(screen.queryByRole('button', { name: 'GT2002' })).not.toBeInTheDocument()
  })

  it('shows ESN result formatting and begins assessment for the selected component', async () => {
    const loadTrains = vi.fn().mockResolvedValue(undefined)
    const searchEquipment = vi.fn().mockResolvedValue({})
    const selectedEquipment = makeEquipment({
      serialNumber: 'GT3003',
      totalEOH: 95000,
      totalStarts: 1250,
    })

    mockUseEquipment.mockReturnValue({
      trains: [makeTrain()],
      loading: false,
      error: null,
      loadTrains,
      searchEquipment,
      selectedEquipment,
      clearSelection: vi.fn(),
    })

    renderPage()

    await waitFor(() => expect(screen.getByText('95,000')).toBeInTheDocument())
    expect(screen.getByText('1,250')).toBeInTheDocument()

    const esnCheckbox = screen.getAllByRole('checkbox')[0]!
    fireEvent.click(esnCheckbox)

    const reviewPeriod = screen.getByRole('combobox')
    fireEvent.mouseDown(reviewPeriod)
    fireEvent.click(screen.getByRole('option', { name: '12-month milestone' }))

    fireEvent.click(screen.getByRole('button', { name: /Begin Assessment/i }))

    expect(mockNavigate).toHaveBeenCalledWith('/unit?esn=GT3003&review_period=12-month')
  })

  it('allows deselecting the selected component by unchecking its checkbox', async () => {
    const loadTrains = vi.fn().mockResolvedValue(undefined)
    const singleEquipment = makeEquipment({ serialNumber: 'GT4004' })

    mockUseEquipment.mockReturnValue({
      trains: [makeTrain({ equipment: [singleEquipment] })],
      loading: false,
      error: null,
      loadTrains,
      searchEquipment: vi.fn(),
      selectedEquipment: null,
      clearSelection: vi.fn(),
    })

    renderPage()

    await waitFor(() => screen.getByText('Unit 1'))
    fireEvent.click(screen.getByText('Unit 1'))

    const equipmentCheckbox = screen.getAllByRole('checkbox')[0]!
    fireEvent.click(equipmentCheckbox)
    expect(screen.getByRole('button', { name: 'GT4004' })).toBeInTheDocument()

    fireEvent.click(equipmentCheckbox)
    expect(screen.queryByRole('button', { name: 'GT4004' })).not.toBeInTheDocument()
  })
})
