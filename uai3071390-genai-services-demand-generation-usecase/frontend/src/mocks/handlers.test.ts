/**
 * MSW Handlers Test
 * Demonstrates API mocking with MSW
 */

import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/node'
import { API_BASE } from '@/store/api'

describe('MSW Handlers', () => {
  it('mocks health check endpoint', async () => {
    const response = await fetch(`${API_BASE}/health`)
    expect(response.ok).toBe(true)
    
    const data = await response.json()
    expect(data).toHaveProperty('status', 'ok')
    expect(data).toHaveProperty('timestamp')
  })

  /**
   * Auth is handled by API Gateway (PingID JWKS authorizer) — no /auth/* routes exist
   * on the API Service. Verify the units endpoint works instead.
   */
  it('mocks units endpoint (auth is upstream at API Gateway)', async () => {
    const response = await fetch(`${API_BASE}/units`)
    expect(response.ok).toBe(true)

    const data = await response.json()
    expect(data).toHaveProperty('units')
    expect(Array.isArray(data.units)).toBe(true)
  })

  it('can override handlers for specific tests', async () => {
    // Override the health check handler for this test
    server.use(
      http.get(`${API_BASE}/health`, () => {
        return HttpResponse.json({ status: 'maintenance' }, { status: 503 })
      })
    )
    
    const response = await fetch(`${API_BASE}/health`)
    expect(response.status).toBe(503)
    
    const data = await response.json()
    expect(data.status).toBe('maintenance')
  })
})
