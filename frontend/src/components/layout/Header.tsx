import React, { useEffect, useState } from 'react';
import { PlatformStatus, WatchlistAsset } from '../../types';
import { api } from '../../services/api';
import {
  Activity,
  ShieldAlert,
  Cpu,
  DollarSign,
  Clock,
  RefreshCw,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  ArrowRight,
  Server,
  Zap,
} from 'lucide-react';
import { HeaderSearchAutocomplete } from '../../features/market/HeaderSearchAutocomplete';

interface HeaderProps {
  status: PlatformStatus | null;
  watchlist: WatchlistAsset[];
  onRefresh: () => void;
  isLoading: boolean;
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  onAddSymbol: (symbol: string) => Promise<void>;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  watchlist,
  onRefresh,
  isLoading,
  selectedSymbol,
  onSelectSymbol,
  onAddSymbol,
  isSidebarOpen,
  onToggleSidebar,
}) => {
  const [time, setTime] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [activeBroker, setActiveBroker] = useState<string | null>(null);
  const [isSwitchingBroker, setIsSwitchingBroker] = useState<boolean>(false);
  const [brokerSwitchError, setBrokerSwitchError] = useState<string | null>(null);

  useEffect(() => {
    // Sync active broker from authoritative backend state. Do NOT assume a
    // broker before the execution engine reports one.
    const fetchBrokers = async () => {
      try {
        const res = await api.listBrokers();
        if (typeof res?.active === 'string' && res.active) {
          setActiveBroker(res.active);
        }
      } catch (e) {
        // Leave activeBroker as null (UNKNOWN) until backend confirms venue.
      }
    };
    fetchBrokers();
  }, [status]);

  const handleBrokerChange = async (newBroker: string) => {
    if (isSwitchingBroker || newBroker === activeBroker) return;
    const previousBroker = activeBroker;
    setIsSwitchingBroker(true);
    setBrokerSwitchError(null);
    try {
      await api.selectBroker(newBroker);
      // Backend confirmed; re-read authoritative state rather than trusting
      // the optimistic selection.
      const res = await api.listBrokers();
      if (typeof res?.active === 'string' && res.active) {
        setActiveBroker(res.active);
      }
      onRefresh();
    } catch (e) {
      // Switch failed. Active broker remains the previously confirmed venue.
      setActiveBroker(previousBroker);
      setBrokerSwitchError(`Switch failed. Active broker remains ${previousBroker ?? 'UNKNOWN'}.`);
      console.error('Failed to switch broker:', e);
    } finally {
      setIsSwitchingBroker(false);
    }
  };


  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toUTCString().slice(17, 25) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const sym = searchQuery.trim().toUpperCase();
    if (!sym) return;

    setIsSearching(true);
    try {
      await onAddSymbol(sym);
      onSelectSymbol(sym);
      setSearchQuery('');
    } catch (err) {
      console.error('Failed to add symbol:', err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <header className="flex flex-col bg-terminal border-b border-card-border select-none z-30">
      {/* Top Ticker Tape */}
      <div className="flex items-center h-7 bg-background px-3 border-b border-card-border overflow-x-auto text-xs whitespace-nowrap scrollbar-none gap-6">
        <div className="flex items-center gap-1.5 text-accent-cyan font-semibold text-[11px] uppercase tracking-wider">
          <Activity className="w-3.5 h-3.5 text-accent-cyan animate-pulse" />
          <span>Institutional Ticker</span>
        </div>
        {watchlist.slice(0, 10).map((asset) => (
          <div
            key={asset.symbol}
            onClick={() => onSelectSymbol(asset.symbol)}
            className={`flex items-center gap-2 font-mono text-[11px] cursor-pointer px-1.5 py-0.5 rounded transition ${
              selectedSymbol === asset.symbol ? 'bg-accent-cyan/15 text-accent-cyan font-bold' : 'hover:bg-card-border/50'
            }`}
          >
            <span className="font-bold text-slate-200">{asset.symbol}</span>
            <span className="text-slate-400">
              {typeof asset.price === 'number' ? `$${asset.price.toFixed(2)}` : '—'}
            </span>
            {typeof asset.change === 'number' && typeof asset.changePercent === 'number' ? (
              <span className={`font-semibold ${asset.change >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                {asset.change >= 0 ? '+' : ''}{asset.changePercent.toFixed(2)}%
              </span>
            ) : (
              <span className="text-slate-500 font-normal">unavailable</span>
            )}
          </div>
        ))}
      </div>

      {/* Main Navigation & Search Bar */}
      <div className="flex items-center justify-between h-16 px-4 bg-card/60 backdrop-blur-md gap-4">
        {/* Brand & Sidebar Toggle */}

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg bg-background hover:bg-card-border border border-card-border text-slate-300 hover:text-white transition cursor-pointer flex items-center gap-1.5"
            title={isSidebarOpen ? 'Hide Watchlist Sidebar' : 'Show Watchlist Sidebar'}
          >
            {isSidebarOpen ? (
              <PanelLeftClose className="w-4 h-4 text-accent-cyan" />
            ) : (
              <PanelLeftOpen className="w-4 h-4 text-accent-cyan" />
            )}
            <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
              {isSidebarOpen ? 'Hide Watchlist' : 'Show Watchlist'}
            </span>
          </button>

          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-gradient-to-tr from-accent-blue via-accent-cyan to-accent-emerald flex items-center justify-center font-black text-white text-sm shadow-lg shadow-accent-cyan/10">
              AQ
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-slate-100 tracking-wide">AI QUANT PLATFORM</span>
                <span className="px-1.5 py-0.5 text-[9px] font-mono font-semibold bg-accent-blue/20 text-accent-cyan border border-accent-blue/30 rounded">
                  v1.3 ENTERPRISE
                </span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono hidden md:block">
                Multi-Agent DAG & Go Execution Core
              </div>
            </div>
          </div>
        </div>

        {/* Global Cross-Asset Search & Autocomplete Bar (Expanded & Prominent) */}
        <div className="flex-1 max-w-2xl mx-4">
          <HeaderSearchAutocomplete
            onSelect={async (item) => {
              try {
                await onAddSymbol(item.symbol);
              } catch (e) {
                // pass
              }
              onSelectSymbol(item.symbol);
            }}
          />
        </div>



        {/* System Health & Status Indicators */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Active Symbol Badge */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-background border border-card-border font-mono text-xs">
            <span className="text-slate-500 text-[10px]">ACTIVE:</span>
            <strong className="text-accent-cyan font-bold">{selectedSymbol}</strong>
          </div>

          {/* Pluggable Broker Venue Selector */}
          <div className="flex flex-col items-end gap-0.5 px-2.5 py-1 rounded bg-background border border-card-border font-mono text-xs">
            <div className="flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-accent-blue" />
              <span className="text-slate-400 text-[10px] hidden md:inline">BROKER:</span>
              <select
                value={activeBroker ?? ''}
                onChange={(e) => { if (e.target.value) handleBrokerChange(e.target.value); }}
                disabled={isSwitchingBroker}
                className="bg-card border border-card-border text-slate-200 text-xs rounded px-1.5 py-0.5 font-bold focus:outline-none focus:border-accent-cyan cursor-pointer disabled:opacity-60"
                title={activeBroker ? `Active venue: ${activeBroker}` : 'No authoritative broker state received from backend yet'}
              >
                <option value="" disabled>{activeBroker ? 'BROKER UNKNOWN' : 'UNKNOWN'}</option>
                <option value="webull-main">Webull (Main)</option>
                <option value="alpaca-paper">Alpaca Paper</option>
                <option value="paper-simulation">Paper Sim</option>
              </select>
            </div>
            <div className="text-[9px] leading-none">
              {isSwitchingBroker ? (
                <span className="text-accent-amber font-semibold">SWITCHING...</span>
              ) : activeBroker ? (
                <span className="text-slate-500">{activeBroker.toUpperCase()}</span>
              ) : (
                <span className="text-slate-500">LOADING / UNKNOWN</span>
              )}
              {brokerSwitchError && (
                <span className="text-accent-rose font-semibold block max-w-[180px] truncate" title={brokerSwitchError}>
                  {brokerSwitchError}
                </span>
              )}
            </div>
          </div>

          {/* Emergency Kill Switch / Freeze State */}
          <button
            onClick={async () => {
              try {
                if (status?.go_engine?.is_frozen) {
                  await api.disengageKillSwitch('Operator header toggle unfreeze', 'operator');
                } else {
                  await api.engageKillSwitch('Operator header emergency kill', 'operator');
                }
                onRefresh();
              } catch (e) {
                console.error('Kill switch toggle failed:', e);
              }
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-mono text-xs font-bold transition cursor-pointer border ${
              status?.go_engine?.is_frozen
                ? 'bg-accent-rose/20 text-accent-rose border-accent-rose/40 animate-pulse hover:bg-accent-rose/30'
                : 'bg-accent-emerald/10 text-accent-emerald border-accent-emerald/30 hover:bg-accent-rose/10 hover:text-accent-rose hover:border-accent-rose/30'
            }`}
            title={status?.go_engine?.is_frozen ? 'Click to RESUME execution' : 'Click to ENGAGE Emergency Kill Switch'}
          >
            <ShieldAlert className={`w-3.5 h-3.5 ${status?.go_engine?.is_frozen ? 'text-accent-rose animate-bounce' : 'text-accent-emerald'}`} />
            <span className="hidden sm:inline">KILL SWITCH:</span>
            <span>{status?.go_engine?.is_frozen ? 'FROZEN' : 'ACTIVE'}</span>
          </button>

          {/* Engine Status */}
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded bg-background border border-card-border font-mono text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                status?.go_engine?.status === 'online'
                  ? 'bg-accent-emerald'
                  : status?.go_engine?.status === 'offline'
                  ? 'bg-accent-rose'
                  : 'bg-slate-500'
              }`}
            ></span>
            <span className="text-slate-300">GO ENGINE:</span>
            <span
              className={`font-bold ${
                status?.go_engine?.status === 'online'
                  ? 'text-accent-emerald'
                  : status?.go_engine?.status === 'offline'
                  ? 'text-accent-rose'
                  : 'text-slate-400'
              }`}
            >
              {status?.go_engine?.status === 'online'
                ? 'ONLINE'
                : status?.go_engine?.status === 'offline'
                ? 'OFFLINE'
                : 'UNKNOWN'}
            </span>
          </div>


          {/* Clock */}
          <div className="hidden xl:flex items-center gap-1.5 text-slate-400 text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>{time}</span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-background hover:bg-card-border border border-card-border text-slate-300 hover:text-white transition cursor-pointer"
            title="Refresh Platform State"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-accent-cyan' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};

