/**
 * Custom Redux Hooks
 * High-level hooks for common operations and state access
 */

import { useCallback, useEffect } from 'react'
import { useAppDispatch, useAppSelector } from './hooks'
import type { Equipment, Assessment, FeedbackRequest } from './types'

// Auth slice imports
import {
  login,
  logout,
  fetchCurrentUser,
  restoreSession,
  clearError as clearAuthError,
  selectAuth,
  selectCurrentUser,
  selectIsAuthenticated,
  selectAuthLoading,
  selectAuthError,
  selectIsAdmin,
} from './slices/authSlice'

// UI slice imports
import {
  toggleTheme,
  setTheme,
  toggleSidebar,
  collapseSidebar,
  expandSidebar,
  selectTheme,
  selectSidebarCollapsed,
} from './slices/uiSlice'

// Equipment slice imports
import {
  fetchTrains,
  searchEquipment,
  setSelectedEquipment,
  clearSelectedEquipment,
  setTypeFilter,
  setSearchQuery,
  clearFilters as clearEquipmentFilters,
  selectTrains,
  selectSelectedEquipment,
  selectEquipmentLoading,
  selectTrainsLoading,
  selectEquipmentError,
  selectEquipmentFilters,
} from './slices/equipmentSlice'

// Assessments slice imports
import {
  createAssessment,
  fetchAssessment,
  runAnalysis,
  runNarrative,
  updateReliability,
  updateOutage,
  submitFeedback,
  exportPDF,
  setCurrentAssessment,
  clearCurrentAssessment,
  selectCurrentAssessment,
  selectAllAssessments,
  selectAssessmentsLoading,
  selectAnalyzing,
  selectAssessmentsError,
} from './slices/assessmentsSlice'

// Documents slice imports
import {
  fetchERCases,
  fetchFSRReports,
  fetchOutageHistory,
  fetchUploadedDocuments,
  uploadDocument,
  fetchAllDocuments,
  selectERCases,
  selectFSRReports,
  selectOutageHistory,
  selectUploadedDocs,
  selectDocumentsLoading,
} from './slices/documentsSlice'

// Chat slice imports
import {
  clearReliabilityChat,
  clearOutageChat,
  selectReliabilityChat,
  selectOutageChat,
  selectChatLoading,
  selectHasReliabilityChat,
  selectHasOutageChat,
} from './slices/chatSlice'

// ============================================================================
// AUTH HOOKS
// ============================================================================

/**
 * Hook for authentication operations
 * 
 * @example
 * ```tsx
 * const { user, isAuthenticated, login, logout } = useAuth()
 * 
 * const handleLogin = async () => {
 *   await login('user-sso')
 * }
 * ```
 */
export const useAuth = () => {
  const dispatch = useAppDispatch()
  const auth = useAppSelector(selectAuth)
  const user = useAppSelector(selectCurrentUser)
  const isAuthenticated = useAppSelector(selectIsAuthenticated)
  const loading = useAppSelector(selectAuthLoading)
  const error = useAppSelector(selectAuthError)
  const isAdmin = useAppSelector(selectIsAdmin)

  const loginUser = useCallback(
    (sso: string) => dispatch(login({ sso })),
    [dispatch]
  )

  const logoutUser = useCallback(() => dispatch(logout()), [dispatch])

  const refreshUser = useCallback(() => dispatch(fetchCurrentUser()), [dispatch])

  const restore = useCallback(() => dispatch(restoreSession()), [dispatch])

  const clearError = useCallback(() => dispatch(clearAuthError()), [dispatch])

  return {
    auth,
    user,
    isAuthenticated,
    loading,
    error,
    isAdmin,
    login: loginUser,
    logout: logoutUser,
    refreshUser,
    restoreSession: restore,
    clearError,
  }
}

/**
 * Hook to automatically restore session on mount
 * Use this at the app root level to restore authentication state
 * 
 * @example
 * ```tsx
 * function App() {
 *   useRestoreSession()
 *   return <AppContent />
 * }
 * ```
 */
export const useRestoreSession = () => {
  const dispatch = useAppDispatch()

  useEffect(() => {
    dispatch(restoreSession())
  }, [dispatch])
}

// ============================================================================
// UI HOOKS
// ============================================================================

/**
 * Hook for UI state and theme management
 * 
 * @example
 * ```tsx
 * const { theme, isDarkMode, toggleTheme, toggleSidebar } = useUI()
 * 
 * return (
 *   <button onClick={toggleTheme}>
 *     Switch to {isDarkMode ? 'light' : 'dark'} mode
 *   </button>
 * )
 * ```
 */
export const useUI = () => {
  const dispatch = useAppDispatch()
  const theme = useAppSelector(selectTheme)
  const isDarkMode = theme === 'dark'
  const sidebarCollapsed = useAppSelector(selectSidebarCollapsed)

  const toggle = useCallback(() => dispatch(toggleTheme()), [dispatch])
  const setLight = useCallback(() => dispatch(setTheme('light')), [dispatch])
  const setDark = useCallback(() => dispatch(setTheme('dark')), [dispatch])

  const toggleSidebarFn = useCallback(() => dispatch(toggleSidebar()), [dispatch])
  const collapseSidebarFn = useCallback(() => dispatch(collapseSidebar()), [dispatch])
  const expandSidebarFn = useCallback(() => dispatch(expandSidebar()), [dispatch])

  return {
    theme,
    isDarkMode,
    sidebarCollapsed,
    toggleTheme: toggle,
    setLightMode: setLight,
    setDarkMode: setDark,
    toggleSidebar: toggleSidebarFn,
    collapseSidebar: collapseSidebarFn,
    expandSidebar: expandSidebarFn,
  }
}

// ============================================================================
// EQUIPMENT HOOKS
// ============================================================================

/**
 * Hook for equipment and trains management
 * 
 * @example
 * ```tsx
 * const { trains, loading, loadTrains, searchEquipment } = useEquipment()
 * 
 * useEffect(() => {
 *   loadTrains('Gas Turbine', 'GT')
 * }, [])
 * 
 * const handleSearch = (esn: string) => {
 *   searchEquipment(esn)
 * }
 * ```
 */
export const useEquipment = () => {
  const dispatch = useAppDispatch()
  const trains = useAppSelector(selectTrains)
  const selectedEquipment = useAppSelector(selectSelectedEquipment)
  const loading = useAppSelector(selectEquipmentLoading)
  const trainsLoading = useAppSelector(selectTrainsLoading)
  const error = useAppSelector(selectEquipmentError)
  const filters = useAppSelector(selectEquipmentFilters)

  const loadTrains = useCallback(
    (filterType = 'all', search = '') => 
      dispatch(fetchTrains({ filterType, search })),
    [dispatch]
  )

  const search = useCallback(
    (esn: string) => dispatch(searchEquipment(esn)),
    [dispatch]
  )

  const selectEquipmentFn = useCallback(
    (equipment: Equipment | null) => dispatch(setSelectedEquipment(equipment)),
    [dispatch]
  )

  const clearSelection = useCallback(
    () => dispatch(clearSelectedEquipment()),
    [dispatch]
  )

  const setFilter = useCallback(
    (type: string) => dispatch(setTypeFilter(type)),
    [dispatch]
  )

  const setSearch = useCallback(
    (query: string) => dispatch(setSearchQuery(query)),
    [dispatch]
  )

  const clearFilters = useCallback(
    () => dispatch(clearEquipmentFilters()),
    [dispatch]
  )

  return {
    trains,
    selectedEquipment,
    loading,
    trainsLoading,
    error,
    filters,
    loadTrains,
    searchEquipment: search,
    selectEquipment: selectEquipmentFn,
    clearSelection,
    setTypeFilter: setFilter,
    setSearchQuery: setSearch,
    clearFilters,
  }
}

// ============================================================================
// ASSESSMENTS HOOKS
// ============================================================================

/**
 * Hook for risk assessments management
 * 
 * @example
 * ```tsx
 * const {
 *   currentAssessment,
 *   loading,
 *   analyzing,
 *   createAssessment,
 *   runAnalysis
 * } = useAssessments()
 *
 * const handleAnalyze = async () => {
 *   await runAnalysis(assessmentId, 'RE')
 * }
 * ```
 */
export const useAssessments = () => {
  const dispatch = useAppDispatch()
  const currentAssessment = useAppSelector(selectCurrentAssessment)
  const allAssessments = useAppSelector(selectAllAssessments)
  const loading = useAppSelector(selectAssessmentsLoading)
  const analyzing = useAppSelector(selectAnalyzing)
  const error = useAppSelector(selectAssessmentsError)

  const create = useCallback(
    (esn: string, reviewPeriod: string, persona: string = 'RE', workflowId: string = 'RE_DEFAULT') =>
      dispatch(createAssessment({ esn, reviewPeriod, persona, workflowId })),
    [dispatch]
  )

  const fetch = useCallback(
    (id: string) => dispatch(fetchAssessment(id)),
    [dispatch]
  )

  const run = useCallback(
    (id: string, persona: 'RE' | 'OE', extras?: Record<string, string>) =>
      dispatch(runAnalysis({ id, request: { persona, ...extras } })),
    [dispatch]
  )

  const narrative = useCallback(
    (id: string, persona: 'RE' | 'OE') =>
      dispatch(runNarrative({ id, request: { persona } })),
    [dispatch]
  )

  const updateRel = useCallback(
    (id: string, data: unknown) =>
      dispatch(updateReliability({ id, data })),
    [dispatch]
  )

  const updateOut = useCallback(
    (id: string, data: unknown) =>
      dispatch(updateOutage({ id, data })),
    [dispatch]
  )

  const feedback = useCallback(
    (assessmentId: string, findingId: string, feedbackData: FeedbackRequest) =>
      dispatch(submitFeedback({ assessmentId, findingId, feedback: feedbackData })),
    [dispatch]
  )

  const exportToPDF = useCallback(
    (id: string) => dispatch(exportPDF(id)),
    [dispatch]
  )

  const setCurrent = useCallback(
    (assessment: Assessment | null) => dispatch(setCurrentAssessment(assessment)),
    [dispatch]
  )

  const clearCurrent = useCallback(
    () => dispatch(clearCurrentAssessment()),
    [dispatch]
  )

  return {
    currentAssessment,
    allAssessments,
    loading,
    analyzing,
    error,
    createAssessment: create,
    fetchAssessment: fetch,
    runAnalysis: run,
    runNarrative: narrative,
    updateReliability: updateRel,
    updateOutage: updateOut,
    submitFeedback: feedback,
    exportPDF: exportToPDF,
    setCurrentAssessment: setCurrent,
    clearCurrentAssessment: clearCurrent,
  }
}

// ============================================================================
// DOCUMENTS HOOKS
// ============================================================================

/**
 * Hook for documents management (ER cases, FSR reports, outage history, uploads)
 * 
 * @param esn - Optional equipment serial number to filter documents
 * 
 * @example
 * ```tsx
 * const { erCases, loading, fetchERCases } = useDocuments('GT12345')
 * 
 * useEffect(() => {
 *   fetchERCases('GT12345')
 * }, [])
 * ```
 */
export const useDocuments = (esn?: string) => {
  const dispatch = useAppDispatch()
  const effectiveEsn = esn || ''
  const erCases = useAppSelector(selectERCases(effectiveEsn))
  const fsrReports = useAppSelector(selectFSRReports(effectiveEsn))
  const outageHistory = useAppSelector(selectOutageHistory(effectiveEsn))
  const uploadedDocs = useAppSelector(selectUploadedDocs(effectiveEsn))
  const loading = useAppSelector(selectDocumentsLoading)

  const loadERCases = useCallback(
    (equipmentESN: string) => dispatch(fetchERCases({ esn: equipmentESN })),
    [dispatch]
  )

  const loadFSRReports = useCallback(
    (equipmentESN: string) => dispatch(fetchFSRReports({ esn: equipmentESN })),
    [dispatch]
  )

  const loadOutageHistory = useCallback(
    (equipmentESN: string) => dispatch(fetchOutageHistory({ esn: equipmentESN })),
    [dispatch]
  )

  const loadUploadedDocs = useCallback(
    (equipmentESN: string) => dispatch(fetchUploadedDocuments(equipmentESN)),
    [dispatch]
  )

  const upload = useCallback(
    (equipmentESN: string, file: File, category: string) =>
      dispatch(uploadDocument({ esn: equipmentESN, file, category })),
    [dispatch]
  )

  const loadAll = useCallback(
    (equipmentESN: string) => dispatch(fetchAllDocuments(equipmentESN)),
    [dispatch]
  )

  return {
    erCases,
    fsrReports,
    outageHistory,
    uploadedDocs,
    loading,
    fetchERCases: loadERCases,
    fetchFSRReports: loadFSRReports,
    fetchOutageHistory: loadOutageHistory,
    fetchUploadedDocuments: loadUploadedDocs,
    uploadDocument: upload,
    fetchAllDocuments: loadAll,
  }
}

// ============================================================================
// CHAT HOOKS
// ============================================================================

/**
 * Hook for AI chat interactions (reliability and outage agents)
 * Chat messages are sent over WebSocket directly from chat components;
 * this hook exposes the Redux-managed chat history and clear actions.
 *
 * @param assessmentId - Optional assessment ID to filter chat history
 */
export const useChat = (assessmentId?: string) => {
  const dispatch = useAppDispatch()
  const effectiveAssessmentId = assessmentId || ''
  const reliabilityChat = useAppSelector(selectReliabilityChat(effectiveAssessmentId))
  const outageChat = useAppSelector(selectOutageChat(effectiveAssessmentId))
  const hasReliabilityChat = useAppSelector(
    selectHasReliabilityChat(effectiveAssessmentId)
  )
  const hasOutageChat = useAppSelector(
    selectHasOutageChat(effectiveAssessmentId)
  )
  const loading = useAppSelector(selectChatLoading)

  const clearReliability = useCallback(
    (id: string) => dispatch(clearReliabilityChat(id)),
    [dispatch]
  )

  const clearOutage = useCallback(
    (id: string) => dispatch(clearOutageChat(id)),
    [dispatch]
  )

  return {
    reliabilityChat,
    outageChat,
    hasReliabilityChat,
    hasOutageChat,
    loading,
    clearReliabilityChat: clearReliability,
    clearOutageChat: clearOutage,
  }
}

// ============================================================================
// COMBINED HOOKS
// ============================================================================

/**
 * Hook that combines assessment, chat, and documents for a specific assessment
 * This provides a unified interface for assessment detail pages
 * 
 * @param assessmentId - The assessment ID to fetch data for
 * 
 * @example
 * ```tsx
 * const {
 *   currentAssessment,
 *   reliabilityChat,
 *   erCases,
 *   loading,
 *   analyzing,
 *   fetchAssessment,
 *   sendReliabilityMessage,
 *   fetchERCases
 * } = useAssessmentDetail(assessmentId)
 * ```
 */
export const useAssessmentDetail = (assessmentId: string) => {
  const assessments = useAssessments()
  const chat = useChat(assessmentId)
  const documents = useDocuments()

  return {
    ...assessments,
    ...chat,
    ...documents,
  }
}
