import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import RiskTableControls from './RiskTableControls'

describe('RiskTableControls', () => {
  it('renders controls and supports search and reset callbacks', () => {
    const onSearchQueryChange = vi.fn()
    const onRiskFilterChange = vi.fn()
    const onStatusFilterChange = vi.fn()
    const onResetControls = vi.fn()

    render(
      <RiskTableControls
        searchQuery=""
        onSearchQueryChange={onSearchQueryChange}
        riskFilter="all"
        onRiskFilterChange={onRiskFilterChange}
        statusFilter="all"
        onStatusFilterChange={onStatusFilterChange}
        onResetControls={onResetControls}
      />
    )

    fireEvent.change(screen.getByLabelText('Search…'), {
      target: { value: 'partial discharge' },
    })
    expect(onSearchQueryChange).toHaveBeenCalledWith('partial discharge')
    expect(screen.getByLabelText('Risk Level')).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toBeInTheDocument()

    expect(onRiskFilterChange).not.toHaveBeenCalled()
    expect(onStatusFilterChange).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Reset sort and filter controls' }))
    expect(onResetControls).toHaveBeenCalledTimes(1)
  })
})
