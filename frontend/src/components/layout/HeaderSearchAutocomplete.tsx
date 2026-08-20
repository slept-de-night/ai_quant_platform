import React, { useState, useEffect, useRef } from 'react';
import { AssetSearchResult } from '../../types';
import { api } from '../../services/api';
import {
  Search,
  ArrowRight,
  TrendingUp,
  Coins,
  Gem,
  Layers,
  Building2,
  Globe,
  Plus
} from 'lucide-react';

interface HeaderSearchAutocompleteProps {
  onSelectSymbol: (symbol: string) => void;
  onAddSymbol: (symbol: string) => Promise<void>;
  placeholder?: string;
  className?: string;
}

export const HeaderSearchAutocomplete: React.FC<HeaderSearchAutocompleteProps> = ({
  onSelectSymbol,
  onAddSymbol,
  placeholder = 'Search Stock, ETF, Gold, Silver, Crypto (e.g. DRAM, GLD, BTC-USD, NVDA)...',
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<AssetSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await api.searchAssets(trimmed, 8);
        setResults(res);
        setIsOpen(res.length > 0);
        setSelectedIndex(-1);
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        setIsLoading(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside to dismiss dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = async (item: AssetSearchResult | string) => {
    const symbol = typeof item === 'string' ? item.trim().toUpperCase() : item.symbol;
    if (!symbol) return;

    setIsOpen(false);
    setQuery('');
    try {
      await onAddSymbol(symbol);
      onSelectSymbol(symbol);
    } catch (err) {
      console.error('Failed to select asset:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        handleSelect(results[selectedIndex]);
      } else if (query.trim()) {
        handleSelect(query.trim().toUpperCase());
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const getAssetBadge = (type: string) => {
    switch (type) {
      case 'ETF':
        return (
          <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-accent-purple/20 text-accent-purple border border-accent-purple/40 rounded flex items-center gap-1">
            <Layers className="w-2.5 h-2.5" />
            <span>ETF</span>
          </span>
        );
      case 'COMMODITY':
        return (
          <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded flex items-center gap-1">
            <Gem className="w-2.5 h-2.5" />
            <span>COMMODITY</span>
          </span>
        );
      case 'CRYPTO':
        return (
          <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 rounded flex items-center gap-1">
            <Coins className="w-2.5 h-2.5" />
            <span>CRYPTO</span>
          </span>
        );
      case 'FOREX':
        return (
          <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-indigo-500/20 text-indigo-400 border border-indigo-500/40 rounded flex items-center gap-1">
            <Globe className="w-2.5 h-2.5" />
            <span>FOREX</span>
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-accent-blue/20 text-accent-cyan border border-accent-blue/40 rounded flex items-center gap-1">
            <Building2 className="w-2.5 h-2.5" />
            <span>STOCK</span>
          </span>
        );
    }
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative flex items-center">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full bg-background border border-card-border rounded-lg pl-9 pr-24 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent-cyan font-mono shadow-inner transition"
        />
        <button
          onClick={() => query.trim() && handleSelect(query.trim().toUpperCase())}
          disabled={!query.trim()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 px-2.5 py-1 bg-accent-cyan hover:bg-cyan-400 text-slate-950 text-[10px] font-bold font-mono rounded shadow transition disabled:opacity-40 cursor-pointer flex items-center gap-1"
        >
          <span>SEARCH</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      {/* Floating Autocomplete Dropdown */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1.5 bg-card/95 backdrop-blur-xl border border-card-border rounded-xl shadow-2xl z-50 overflow-hidden divide-y divide-card-border/50 max-h-80 overflow-y-auto animate-in fade-in zoom-in-95 duration-100">
          <div className="p-2 bg-background/60 text-[10px] font-mono text-slate-400 flex items-center justify-between">
            <span>SUGGESTED INSTRUMENTS</span>
            <span>Use ↑↓ to navigate, Enter to select</span>
          </div>

          {results.map((item, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <div
                key={item.symbol}
                onClick={() => handleSelect(item)}
                className={`p-2.5 transition cursor-pointer flex items-center justify-between ${
                  isSelected ? 'bg-accent-cyan/15 text-accent-cyan' : 'hover:bg-background/80 text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="font-mono font-bold text-xs text-slate-100 shrink-0">
                    {item.symbol}
                  </span>
                  {getAssetBadge(item.asset_type)}
                  <span className="text-[11px] text-slate-300 truncate max-w-[220px]">
                    {item.name}
                  </span>
                </div>

                <div className="text-right text-[10px] font-mono text-slate-500 shrink-0">
                  <span>{item.exchange}</span>
                </div>
              </div>
            );
          })}

          {/* Direct Search Add Item */}
          {query.trim() && !results.some((r) => r.symbol.toUpperCase() === query.trim().toUpperCase()) && (
            <div
              onClick={() => handleSelect(query.trim().toUpperCase())}
              className="p-2.5 bg-accent-cyan/10 hover:bg-accent-cyan/20 cursor-pointer flex items-center justify-between text-xs font-mono text-accent-cyan"
            >
              <div className="flex items-center gap-2">
                <Plus className="w-3.5 h-3.5" />
                <span>Search custom symbol: <strong>{query.trim().toUpperCase()}</strong></span>
              </div>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
