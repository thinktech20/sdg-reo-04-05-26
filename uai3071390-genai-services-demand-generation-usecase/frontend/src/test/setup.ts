import { expect, afterEach, beforeAll, afterAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/dom'
import '@testing-library/jest-dom/vitest'
import { server } from '@/mocks/node'

let getBoundingClientRectSpy: ReturnType<typeof vi.spyOn> | null = null

// Setup MSW server for API mocking in tests
beforeAll(() => {
  // MUI Popover/Menu validates anchor element layout; jsdom returns zeroed rects by default.
  getBoundingClientRectSpy = vi
    .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
    .mockImplementation(() => {
      if (typeof DOMRect === 'function') {
        return new DOMRect(0, 0, 100, 40)
      }
      return {
        x: 0,
        y: 0,
        width: 100,
        height: 40,
        top: 0,
        right: 100,
        bottom: 40,
        left: 0,
        toJSON: () => ({}),
      } as DOMRect
    })

  server.listen({ onUnhandledRequest: 'warn' })
})

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers()
  cleanup()
})

// Cleanup server after all tests
afterAll(() => {
  getBoundingClientRectSpy?.mockRestore()
  server.close()
})

// Extend Vitest matchers with Testing Library matchers
expect.extend({})
