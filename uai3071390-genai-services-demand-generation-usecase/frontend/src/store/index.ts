import { configureStore } from '@reduxjs/toolkit'
import authReducer from './slices/authSlice'
import uiReducer from './slices/uiSlice'
import equipmentReducer from './slices/equipmentSlice'
import assessmentsReducer from './slices/assessmentsSlice'
import documentsReducer from './slices/documentsSlice'
import chatReducer from './slices/chatSlice'

/**
 * Redux store configuration
 *
 * Slices implemented:
 * - auth: Authentication and user session
 * - ui: UI preferences (theme, sidebar)
 * - equipment: Equipment and trains management
 * - assessments: Risk assessments and analysis
 * - documents: ER cases, FSR reports, outage history
 * - chat: Chat interactions with AI agents
 */
export const store = configureStore({
  reducer: {
    auth: authReducer,
    ui: uiReducer,
    equipment: equipmentReducer,
    assessments: assessmentsReducer,
    documents: documentsReducer,
    chat: chatReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Configuration for non-serializable values if needed
      },
    }),
  devTools: import.meta.env.MODE !== 'production',
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

// Export base hooks
export { useAppDispatch, useAppSelector } from './hooks'

// Export custom hooks (preferred for component usage)
export {
  useAuth,
  useRestoreSession,
  useUI,
  useEquipment,
  useAssessments,
  useDocuments,
  useChat,
  useAssessmentDetail,
} from './customHooks'

// Export all slice actions (for advanced usage)
export * as authActions from './slices/authSlice'
export * as uiActions from './slices/uiSlice'
export * as equipmentActions from './slices/equipmentSlice'
export * as assessmentActions from './slices/assessmentsSlice'
export * as documentActions from './slices/documentsSlice'
export * as chatActions from './slices/chatSlice'
