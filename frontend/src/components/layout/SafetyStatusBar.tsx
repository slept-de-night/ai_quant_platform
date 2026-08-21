import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Radio,
  RefreshCw,
  OctagonAlert,
  Database,
  Cpu,
  CheckCircle2,
} from 'lucide-react';
import { ReadinessReport } from '../../types';
import { UnfreezeModal } from './UnfreezeModal';
import { api } from '../../services/api';

interface SafetyStatusBarProps {
  readiness: ReadinessReport | null;
  onRefresh: () => void;
}

export const SafetyStatusBar: React.FC<SafetyStatusBarProps> = ({ readiness, onRefresh }) => {
  const [isUnfreezeOpen, setIsUnfreezeOpen] = useState(false);
  const [isKilling, setIsKilling] = useState(false);
  const [showBlockingDetails, setShowBlockingDetails] = useState(false);

  const handleQuickKill = async () => {
    if (!window.confirm('CRITICAL ACTION: Are you sure you want to trigger the firm-wide EMERGENCY KILL SWITCH? All pending and new order submissions will be immediately blocked.')) {
      return;
    }
    try {
      setIsKilling(true);
      await api.engageKillSwitch('Emergency Kill Switch triggered from Global Safety Status Bar', 'operator');
      onRefresh();
    } catch (err) {
      console.error('Kill switch failed:', err);
    } finally {
      setIsKilling(false);
    }
  };

  const isFrozen = readiness?.is_frozen ?? true;
  const tradingReadiness = readiness?.trading_readiness || 'UNKNOWN';
  const activeBroker = readiness?.active_broker || 'none';
  const brokerConnected = readiness?.broker_connected ?? false;
  const execMode = readiness?.execution_mode || 'SIMULATION';
  const reconStatus = readiness?.reconciliation?.status || 'UNKNOWN';
  const isReconFresh = readiness?.reconciliation?.is_fresh ?? false;
  const blockingReasons = readiness?.blocking_reasons || [];
  const marketStatus = readiness?.market_data?.status || 'UNAVAILABLE';

  // Badge Color Mappings
  const getReadinessBadge = () => {
    switch (tradingReadiness) {
      case 'READY':
        return {
          bg: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
          icon: <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />,
          label: 'EXECUTION READY',
        };
      case 'FROZEN':
        return {
          bg: 'bg-rose-500/15 border-rose-500/30 text-rose-400',
          icon: <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />,
          label: 'ENGINE FROZEN',
        };
      case 'NOT_READY':
        return {
          bg: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
          icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
          label: 'NOT READY',
        };
      default:
        return {
          bg: 'bg-slate-500/15 border-slate-500/30 text-slate-400',
          icon: <Radio className="w-3.5 h-3.5 text-slate-400" />,
          label: 'OFFLINE / UNKNOWN',
        };
    }
  };

  const badge = getReadinessBadge();

  return (
    <>
      <div className="flex flex-col select-none z-20 border-b border-card-border bg-terminal">
        {/* Prominent Emergency Frozen Banner */}
        {isFrozen && (
          <div className="bg-rose-950/80 border-b border-rose-600/40 px-4 py-2 flex items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-2 text-rose-200">
              <OctagonAlert className="w-4 h-4 text-rose-400 animate-pulse shrink-0" />
              <span className="font-bold tracking-wide uppercase text-rose-300">
                Operational Gate Triggered:
              </span>
              <span className="font-mono text-rose-100 truncate max-w-xl">
                {readiness?.freeze_reason || 'Order execution is halted by emergency kill switch or reconciliation discrepancy.'}
              </span>
            </div>
            <button
              onClick={() => setIsUnfreezeOpen(true)}
              className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-bold tracking-wider text-[11px] uppercase transition shadow-md shadow-rose-900/40 cursor-pointer shrink-0"
            >
              Review Safety Gates & Unfreeze
            </button>
          </div>
        )}

        {/* Global Safety Status Ribbon */}
        <div className="flex items-center justify-between px-4 py-1.5 bg-card/40 backdrop-blur text-xs gap-4 overflow-x-auto scrollbar-none">
          {/* Left Subsystems Group */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Engine Readiness Badge */}
            <div
              onClick={() => blockingReasons.length > 0 && setShowBlockingDetails(!showBlockingDetails)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border font-mono font-bold text-[11px] cursor-pointer transition ${badge.bg}`}
              title={blockingReasons.length > 0 ? `Blocking reasons: ${blockingReasons.join(', ')}` : 'System readiness normal'}
            >
              {badge.icon}
              <span>{badge.label}</span>
              {blockingReasons.length > 0 && (
                <span className="ml-1 px-1 rounded bg-amber-400/20 text-amber-300 text-[10px]">
                  {blockingReasons.length}
                </span>
              )}
            </div>

            {/* Active Execution Broker */}
            <div className="flex items-center gap-2 font-mono text-[11px] px-2 py-0.5 rounded bg-card-border/30 border border-card-border/60">
              <Cpu className="w-3.5 h-3.5 text-accent-cyan" />
              <span className="text-slate-400">Broker:</span>
              <span className="text-slate-200 font-semibold">{activeBroker}</span>
              <span className="px-1.5 py-0.2 rounded bg-accent-cyan/15 text-accent-cyan text-[10px] font-bold uppercase">
                {execMode}
              </span>
              <span
                className={`w-2 h-2 rounded-full ${
                  brokerConnected ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-slate-500'
                }`}
                title={brokerConnected ? 'Broker Connected' : 'Broker Unconfigured or Disconnected'}
              />
            </div>

            {/* Reconciliation Evidence */}
            <div className="flex items-center gap-2 font-mono text-[11px] px-2 py-0.5 rounded bg-card-border/30 border border-card-border/60">
              <Database className="w-3.5 h-3.5 text-accent-cyan" />
              <span className="text-slate-400">Recon:</span>
              <span
                className={`font-semibold ${
                  reconStatus === 'CLEAN' && isReconFresh
                    ? 'text-emerald-400'
                    : reconStatus === 'UNKNOWN'
                    ? 'text-slate-400'
                    : 'text-amber-400'
                }`}
              >
                {reconStatus}
              </span>
              {readiness?.reconciliation?.last_run_at && (
                <span className="text-[10px] text-slate-500">
                  {isReconFresh ? '(Fresh)' : '(Stale)'}
                </span>
              )}
            </div>

            {/* Market Data Feed Integrity */}
            <div className="flex items-center gap-1.5 font-mono text-[11px] px-2 py-0.5 rounded bg-card-border/30 border border-card-border/60">
              <Radio className="w-3.5 h-3.5 text-accent-cyan" />
              <span className="text-slate-400">Feed:</span>
              <span
                className={`font-semibold text-[10px] uppercase ${
                  marketStatus === 'LIVE'
                    ? 'text-emerald-400'
                    : marketStatus === 'DEMO'
                    ? 'text-accent-cyan'
                    : 'text-slate-500'
                }`}
              >
                {marketStatus}
              </span>
            </div>
          </div>

          {/* Right Action Controls */}
          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={onRefresh}
              className="p-1 rounded bg-card-border/30 hover:bg-card-border text-slate-400 hover:text-white transition cursor-pointer"
              title="Refresh Global Readiness"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>

            {isFrozen ? (
              <button
                onClick={() => setIsUnfreezeOpen(true)}
                className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shadow-sm shadow-emerald-500/20"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-slate-950" />
                <span>Unfreeze OMS</span>
              </button>
            ) : (
              <button
                onClick={handleQuickKill}
                disabled={isKilling}
                className="px-3 py-1 rounded bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 text-rose-300 hover:text-rose-100 font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
              >
                <OctagonAlert className="w-3.5 h-3.5 text-rose-400" />
                <span>{isKilling ? 'Freezing...' : 'Engage Kill Switch'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Expandable Blocking Reasons Popover */}
        {showBlockingDetails && blockingReasons.length > 0 && (
          <div className="bg-amber-950/40 border-t border-amber-500/30 px-4 py-2 flex items-center justify-between text-xs text-amber-200">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span className="font-bold">Active Safety Gate Failures:</span>
              <span className="font-mono text-amber-300">{blockingReasons.join(' | ')}</span>
            </div>
            <button
              onClick={() => setShowBlockingDetails(false)}
              className="text-amber-400 hover:text-amber-100 font-bold text-[11px] underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      <UnfreezeModal
        isOpen={isUnfreezeOpen}
        onClose={() => setIsUnfreezeOpen(false)}
        readiness={readiness}
        onSuccess={onRefresh}
      />
    </>
  );
};
