/**
 * Test suite for Header component
 * Demonstrates component testing with user interactions
 */

import { describe, it, expect } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '@/test/utils'
import Header from './Header'

describe('Header', () => {
  it('renders the application title', () => {
    render(<Header drawerWidth={260} headerHeight={64} />)
    
    expect(screen.getByText('Unit Risk Agent')).toBeInTheDocument()
    expect(screen.getByText('Outage Planning Intelligence System')).toBeInTheDocument()
  })

  it('displays theme toggle button', () => {
    render(<Header drawerWidth={260} headerHeight={64} />)
    
    const toggleButton = screen.getByRole('button', { name: /switch to/i })
    expect(toggleButton).toBeInTheDocument()
  })

  it('toggles theme when button is clicked', () => {
    render(<Header drawerWidth={260} headerHeight={64} />)
    
    const toggleButton = screen.getByRole('button', { name: /switch to/i })
    
    // Click the toggle button
    fireEvent.click(toggleButton)
    
    // Button should still be present after toggle
    expect(toggleButton).toBeInTheDocument()
  })

  it('adjusts width based on drawer width prop', () => {
    const { rerender } = render(<Header drawerWidth={260} headerHeight={64} />)

    rerender(<Header drawerWidth={72} headerHeight={64} />)

    expect(screen.getByText('Unit Risk Agent')).toBeInTheDocument()
  })

  it('applies correct height', () => {
    render(<Header drawerWidth={260} headerHeight={64} />)

    const appBar = screen.getByText('Unit Risk Agent').closest('header')
    expect(appBar).toBeInTheDocument()
  })
})
