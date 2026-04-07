import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/utils'
import type { RootState } from '@/store'
import type { Assessment } from '@/store/types'
import OutageChatPanel from './OutageChatPanel'

const getSendButton = () => {
  const icon = screen.getByTestId('SendIcon')
  return icon.closest('button') as HTMLButtonElement
}

const baseAssessment: Assessment = {
  id: 'assessment-1',
  serialNumber: 'GG10632',
  reviewPeriod: '18-month',
  reliabilityStatus: 'not-started',
  outageStatus: 'not-started',
  reliabilityFindings: [],
  outageFindings: [],
  reliabilityChat: [],
  outageChat: [],
  uploadedDocs: [],
  createdAt: '2026-02-18T12:00:00Z',
  updatedAt: '2026-02-18T12:00:00Z',
}

const createPreloadedState = (workflowStatus?: string): Partial<RootState> => ({
  assessments: {
    assessments: {},
    currentAssessment: null,
    loading: false,
    analyzing: false,
    error: null,
    analyzeJobs: workflowStatus
      ? {
          'assessment-1': {
            OE_DEFAULT: {
              assessmentId: 'assessment-1',
              workflowId: 'OE_DEFAULT',
              workflowStatus,
            },
          },
        }
      : {},
  },
})

const agentOk = {
  response: {
    message: ['**Answer**', '', '- Check `OE_DEFAULT` status'].join('\n'),
    timestamp: '2026-03-25T10:00:00Z',
    agent: 'outage',
  },
  chatHistory: [],
}

let fetchMock: ReturnType<typeof vi.fn>
let writeTextMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  writeTextMock = vi.fn().mockResolvedValue(undefined)
  Object.assign(navigator, {
    clipboard: { writeText: writeTextMock },
  })
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubEnv('VITE_QNA_AGENT_URL', '')
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('OutageChatPanel', () => {
  it('shows the locked state until OE analysis is completed', () => {
    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('RUNNING'),
    })

    expect(screen.getByText(/Available After Assessment/i)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/Ask a question about the outage assessment/i)).not.toBeInTheDocument()
  })

  it('shows the chat interface when OE analysis is completed', () => {
    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    expect(screen.getByText('unlocked')).toBeInTheDocument()
    expect(screen.getByText('Summarise outage scope recommendations')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask a question about the outage assessment/i)).toBeInTheDocument()
  })

  it('renders user text plainly and assistant replies with formatted markdown', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    const input = screen.getByPlaceholderText(/Ask a question about the outage assessment/i)
    await userEvent.type(input, 'Need outage summary')
    fireEvent.click(getSendButton())

    expect(await screen.findByText('Need outage summary')).toBeInTheDocument()
    expect(await screen.findByText('Answer')).toBeInTheDocument()
    expect(screen.getByText('OE_DEFAULT').tagName.toLowerCase()).toBe('code')
    expect(screen.getByRole('list')).toBeInTheDocument()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, options] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe('/questionansweragent/api/v1/assessments/assessment-1/chat/outage')
    const body = JSON.parse((options as RequestInit).body as string) as {
      message: string
      context: { assessmentId: string }
    }
    expect(body.message).toBe('Need outage summary')
    expect(body.context.assessmentId).toBe('assessment-1')
  })

  it('uses the direct agent URL when VITE_QNA_AGENT_URL is set', async () => {
    vi.stubEnv('VITE_QNA_AGENT_URL', 'http://questionansweragent.sdg.dev:8087')
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    await userEvent.type(
      screen.getByPlaceholderText(/Ask a question about the outage assessment/i),
      'test direct url',
    )
    fireEvent.click(getSendButton())

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      'http://questionansweragent.sdg.dev:8087/api/assessments/assessment-1/chat/outage',
    )
  })

  it('shows an error message when the agent returns a non-OK response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
      statusText: 'Internal Server Error',
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    await userEvent.type(
      screen.getByPlaceholderText(/Ask a question about the outage assessment/i),
      'cause error',
    )
    fireEvent.click(getSendButton())

    expect(await screen.findByText(/Agent error.*500/i)).toBeInTheDocument()
    expect(screen.getByText(/Failed to reach the outage-agent/i)).toBeInTheDocument()
  })

  it('shows an error message on network failure', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    await userEvent.type(
      screen.getByPlaceholderText(/Ask a question about the outage assessment/i),
      'network issue',
    )
    fireEvent.click(getSendButton())

    expect(await screen.findByText(/Agent error.*Failed to fetch/i)).toBeInTheDocument()
    expect(screen.getByText(/Failed to reach the outage-agent/i)).toBeInTheDocument()
  })

  it('sends a quick-action message when a chip is clicked', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    fireEvent.click(screen.getByText('Summarise outage scope recommendations'))

    expect(await screen.findByText('Summarise outage scope recommendations')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit
    const body = JSON.parse(requestInit.body as string) as { message: string }
    expect(body.message).toBe('Summarise outage scope recommendations')
  })

  it('disables the input while waiting for a response', async () => {
    fetchMock.mockReturnValueOnce(new Promise(() => {}))

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    const input = screen.getByPlaceholderText(/Ask a question about the outage assessment/i)
    await userEvent.type(input, 'wait for response')
    fireEvent.click(getSendButton())

    await waitFor(() => expect(input).toBeDisabled())
    expect(screen.getByText(/Agent is thinking/i)).toBeInTheDocument()
  })

  it('sends on Enter but not on Shift+Enter', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    const input = screen.getByPlaceholderText(/Ask a question about the outage assessment/i)
    await userEvent.type(input, 'keyboard send')
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true })
    expect(fetchMock).toHaveBeenCalledTimes(0)

    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  })

  it('copies an assistant message to the clipboard', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(agentOk),
    })

    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    await userEvent.type(
      screen.getByPlaceholderText(/Ask a question about the outage assessment/i),
      'copy response',
    )
    fireEvent.click(getSendButton())

    await screen.findByText('Answer')
    await userEvent.click(screen.getByTitle('Copy message'))

    expect(writeTextMock).toHaveBeenCalledWith(agentOk.response.message)
  })

  it('aborts an in-flight request on unmount', async () => {
    const abortSpy = vi.fn()
    const originalAbortController = globalThis.AbortController

    vi.stubGlobal(
      'AbortController',
      class {
        signal = new originalAbortController().signal
        abort = abortSpy
      },
    )

    fetchMock.mockReturnValueOnce(new Promise(() => {}))

    const { unmount } = renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    await userEvent.type(
      screen.getByPlaceholderText(/Ask a question about the outage assessment/i),
      'abort me',
    )
    fireEvent.click(getSendButton())

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    unmount()
    expect(abortSpy).toHaveBeenCalled()
  })

  it('does not send when the input is empty', () => {
    renderWithProviders(<OutageChatPanel assessment={baseAssessment} />, {
      preloadedState: createPreloadedState('COMPLETED'),
    })

    const sendButton = getSendButton()
    expect(sendButton).toBeDisabled()
    fireEvent.click(sendButton)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})