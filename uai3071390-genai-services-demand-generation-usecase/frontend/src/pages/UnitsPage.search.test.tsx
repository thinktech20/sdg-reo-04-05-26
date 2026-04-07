import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

describe('UnitsPage search interactions', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockUseEquipment.mockReset()
  })

  it('searches by ESN, shows not-found feedback, and clears from the search bar action', async () => {
    const searchEquipment = vi.fn().mockResolvedValue({ error: true })
    const clearSelection = vi.fn()
    const loadTrains = vi.fn().mockResolvedValue(undefined)

    mockUseEquipment.mockReturnValue({
      trains: [],
      loading: false,
      error: null,
      loadTrains,
      searchEquipment,
      selectedEquipment: null,
      clearSelection,
    })

    render(
      <MemoryRouter>
        <UnitsPage />
      </MemoryRouter>
    )

    const searchInput = screen.getByPlaceholderText(/Search by unit name, site, or ESN/i)
    fireEvent.change(searchInput, { target: { value: 'gt3003' } })
    fireEvent.keyDown(searchInput, { key: 'Enter', code: 'Enter' })

    await waitFor(() => {
      expect(searchEquipment).toHaveBeenCalledWith('GT3003')
    })

    expect(await screen.findByText(/No equipment found for ESN/i)).toBeInTheDocument()

    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0]!)

    expect(searchInput).toHaveValue('')
    await waitFor(() => {
      expect(clearSelection).toHaveBeenCalled()
    })
    expect(screen.queryByText(/No equipment found for ESN/i)).not.toBeInTheDocument()
  })

  it('shows not-found feedback when ESN lookup throws', async () => {
    const searchEquipment = vi.fn().mockRejectedValue(new Error('lookup failed'))

    mockUseEquipment.mockReturnValue({
      trains: [],
      loading: false,
      error: null,
      loadTrains: vi.fn().mockResolvedValue(undefined),
      searchEquipment,
      selectedEquipment: null,
      clearSelection: vi.fn(),
    })

    render(
      <MemoryRouter>
        <UnitsPage />
      </MemoryRouter>
    )

    const searchInput = screen.getByPlaceholderText(/Search by unit name, site, or ESN/i)
    fireEvent.change(searchInput, { target: { value: 'gt9999' } })
    fireEvent.keyDown(searchInput, { key: 'Enter', code: 'Enter' })

    await waitFor(() => {
      expect(searchEquipment).toHaveBeenCalledWith('GT9999')
    })

    expect(await screen.findByText(/No equipment found for ESN/i)).toBeInTheDocument()
  })
})
