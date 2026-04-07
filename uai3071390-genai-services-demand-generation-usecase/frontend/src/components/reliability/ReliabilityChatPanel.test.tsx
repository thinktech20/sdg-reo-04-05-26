/**
 * ReliabilityChatPanel Tests
 *
 * Covers:
 *  - buildChatUrl (proxied vs direct via VITE_QNA_AGENT_URL)
 *  - Rendering states (no analysis, empty chat, error alert)
 *  - Sending a message (success path)
 *  - API error handling (non-OK response)
 *  - Network error handling
 *  - Quick-action chip sends the message
 *  - Input disabled while sending
 *  - Abort on unmount
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ReliabilityChatPanel from './ReliabilityChatPanel'
import type { Assessment } from '@/store/types'

/** The MUI IconButton wrapping <Send /> has no accessible name;
 *  locate it via the SVG data-testid that MUI generates. */
const getSendButton = () => {
  const icon = screen.getByTestId('SendIcon')
  return icon.closest('button') as HTMLButtonElement
}

// jsdom lacks scrollIntoView and clipboard
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
})

// ── Helpers ──────────────────────────────────────────────────────────────────

const baseAssessment: Assessment = {
  id: 'assess-1',
  serialNumber: 'GT12345',
  reviewPeriod: '18-month',
  reliabilityStatus: 'not-started',
  outageStatus: 'not-started',
  createdAt: '2026-02-18T12:00:00Z',
  updatedAt: '2026-02-18T12:00:00Z',
  reliabilityFindings: [],
  outageFindings: [],
  reliabilityChat: [],
  outageChat: [],
  uploadedDocs: [],
}

const analysedAssessment: Assessment = {
  ...baseAssessment,
  reliabilityRiskCategories: {
    'cat-1': {
      id: 'cat-1',
      name: 'Stator Rewind',
      component: 'Stator',
      overallRisk: 'Heavy',
      processDocument: 'GEK-123',
      reliabilityModelRef: 'v1',
      description: 'desc',
      conditions: [],
    },
  },
}

const agentOk = {
  response: {
    message: 'Here is the answer.',
    timestamp: '2026-03-25T10:00:00Z',
    agent: 'reliability',
  },
  chatHistory: [],
}

// ── Mocks ────────────────────────────────────────────────────────────────────

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  // Default: clear VITE_QNA_AGENT_URL
  vi.stubEnv('VITE_QNA_AGENT_URL', '')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// ── Tests ────────────────────────────────────────────────────────────────────

describe('ReliabilityChatPanel', () => {
  // ── Rendering ────────────────────────────────────────────────────────────

  it('shows pre-analysis info alert when assessment has no risk categories', () => {
    render(<ReliabilityChatPanel assessment={baseAssessment} />)

    expect(screen.getByText(/Available After Analysis/i)).toBeInTheDocument()
    // Input area should NOT be shown
    expect(screen.queryByPlaceholderText(/Ask a question/i)).not.toBeInTheDocument()
  })

  it('shows chat interface with quick actions when analysis exists', () => {
    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    expect(screen.queryByText(/Available After Analysis/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Does Not Re-Run Analysis/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask a question/i)).toBeInTheDocument()

    // Quick-action chips
    expect(screen.getByText('Explain stator rewind risk')).toBeInTheDocument()
    expect(screen.getByText('Compare to fleet average')).toBeInTheDocument()
  })

  it('renders nothing meaningful when assessment is null', () => {
    render(<ReliabilityChatPanel assessment={null} />)
    // Header still renders but no input
    expect(screen.getByText(/Step 8/)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/Ask a question/i)).not.toBeInTheDocument()
  })

  // ── Sending a message (success) ──────────────────────────────────────────

  it('sends a message and renders the assistant reply', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'What is the stator risk?')

    fireEvent.click(getSendButton())

    // User message appears immediately
    expect(await screen.findByText('What is the stator risk?')).toBeInTheDocument()

    // Wait for assistant response
    expect(await screen.findByText('Here is the answer.')).toBeInTheDocument()

    // fetch was called with the proxied URL
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, opts] = fetchMock.mock.calls[0]!
    expect(url).toBe('/questionansweragent/api/v1/assessments/assess-1/chat/reliability')
    const requestInit = opts as RequestInit
    expect(requestInit.method).toBe('POST')
    expect(typeof requestInit.body).toBe('string')
    const body = JSON.parse(requestInit.body as string) as {
      message: string
      context: { assessmentId: string }
    }
    expect(body.message).toBe('What is the stator risk?')
    expect(body.context.assessmentId).toBe('assess-1')
  })

  // ── buildChatUrl with VITE_QNA_AGENT_URL ─────────────────────────────────

  it('uses direct URL when VITE_QNA_AGENT_URL is set', async () => {
    vi.stubEnv('VITE_QNA_AGENT_URL', 'http://questionansweragent.sdg.dev:8087')

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'test')
    fireEvent.click(getSendButton())

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const [url] = fetchMock.mock.calls[0]!
    expect(url).toBe(
      'http://questionansweragent.sdg.dev:8087/api/assessments/assess-1/chat/reliability',
    )
  })

  // ── API error handling ───────────────────────────────────────────────────

  it('shows error message when the agent returns a non-OK response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
      statusText: 'Internal Server Error',
    })

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'break things')
    fireEvent.click(getSendButton())

    // Error message in chat
    expect(await screen.findByText(/Agent error.*500/i)).toBeInTheDocument()

    // Connection error alert
    expect(
      screen.getByText(/Failed to reach the Q&A agent/i),
    ).toBeInTheDocument()
  })

  it('shows error message on network failure', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'hello')
    fireEvent.click(getSendButton())

    expect(await screen.findByText(/Agent error.*Failed to fetch/i)).toBeInTheDocument()
    expect(screen.getByText(/Failed to reach the Q&A agent/i)).toBeInTheDocument()
  })

  // ── Quick action chips ───────────────────────────────────────────────────

  it('sends a message when a quick-action chip is clicked', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    fireEvent.click(screen.getByText('Explain stator rewind risk'))

    // User message should be the quick action text
    expect(await screen.findByText('Explain stator rewind risk')).toBeInTheDocument()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const requestInit = fetchMock.mock.calls[0]![1] as RequestInit
    expect(typeof requestInit.body).toBe('string')
    const body = JSON.parse(requestInit.body as string) as { message: string }
    expect(body.message).toBe('Explain stator rewind risk')
  })

  // ── Input disabled while sending ──────────────────────────────────────────

  it('disables input and send button while waiting for a response', async () => {
    // Never resolve — keep the component in "sending" state
    fetchMock.mockReturnValueOnce(new Promise(() => {}))

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'wait for this')
    fireEvent.click(getSendButton())

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Ask a question/i)).toBeDisabled()
    })

    // "Agent is thinking..." indicator
    expect(screen.getByText(/Agent is thinking/i)).toBeInTheDocument()
  })

  // ── Enter to send ────────────────────────────────────────────────────────

  it('sends on Enter key press', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'enter test')
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  })

  // ── Abort on unmount ─────────────────────────────────────────────────────

  it('aborts in-flight request when component unmounts', async () => {
    const abortSpy = vi.fn()
    const originalAbortController = globalThis.AbortController

    // Patch AbortController to spy on abort()
    vi.stubGlobal(
      'AbortController',
      class {
        signal = new originalAbortController().signal
        abort = abortSpy
      },
    )

    // Never-resolving fetch so the request stays in-flight
    fetchMock.mockReturnValueOnce(new Promise(() => {}))

    const { unmount } = render(
      <ReliabilityChatPanel assessment={analysedAssessment} />,
    )

    const input = screen.getByPlaceholderText(/Ask a question/i)
    await userEvent.type(input, 'unmount me')
    fireEvent.click(getSendButton())

    // The fetch should be in-flight
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    // Unmount → abort should be called
    unmount()
    expect(abortSpy).toHaveBeenCalled()
  })

  // ── Does not send empty messages ─────────────────────────────────────────

  it('does not send when input is empty', () => {
    render(<ReliabilityChatPanel assessment={analysedAssessment} />)

    const sendBtn = getSendButton()
    expect(sendBtn).toBeDisabled()

    fireEvent.click(sendBtn)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
