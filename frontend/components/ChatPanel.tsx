'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { formatPrice, formatQuantity } from '@/lib/format';
import { ExecutedAction } from '@/lib/types';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: ExecutedAction[];
}

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  collapsed: boolean;
  onToggle: () => void;
  onSend: (message: string) => Promise<void>;
}

export function ChatPanel({ messages, loading, collapsed, onToggle, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, loading]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || loading) return;
    setDraft('');
    await onSend(text);
  };

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Open AI assistant"
        className="flex w-10 shrink-0 flex-col items-center justify-center gap-2 rounded border border-terminal-border bg-terminal-panel text-2xs uppercase tracking-[0.3em] text-accent-yellow"
      >
        <span style={{ writingMode: 'vertical-rl' }}>AI Copilot</span>
      </button>
    );
  }

  return (
    <section className="panel w-[340px] shrink-0" aria-label="AI assistant">
      <div className="panel-header">
        <h2 className="panel-title">AI Copilot</h2>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Collapse AI assistant"
          className="text-terminal-muted transition-colors hover:text-accent-yellow"
        >
          ›
        </button>
      </div>

      <div ref={scrollRef} className="panel-body space-y-3 p-3">
        {messages.length === 0 && !loading && (
          <p className="text-2xs leading-relaxed text-terminal-muted">
            Ask about your portfolio, request analysis, or say &quot;buy 10 NVDA&quot; — trades execute immediately.
          </p>
        )}

        {messages.map((message) => (
          <div key={message.id} className={message.role === 'user' ? 'text-right' : ''}>
            <div
              className={`inline-block max-w-[92%] whitespace-pre-wrap rounded px-2.5 py-1.5 text-xs leading-relaxed ${
                message.role === 'user'
                  ? 'bg-accent-purple/30 text-terminal-text'
                  : 'bg-terminal-raised text-terminal-text'
              }`}
            >
              {message.content}
            </div>
            {message.actions && message.actions.length > 0 && (
              <ul className="mt-1.5 space-y-1 text-left">
                {message.actions.map((action, index) => (
                  <li
                    key={`${message.id}-${index}`}
                    className={`rounded border px-2 py-1 text-2xs ${
                      action.success
                        ? 'border-tick-up/40 bg-tick-up/10 text-tick-up'
                        : 'border-tick-down/40 bg-tick-down/10 text-tick-down'
                    }`}
                  >
                    {describeAction(action)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        {loading && (
          <div role="status" className="flex items-center gap-1.5 text-2xs uppercase tracking-widest text-terminal-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-yellow" />
            Thinking…
          </div>
        )}
      </div>

      <form onSubmit={submit} className="flex shrink-0 gap-2 border-t border-terminal-border p-2">
        <input
          aria-label="Chat message"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask FinAlly…"
          className="field flex-1"
          disabled={loading}
        />
        <button type="submit" className="btn-submit" disabled={loading || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}

export function describeAction(action: ExecutedAction): string {
  const prefix = action.success ? '✓' : '✗';
  if (action.trade) {
    const { side, quantity, price } = action.trade;
    return `${prefix} ${side.toUpperCase()} ${formatQuantity(quantity)} ${action.ticker} @ ${formatPrice(price)}`;
  }
  const label = action.type.replace(/_/g, ' ');
  return `${prefix} ${label} ${action.ticker}${action.error ? ` — ${action.error}` : ''}`;
}
