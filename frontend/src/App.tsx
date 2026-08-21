import React, { useEffect, useState } from 'react';
import { PlatformStatus, WatchlistAsset, StrategyItem, ReadinessReport } from './types';
import { api } from './services/api';
import { Header } from './components/layout/Header';
import { SafetyStatusBar } from './components/layout/SafetyStatusBar';
import { Sidebar } from './components/layout/Sidebar';
import { TabNavigation, TabKey } from './components/layout/TabNavigation';
import { DashboardView } from './components/views/DashboardView';
import { IntelligenceHubView } from './components/views/IntelligenceHubView';
import { RuntimeDAGView } from './components/views/RuntimeDAGView';
import { AlphaStudioView } from './components/views/AlphaStudioView';
import { ModelControlView } from './components/views/ModelControlView';
import { PaperTradingDeskView } from './components/views/PaperTradingDeskView';
import { MemoryAuditView } from './components/views/MemoryAuditView';
import { InstitutionalArchitectureView } from './components/views/InstitutionalArchitectureView';
import { ChatGPTQuantCopilot } from './components/chat/ChatGPTQuantCopilot';
import { KnowledgeBaseModal } from './components/knowledge/KnowledgeBaseModal';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('NVDA');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Learning Mode and Knowledge Base state
  const [learningMode, setLearningMode] = useState<boolean>(() => localStorage.getItem('aq_learning_mode') === 'true');
  const [isKnowledgeBaseOpen, setIsKnowledgeBaseOpen] = useState<boolean>(false);
  const [knowledgeBaseInitialMetric, setKnowledgeBaseInitialMetric] = useState<string | null>(null);

  const toggleLearningMode = () => {
    setLearningMode((prev) => {
      const next = !prev;
      localStorage.setItem('aq_learning_mode', String(next));
      return next;
    });
  };

  const handleOpenKnowledgeBase = (metricId?: string) => {
    setKnowledgeBaseInitialMetric(metricId ?? null);
    setIsKnowledgeBaseOpen(true);
  };

  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistAsset[]>([]);
  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadInitialData = async () => {
    setIsLoading(true);
    try {
      const [statusRes, readinessRes, watchlistRes, strategiesRes] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getReadiness().catch(() => null),
        api.getWatchlist().catch(() => ({ items: [] })),
        api.listStrategies().catch(() => []),
      ]);

      if (statusRes) setStatus(statusRes);
      if (readinessRes) setReadiness(readinessRes);
      if (watchlistRes?.items && watchlistRes.items.length > 0) {
        setWatchlist(watchlistRes.items);
      } else {
        // Explicitly un-fetched / un-priced watchlist items
        setWatchlist([
          { symbol: 'NVDA', price: null, change: null, changePercent: null, volume: null, companyName: 'NVIDIA Corporation', sector: 'Semiconductors', dataStatus: 'unavailable' },
          { symbol: 'SPY', price: null, change: null, changePercent: null, volume: null, companyName: 'SPDR S&P 500 ETF', sector: 'Index', dataStatus: 'unavailable' },
          { symbol: 'QQQ', price: null, change: null, changePercent: null, volume: null, companyName: 'Invesco QQQ Trust', sector: 'Technology', dataStatus: 'unavailable' },
          { symbol: 'AAPL', price: null, change: null, changePercent: null, volume: null, companyName: 'Apple Inc.', sector: 'Consumer Tech', dataStatus: 'unavailable' },
          { symbol: 'MSFT', price: null, change: null, changePercent: null, volume: null, companyName: 'Microsoft Corporation', sector: 'Software', dataStatus: 'unavailable' },
          { symbol: 'TSLA', price: null, change: null, changePercent: null, volume: null, companyName: 'Tesla Inc.', sector: 'Auto/CleanTech', dataStatus: 'unavailable' },
          { symbol: 'AMZN', price: null, change: null, changePercent: null, volume: null, companyName: 'Amazon.com Inc.', sector: 'E-Commerce', dataStatus: 'unavailable' },
          { symbol: 'META', price: null, change: null, changePercent: null, volume: null, companyName: 'Meta Platforms Inc.', sector: 'Social Tech', dataStatus: 'unavailable' },
          { symbol: 'GLD', price: null, change: null, changePercent: null, volume: null, companyName: 'SPDR Gold Shares', sector: 'Commodities', dataStatus: 'unavailable' },
          { symbol: 'TLT', price: null, change: null, changePercent: null, volume: null, companyName: 'iShares 20+ Year Treasury', sector: 'Bonds', dataStatus: 'unavailable' },
        ]);
      }
      if (strategiesRes) setStrategies(strategiesRes);
    } catch (err) {
      console.error('Initial data load error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddSymbol = async (symbol: string) => {
    const cleanSym = symbol.trim().toUpperCase();
    if (!cleanSym) return;

    try {
      // Check if already in watchlist
      const existing = watchlist.find((a) => a.symbol === cleanSym);
      if (existing) {
        setSelectedSymbol(cleanSym);
        return;
      }

      // Fetch live quote and company fundamentals
      const [quote, fund] = await Promise.all([
        api.getQuote(cleanSym).catch(() => ({})),
        api.getFundamentals(cleanSym).catch(() => ({})),
      ]);

      const priceVal = typeof quote.regular_market_price === 'number' ? quote.regular_market_price : typeof quote.price === 'number' ? quote.price : null;
      const changeVal = typeof quote.change === 'number' ? quote.change : null;
      const changePctVal = typeof quote.change_pct === 'number' ? quote.change_pct : typeof quote.changePercent === 'number' ? quote.changePercent : null;
      const volVal = typeof quote.volume === 'number' && quote.volume > 0 ? `${(quote.volume / 1e6).toFixed(1)}M` : null;

      const newAsset: WatchlistAsset = {
        symbol: cleanSym,
        price: priceVal,
        change: changeVal,
        changePercent: changePctVal,
        volume: volVal,
        companyName: fund.company_name || quote.short_name || null,
        sector: fund.sector || null,
        dataStatus: priceVal !== null ? 'live' : 'unavailable',
      };

      setWatchlist((prev) => [newAsset, ...prev.filter((a) => a.symbol !== cleanSym)]);
      setSelectedSymbol(cleanSym);
    } catch (err) {
      console.error('Error adding symbol to watchlist:', err);
      // Fallback: create asset with null price/dataStatus=unavailable
      const fallbackAsset: WatchlistAsset = {
        symbol: cleanSym,
        price: null,
        change: null,
        changePercent: null,
        volume: null,
        companyName: null,
        sector: null,
        dataStatus: 'unavailable',
      };
      setWatchlist((prev) => [fallbackAsset, ...prev.filter((a) => a.symbol !== cleanSym)]);
      setSelectedSymbol(cleanSym);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-background text-slate-100 overflow-hidden select-none relative">
      {/* Top Ticker & System Health Bar */}
      <Header
        status={status}
        watchlist={watchlist}
        onRefresh={loadInitialData}
        isLoading={isLoading}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={(sym) => setSelectedSymbol(sym)}
        onAddSymbol={handleAddSymbol}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        learningMode={learningMode}
        onToggleLearningMode={toggleLearningMode}
        onOpenKnowledgeBase={handleOpenKnowledgeBase}
      />

      {/* Global Trading Safety Status Bar */}
      <SafetyStatusBar readiness={readiness} onRefresh={loadInitialData} />

      {/* Navigation Bar */}
      <TabNavigation
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
      />

      {/* Main Workspace Body with Watchlist Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          watchlist={watchlist}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={(sym) => setSelectedSymbol(sym)}
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
          onAddSymbol={handleAddSymbol}
        />

        {/* Tab View Router */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === 'dashboard' && (
            <DashboardView
              status={status}
              readiness={readiness}
              strategies={strategies}
              selectedSymbol={selectedSymbol}
              onNavigateTab={(tab) => setActiveTab(tab)}
            />
          )}

          {activeTab === 'intelligence' && (
            <IntelligenceHubView selectedSymbol={selectedSymbol} />
          )}

          {activeTab === 'runtime' && (
            <RuntimeDAGView selectedSymbol={selectedSymbol} />
          )}

          {activeTab === 'alpha' && (
            <AlphaStudioView
              selectedSymbol={selectedSymbol}
              strategies={strategies}
              onRefreshStrategies={loadInitialData}
            />
          )}

          {activeTab === 'models' && (
            <ModelControlView />
          )}

          {activeTab === 'paper' && (
            <PaperTradingDeskView
              selectedSymbol={selectedSymbol}
              strategies={strategies}
              readiness={readiness}
            />
          )}

          {activeTab === 'memory' && (
            <MemoryAuditView />
          )}

          {activeTab === 'architecture' && (
            <InstitutionalArchitectureView />
          )}
        </main>
      </div>

      {/* Interactive ChatGPT Quant Co-Pilot Floating Chat Drawer */}
      <ChatGPTQuantCopilot selectedSymbol={selectedSymbol} />

      {/* Financial Knowledge & Pedagogical Modal */}
      <KnowledgeBaseModal
        isOpen={isKnowledgeBaseOpen}
        onClose={() => setIsKnowledgeBaseOpen(false)}
        initialMetricId={knowledgeBaseInitialMetric}
      />
    </div>
  );
};
