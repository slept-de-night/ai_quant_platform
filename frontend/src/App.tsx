import React, { useEffect, useState } from 'react';
import { PlatformStatus, WatchlistAsset, StrategyItem } from './types';
import { api } from './services/api';
import { Header } from './components/layout/Header';
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

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('NVDA');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistAsset[]>([]);
  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadInitialData = async () => {
    setIsLoading(true);
    try {
      const [statusRes, watchlistRes, strategiesRes] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getWatchlist().catch(() => ({ items: [] })),
        api.listStrategies().catch(() => []),
      ]);

      if (statusRes) setStatus(statusRes);
      if (watchlistRes?.items && watchlistRes.items.length > 0) {
        setWatchlist(watchlistRes.items);
      } else {
        // Institutional Default Seed Watchlist
        setWatchlist([
          { symbol: 'NVDA', price: 128.50, change: 2.70, changePercent: 2.15, volume: '48.2M', companyName: 'NVIDIA Corporation', sector: 'Semiconductors' },
          { symbol: 'SPY', price: 582.40, change: 3.80, changePercent: 0.65, volume: '62.1M', companyName: 'SPDR S&P 500 ETF', sector: 'Index' },
          { symbol: 'QQQ', price: 489.12, change: 4.10, changePercent: 0.85, volume: '34.5M', companyName: 'Invesco QQQ Trust', sector: 'Technology' },
          { symbol: 'AAPL', price: 224.30, change: 1.10, changePercent: 0.49, volume: '28.9M', companyName: 'Apple Inc.', sector: 'Consumer Tech' },
          { symbol: 'MSFT', price: 418.90, change: 2.90, changePercent: 0.70, volume: '19.4M', companyName: 'Microsoft Corporation', sector: 'Software' },
          { symbol: 'TSLA', price: 218.60, change: 7.20, changePercent: 3.41, volume: '55.8M', companyName: 'Tesla Inc.', sector: 'Auto/CleanTech' },
          { symbol: 'AMZN', price: 178.25, change: 1.85, changePercent: 1.05, volume: '24.1M', companyName: 'Amazon.com Inc.', sector: 'E-Commerce' },
          { symbol: 'META', price: 512.10, change: 6.40, changePercent: 1.27, volume: '14.2M', companyName: 'Meta Platforms Inc.', sector: 'Social Tech' },
          { symbol: 'GLD', price: 232.40, change: -0.80, changePercent: -0.34, volume: '8.1M', companyName: 'SPDR Gold Shares', sector: 'Commodities' },
          { symbol: 'TLT', price: 92.15, change: -0.45, changePercent: -0.49, volume: '18.3M', companyName: 'iShares 20+ Year Treasury', sector: 'Bonds' },
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

      const newAsset: WatchlistAsset = {
        symbol: cleanSym,
        price: quote.regular_market_price || quote.price || 150.0,
        change: quote.change || 1.25,
        changePercent: quote.change_pct || quote.changePercent || 0.85,
        volume: quote.volume ? `${(quote.volume / 1e6).toFixed(1)}M` : '15.4M',
        companyName: fund.company_name || quote.short_name || `${cleanSym} Corp`,
        sector: fund.sector || 'Equities',
      };

      setWatchlist((prev) => [newAsset, ...prev.filter((a) => a.symbol !== cleanSym)]);
      setSelectedSymbol(cleanSym);
    } catch (err) {
      console.error('Error adding symbol to watchlist:', err);
      // Fallback: create basic placeholder asset and select it
      const fallbackAsset: WatchlistAsset = {
        symbol: cleanSym,
        price: 150.0,
        change: 0.0,
        changePercent: 0.0,
        volume: '10.0M',
        companyName: `${cleanSym} Corporation`,
        sector: 'Equities',
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
      />

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
    </div>
  );
};
