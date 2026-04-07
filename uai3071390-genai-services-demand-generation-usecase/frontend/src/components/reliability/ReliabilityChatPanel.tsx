import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Box,
  Typography,
  Paper,
  TextField,
  IconButton,
  Chip,
  Avatar,
  CircularProgress,
  Alert,
  AlertTitle,
} from '@mui/material'
import {
  Send,
  PersonOutline,
  ContentCopy,
  ThumbUp,
  ThumbDown,
  AutoAwesome,
} from '@mui/icons-material'
import FormattedChatMessage from '@/components/chat/FormattedChatMessage'
import type { Assessment } from '@/store/types'

const chatAvatarIconSx = { fontSize: 20 }

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  citations?: string[]
}

interface ReliabilityChatPanelProps {
  assessment: Assessment | null
}

/**
 * Build the chat URL for the QnA agent REST API.
 *
 * When VITE_QNA_AGENT_URL is set (e.g. "http://questionansweragent.sdg.dev:8087")
 * the browser connects directly to the agent — bypassing nginx entirely.
 * The URL goes straight to the agent's /api/assessments mount (no prefix).
 *
 * When it is NOT set, the path is relative and routed through the proxy layer:
 *   - Vite dev server: /questionansweragent/* → http://localhost:8087/* (passthrough)
 *   - Production nginx: /questionansweragent/* → qna-agent:8087 (passthrough)
 */
function buildChatUrl(assessmentId: string): string {
  const envUrl = import.meta.env.VITE_QNA_AGENT_URL as string | undefined
  if (envUrl) {
    // Direct connection — agent listens at /api/assessments/...
    const base = envUrl.replace(/\/+$/, '')
    return `${base}/api/assessments/${encodeURIComponent(assessmentId)}/chat/reliability`
  }
  // Proxied — /questionansweragent prefix handled by Vite proxy (dev) or nginx (Docker)
  return `/questionansweragent/api/v1/assessments/${encodeURIComponent(assessmentId)}/chat/reliability`
}

/**
 * Reliability Chat Panel - Step 8
 *
 * Ad-hoc Q&A chat interface backed by the QnA agent via REST POST.
 * Returns complete responses per ADR-001 (no streaming).
 * CRITICAL: Does NOT trigger re-analysis of Steps 3-6.
 */
const ReliabilityChatPanel = ({ assessment }: ReliabilityChatPanelProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hasAnalysis = assessment?.reliabilityRiskCategories !== undefined

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Send message ───────────────────────────────────────────────────────────
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || !assessment) return

      const trimmed = content.trim()
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: trimmed, timestamp: new Date().toISOString() },
      ])
      setInputValue('')
      setSending(true)
      setError(null)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        const url = buildChatUrl(assessment.id)
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: trimmed,
            context: { assessmentId: assessment.id, serialNumber: assessment.serialNumber },
          }),
          signal: controller.signal,
        })

        if (!res.ok) {
          const detail = await res.text().catch(() => res.statusText)
          throw new Error(`Agent returned ${res.status}: ${detail}`)
        }

        const data = (await res.json()) as {
          response: { message: string; timestamp: string; agent: string }
          chatHistory: { role: string; content: string; timestamp: string }[]
        }

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.response.message,
            timestamp: data.response.timestamp,
          },
        ])
      } catch (err: unknown) {
        if ((err as Error).name === 'AbortError') return
        const msg = err instanceof Error ? err.message : 'Unknown error'
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ Agent error: ${msg}`,
            timestamp: new Date().toISOString(),
          },
        ])
        setError('Failed to reach the Q&A agent. Check that the service is running.')
      } finally {
        setSending(false)
        abortRef.current = null
      }
    },
    [assessment],
  )

  // ── Quick actions ──────────────────────────────────────────────────────────
  const quickActions = [
    'Explain stator rewind risk',
    'Compare to fleet average',
    'What TILs apply?',
    'Show recent FSR reports',
  ]

  const handleCopyMessage = (content: string) => {
    void navigator.clipboard.writeText(content)
  }

  return (
    <Box>
      {/* Section Header */}
      <Paper elevation={1} sx={{ p: 3, mb: 3, bgcolor: 'primary.50' }}>
        <Typography variant="h6" gutterBottom>
          Step 8: Ad Hoc Q&amp;A
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Ask questions about the assessment, request clarification, or explore additional context.
        </Typography>
      </Paper>

      {/* No Analysis Warning */}
      {!hasAnalysis && (
        <Alert severity="info" icon={<AutoAwesome />} sx={{ mb: 3 }}>
          <AlertTitle>Q&amp;A Available After Analysis</AlertTitle>
          Complete the risk analysis (Step 3) first. The Q&amp;A agent will answer questions based on
          your assessment results and available data sources.
        </Alert>
      )}

      {/* Critical Constraint Notice */}
      {hasAnalysis && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <AlertTitle>Important: Q&amp;A Does Not Re-Run Analysis</AlertTitle>
          This chat provides supplementary information and clarifications. It does NOT trigger
          regeneration of the risk table or narrative. To update the assessment with new data, use
          the &quot;Re-run Analysis&quot; button in Step 3.
        </Alert>
      )}

      {/* Connection error */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Chat Interface */}
      <Paper elevation={2} sx={{ height: 600, display: 'flex', flexDirection: 'column' }}>
        {/* Quick Actions */}
        {hasAnalysis && messages.length === 0 && (
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary" display="block" mb={1}>
              Quick Actions:
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap">
              {quickActions.map((action) => (
                <Chip
                  key={action}
                  label={action}
                  onClick={() => {
                    void handleSendMessage(action)
                  }}
                  clickable
                  size="small"
                  icon={<AutoAwesome />}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Messages Area */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 2, bgcolor: 'grey.50' }}>
          {messages.length === 0 && hasAnalysis && (
            <Box
              display="flex"
              flexDirection="column"
              alignItems="center"
              justifyContent="center"
              height="100%"
              color="text.secondary"
            >
              <AutoAwesome sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
              <Typography variant="body2">
                Start a conversation by asking a question or selecting a quick action above
              </Typography>
            </Box>
          )}

          {messages.map((message, index) => (
            <Box
              key={index}
              sx={{
                mb: 2,
                display: 'flex',
                gap: 1.5,
                flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
              }}
            >
              <Avatar
                sx={{
                  bgcolor: message.role === 'user' ? 'primary.main' : 'grey.600',
                  width: 36,
                  height: 36,
                }}
              >
                {message.role === 'user' ? (
                  <PersonOutline sx={chatAvatarIconSx} />
                ) : (
                  <AutoAwesome sx={chatAvatarIconSx} />
                )}
              </Avatar>

              <Box
                sx={{
                  maxWidth: '75%',
                  bgcolor: message.role === 'user' ? 'primary.100' : 'white',
                  p: 2,
                  borderRadius: 2,
                  border: 1,
                  borderColor: 'divider',
                }}
              >
                <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={0.5}>
                  <Typography variant="caption" fontWeight="bold" color="text.secondary">
                    {message.role === 'user' ? 'You' : 'Risk Agent'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {message.timestamp ? new Date(message.timestamp).toLocaleTimeString() : ''}
                  </Typography>
                </Box>

                {message.role === 'assistant' ? (
                  <FormattedChatMessage content={message.content} />
                ) : (
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                    {message.content}
                  </Typography>
                )}

                {message.citations && message.citations.length > 0 && (
                  <Box mt={1.5} pt={1.5} borderTop={1} borderColor="divider">
                    <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                      📎 Citations:
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {message.citations.map((citation, idx) => (
                        <Chip
                          key={idx}
                          label={citation}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem' }}
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                {message.role === 'assistant' && (
                  <Box display="flex" gap={0.5} mt={1}>
                    <IconButton
                      size="small"
                      onClick={() => handleCopyMessage(message.content)}
                      title="Copy message"
                    >
                      <ContentCopy sx={{ fontSize: 16 }} />
                    </IconButton>
                    <IconButton size="small" title="Helpful">
                      <ThumbUp sx={{ fontSize: 16 }} />
                    </IconButton>
                    <IconButton size="small" title="Not helpful">
                      <ThumbDown sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Box>
                )}
              </Box>
            </Box>
          ))}

          {/* Thinking indicator — waiting for complete response */}
          {sending && (
            <Box display="flex" gap={1.5} mb={2}>
              <Avatar sx={{ bgcolor: 'grey.600', width: 36, height: 36 }}>
                <AutoAwesome sx={chatAvatarIconSx} />
              </Avatar>
              <Box
                sx={{ bgcolor: 'white', p: 2, borderRadius: 2, border: 1, borderColor: 'divider' }}
              >
                <Box display="flex" gap={0.5} alignItems="center">
                  <CircularProgress size={12} />
                  <Typography variant="caption" color="text.secondary" ml={1}>
                    Agent is thinking...
                  </Typography>
                </Box>
              </Box>
            </Box>
          )}

          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        {hasAnalysis && (
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Box display="flex" gap={1}>
              <TextField
                fullWidth
                size="small"
                placeholder="Ask a question about the assessment..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void handleSendMessage(inputValue)
                  }
                }}
                disabled={sending}
                multiline
                maxRows={3}
              />
              <IconButton
                color="primary"
                onClick={() => {
                  void handleSendMessage(inputValue)
                }}
                disabled={!inputValue.trim() || sending}
                sx={{ alignSelf: 'flex-end' }}
              >
                <Send />
              </IconButton>
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
              Press Enter to send, Shift+Enter for new line
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  )
}

export default ReliabilityChatPanel
