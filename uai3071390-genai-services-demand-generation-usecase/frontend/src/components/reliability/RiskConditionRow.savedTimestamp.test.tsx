import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RiskCondition } from '@/store/types'
import RiskConditionRow from './RiskConditionRow'

const { mockDispatch } = vi.hoisted(() => ({
  mockDispatch: vi.fn(() => ({
    unwrap: vi.fn().mockResolvedValue(undefined),
  })),
}))

vi.mock('@/store', () => ({
  useAppDispatch: () => mockDispatch,
}))

vi.mock('@/store/slices/assessmentsSlice', () => ({
  updateReliability: vi.fn(),
  submitFeedback: vi.fn(),
}))

const condition: RiskCondition = {
  findingId: 'sr-001',
  id: 'sr-001',
  category: 'Age',
  issueName: 'Unit Age > 25 years',
  condition: 'Unit age exceeds 25-year reliability threshold.',
  threshold: '> 25 years',
  actualValue: '26 years',
  riskLevel: 'Medium',
  testMethod: 'Calculated from COD',
  evidence: 'Test evidence',
  dataSource: 'Install Base',
  justification: 'Test justification',
  primaryCitation: 'GEK-103542',
  status: 'complete',
  feedback: null,
  feedbackType: null,
  comments: '',
}

describe('RiskConditionRow saved timestamp', () => {
  beforeEach(() => {
    mockDispatch.mockClear()
  })

  it('renders last-saved tooltip text using en-US locale', () => {
    const savedTimestamp = '2026-03-11T09:30:00.000Z'

    render(
      <table>
        <tbody>
          <RiskConditionRow
            condition={condition}
            assessmentId="assess-001"
            savedTimestamp={savedTimestamp}
            editable={true}
            getRiskColor={() => 'warning'}
            getStatusColor={() => 'success'}
          />
        </tbody>
      </table>
    )

    expect(
      screen.getByLabelText(`Last saved: ${new Date(savedTimestamp).toLocaleString('en-US')}`)
    ).toBeInTheDocument()
  })
})
