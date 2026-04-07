/**
 * MSW Node Setup
 * Used for test environment (Vitest/Node)
 */

import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
