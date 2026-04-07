import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { RiskCondition } from '@/store/types'
import RiskConditionRow from './RiskConditionRow'

type SubmitFeedbackPayload = {
  assessmentId: string
  findingId: string
  feedback: {
    feedback?: 'up' | 'down' | null
    feedbackType?: string | null
    comments?: string
  }
}

const { mockDispatch, mockSubmitFeedback } = vi.hoisted(() => ({
  mockDispatch: vi.fn(() => ({
    unwrap: vi.fn().mockResolvedValue(undefined),
  })),
  mockSubmitFeedback: vi.fn((payload: SubmitFeedbackPayload) => ({
    type: 'MOCK_SUBMIT_FEEDBACK',
    payload,
  })),
}))

vi.mock('@/store', () => ({
  useAppDispatch: () => mockDispatch,
}))

vi.mock('@/store/slices/assessmentsSlice', () => ({
  updateReliability: vi.fn(),
  submitFeedback: mockSubmitFeedback,
}))

const baseCondition: RiskCondition = {
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

const renderRow = (overrides: Partial<RiskCondition> = {}) => {
  const condition: RiskCondition = { ...baseCondition, ...overrides }
  return render(
    <table>
      <tbody>
        <RiskConditionRow
          condition={condition}
          assessmentId="assess-001"
          savedTimestamp={undefined}
          editable={true}
          getRiskColor={() => 'warning'}
          getStatusColor={() => 'success'}
        />
      </tbody>
    </table>
  )
}

describe('RiskConditionRow feedback actions', () => {
  beforeEach(() => {
    mockDispatch.mockClear()
    mockSubmitFeedback.mockClear()
  })

  it('renders thumbs up/down actions in the actions column', () => {
    renderRow()

    expect(screen.getByRole('button', { name: 'Thumbs up feedback' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Thumbs down feedback' })).toBeInTheDocument()
    expect(screen.queryByTestId('EditIcon')).not.toBeInTheDocument()
  })

  it('saves thumbs up feedback directly', async () => {
    renderRow()

    const upButton = screen.getByRole('button', { name: 'Thumbs up feedback' })

    fireEvent.click(upButton)

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assessmentId: 'assess-001',
        findingId: 'sr-001',
        feedback: {
          feedback: 'up',
          comments: '',
        },
      })
    })
    expect(screen.getByRole('button', { name: 'Thumbs up feedback' }).className).toContain(
      'MuiIconButton-colorSuccess'
    )
  })

  it('requires risk level on thumbs down and saves selected level with reason', async () => {
    renderRow()

    fireEvent.click(screen.getByRole('button', { name: 'Thumbs down feedback' }))
    const saveNegativeFeedbackButton = await screen.findByRole(
      'button',
      { name: 'Save negative feedback', hidden: true }
    )

    expect(saveNegativeFeedbackButton).toBeDisabled()
    fireEvent.mouseDown(
      await screen.findByRole('combobox', { name: /risk level/i, hidden: true })
    )
    fireEvent.click(screen.getByRole('option', { name: 'Medium' }))

    const reasonInput = screen.getByLabelText('Reason', { selector: 'textarea' })
    expect(reasonInput).toBeInTheDocument()
    await waitFor(() => {
      expect(reasonInput).toHaveFocus()
    })

    fireEvent.change(reasonInput, {
      target: { value: 'Evidence does not support this risk call' },
    })
    expect(saveNegativeFeedbackButton).not.toBeDisabled()
    fireEvent.click(saveNegativeFeedbackButton)

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assessmentId: 'assess-001',
        findingId: 'sr-001',
        feedback: {
          feedback: 'down',
          feedbackType: 'Medium',
          comments: 'Evidence does not support this risk call',
        },
      })
    })
  })

  it('supports canceling the negative feedback reason flow', async () => {
    renderRow({ feedback: null, comments: '' })

    fireEvent.click(screen.getByRole('button', { name: 'Thumbs down feedback' }))
    fireEvent.mouseDown(
      await screen.findByRole('combobox', { name: /risk level/i, hidden: true })
    )
    fireEvent.click(screen.getByRole('option', { name: 'High' }))
    fireEvent.change(screen.getByLabelText('Reason', { selector: 'textarea' }), {
      target: { value: 'Temporary draft reason' },
    })
    fireEvent.click(
      await screen.findByRole('button', { name: 'Cancel negative feedback', hidden: true })
    )

    expect(screen.getByRole('button', { name: 'Thumbs down feedback' }).className).toContain(
      'MuiIconButton-colorPrimary'
    )
  })

  it('submits negative feedback on Enter when save is enabled', async () => {
    renderRow()

    fireEvent.click(screen.getByRole('button', { name: 'Thumbs down feedback' }))
    fireEvent.mouseDown(
      await screen.findByRole('combobox', { name: /risk level/i, hidden: true })
    )
    fireEvent.click(screen.getByRole('option', { name: 'Low' }))

    const reasonInput = screen.getByLabelText('Reason', { selector: 'textarea' })
    fireEvent.change(reasonInput, {
      target: { value: 'Submitting with Enter key' },
    })
    fireEvent.keyDown(reasonInput, { key: 'Enter', code: 'Enter' })

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assessmentId: 'assess-001',
        findingId: 'sr-001',
        feedback: {
          feedback: 'down',
          feedbackType: 'Low',
          comments: 'Submitting with Enter key',
        },
      })
    })
  })

  it('handles feedback submission failure gracefully', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    mockDispatch.mockImplementationOnce(() => ({
      unwrap: vi.fn().mockRejectedValue(new Error('save failed')),
    }))

    renderRow()
    fireEvent.click(screen.getByRole('button', { name: 'Thumbs up feedback' }))

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to save feedback:',
        expect.any(Error)
      )
    })

    errorSpy.mockRestore()
  })
})
