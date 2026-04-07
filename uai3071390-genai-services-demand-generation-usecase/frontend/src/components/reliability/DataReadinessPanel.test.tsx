import { screen, within, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from '@/test/utils'
import type { Assessment } from '@/store/types'
import { API_BASE } from '@/store/api'
import { server } from '@/mocks/node'
import DataReadinessPanel from './DataReadinessPanel'

const SOURCE_NAME_TO_ID: Record<string, string> = {
  'Install Base Data': 'install-base',
  'ER Cases': 'er-cases',
  'FSR Reports': 'fsr-reports',
  'Outage History': 'outage-history',
  'Reliability Models': 'rel-models',
  'Uploaded Documents': 'uploaded',
}

const getSourceRow = (sourceName: string): HTMLElement => {
  const sourceId = SOURCE_NAME_TO_ID[sourceName]
  if (!sourceId) {
    throw new Error(`Could not resolve source id for "${sourceName}"`)
  }

  const row = screen.getByTestId(`data-source-row-${sourceId}`)
  if (!(row instanceof HTMLElement)) {
    throw new Error(`Could not find source row action element for "${sourceName}"`)
  }
  return row
}

const getSourceContainer = (sourceId: string): HTMLElement => {
  const container = screen.getByTestId(`data-source-${sourceId}`)
  if (!(container instanceof HTMLElement)) {
    throw new Error(`Could not find source container for "${sourceId}"`)
  }
  return container
}

describe('DataReadinessPanel', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
      configurable: true,
    })
  })

  const createAssessment = (overrides: Partial<Assessment> = {}): Assessment => ({
    id: 'assessment-1',
    serialNumber: 'GT12345',
    milestone: '18-month',
    reliabilityStatus: 'not-started',
    outageStatus: 'not-started',
    reliabilityFindings: [],
    outageFindings: [],
    reliabilityChat: [],
    outageChat: [],
    uploadedDocs: [],
    createdAt: '2026-02-18T12:00:00Z',
    updatedAt: '2026-02-18T12:00:00Z',
    ...overrides,
  })

  const renderPanel = (assessment: Assessment | null = createAssessment()) =>
    renderWithProviders(<DataReadinessPanel assessment={assessment} />)

  it('renders ER-specific preview headers and lazy-loads case previews', async () => {
    const assessment = createAssessment({
      serialNumber: 'GT12345',
      uploadedDocs: [
        {
          id: 'uploaded-1',
          name: 'test.pdf',
          category: 'fsr',
          uploadedAt: '2026-01-01',
          size: 1024,
          uploadedBy: 'user@example.com',
        },
      ],
    })
    renderPanel(assessment)

    // Wait for async data-readiness API data to load
    await waitFor(() => {
      expect(within(getSourceRow('ER Cases')).getByText(/2 items/i)).toBeInTheDocument()
    }, { timeout: 5000 })

    // Expanding accordion triggers lazy-load of ER cases detail data
    fireEvent.click(getSourceRow('ER Cases'))
    const erPreviewTable = await within(getSourceContainer('er-cases')).findByRole('table', {
      name: 'ER Cases case previews',
    })
    expect(within(erPreviewTable).getByRole('columnheader', { name: 'Case ID' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('columnheader', { name: 'Description' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('columnheader', { name: 'Close Notes' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('columnheader', { name: 'Date' })).toBeInTheDocument()
    expect(within(erPreviewTable).queryByRole('columnheader', { name: 'Outage' })).not.toBeInTheDocument()
    expect(
      within(erPreviewTable).getByRole('columnheader', { name: 'Case Summary' })
    ).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('cell', { name: 'ER-2023-001' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('cell', { name: 'HGP Degradation - Stage 1 Nozzles' })).toBeInTheDocument()
    expect(
      within(erPreviewTable).getByRole('cell', {
        name: 'Replaced Stage 1 nozzles during 2024 HGP inspection',
      })
    ).toBeInTheDocument()
  }, 30000)

  it('renders ER fallback description, close notes, and case summary values', async () => {
    server.use(
      http.get(`${API_BASE}/equipment/:esn/data-readiness`, ({ params }) =>
        HttpResponse.json({
          esn: params.esn,
          fromDate: null,
          toDate: null,
          dataSources: {
            ibatData: { available: true },
            erCases: { available: true, count: 2 },
            fsrReports: { available: false, count: 0 },
            outageHistory: { available: false, count: 0 },
            prismData: { available: true },
          },
          totalAvailable: 3,
          totalSources: 5,
        })
      ),
      http.get(`${API_BASE}/equipment/:esn/er-cases`, () =>
        HttpResponse.json({
          erCases: [
            {
              erNumber: 'ER-OPEN-001',
              title: 'Fallback Title',
              description: 'Explicit ER description',
              dateReported: '2026-01-15',
              status: 'Open',
              severity: 'High',
              component: 'Rotor',
            },
            {
              erNumber: 'ER-CLOSED-002',
              title: 'Closed Case Title',
              dateReported: '2026-02-20',
              status: 'Closed',
              severity: 'Medium',
              component: 'Combustion',
              summary: 'Closed case summary.',
            },
          ],
        })
      )
    )

    renderPanel(createAssessment({ serialNumber: 'ER-FALLBACK-UNIT' }))

    await waitFor(() => {
      expect(within(getSourceRow('ER Cases')).getByText(/2 items/i)).toBeInTheDocument()
    })

    fireEvent.click(getSourceRow('ER Cases'))
    const erPreviewTable = await within(getSourceContainer('er-cases')).findByRole('table', {
      name: 'ER Cases case previews',
    })

    expect(within(erPreviewTable).getAllByRole('cell', { name: 'Explicit ER description' })).toHaveLength(2)
    expect(within(erPreviewTable).getByRole('cell', { name: 'Resolution pending.' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('cell', { name: 'Closed Case Title' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('cell', { name: 'Closed without additional notes.' })).toBeInTheDocument()
    expect(within(erPreviewTable).getByRole('cell', { name: 'Closed case summary.' })).toBeInTheDocument()
  })

  it('renders safely when assessment is null', () => {
    renderPanel(null)
    expect(screen.getByText('Step 2: Data Readiness Review')).toBeInTheDocument()
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('To')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to Analysis' })).toBeInTheDocument()
  })

  it('keeps non-ER preview headers unchanged', async () => {
    const assessment = createAssessment({ serialNumber: 'GT12345' })
    renderPanel(assessment)

    // Wait for async data-readiness API data to load
    await waitFor(() => {
      expect(within(getSourceRow('ER Cases')).getByText(/2 items/i)).toBeInTheDocument()
    }, { timeout: 5000 })
    expect(within(getSourceRow('FSR Reports')).getByText(/1 item/i)).toBeInTheDocument()
    expect(within(getSourceRow('Outage History')).getByText(/2 items/i)).toBeInTheDocument()

    fireEvent.click(getSourceRow('FSR Reports'))
    const fsrPreviewTable = await within(getSourceContainer('fsr-reports')).findByRole('table', {
      name: 'FSR Reports case previews',
    })
    expect(within(fsrPreviewTable).getByRole('columnheader', { name: 'Title' })).toBeInTheDocument()
    expect(within(fsrPreviewTable).getByRole('columnheader', { name: 'Date' })).toBeInTheDocument()
    expect(within(fsrPreviewTable).getByRole('columnheader', { name: 'Outage' })).toBeInTheDocument()
    expect(within(fsrPreviewTable).getByRole('columnheader', { name: 'Outage Summary' })).toBeInTheDocument()
    expect(within(fsrPreviewTable).getByRole('cell', { name: 'HGP Borescope Inspection' })).toBeInTheDocument()
  })

  it('renders outage-history fallback summaries and collapses previews', async () => {
    server.use(
      http.get(`${API_BASE}/equipment/:esn/data-readiness`, ({ params }) =>
        HttpResponse.json({
          esn: params.esn,
          fromDate: null,
          toDate: null,
          dataSources: {
            ibatData: { available: false },
            erCases: { available: false, count: 0 },
            fsrReports: { available: false, count: 0 },
            outageHistory: { available: true, count: 1 },
            prismData: { available: false },
          },
          totalAvailable: 1,
          totalSources: 5,
        })
      ),
      http.get(`${API_BASE}/equipment/:esn/outage-history`, () =>
        HttpResponse.json({
          outageHistory: [
            {
              outageId: 'OUT-2026-001',
              outageType: 'Minor',
              startDate: '2026-03-01',
              endDate: '2026-03-02',
              duration: 1,
              workPerformed: [],
            },
          ],
        })
      )
    )

    renderPanel(createAssessment({ serialNumber: 'OUTAGE-FALLBACK-UNIT' }))

    await waitFor(() => {
      expect(within(getSourceRow('Outage History')).getByText(/1 item/i)).toBeInTheDocument()
    })

    fireEvent.click(getSourceRow('Outage History'))
    const outagePreviewTable = await within(getSourceContainer('outage-history')).findByRole('table', {
      name: 'Outage History case previews',
    })
    expect(
      within(outagePreviewTable).getByRole('cell', { name: 'Minor outage starting 2026-03-01.' })
    ).toBeInTheDocument()

    fireEvent.click(getSourceRow('Outage History'))
    await waitFor(() => {
      expect(
        within(getSourceContainer('outage-history')).queryByRole('table', {
          name: 'Outage History case previews',
        })
      ).not.toBeInTheDocument()
    })
  })

  it('keeps continue-to-analysis behavior intact', async () => {
    const scrollIntoViewMock = vi.fn()
    const assessment = createAssessment({ serialNumber: 'UNKNOWN-UNIT' })
    renderPanel(assessment)

    // Wait for data-readiness API to resolve so aria-disabled is populated
    await waitFor(() => {
      expect(getSourceRow('Outage History')).toHaveAttribute('aria-disabled', 'true')
    })

    const continueButton = screen.getByRole('button', { name: 'Continue to Analysis' })
    const riskSection = document.createElement('div')
    riskSection.id = 'risk-analysis-section'
    riskSection.scrollIntoView = scrollIntoViewMock
    document.body.appendChild(riskSection)

    fireEvent.click(continueButton)
    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1)

    const outageRow = getSourceRow('Outage History')
    expect(outageRow).toHaveAttribute('aria-disabled', 'true')

    riskSection.remove()
  }, 15000)
})
