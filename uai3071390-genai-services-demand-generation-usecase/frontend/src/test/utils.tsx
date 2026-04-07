/**
 * Test Utilities
 * Helper functions for testing React components and Redux
 */

import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { Provider } from 'react-redux'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from '@/theme'
import { store as defaultStore } from '@/store'
import { configureStore } from '@reduxjs/toolkit'
import type { RootState } from '@/store'
import authReducer from '@/store/slices/authSlice'
import uiReducer from '@/store/slices/uiSlice'
import equipmentReducer from '@/store/slices/equipmentSlice'
import assessmentsReducer from '@/store/slices/assessmentsSlice'
import documentsReducer from '@/store/slices/documentsSlice'
import chatReducer from '@/store/slices/chatSlice'
import type { User, Equipment, Train, Assessment, ERCase, FSRReport, OutageEvent, ChatMessage, UploadedDocument } from '@/store/types'

/**
 * Create a test store with optional preloaded state
 */
export function createTestStore(preloadedState?: Partial<RootState>) {
  return configureStore({
    reducer: {
      auth: authReducer,
      ui: uiReducer,
      equipment: equipmentReducer,
      assessments: assessmentsReducer,
      documents: documentsReducer,
      chat: chatReducer,
    },
    preloadedState: preloadedState as RootState,
  })
}

export type TestStore = ReturnType<typeof createTestStore>

/**
 * Custom render function that wraps components with required providers
 * Use this instead of @testing-library/react's render for component tests
 */
export function renderWithProviders(
  ui: ReactElement,
  {
    // Override store if needed
    preloadedState = {},
    store = preloadedState ? createTestStore(preloadedState) : defaultStore,
    // Override render options if needed
    ...renderOptions
  }: RenderOptions & { preloadedState?: Partial<RootState>; store?: TestStore | typeof defaultStore } = {}
) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <Provider store={store}>
        <ThemeProvider>
          <BrowserRouter>{children}</BrowserRouter>
        </ThemeProvider>
      </Provider>
    )
  }

  return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) }
}

// ============================================================================
// MOCK DATA FACTORIES
// ============================================================================

/**
 * Create mock user for testing
 */
export const createMockUser = (overrides: Partial<User> = {}): User => ({
  id: '1',
  sso: 'demo',
  name: 'Demo User',
  email: 'demo@example.com',
  role: 'reliability',
  accessLevel: 'normal',
  ...overrides,
})

/**
 * Create mock equipment for testing
 */
export const createMockEquipment = (overrides: Partial<Equipment> = {}): Equipment => ({
  serialNumber: 'GT12345',
  equipmentType: 'Gas Turbine',
  equipmentCode: 'GT-001',
  model: '7FA',
  site: 'Moss Landing',
  commercialOpDate: '2020-01-01',
  totalEOH: 50000,
  totalStarts: 1000,
  ...overrides,
})

/**
 * Create mock train for testing
 */
export const createMockTrain = (overrides: Partial<Train> = {}): Train => ({
  id: '1',
  trainName: 'Moss Landing Unit 1',
  site: 'Moss Landing Energy Storage Facility, California',
  trainType: 'Combined Cycle 1x1',
  outageId: 'OUT-2026-001',
  outageType: 'Major',
  startDate: '2026-03-01',
  endDate: '2026-03-15',
  equipment: [createMockEquipment()],
  ...overrides,
})

/**
 * Create mock assessment for testing
 */
export const createMockAssessment = (overrides: Partial<Assessment> = {}): Assessment => ({
  id: 'assessment-1',
  serialNumber: 'GT12345',
  reviewPeriod: '18-month',
  reliabilityStatus: 'not-started',
  outageStatus: 'not-started',
  createdAt: '2026-02-18T12:00:00Z',
  updatedAt: '2026-02-18T12:00:00Z',
  reliabilityFindings: [],
  outageFindings: [],
  reliabilityChat: [],
  outageChat: [],
  uploadedDocs: [],
  ...overrides,
})

/**
 * Create mock ER case for testing
 */
export const createMockERCase = (overrides: Partial<ERCase> = {}): ERCase => ({
  erNumber: 'ER-2025-001',
  title: 'Test ER Case',
  summary: 'Test ER case summary.',
  description: 'Test ER case description',
  dateReported: '2025-01-15',
  status: 'Open',
  severity: 'High',
  component: 'Hot Gas Path',
  ...overrides,
})

/**
 * Create mock FSR report for testing
 */
export const createMockFSRReport = (overrides: Partial<FSRReport> = {}): FSRReport => ({
  reportId: 'FSR-2025-001',
  title: 'Test FSR Report',
  dateCompleted: '2025-02-01',
  outageDate: '2025-01-01',
  testType: 'Field Service',
  findings: 'Test FSR report findings',
  recommendation: 'Test recommendation',
  component: 'Turbine',
  ...overrides,
})

/**
 * Create mock outage event for testing
 */
export const createMockOutageEvent = (overrides: Partial<OutageEvent> = {}): OutageEvent => ({
  outageId: 'OUT-2025-001',
  startDate: '2025-01-01',
  endDate: '2025-01-15',
  duration: 14,
  outageType: 'Major',
  workPerformed: ['Maintenance', 'Testing'],
  ...overrides,
})

/**
 * Create mock uploaded document for testing
 */
export const createMockUploadedDocument = (overrides: Partial<UploadedDocument> = {}): UploadedDocument => ({
  id: '1',
  name: 'test.pdf',
  category: 'fsr',
  uploadedAt: '2026-01-01',
  size: 1024,
  uploadedBy: 'user@example.com',
  ...overrides,
})

/**
 * Create mock chat message for testing
 */
export const createMockChatMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  role: 'user',
  content: 'Test message',
  timestamp: new Date().toISOString(),
  ...overrides,
})

// Re-export everything from testing library
export * from '@testing-library/react'
export { renderWithProviders as render }
