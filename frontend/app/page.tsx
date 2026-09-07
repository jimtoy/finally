'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChatMessage, ChatPanel } from '@/components/ChatPanel';
import { Header } from '@/components/Header';
import { MainChart } from '@/components/MainChart';
import { PnlChart } from '@/components/PnlChart';
import { PortfolioHeatmap } from '@/components/PortfolioHeatmap';
import { PositionsTable } from '@/components/PositionsTable';
import { TradeBar } from '@/components/TradeBar';
import { WatchlistPanel } from '@/components/WatchlistPanel';
import * as api from '@/lib/api';
import { derivePortfolio } from '@/lib/portfolio';
import { HistoryPoint, Portfolio, TradeSide, WatchlistEntry } from '@/lib/types';
import { usePriceStream } from '@/lib/usePriceStream';

const PORTFOLIO_POLL_MS = 15_000;
const HISTORY_POLL_MS = 30_000;

export default function Workstation() {
  const { prices, history: priceHistory, status } = usePriceStream();

  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [valueHistory, setValueHistory] = useState<HistoryPoint[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);

  const selectionTouched = useRef(false);

  const refreshPortfolio = useCallback(async () => {
    try {
      setPortfolio(await api.getPortfolio());
      setBackendError(null);
    } catch (cause) {
      setBackendError(cause instanceof Error ? cause.message : 'Backend unavailable');
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      setValueHistory(await api.getPortfolioHistory());
    } catch {
      // The P&L chart simply stays on its placeholder until the backend answers.
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      setWatchlist(await api.getWatchlist());
    } catch {
      // Watchlist renders its empty state; the price stream indicator reports connectivity.
    }
  }, []);

  useEffect(() => {
    void refreshPortfolio();
    void refreshHistory();
    void refreshWatchlist();
    const portfolioTimer = setInterval(() => void refreshPortfolio(), PORTFOLIO_POLL_MS);
    const historyTimer = setInterval(() => void refreshHistory(), HISTORY_POLL_MS);
    return () => {
      clearInterval(portfolioTimer);
      clearInterval(historyTimer);
    };
  }, [refreshPortfolio, refreshHistory, refreshWatchlist]);

  useEffect(() => {
    if (!selectionTouched.current && !selectedTicker && watchlist.length > 0) {
      setSelectedTicker(watchlist[0].ticker);
    }
  }, [watchlist, selectedTicker]);

  const derived = useMemo(() => derivePortfolio(portfolio, prices), [portfolio, prices]);

  const handleSelect = useCallback((ticker: string) => {
    selectionTouched.current = true;
    setSelectedTicker(ticker);
  }, []);

  const handleAdd = useCallback(
    async (ticker: string) => {
      try {
        await api.addToWatchlist(ticker);
        await refreshWatchlist();
      } catch (cause) {
        setBackendError(cause instanceof Error ? cause.message : 'Could not add ticker');
      }
    },
    [refreshWatchlist],
  );

  const handleRemove = useCallback(
    async (ticker: string) => {
      try {
        await api.removeFromWatchlist(ticker);
        setWatchlist((current) => current.filter((entry) => entry.ticker !== ticker));
      } catch (cause) {
        setBackendError(cause instanceof Error ? cause.message : 'Could not remove ticker');
      }
    },
    [],
  );

  const handleTrade = useCallback(
    async (ticker: string, quantity: number, side: TradeSide) => {
      const result = await api.executeTrade({ ticker, quantity, side });
      setPortfolio(result.portfolio);
      void refreshHistory();
    },
    [refreshHistory],
  );

  const handleSend = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text };
      setMessages((current) => [...current, userMessage]);
      setChatLoading(true);
      try {
        const response = await api.sendChatMessage(text);
        setMessages((current) => [
          ...current,
          { id: `a-${Date.now()}`, role: 'assistant', content: response.message, actions: response.executed_actions },
        ]);
        if (response.executed_actions?.length) {
          await Promise.all([refreshPortfolio(), refreshWatchlist(), refreshHistory()]);
        }
      } catch (cause) {
        setMessages((current) => [
          ...current,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            content: cause instanceof Error ? cause.message : 'The assistant is unavailable right now.',
          },
        ]);
      } finally {
        setChatLoading(false);
      }
    },
    [refreshPortfolio, refreshWatchlist, refreshHistory],
  );

  return (
    <div className="flex h-full flex-col">
      <Header
        totalValue={derived.total_value}
        cashBalance={derived.cash_balance}
        unrealizedPnl={derived.unrealized_pnl}
        status={status}
      />

      {backendError && (
        <p role="alert" className="shrink-0 bg-tick-down/15 px-4 py-1 text-2xs text-tick-down">
          {backendError}
        </p>
      )}

      <main className="flex min-h-0 flex-1 gap-2 p-2">
        <div className="flex w-[320px] shrink-0 flex-col gap-2">
          <div className="min-h-0 flex-1">
            <WatchlistPanel
              entries={watchlist}
              prices={prices}
              history={priceHistory}
              selectedTicker={selectedTicker}
              onSelect={handleSelect}
              onAdd={handleAdd}
              onRemove={handleRemove}
            />
          </div>
          <div className="h-[220px] shrink-0">
            <PortfolioHeatmap positions={derived.positions} onSelect={handleSelect} />
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="min-h-0 flex-1">
            <MainChart
              ticker={selectedTicker}
              tick={selectedTicker ? prices[selectedTicker] : undefined}
              points={selectedTicker ? priceHistory[selectedTicker] : undefined}
            />
          </div>
          <div className="h-[190px] shrink-0">
            <PnlChart history={valueHistory} liveValue={portfolio ? derived.total_value : null} />
          </div>
          <div className="shrink-0">
            <TradeBar selectedTicker={selectedTicker} prices={prices} onTrade={handleTrade} />
          </div>
          <div className="h-[220px] shrink-0">
            <PositionsTable positions={derived.positions} onSelect={handleSelect} />
          </div>
        </div>

        <ChatPanel
          messages={messages}
          loading={chatLoading}
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed((current) => !current)}
          onSend={handleSend}
        />
      </main>
    </div>
  );
}
