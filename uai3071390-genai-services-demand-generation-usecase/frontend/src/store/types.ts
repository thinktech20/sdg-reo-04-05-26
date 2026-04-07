/**
 * Redux Store Type Definitions
 * Centralized type definitions for all store slices
 * Migrated from sdg-risk-analyser-archive
 */

import type { RiskCondition, RiskCategory, Assessment as AssessmentData, UploadedDocument } from '@/mocks/data/assessments'
import type { Equipment, Train } from '@/mocks/data/equipment'
import type { User } from '@/mocks/data/users'
import type { ERCase, FSRReport, OutageEvent } from '@/mocks/data/documents'

// Re-export types from mock data for convenience
export type {
  RiskCondition,
  RiskCategory,
  Equipment,
  Train,
  User,
  ERCase,
  FSRReport,
  OutageEvent,
  UploadedDocument,
}

// ============================================================================
// AUTH TYPES
// ============================================================================

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  loading: boolean
  error: string | null
}

// ============================================================================
// UI TYPES
// ============================================================================

export interface UIState {
  theme: 'light' | 'dark'
  sidebarCollapsed: boolean
  sidebarOpen: boolean
}

// ============================================================================
// EQUIPMENT TYPES
// ============================================================================

export interface EquipmentState {
  trains: Train[]
  selectedEquipment: Equipment | null
  searchResults: Equipment[]
  loading: boolean
  /** True only while fetchTrains is in-flight (distinct from ESN-search loading). */
  trainsLoading: boolean
  error: string | null
  filters: {
    type: string
    search: string
  }
}

// ============================================================================
// ASSESSMENT TYPES
// ============================================================================

export type Assessment = AssessmentData

// ============================================================================
// JOB STATUS TYPES (Task Bridge / async analysis)
// ============================================================================

/** Status values for async analysis jobs tracked via Task Bridge (SQS → ECS). */
export type JobStatusValue = 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED'

export interface NodeTiming {
  startedAt: string
  completedAt?: string
}

export interface JobStatus {
  assessmentId: string
  workflowId: string
  workflowStatus: string       // PENDING | IN_QUEUE | IN_PROGRESS | COMPLETED | FAILED
  errorMessage?: string
  /** Which pipeline node is currently executing. */
  activeNode?: string
  /** Per-node start / end timestamps keyed by node name. */
  nodeTimings?: Record<string, NodeTiming>
}

// ============================================================================
// ASSESSMENT STATE
// ============================================================================

export interface AssessmentState {
  assessments: Record<string, Assessment>
  currentAssessment: Assessment | null
  loading: boolean
  analyzing: boolean
  error: string | null
  /**
   * Tracks async job state per assessment and jobType.
   * Shape: { [assessmentId]: { reliability?: JobStatus; outage?: JobStatus } }
   */
  analyzeJobs: Record<string, Record<string, JobStatus>>
}

// ============================================================================
// DOCUMENT TYPES
// ============================================================================

export interface ERCasePreview {
  erNumber: string
  dateReported: string
  component: string
  summary: string
}

export interface PrismReadiness {
  available: boolean
  statorRisk?: string | null
  rotorRisk?: string | null
  statorLastRewind?: string | null
  rotorLastRewind?: string | null
  error?: string
}

export interface InstallBaseReadiness {
  available: boolean
  model?: string | null
  equipmentType?: string | null
  commercialOpDate?: string | null
  site?: string | null
}

export interface ERCasesReadiness {
  available: boolean
  count: number
  preview?: ERCasePreview[]
  error?: string
}

export interface SourceReadiness {
  available: boolean
  count: number
}

export interface DataReadiness {
  esn: string
  fromDate: string | null
  toDate: string | null
  dataSources: {
    ibatData: { available: boolean }
    erCases: { available: boolean; count: number }
    fsrReports: { available: boolean; count: number }
    outageHistory: { available: boolean; count: number }
    prismData: { available: boolean }
  }
  totalAvailable: number
  totalSources: number
}

export interface PaginatedList<T> {
  items: T[]
  page: number
  hasMore: boolean
}

export interface DocumentState {
  erCases: Record<string, PaginatedList<ERCase>>
  fsrReports: Record<string, PaginatedList<FSRReport>>
  outageHistory: Record<string, PaginatedList<OutageEvent>>
  uploadedDocs: Record<string, UploadedDocument[]>
  dataReadiness: Record<string, DataReadiness>
  loading: boolean
  error: string | null
}

// ============================================================================
// CHAT TYPES
// ============================================================================

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface ChatResponse {
  message: string
  timestamp: string
  agent: 'reliability-agent' | 'outage-agent'
}

export interface ChatState {
  reliabilityChats: Record<string, ChatMessage[]>
  outageChats: Record<string, ChatMessage[]>
  loading: boolean
  error: string | null
  reliabilityLoading: Record<string, boolean>
  reliabilityErrors: Record<string, string | null>
}

// ============================================================================
// API REQUEST/RESPONSE TYPES
// ============================================================================

export interface ApiError {
  error: string
  status?: number
}

export interface LoginRequest {
  sso: string
}

export interface LoginResponse {
  user: User
  token: string
}

export interface CreateAssessmentRequest {
  esn: string
  persona: string
  workflowId: string
  unitNumber?: string
  component?: string
  reviewPeriod?: string
  equipmentType?: string
  dataTypes?: string[]
  createdBy?: string
  dateFrom?: string
  dateTo?: string
}

export interface RunAnalysisRequest {
  persona: 'RE' | 'OE'
  workflowId?: string       // if omitted, backend defaults to {persona}_DEFAULT
  equipmentType?: string
  reviewPeriod?: string
  unitNumber?: string
  dataTypes?: string[]
  dateFrom?: string
  dateTo?: string
}

export interface NarrativeRequest {
  persona: 'RE' | 'OE'
}

export interface AnalyzeReliabilityRequest {
  assessmentId: string
  equipmentType: string
  serialNumber: string
}

export interface AnalyzeReliabilityResponse {
  riskCategories: Record<string, RiskCategory>
  narrativeSummary: string
}

export interface ChatRequest {
  message: string
  context: string | Record<string, unknown>
}

export interface FeedbackRequest {
  feedback?: 'up' | 'down' | null
  feedbackType?: string | null
  comments?: string
}
