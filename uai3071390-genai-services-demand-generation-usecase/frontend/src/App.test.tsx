import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { ThemeProvider } from './theme'
import { store } from './store'
import App from './App'

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <Provider store={store}>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </Provider>
    )

    // Multiple instances of this text exist (header + page title)
    const elements = screen.getAllByText(/Services Demand Generation/i)
    expect(elements.length).toBeGreaterThan(0)
  })

  it('displays welcome message', () => {
    render(
      <Provider store={store}>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </Provider>
    )

    // Page heading is "Services Demand Generation"
    const elements = screen.getAllByText(/Services Demand Generation/i)
    expect(elements.length).toBeGreaterThan(0)
  })
})
