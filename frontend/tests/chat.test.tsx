import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ChatMessage, ChatPanel } from '@/components/ChatPanel';

const messages: ChatMessage[] = [
  { id: 'u1', role: 'user', content: 'Buy 10 NVDA' },
  {
    id: 'a1',
    role: 'assistant',
    content: 'Bought 10 NVDA.',
    actions: [
      {
        type: 'trade',
        ticker: 'NVDA',
        success: true,
        trade: {
          id: 't1',
          ticker: 'NVDA',
          side: 'buy',
          quantity: 10,
          price: 121.5,
          executed_at: '2026-09-07T12:00:00Z',
        },
      },
      { type: 'watchlist_add', ticker: 'PYPL', success: false, error: 'already watched' },
    ],
  },
];

const baseProps = {
  messages: [],
  loading: false,
  collapsed: false,
  onToggle: vi.fn(),
  onSend: vi.fn().mockResolvedValue(undefined),
};

describe('ChatPanel', () => {
  it('renders the conversation with inline action confirmations', () => {
    render(<ChatPanel {...baseProps} messages={messages} />);

    expect(screen.getByText('Buy 10 NVDA')).toBeInTheDocument();
    expect(screen.getByText('✓ BUY 10 NVDA @ 121.50')).toBeInTheDocument();
    expect(screen.getByText('✗ watchlist add PYPL — already watched')).toBeInTheDocument();
  });

  it('shows a loading indicator and blocks sending while awaiting the LLM', () => {
    render(<ChatPanel {...baseProps} loading />);

    expect(screen.getByRole('status')).toHaveTextContent('Thinking');
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  });

  it('sends the trimmed draft and clears the input', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<ChatPanel {...baseProps} onSend={onSend} />);

    const input = screen.getByLabelText('Chat message');
    await user.type(input, '  how am I doing?  ');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(onSend).toHaveBeenCalledWith('how am I doing?');
    expect(input).toHaveValue('');
  });

  it('collapses to a reopen affordance', () => {
    render(<ChatPanel {...baseProps} collapsed />);
    expect(screen.getByRole('button', { name: 'Open AI assistant' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Chat message')).not.toBeInTheDocument();
  });
});
