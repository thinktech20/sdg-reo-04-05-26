/**
 * Chat Slice
 * Manages AI agent chat interactions for reliability and outage assessments
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { ChatState } from '../types'

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: ChatState = {
  reliabilityChats: {},
  outageChats: {},
  loading: false,
  error: null,
  reliabilityLoading: {},
  reliabilityErrors: {},
}

// ============================================================================
// SLICE
// ============================================================================

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    /**
     * Clear error
     */
    clearError: (state) => {
      state.error = null
      state.reliabilityErrors = {}
    },
    
    /**
     * Clear reliability chat for assessment
     */
    clearReliabilityChat: (state, action: PayloadAction<string>) => {
      delete state.reliabilityChats[action.payload]
    },
    
    /**
     * Clear outage chat for assessment
     */
    clearOutageChat: (state, action: PayloadAction<string>) => {
      delete state.outageChats[action.payload]
    },
    
    /**
     * Clear all chats for assessment
     */
    clearAllChats: (state, action: PayloadAction<string>) => {
      const assessmentId = action.payload
      delete state.reliabilityChats[assessmentId]
      delete state.outageChats[assessmentId]
    },
    
    /**
     * Add user message optimistically (reliability)
     */
    addReliabilityUserMessage: (
      state,
      action: PayloadAction<{ assessmentId: string; message: string }>,
    ) => {
      const { assessmentId, message } = action.payload
      if (!state.reliabilityChats[assessmentId]) {
        state.reliabilityChats[assessmentId] = []
      }
      state.reliabilityChats[assessmentId].push({
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      })
    },
    
    /**
     * Add user message optimistically (outage)
     */
    addOutageUserMessage: (
      state,
      action: PayloadAction<{ assessmentId: string; message: string }>,
    ) => {
      const { assessmentId, message } = action.payload
      if (!state.outageChats[assessmentId]) {
        state.outageChats[assessmentId] = []
      }
      state.outageChats[assessmentId].push({
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      })
    },
  },
})

// ============================================================================
// EXPORTS
// ============================================================================

export const {
  clearError,
  clearReliabilityChat,
  clearOutageChat,
  clearAllChats,
  addReliabilityUserMessage,
  addOutageUserMessage,
} = chatSlice.actions

export default chatSlice.reducer

const EMPTY_RELIABILITY_CHAT: ChatState['reliabilityChats'][string] = []
const EMPTY_OUTAGE_CHAT: ChatState['outageChats'][string] = []

// Selectors
export const selectChat = (state: { chat: ChatState }) => state.chat
export const selectReliabilityChat = (assessmentId: string) => 
  (state: { chat: ChatState }) => state.chat.reliabilityChats[assessmentId] ?? EMPTY_RELIABILITY_CHAT
export const selectOutageChat = (assessmentId: string) => 
  (state: { chat: ChatState }) => state.chat.outageChats[assessmentId] ?? EMPTY_OUTAGE_CHAT
export const selectChatLoading = (state: { chat: ChatState }) => state.chat.loading
export const selectChatError = (state: { chat: ChatState }) => state.chat.error

// Derived selectors
export const selectHasReliabilityChat = (assessmentId: string) => 
  (state: { chat: ChatState }) => {
    const chat = state.chat.reliabilityChats[assessmentId]
    return Boolean(chat && chat.length > 0)
  }

export const selectHasOutageChat = (assessmentId: string) => 
  (state: { chat: ChatState }) => {
    const chat = state.chat.outageChats[assessmentId]
    return Boolean(chat && chat.length > 0)
  }
