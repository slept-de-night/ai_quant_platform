import React, { useState } from 'react';
import { WatchlistAsset } from '../../types';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Layers,
  ChevronLeft,
  ChevronRight,
  Plus,
  ArrowRight,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

interface SidebarProps {
  watchlist: WatchlistAsset[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  isOpen: boolean;
  onToggle: () => void;
  onAddSymbol?: (symbol: string) => Promise<void>;
}

export const Sidebar: React.FC<SidebarProps> = ({
  watchlist,
  selectedSymbol,
  onSelectSymbol,
  isOpen,
  onToggle,
  onAddSymbol,
}) => {
  const [filter, setFilter] = useState('');
  const [newSymbolInput, setNewSymbolInput] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const handleAddSymbolSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const sym = newSymbolInput.trim().toUpperCase();
    if (!sym || !onAddSymbol) return;

    setIsAdding(true);
    try {
      await onAddSymbol(sym);
      onSelectSymbol(sym);
      setNewSymbolInput('');
    } catch (err) {
      console.error('Failed to add symbol:', err);
    } finally {
      setIsAdding(false);
    }
  };

  const filteredAssets = watchlist.filter(
    (a) =>
      a.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      (a.companyName && a.companyName.toLowerCase().includes(filter.toLowerCase())) ||
      (a.sector && a.sector.toLowerCase().includes(filter.toLowerCase()))
  );

  // If sidebar is collapsed, render a sleek floating edge button
  if (!isOpen) {
    return (
      <div className="relative z-20 flex flex-col justify-start bg-card/40 border-r border-card-border/60 py-3 px-1">
        <button
          onClick={onToggle}
          className="p-2 rounded-lg bg-background hover:bg-card-border border border-card-border text-accent-cyan hover:text-white transition shadow-lg cursor-pointer flex flex-col items-center gap-1 group"
          title="Open Watchlist (Ctrl+B)"
        >
          <PanelLeftOpen className="w-4 h-4 group-hover:scale-110 transition-transform" />
          <span className="text-[9px] font-mono [writing-mode:vertical-lr] text-slate-400 font-bold tracking-widest uppercase">
            Watchlist
          </span>
        </button>
      </div>
    );
  }

  return (
    <aside className="w-68 bg-card/95 border-r border-card-border flex flex-col h-full shrink-0 select-none shadow-xl transition-all duration-200">
      {/* Sidebar Header with Collapse Button */}
      <div className="p-3 border-b border-card-border flex items-center justify-between bg-background/50">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-accent-cyan" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Watchlist
          </span>
          <span className="px-1.5 py-0.2 text-[9px] font-mono bg-background border border-card-border rounded text-slate-400">
            {watchlist.length}
          </span>
        </div>

        <button
          onClick={onToggle}
          className="p-1 hover:bg-card-border text-slate-400 hover:text-slate-200 rounded transition cursor-pointer"
          title="Hide Watchlist"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* Quick Add Symbol Bar */}
      <div className="p-2.5 bg-background/30 border-b border-card-border">
        <form onSubmit={handleAddSymbolSubmit} className="flex items-center gap-1.5">
          <input
            type="text"
            value={newSymbolInput}
            onChange={(e) => setNewSymbolInput(e.target.value)}
            placeholder="Add ticker (e.g. AMD)..."
            className="flex-1 bg-background border border-card-border rounded px-2.5 py-1 text-xs text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:border-accent-cyan transition uppercase"
          />
          <button
            type="submit"
            disabled={!newSymbolInput.trim() || isAdding}
            className="p-1.5 bg-accent-cyan hover:bg-cyan-400 text-slate-950 rounded transition cursor-pointer disabled:opacity-40 shadow-sm"
            title="Add Symbol to Watchlist"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>

      {/* Local Filter Input */}
      <div className="p-2 border-b border-card-border/60">
        <div className="relative">
          <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter list..."
            className="w-full bg-background/80 border border-card-border rounded pl-7 pr-2.5 py-1 text-[11px] text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent-cyan transition"
          />
        </div>
      </div>

      {/* Symbol List */}
      <div className="flex-1 overflow-y-auto divide-y divide-card-border/40">
        {filteredAssets.map((asset) => {
          const isSelected = selectedSymbol === asset.symbol;
          const isPositive = typeof asset.change === 'number' && asset.change >= 0;

          return (
            <div
              key={asset.symbol}
              onClick={() => onSelectSymbol(asset.symbol)}
              className={`p-2.5 transition cursor-pointer flex items-center justify-between ${
                isSelected
                  ? 'bg-accent-blue/15 border-l-2 border-accent-cyan'
                  : 'hover:bg-background/60 border-l-2 border-transparent'
              }`}
            >
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono font-bold text-xs text-slate-100">{asset.symbol}</span>
                  <span className="text-[9px] px-1 py-0.2 rounded bg-card-border text-slate-400 truncate max-w-[80px]">
                    {asset.sector || 'Asset'}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 truncate max-w-[120px]">
                  {asset.companyName || '—'}
                </div>
              </div>

              <div className="text-right font-mono">
                <div className="text-xs font-semibold text-slate-200">
                  {typeof asset.price === 'number' ? `$${asset.price.toFixed(2)}` : '—'}
                </div>
                {typeof asset.changePercent === 'number' && typeof asset.change === 'number' ? (
                  <div
                    className={`flex items-center justify-end text-[11px] font-semibold ${
                      isPositive ? 'text-accent-emerald' : 'text-accent-rose'
                    }`}
                  >
                    {isPositive ? (
                      <TrendingUp className="w-3 h-3 mr-0.5 inline" />
                    ) : (
                      <TrendingDown className="w-3 h-3 mr-0.5 inline" />
                    )}
                    <span>{isPositive ? '+' : ''}{asset.changePercent.toFixed(2)}%</span>
                  </div>
                ) : (
                  <div className="text-[10px] text-slate-500 font-sans">
                    Unavailable
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {filteredAssets.length === 0 && (
          <div className="p-6 text-center text-xs text-slate-500 font-mono">
            No assets match &quot;{filter}&quot;. Use the add bar above to search and pin new tickers!
          </div>
        )}
      </div>
    </aside>
  );
};
