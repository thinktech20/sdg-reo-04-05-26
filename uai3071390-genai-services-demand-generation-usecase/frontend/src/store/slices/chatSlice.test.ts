/**
 * Chat Slice Tests
 */

import { describe, it, expect, beforeEach } from 'vitest'
import chatReducer, {
  clearError,
  clearReliabilityChat,
  clearOutageChat,
  clearAllChats,
  addReliabilityUserMessage,
  addOutageUserMessage,
  selectChat,
  selectReliabilityChat,
  selectOutageChat,
  selectChatLoading,
  selectChatError,
  selectHasReliabilityChat,
  selectHasOutageChat,
} from './chatSlice'
import { createTestStore, createMockChatMessage } from '@/test/utils'
import type { ChatState } from '../types'

describe('chatSlice', () => {
  let initialState: ChatState

  beforeEach(() => {
    initialState = {
      reliabilityChats: {},
      outageChats: {},
      loading: false,
      error: null,
      reliabilityLoading: {},
      reliabilityErrors: {},
    }
  })

  describe('reducers', () => {
    it('should return initial state', () => {
      expect(chatReducer(undefined, { type: 'unknown' })).toEqual(initialState)
    })

    it('should handle clearError', () => {
      const stateWithError = { ...initialState, error: 'Test error' }
      const state = chatReducer(stateWithError, clearError())
      expect(state.error).toBeNull()
    })

    it('should handle clearReliabilityChat', () => {
      const stateWithChat = {
        ...initialState,
        reliabilityChats: { 'assessment-1': [createMockChatMessage()] },
      }
      const state = chatReducer(stateWithChat, clearReliabilityChat('assessment-1'))
      expect(state.reliabilityChats['assessment-1']).toBeUndefined()
    })

    it('should handle clearOutageChat', () => {
      const stateWithChat = {
        ...initialState,
        outageChats: { 'assessment-1': [createMockChatMessage()] },
      }
      const state = chatReducer(stateWithChat, clearOutageChat('assessment-1'))
      expect(state.outageChats['assessment-1']).toBeUndefined()
    })

    it('should handle clearAllChats', () => {
      const stateWithChats = {
        ...initialState,
        reliabilityChats: { 'assessment-1': [createMockChatMessage()] },
        outageChats: { 'assessment-1': [createMockChatMessage()] },
      }
      const state = chatReducer(stateWithChats, clearAllChats('assessment-1'))
      expect(state.reliabilityChats['assessment-1']).toBeUndefined()
      expect(state.outageChats['assessment-1']).toBeUndefined()
    })

    it('should handle addReliabilityUserMessage', () => {
      const state = chatReducer(
        initialState,
        addReliabilityUserMessage({ assessmentId: 'assessment-1', message: 'Test message' })
      )
      
      expect(state.reliabilityChats['assessment-1']).toHaveLength(1)
      expect(state.reliabilityChats['assessment-1']![0]!.role).toBe('user')
      expect(state.reliabilityChats['assessment-1']![0]!.content).toBe('Test message')
      expect(state.reliabilityChats['assessment-1']![0]!.timestamp).toBeDefined()
    })

    it('should handle addReliabilityUserMessage to existing chat', () => {
      const stateWithChat = {
        ...initialState,
        reliabilityChats: {
          'assessment-1': [createMockChatMessage({ content: 'First message' })],
        },
      }
      const state = chatReducer(
        stateWithChat,
        addReliabilityUserMessage({ assessmentId: 'assessment-1', message: 'Second message' })
      )
      
      expect(state.reliabilityChats['assessment-1']).toHaveLength(2)
      expect(state.reliabilityChats['assessment-1']![1]!.content).toBe('Second message')
    })

    it('should handle addOutageUserMessage', () => {
      const state = chatReducer(
        initialState,
        addOutageUserMessage({ assessmentId: 'assessment-1', message: 'Outage question' })
      )
      
      expect(state.outageChats['assessment-1']).toHaveLength(1)
      expect(state.outageChats['assessment-1']![0]!.content).toBe('Outage question')
    })

    it('should handle addOutageUserMessage to existing chat', () => {
      const stateWithChat = {
        ...initialState,
        outageChats: {
          'assessment-1': [createMockChatMessage({ content: 'First message' })],
        },
      }
      const state = chatReducer(
        stateWithChat,
        addOutageUserMessage({ assessmentId: 'assessment-1', message: 'Second message' })
      )
      
      expect(state.outageChats['assessment-1']).toHaveLength(2)
    })
  })

  describe('selectors', () => {
    it('selectChat should return chat state', () => {
      const store = createTestStore({ chat: initialState })
      expect(selectChat(store.getState())).toEqual(initialState)
    })

    it('selectReliabilityChat should return reliability chat for assessment', () => {
      const messages = [createMockChatMessage()]
      const store = createTestStore({
        chat: { ...initialState, reliabilityChats: { 'assessment-1': messages } },
      })
      expect(selectReliabilityChat('assessment-1')(store.getState())).toEqual(messages)
    })

    it('selectReliabilityChat should return empty array when no chat', () => {
      const store = createTestStore({ chat: initialState })
      expect(selectReliabilityChat('assessment-1')(store.getState())).toEqual([])
    })

    it('selectOutageChat should return outage chat for assessment', () => {
      const messages = [createMockChatMessage()]
      const store = createTestStore({
        chat: { ...initialState, outageChats: { 'assessment-1': messages } },
      })
      expect(selectOutageChat('assessment-1')(store.getState())).toEqual(messages)
    })

    it('selectOutageChat should return empty array when no chat', () => {
      const store = createTestStore({ chat: initialState })
      expect(selectOutageChat('assessment-1')(store.getState())).toEqual([])
    })

    it('selectChatLoading should return loading state', () => {
      const store = createTestStore({ chat: { ...initialState, loading: true } })
      expect(selectChatLoading(store.getState())).toBe(true)
    })

    it('selectChatError should return error', () => {
      const store = createTestStore({ chat: { ...initialState, error: 'Test error' } })
      expect(selectChatError(store.getState())).toBe('Test error')
    })

    it('selectHasReliabilityChat should return true when chat exists', () => {
      const store = createTestStore({
        chat: { ...initialState, reliabilityChats: { 'assessment-1': [createMockChatMessage()] } },
      })
      expect(selectHasReliabilityChat('assessment-1')(store.getState())).toBe(true)
    })

    it('selectHasReliabilityChat should return false when chat is empty', () => {
      const store = createTestStore({
        chat: { ...initialState, reliabilityChats: { 'assessment-1': [] } },
      })
      expect(selectHasReliabilityChat('assessment-1')(store.getState())).toBe(false)
    })

    it('selectHasReliabilityChat should return false when no chat', () => {
      const store = createTestStore({ chat: initialState })
      expect(selectHasReliabilityChat('assessment-1')(store.getState())).toBe(false)
    })

    it('selectHasOutageChat should return true when chat exists', () => {
      const store = createTestStore({
        chat: { ...initialState, outageChats: { 'assessment-1': [createMockChatMessage()] } },
      })
      expect(selectHasOutageChat('assessment-1')(store.getState())).toBe(true)
    })

    it('selectHasOutageChat should return false when no chat', () => {
      const store = createTestStore({ chat: initialState })
      expect(selectHasOutageChat('assessment-1')(store.getState())).toBe(false)
    })
  })
})
