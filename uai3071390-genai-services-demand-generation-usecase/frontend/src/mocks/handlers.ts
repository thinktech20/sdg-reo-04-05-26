/**
 * MSW HTTP Request Handlers
 *
 * Mirrors the API Service contract exactly:
 *   - Auth:  handled upstream by API Gateway (PingID JWKS) — no /auth/* routes here
 *   - Chat:  handled by Q&A Agent container — no /chat/* routes here
 *   - Units: was /api/trains — now /api/units (domain terminology)
 *
 * All endpoints match backend/api/routes/:
 *   equipment   → GET /api/units, GET /api/equipment/search, GET|POST /api/equipment/:esn/*
 *   assessments → POST|GET /api/assessments, POST /analyze/*, GET /status, PUT reliability|outage
 *   documents   → GET /api/equipment/:esn/er-cases|fsr-reports|outage-history|documents
 */

import { http, HttpResponse } from 'msw'
import {
  MOCK_ASSESSMENTS,
  SAMPLE_GENERATOR_RELIABILITY_ANALYSIS,
  SAMPLE_GENERATOR_NARRATIVE,
  type Assessment,
  type UploadedDocument,
} from './data/assessments'
import { MOCK_ER_CASES, MOCK_FSR_REPORTS, MOCK_OUTAGE_HISTORY } from './data/documents'
import { MOCK_TRAINS } from './data/equipment'

import { API_BASE } from '@/store/api'

// In-memory uploaded-document store (per ESN, resets each test run)
const uploadedDocs: Record<string, UploadedDocument[]> = {}

// In-memory assessment store seeded from mock data
const assessments: Record<string, Assessment> = { ...MOCK_ASSESSMENTS }

// Tracks which analyze jobs have been submitted (assessmentId:jobType → true)
const analyzedJobs: Record<string, boolean> = {}

export const handlers = [
  // ── Meta ─────────────────────────────────────────────────────────────────

  http.get(`${API_BASE}/health`, () =>
    HttpResponse.json({ status: 'ok', service: 'api-service', timestamp: new Date().toISOString() }),
  ),

  // ── Equipment / Units ─────────────────────────────────────────────────────

  /**
   * GET /api/units
   * Returns all units with optional filter_type and search query params.
   */
  http.get(`${API_BASE}/units`, ({ request }) => {
    const url = new URL(request.url)
    const filterType = url.searchParams.get('filter_type') ?? 'all'
    const search = (url.searchParams.get('search') ?? '').toLowerCase()

    let units = [...MOCK_TRAINS]

    if (filterType !== 'all') {
      units = units.filter((u) => u.outageType.toLowerCase() === filterType.toLowerCase())
    }

    if (search) {
      units = units.filter(
        (u) =>
          u.trainName.toLowerCase().includes(search) ||
          u.site.toLowerCase().includes(search) ||
          u.outageId.toLowerCase().includes(search) ||
          u.equipment.some(
            (eq) =>
              eq.serialNumber.toLowerCase().includes(search) ||
              eq.equipmentCode.toLowerCase().includes(search),
          ),
      )
    }

    return HttpResponse.json({ units })
  }),

  /**
   * GET /api/equipment/search?esn=
   * Look up a single piece of equipment by serial number / ESN.
   */
  // http.get(`${API_BASE}/equipment/search`, ({ request }) => {
  //   const url = new URL(request.url)
  //   const esn = url.searchParams.get('esn') ?? ''

  //   const equipment = MOCK_INSTALL_BASE.find(
  //     (e) => e.serialNumber.toLowerCase() === esn.toLowerCase(),
  //   )

  //   if (!equipment) {
  //     return HttpResponse.json({ error: `Equipment '${esn}' not found` }, { status: 404 })
  //   }

  //   return HttpResponse.json({ equipment })
  // }),

  /** GET /api/equipment/:esn/er-cases */
  http.get(`${API_BASE}/equipment/:esn/er-cases`, ({ params }) => {
    const esn = params.esn as string
    return HttpResponse.json({ erCases: MOCK_ER_CASES[esn] ?? [] })
  }),

  /** GET /api/equipment/:esn/data-readiness */
  http.get(`${API_BASE}/equipment/:esn/data-readiness`, ({ params, request }) => {
    const esn = params.esn as string
    const url = new URL(request.url)
    const fromDate = url.searchParams.get('from_date') ?? undefined
    const toDate = url.searchParams.get('to_date') ?? undefined

    const inRange = (dateStr: string | undefined) => {
      if (!dateStr) return true
      if (fromDate && dateStr < fromDate) return false
      if (toDate && dateStr > toDate) return false
      return true
    }

    const erCases = (MOCK_ER_CASES[esn] ?? []).filter((c) => inRange(c.dateReported))
    const fsrReports = (MOCK_FSR_REPORTS[esn] ?? []).filter((r) => inRange(r.outageDate))
    const outageHistory = (MOCK_OUTAGE_HISTORY[esn] ?? []).filter((e) => inRange(e.startDate))

    const dataSources = {
      ibatData: { available: (MOCK_ER_CASES[esn] ?? []).length > 0 },
      erCases: { available: erCases.length > 0, count: erCases.length },
      fsrReports: { available: fsrReports.length > 0, count: fsrReports.length },
      outageHistory: { available: outageHistory.length > 0, count: outageHistory.length },
      prismData: { available: (MOCK_ER_CASES[esn] ?? []).length > 0 },
    }
    const totalAvailable = Object.values(dataSources).filter((s) => s.available).length

    return HttpResponse.json({
      esn,
      fromDate: fromDate ?? null,
      toDate: toDate ?? null,
      dataSources,
      totalAvailable,
      totalSources: Object.keys(dataSources).length,
    })
  }),

  /** GET /api/equipment/:esn/fsr-reports */
  http.get(`${API_BASE}/equipment/:esn/fsr-reports`, ({ params }) => {
    const esn = params.esn as string
    return HttpResponse.json({ fsrReports: MOCK_FSR_REPORTS[esn] ?? [] })
  }),

  /** GET /api/equipment/:esn/outage-history */
  http.get(`${API_BASE}/equipment/:esn/outage-history`, ({ params }) => {
    const esn = params.esn as string
    return HttpResponse.json({ outageHistory: MOCK_OUTAGE_HISTORY[esn] ?? [] })
  }),

  /** GET /api/equipment/:esn/documents */
  http.get(`${API_BASE}/equipment/:esn/documents`, ({ params }) => {
    const esn = params.esn as string
    return HttpResponse.json({ documents: uploadedDocs[esn] ?? [] })
  }),

  /**
   * GET /api/case-previews?sourceId=&serialNumber=&startDate=&endDate=
   * Mock endpoint used by Data Readiness preview accordion to simulate first-load fetch.
   */
  http.get(`${API_BASE}/case-previews`, async () => {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return HttpResponse.json({ status: 'ok' })
  }),

  /**
   * POST /api/equipment/:esn/documents
   * Accepts multipart/form-data with `file` and `category` fields.
   */
  http.post(`${API_BASE}/equipment/:esn/documents`, async ({ params, request }) => {
    const esn = params.esn as string
    const formData = await request.formData()
    const file = formData.get('file') as File
    const category = (formData.get('category') as string) ?? 'other'

    const doc: UploadedDocument = {
      id: `doc-${Date.now()}`,
      name: file?.name ?? 'upload',
      category: category as UploadedDocument['category'],
      uploadedAt: new Date().toISOString(),
      size: file?.size ?? 0,
      uploadedBy: 'test-user',
    }

    uploadedDocs[esn] = [...(uploadedDocs[esn] ?? []), doc]
    return HttpResponse.json({ document: doc }, { status: 201 })
  }),

  // ── Assessments ───────────────────────────────────────────────────────────

  /**
   * POST /api/assessments
   * Create a new assessment. Returns 201 + { assessment }.
   */
  http.post(`${API_BASE}/assessments`, async ({ request }) => {
    const body = (await request.json()) as Partial<Assessment & { serialNumber: string; esn: string }>
    const serialNumber = body.esn ?? body.serialNumber ?? 'UNKNOWN'
    const milestone = body.milestone ?? '18-month'
    const key = `${serialNumber}-${milestone}`

    if (assessments[key]) {
      return HttpResponse.json({ assessment: assessments[key] }, { status: 201 })
    }

    const assessment: Assessment = {
      id: `assess-${Date.now()}`,
      serialNumber,
      milestone: milestone,
      reliabilityStatus: 'not-started',
      outageStatus: 'not-started',
      reliabilityFindings: [],
      outageFindings: [],
      reliabilityChat: [],
      outageChat: [],
      uploadedDocs: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }

    assessments[key] = assessment
    return HttpResponse.json({ assessment }, { status: 201 })
  }),

  /**
   * GET /api/assessments/:id
   */
  http.get(`${API_BASE}/assessments/:id`, ({ params }) => {
    const id = params.id as string
    const assessment = Object.values(assessments).find((a) => a.id === id)

    if (!assessment) {
      return HttpResponse.json({ error: 'Assessment not found' }, { status: 404 })
    }

    return HttpResponse.json({ assessment })
  }),

  /**
   * POST /api/assessments/:id/analyze/run  → 202 PENDING
   * Unified endpoint for both RE and OE personas.
   */
  http.post(`${API_BASE}/assessments/:id/analyze/run`, async ({ params, request }) => {
    const id = params.id as string
    const body = (await request.json()) as { persona?: string; workflowId?: string }
    const persona = (body.persona ?? 'RE').toUpperCase()
    // workflowId may be passed explicitly (e.g. RE_NARRATIVE for regeneration)
    const workflowId = body.workflowId ?? `${persona}_DEFAULT`
    analyzedJobs[`${id}:${workflowId}`] = true
    // Seed assessment store on the default analysis run
    const existing = Object.values(assessments).find((a) => a.id === id)
    if (existing && persona === 'RE' && !workflowId.endsWith('_NARRATIVE')) {
      const key = `${existing.serialNumber}-${existing.milestone}`
      assessments[key] = {
        ...existing,
        reliabilityStatus: 'completed',
        reliabilityRiskCategories: SAMPLE_GENERATOR_RELIABILITY_ANALYSIS as Assessment['reliabilityRiskCategories'],
        narrativeSummary: SAMPLE_GENERATOR_NARRATIVE,
        updatedAt: new Date().toISOString(),
      }
    } else if (existing && workflowId.endsWith('_NARRATIVE')) {
      // Narrative regeneration — update narrativeSummary in store
      const key = `${existing.serialNumber}-${existing.milestone}`
      assessments[key] = {
        ...existing,
        narrativeSummary: SAMPLE_GENERATOR_NARRATIVE,
        updatedAt: new Date().toISOString(),
      }
    }
    return HttpResponse.json(
      { assessmentId: id, workflowId, workflowStatus: 'PENDING' },
      { status: 202 },
    )
  }),

  /**
   * POST /api/assessments/:id/analyze/reliability  → 202 PENDING
   */
  http.post(`${API_BASE}/assessments/:id/analyze/reliability`, ({ params }) => {
    const id = params.id as string
    analyzedJobs[`${id}:reliability`] = true
    return HttpResponse.json(
      { assessmentId: id, jobType: 'reliability', status: 'PENDING' },
      { status: 202 },
    )
  }),

  /**
   * POST /api/assessments/:id/analyze/outage  → 202 PENDING
   */
  http.post(`${API_BASE}/assessments/:id/analyze/outage`, ({ params }) => {
    const id = params.id as string
    analyzedJobs[`${id}:outage`] = true
    return HttpResponse.json(
      { assessmentId: id, jobType: 'outage', status: 'PENDING' },
      { status: 202 },
    )
  }),

  /**
   * GET /api/assessments/:id/status?workflowId=RE_DEFAULT|OE_DEFAULT|RE_NARRATIVE|OE_NARRATIVE
   * Returns COMPLETED on first poll after analyze/run was called.
   * Shape matches real data-service API: { assessmentId, workflowId, workflowStatus, activeNode, nodeTimings }
   */
  http.get(`${API_BASE}/assessments/:id/status`, ({ params, request }) => {
    const id = params.id as string
    const url = new URL(request.url)
    const workflowId = url.searchParams.get('workflowId') ?? 'RE_DEFAULT'

    const wasSubmitted = analyzedJobs[`${id}:${workflowId}`] ?? false

    return HttpResponse.json({
      assessmentId: id,
      workflowId,
      workflowStatus: wasSubmitted ? 'COMPLETED' : 'PENDING',
      activeNode: wasSubmitted ? null : 'risk_eval',
      nodeTimings: wasSubmitted ? {} : null,
      errorMessage: null,
    })
  }),

  /**
   * PUT /api/assessments/:id/reliability
   * Update reliability findings on an assessment.
   */
  http.put(`${API_BASE}/assessments/:id/reliability`, async ({ params, request }) => {
    const id = params.id as string
    const body = (await request.json()) as Partial<Assessment>
    const assessment = Object.values(assessments).find((a) => a.id === id)

    if (!assessment) {
      return HttpResponse.json({ error: 'Assessment not found' }, { status: 404 })
    }

    const updated = { ...assessment, ...body, updatedAt: new Date().toISOString() }
    const key = `${assessment.serialNumber}-${assessment.milestone}`
    assessments[key] = updated

    return HttpResponse.json({ assessment: updated })
  }),

  /**
   * PUT /api/assessments/:id/outage
   * Update outage scope on an assessment.
   */
  http.put(`${API_BASE}/assessments/:id/outage`, async ({ params, request }) => {
    const id = params.id as string
    const body = (await request.json()) as Partial<Assessment>
    const assessment = Object.values(assessments).find((a) => a.id === id)

    if (!assessment) {
      return HttpResponse.json({ error: 'Assessment not found' }, { status: 404 })
    }

    const updated = { ...assessment, ...body, updatedAt: new Date().toISOString() }
    const key = `${assessment.serialNumber}-${assessment.milestone}`
    assessments[key] = updated

    return HttpResponse.json({ assessment: updated })
  }),

  /**
   * POST /api/assessments/:id/findings/:findingId/feedback
   */
  http.post(
    `${API_BASE}/assessments/:id/findings/:findingId/feedback`,
    () => HttpResponse.json({ success: true }),
  ),
]
