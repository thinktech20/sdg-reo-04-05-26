/**
 * MSW Browser Setup
 * Used for development/browser-based mocking
 */

import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
