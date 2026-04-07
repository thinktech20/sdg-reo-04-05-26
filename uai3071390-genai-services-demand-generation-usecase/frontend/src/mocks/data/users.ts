/**
 * Mock user data for MSW
 * Migrated from sdg-risk-analyser-archive
 */

export interface User {
  id: string
  sso: string
  name: string
  email: string
  role: 'reliability' | 'outage' | 'admin'
  accessLevel: 'normal' | 'super'
}

export const MOCK_USERS: User[] = [
  {
    id: 'u001',
    sso: 'demo',
    name: 'Demo User',
    email: 'demo@ge.com',
    role: 'reliability',
    accessLevel: 'normal',
  },
  {
    id: 'u002',
    sso: 'jsmith',
    name: 'John Smith',
    email: 'john.smith@ge.com',
    role: 'reliability',
    accessLevel: 'normal',
  },
  {
    id: 'u003',
    sso: 'mjohnson',
    name: 'Mary Johnson',
    email: 'mary.johnson@ge.com',
    role: 'outage',
    accessLevel: 'normal',
  },
  {
    id: 'u004',
    sso: 'admin',
    name: 'Admin User',
    email: 'admin@ge.com',
    role: 'admin',
    accessLevel: 'super',
  },
]

// Mock JWT token (not a real token, just for demo)
export const generateMockToken = (userId: string): string => {
  return `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(JSON.stringify({ userId, iat: Date.now() }))}.mock-signature`
}
