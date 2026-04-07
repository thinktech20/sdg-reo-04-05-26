/**
 * Test suite for HomePage component
 */

import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '@/test/utils'
import HomePage from './HomePage'

describe('HomePage', () => {
  it('renders the page heading', () => {
    render(<HomePage />)
    expect(
      screen.getByRole('heading', { name: /Services Demand Generation/i }),
    ).toBeInTheDocument()
  })

  it('displays the application description', () => {
    render(<HomePage />)
    expect(screen.getByText(/AI-powered reliability assessment/i)).toBeInTheDocument()
  })

  it('shows feature cards', () => {
    render(<HomePage />)
    expect(screen.getByText('Units')).toBeInTheDocument()
    expect(screen.getByText('Search by ESN')).toBeInTheDocument()
    expect(screen.getByText('My Assessments')).toBeInTheDocument()
  })

  it('has active navigation buttons', () => {
    render(<HomePage />)
    expect(screen.getByRole('button', { name: /View Units/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Search Equipment/i })).toBeEnabled()
  })

  it('shows a coming-soon button for My Assessments', () => {
    render(<HomePage />)
    const comingSoonButtons = screen.getAllByRole('button', { name: /Coming Soon/i })
    expect(comingSoonButtons.length).toBeGreaterThan(0)
    expect(comingSoonButtons[0]).toBeDisabled()
  })
})
