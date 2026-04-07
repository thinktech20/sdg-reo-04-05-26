/**
 * Outage Chat Panel — Step 5 of the OE Assessment Workflow
 *
 * Q&A with the outage-agent once the OE assessment pipeline has completed.
 * Locked (shows info state) until outageStatus === 'completed'.
 * Mirrors ReliabilityChatPanel but targets /chat/outage endpoint.
 */
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
  SmartToy,
  PersonOutline,
  Psychology,
  ContentCopy,
  ThumbUp,
  ThumbDown,
} from '@mui/icons-material'
import FormattedChatMessage from '@/components/chat/FormattedChatMessage'
import { useAppDispatch, useAppSelector } from '@/store'
import { selectAnalyzeJob } from '@/store/slices/assessmentsSlice'
import { selectOutageChat } from '@/store/slices/chatSlice'
import type { Assessment } from '@/store/types'

const chatAvatarIconSx = { fontSize: 20 }

interface OutageChatPanelProps {
  assessment: Assessment
}

/**
 * Build the chat URL for the outage-agent REST API.
 *
 * When VITE_QNA_AGENT_URL is set the browser connects directly to the agent.
 * Otherwise the path is proxied through Vite (dev) or nginx (Docker):
 * /questionansweragent/* → qna-agent:8087 (passthrough, prefix preserved).
 */
function buildChatUrl(assessmentId: string): string {
  const envUrl = import.meta.env.VITE_QNA_AGENT_URL as string | undefined
  if (envUrl) {
    const base = envUrl.replace(/\/+$/, '')
    return `${base}/api/assessments/${encodeURIComponent(assessmentId)}/chat/outage`
  }
  return `/questionansweragent/api/v1/assessments/${encodeURIComponent(assessmentId)}/chat/outage`
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

const OutageChatPanel = ({ assessment }: OutageChatPanelProps) => {
  const dispatch = useAppDispatch()
  void dispatch // reserved for future Redux chat persistence
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const oeJob = useAppSelector(selectAnalyzeJob(assessment.id, 'OE_DEFAULT'))
  const _savedChat = useAppSelector(selectOutageChat(assessment.id))
  void _savedChat // future: restore messages from Redux on mount

  const isComplete = oeJob?.workflowStatus === 'COMPLETED'

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || !isComplete) return

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
        setError('Failed to reach the outage-agent. Check that the service is running.')
      } finally {
        setSending(false)
        abortRef.current = null
      }
    },
    [assessment, isComplete],
  )

  const handleCopyMessage = (content: string) => {
    void navigator.clipboard.writeText(content)
  }

  const quickActions = [
    'Summarise outage scope recommendations',
    'What are the key repair items?',
    'Compare to previous outage events',
    'What TILs apply to this unit?',
  ]

  return (
    <Box>
      {/* Header */}
      <Box mb={2} display="flex" alignItems="center" gap={1.5}>
        <SmartToy color="primary" />
        <Typography variant="h6" fontWeight={700}>
          Step 5: OE AI Chat
        </Typography>
        <Chip label="Step 5" size="small" color="primary" variant="outlined" />
        {isComplete && <Chip label="unlocked" size="small" color="success" />}
      </Box>

      <Typography variant="body2" color="text.secondary" mb={3}>
        Ask questions about the outage engineering assessment findings, scope recommendations,
        and historical event patterns. Available once the OE assessment has completed.
      </Typography>

      {/* Locked state */}
      {!isComplete && (
        <Alert severity="info" icon={<SmartToy />} sx={{ mb: 3 }}>
          <AlertTitle>Q&amp;A Available After Assessment</AlertTitle>
          Complete the OE assessment (Step 4) first. The outage-agent will answer questions
          based on the assessment results and event history.
        </Alert>
      )}

      {/* Connection error */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Chat interface — only rendered when OE is complete */}
      {isComplete && (
        <Paper elevation={2} sx={{ height: 600, display: 'flex', flexDirection: 'column' }}>
          {/* Quick actions */}
          {messages.length === 0 && (
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
                    icon={<SmartToy />}
                  />
                ))}
              </Box>
            </Box>
          )}

          {/* Messages */}
          <Box sx={{ flex: 1, overflowY: 'auto', p: 2, bgcolor: 'grey.50' }}>
            {messages.length === 0 && (
              <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                height="100%"
                color="text.secondary"
              >
                <SmartToy sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
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
                    <Psychology sx={chatAvatarIconSx} />
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
                  <Box
                    display="flex"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    mb={0.5}
                  >
                    <Typography variant="caption" fontWeight="bold" color="text.secondary">
                      {message.role === 'user' ? 'You' : 'Outage Agent'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {message.timestamp
                        ? new Date(message.timestamp).toLocaleTimeString()
                        : ''}
                    </Typography>
                  </Box>

                  {message.role === 'assistant' ? (
                    <FormattedChatMessage content={message.content} />
                  ) : (
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                      {message.content}
                    </Typography>
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

            {sending && (
              <Box display="flex" gap={1.5} mb={2}>
                <Avatar sx={{ bgcolor: 'grey.600', width: 36, height: 36 }}>
                  <Psychology sx={chatAvatarIconSx} />
                </Avatar>
                <Box
                  sx={{
                    bgcolor: 'white',
                    p: 2,
                    borderRadius: 2,
                    border: 1,
                    borderColor: 'divider',
                  }}
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

          {/* Input */}
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Box display="flex" gap={1}>
              <TextField
                fullWidth
                size="small"
                placeholder="Ask a question about the outage assessment..."
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
        </Paper>
      )}
    </Box>
  )
}

export default OutageChatPanel
