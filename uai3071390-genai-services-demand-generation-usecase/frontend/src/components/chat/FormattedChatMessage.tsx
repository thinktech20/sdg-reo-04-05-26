import { Fragment } from 'react'
import type { ReactNode } from 'react'
import { Box, Typography } from '@mui/material'

interface FormattedChatMessageProps {
  content: string
}

const inlineTokenPattern = /(\*\*[^*]+?\*\*|`[^`]+?`|\*[^*\n]+?\*)/g

function renderInline(content: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let key = 0

  for (const match of content.matchAll(inlineTokenPattern)) {
    const token = match[0]
    const index = match.index

    if (index > lastIndex) {
      nodes.push(<Fragment key={`text-${key++}`}>{content.slice(lastIndex, index)}</Fragment>)
    }

    if (token.startsWith('`')) {
      nodes.push(
        <Box
          key={`code-${key++}`}
          component="code"
          sx={{
            px: 0.5,
            py: 0.125,
            borderRadius: 0.75,
            bgcolor: 'grey.100',
            fontFamily: 'Monaco, Consolas, "Liberation Mono", monospace',
            fontSize: '0.85em',
          }}
        >
          {token.slice(1, -1)}
        </Box>
      )
    } else if (token.startsWith('**')) {
      nodes.push(<strong key={`bold-${key++}`}>{token.slice(2, -2)}</strong>)
    } else {
      nodes.push(<em key={`italic-${key++}`}>{token.slice(1, -1)}</em>)
    }

    lastIndex = index + token.length
  }

  if (lastIndex < content.length) {
    nodes.push(<Fragment key={`text-${key++}`}>{content.slice(lastIndex)}</Fragment>)
  }

  return nodes.length > 0 ? nodes : [content]
}

function renderParagraph(lines: string[], key: string): ReactNode {
  return (
    <Typography key={key} variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
      {lines.map((line, index) => (
        <Fragment key={`${key}-line-${index}`}>
          {index > 0 ? <br /> : null}
          {renderInline(line)}
        </Fragment>
      ))}
    </Typography>
  )
}

function renderSpacer(key: string): ReactNode {
  return <Box key={key} data-testid="formatted-chat-spacer" sx={{ height: 12 }} />
}

function renderList(items: string[], key: string): ReactNode {
  return (
    <Box
      key={key}
      component="ul"
      sx={{
        my: 0,
        ml: 2.5,
        pl: 2,
        listStyleType: 'disc',
        listStylePosition: 'outside',
      }}
    >
      {items.map((item, index) => (
        <Box key={`${key}-item-${index}`} component="li" sx={{ display: 'list-item', mb: 0.5 }}>
          <Typography component="span" variant="body2" sx={{ lineHeight: 1.6 }}>
            {renderInline(item)}
          </Typography>
        </Box>
      ))}
    </Box>
  )
}

function buildBlocks(content: string): ReactNode[] {
  const blocks: ReactNode[] = []
  const paragraphLines: string[] = []
  const listItems: string[] = []
  let previousLineWasBlank = false

  const flushParagraph = () => {
    if (paragraphLines.length === 0) return
    blocks.push(renderParagraph([...paragraphLines], `paragraph-${blocks.length}`))
    paragraphLines.length = 0
  }

  const flushList = () => {
    if (listItems.length === 0) return
    blocks.push(renderList([...listItems], `list-${blocks.length}`))
    listItems.length = 0
  }

  for (const line of content.split(/\r?\n/)) {
    const bulletMatch = line.match(/^\s*-\s+(.*)$/)
    if (bulletMatch) {
      flushParagraph()
      const [, bulletContent = ''] = bulletMatch
      listItems.push(bulletContent)
      previousLineWasBlank = false
      continue
    }

    if (line.trim() === '') {
      flushParagraph()
      flushList()
      if (!previousLineWasBlank && blocks.length > 0) {
        blocks.push(renderSpacer(`spacer-${blocks.length}`))
      }
      previousLineWasBlank = true
      continue
    }

    flushList()
    paragraphLines.push(line)
    previousLineWasBlank = false
  }

  flushParagraph()
  flushList()

  return blocks.length > 0 ? blocks : [renderParagraph([content], 'paragraph-0')]
}

const FormattedChatMessage = ({ content }: FormattedChatMessageProps) => {
  return <Box>{buildBlocks(content)}</Box>
}

export default FormattedChatMessage