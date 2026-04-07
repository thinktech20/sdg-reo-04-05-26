import { afterEach, describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import NarrativeSummaryPanel from './NarrativeSummaryPanel'
import type { Assessment } from '@/store/types'

const createAssessment = (overrides?: Partial<Assessment>): Assessment => ({
  id: 'assess-001',
  serialNumber: 'GT12345',
  milestone: '18-month',
  reliabilityStatus: 'in-progress',
  outageStatus: 'not-started',
  reliabilityRiskCategories: {},
  narrativeSummary: '',
  reliabilityFindings: [],
  outageFindings: [],
  reliabilityChat: [],
  outageChat: [],
  uploadedDocs: [],
  createdAt: '2026-03-05T00:00:00Z',
  updatedAt: '2026-03-05T00:00:00Z',
  ...overrides,
})

afterEach(() => {
  vi.restoreAllMocks()
})

const structuredNarrative = JSON.stringify({
  Recommendations:
    '1. Stator BI inspection required to evaluate Inside Space Block (ISSB) and Outside Space Block (OSSB) migration.',
  'Unit Summary':
    'This report was generated based on a request for analysis of the Generator Unit Serial # GG10632.',
  'Overall Equipment Health Assessment':
    '1. The generator stator is rated at heavy probability of a stator rewind for the upcoming outage.',
})

describe('NarrativeSummaryPanel copy action', () => {
  it('copies fallback summary text and shows success feedback', async () => {
    const user = userEvent.setup()
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    })

    renderWithProviders(<NarrativeSummaryPanel assessment={createAssessment({ narrativeSummary: 'RELIABILITY ASSESSMENT SUMMARY\nTest narrative content.' })} />)

    await user.click(screen.getByRole('button', { name: /copy/i }))

    expect(writeTextMock).toHaveBeenCalledTimes(1)
    expect(writeTextMock).toHaveBeenCalledWith(expect.stringContaining('RELIABILITY ASSESSMENT SUMMARY'))
    expect(await screen.findByText('Executive summary copied to clipboard.')).toBeInTheDocument()
  })

  it('shows error feedback when clipboard copy fails', async () => {
    const user = userEvent.setup()
    const writeTextMock = vi.fn().mockRejectedValue(new Error('clipboard denied'))
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      value: vi.fn().mockReturnValue(false),
    })
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    })

    renderWithProviders(
      <NarrativeSummaryPanel
        assessment={createAssessment({ narrativeSummary: 'AI narrative summary text' })}
      />
    )

    await user.click(screen.getByRole('button', { name: /copy/i }))

    expect(writeTextMock).toHaveBeenCalledTimes(1)
    expect(writeTextMock).toHaveBeenCalledWith('AI narrative summary text')
    expect(
      await screen.findByText('Copy failed. Please check browser clipboard permissions and try again.')
    ).toBeInTheDocument()
  })

  it('renders structured narrative sections and copies as readable text', async () => {
    const user = userEvent.setup()
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    })

    renderWithProviders(
      <NarrativeSummaryPanel
        assessment={createAssessment({ narrativeSummary: structuredNarrative })}
      />
    )

    expect(screen.getByText('Recommendations')).toBeInTheDocument()
    expect(screen.getByText('Unit Summary')).toBeInTheDocument()
    expect(screen.getByText('Overall Equipment Health Assessment')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /copy/i }))

    expect(writeTextMock).toHaveBeenCalledTimes(1)
    expect(writeTextMock).toHaveBeenCalledWith(
      expect.stringContaining('Recommendations\n1. Stator BI inspection required to evaluate')
    )
    expect(writeTextMock).toHaveBeenCalledWith(
      expect.stringContaining('Unit Summary\nThis report was generated based on a request for analysis')
    )
  })
})
