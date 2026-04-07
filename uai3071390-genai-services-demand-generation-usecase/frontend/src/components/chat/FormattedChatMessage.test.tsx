import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FormattedChatMessage from './FormattedChatMessage'

describe('FormattedChatMessage', () => {
  it('renders bold, italic, inline code, and bullet lists', () => {
    render(
      <FormattedChatMessage
        content={[
          '**Answer**',
          '',
          '*Explanation*',
          '- Uses `read_re_table(asmt_35c19774)`',
          '- Shows **formatted** output',
        ].join('\n')}
      />,
    )

    expect(screen.getByText('Answer').tagName.toLowerCase()).toBe('strong')
    expect(screen.getByText('Explanation').tagName.toLowerCase()).toBe('em')
    expect(screen.getByText('read_re_table(asmt_35c19774)').tagName.toLowerCase()).toBe('code')
    expect(screen.getByRole('list')).toHaveStyle({ listStyleType: 'disc' })
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('formatted').tagName.toLowerCase()).toBe('strong')
    expect(screen.getAllByTestId('formatted-chat-spacer')).toHaveLength(1)
  })

  it('leaves plain text untouched', () => {
    render(<FormattedChatMessage content="Plain response without markdown markers." />)

    expect(screen.getByText('Plain response without markdown markers.')).toBeInTheDocument()
  })

  it('keeps multiple lines in the same paragraph separated with line breaks', () => {
    render(<FormattedChatMessage content={['First line', 'Second line'].join('\n')} />)

    const paragraph = screen.getByText(/First line/).closest('p')

    expect(paragraph).toHaveTextContent('First lineSecond line')
    expect(paragraph?.querySelectorAll('br')).toHaveLength(1)
  })

  it('does not add repeated spacers for consecutive blank lines', () => {
    render(<FormattedChatMessage content={['First line', '', '', 'Second line'].join('\n')} />)

    expect(screen.getByText('First line')).toBeInTheDocument()
    expect(screen.getByText('Second line')).toBeInTheDocument()
    expect(screen.getAllByTestId('formatted-chat-spacer')).toHaveLength(1)
  })

  it('renders an empty message without crashing', () => {
    render(<FormattedChatMessage content="" />)

    expect(screen.queryAllByRole('list')).toHaveLength(0)
    expect(screen.queryAllByTestId('formatted-chat-spacer')).toHaveLength(0)
  })
})