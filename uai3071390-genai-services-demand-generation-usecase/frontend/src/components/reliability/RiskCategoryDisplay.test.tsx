import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { RiskCategory, RiskCondition } from '@/store/types'
import RiskCategoryDisplay from './RiskCategoryDisplay'

interface MockRiskConditionRowProps {
  condition: RiskCondition
  getRiskColor: (risk: string) => string
  getStatusColor: (status: string) => string
}

vi.mock('./RiskConditionRow', () => ({
  default: ({ condition, getRiskColor, getStatusColor }: MockRiskConditionRowProps) => (
    <tr data-testid={`row-${condition.findingId}`}>
      <td>{condition.findingId}</td>
      <td data-testid={`risk-color-${condition.findingId}`}>{getRiskColor(condition.riskLevel)}</td>
      <td data-testid={`status-color-${condition.findingId}`}>
        {getStatusColor(condition.status)}
      </td>
    </tr>
  ),
}))

const createCondition = (overrides: Partial<RiskCondition>): RiskCondition => ({
  findingId: 'z-000',
  id: 'z-000',
  category: 'Default',
  issueName: '',
  condition: 'Default condition',
  threshold: 'N/A',
  actualValue: 'N/A',
  riskLevel: 'Low',
  testMethod: 'Test',
  evidence: 'Evidence',
  dataSource: 'Source',
  justification: 'Justification',
  primaryCitation: 'Citation',
  status: 'complete',
  feedback: null,
  feedbackType: null,
  comments: '',
  ...overrides,
})

const createCategory = (overrides: Partial<RiskCategory> = {}): RiskCategory => ({
  id: 'stator-rewind',
  name: 'Stator Rewind Risk',
  component: 'Stator',
  overallRisk: 'Heavy',
  processDocument: 'GEK-123',
  reliabilityModelRef: 'Model v1',
  description: 'Risk table description',
  conditions: [
    createCondition({
      findingId: 'c-003',
      category: 'Electrical',
      condition: 'Condition C',
      riskLevel: 'High',
      status: 'complete',
    }),
    createCondition({
      findingId: 'a-001',
      category: 'Mechanical',
      condition: 'Condition A',
      riskLevel: 'Low',
      status: 'in-progress',
    }),
    createCondition({
      findingId: 'b-002',
      category: 'Thermal',
      condition: 'Condition B',
      riskLevel: 'Medium',
      status: 'data-needed',
    }),
    createCondition({
      findingId: 'd-004',
      category: 'Auxiliary',
      condition: 'Condition D',
      riskLevel: 'Unknown' as unknown as RiskCondition['riskLevel'],
      status: 'unknown-status' as unknown as RiskCondition['status'],
    }),
  ],
  ...overrides,
})

const getRenderedOrder = (): string[] =>
  screen
    .getAllByTestId(/row-/)
    .map((row) => row.getAttribute('data-testid') || '')
    .filter(Boolean)

const openSelect = (label: string) => {
  const selectElement = screen.getAllByLabelText(label)[0]
  if (!selectElement) {
    throw new Error(`Select control not found for label: ${label}`)
  }
  fireEvent.mouseDown(selectElement)
}

describe('RiskCategoryDisplay', () => {
  it('supports default sorting, filtering, reset, and no-results state', () => {
    render(
      <RiskCategoryDisplay
        category={createCategory()}
        assessmentId="assess-001"
        savedRows={{}}
        editable={false}
      />
    )

    expect(getRenderedOrder()).toEqual(['row-d-004', 'row-c-003', 'row-b-002', 'row-a-001'])
    fireEvent.click(screen.getByRole('button', { name: /stator rewind risk/i }))
    fireEvent.click(screen.getByRole('button', { name: /stator rewind risk/i }))

    fireEvent.change(screen.getByLabelText('Search…'), {
      target: { value: 'Condition B' },
    })
    expect(getRenderedOrder()).toEqual(['row-b-002'])

    openSelect('Risk Level')
    fireEvent.click(screen.getByRole('option', { name: 'High' }))
    expect(screen.queryByTestId('row-b-002')).not.toBeInTheDocument()

    openSelect('Status')
    fireEvent.click(screen.getByRole('option', { name: 'Data Needed' }))
    expect(screen.getByText('No conditions match selected filters.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reset sort and filter controls' }))
    expect(getRenderedOrder()).toEqual(['row-d-004', 'row-c-003', 'row-b-002', 'row-a-001'])
    expect(screen.getByText(/Showing:\s*4 of 4/)).toBeInTheDocument()
  })

  it('supports sort fields and both directions', () => {
    render(
      <RiskCategoryDisplay
        category={createCategory()}
        assessmentId="assess-001"
        savedRows={{}}
        editable={true}
      />
    )

    const findingHeader = screen.getByTestId('sort-header-condition')
    const categoryHeader = screen.getByTestId('sort-header-category')
    const riskLevelHeader = screen.getByTestId('sort-header-riskLevel')
    const statusHeader = screen.getByTestId('sort-header-status')

    expect(categoryHeader).toHaveStyle({ cursor: 'pointer' })
    expect(within(categoryHeader).getByText('Category')).toHaveStyle({ whiteSpace: 'nowrap' })
    expect(within(findingHeader).getByTestId('ImportExportIcon')).toBeInTheDocument()
    expect(within(categoryHeader).getByTestId('ImportExportIcon')).toBeInTheDocument()
    expect(within(riskLevelHeader).getByTestId('ArrowUpwardIcon')).toBeInTheDocument()
    expect(within(statusHeader).getByTestId('ImportExportIcon')).toBeInTheDocument()

    fireEvent.click(categoryHeader)
    expect(getRenderedOrder()).toEqual(['row-d-004', 'row-c-003', 'row-a-001', 'row-b-002'])
    expect(within(categoryHeader).getByTestId('ArrowDownwardIcon')).toBeInTheDocument()

    fireEvent.click(categoryHeader)
    expect(getRenderedOrder()).toEqual(['row-b-002', 'row-a-001', 'row-c-003', 'row-d-004'])
    expect(within(categoryHeader).getByTestId('ArrowUpwardIcon')).toBeInTheDocument()

    fireEvent.click(riskLevelHeader)
    expect(getRenderedOrder()).toEqual(['row-a-001', 'row-b-002', 'row-c-003', 'row-d-004'])
    expect(within(riskLevelHeader).getByTestId('ArrowDownwardIcon')).toBeInTheDocument()
    expect(within(categoryHeader).getByTestId('ImportExportIcon')).toBeInTheDocument()

    fireEvent.click(statusHeader)
    expect(getRenderedOrder()).toEqual(['row-c-003', 'row-a-001', 'row-b-002', 'row-d-004'])
    expect(within(statusHeader).getByTestId('ArrowDownwardIcon')).toBeInTheDocument()
    expect(within(riskLevelHeader).getByTestId('ImportExportIcon')).toBeInTheDocument()

    fireEvent.click(statusHeader)
    expect(getRenderedOrder()).toEqual(['row-d-004', 'row-b-002', 'row-a-001', 'row-c-003'])
    expect(within(statusHeader).getByTestId('ArrowUpwardIcon')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search\u2026'), {
      target: { value: 'not-present' },
    })
    const noResultsCell = screen.getByText('No conditions match selected filters.').closest('td')
    expect(noResultsCell).toHaveAttribute('colspan', '8')
  })

  it('maps risk and status colors for known and unknown values', () => {
    render(
      <RiskCategoryDisplay
        category={createCategory({ overallRisk: 'Unknown' as unknown as RiskCategory['overallRisk'] })}
        assessmentId="assess-001"
        savedRows={{}}
        editable={false}
      />
    )

    expect(screen.getByTestId('risk-color-a-001')).toHaveTextContent('success')
    expect(screen.getByTestId('risk-color-b-002')).toHaveTextContent('warning')
    expect(screen.getByTestId('risk-color-c-003')).toHaveTextContent('error')
    expect(screen.getByTestId('risk-color-d-004')).toHaveTextContent('default')
    expect(screen.getByTestId('status-color-c-003')).toHaveTextContent('success')
    expect(screen.getByTestId('status-color-a-001')).toHaveTextContent('info')
    expect(screen.getByTestId('status-color-b-002')).toHaveTextContent('warning')
    expect(screen.getByTestId('status-color-d-004')).toHaveTextContent('default')
  })
})
