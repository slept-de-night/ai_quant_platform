import React, { useEffect, useState } from 'react';
import { PlatformStatus, StrategyItem, InstitutionalRiskMetrics } from '../../types';
import { api } from '../../services/api';
import {
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Zap,
  Activity,
  Layers,
  Cpu,
  ArrowUpRight,
  Clock
} from 'lucide-react';

interface DashboardViewProps {
  status: PlatformStatus | null;
  strategies: StrategyItem[];
  selectedSymbol: string;
  onNavigateTab: (tab: any) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  status,
  strategies,
  selectedSymbol,
  onNavigateTab,
}) => {
  const [riskMetrics, setRiskMetrics] = useState<InstitutionalRiskMetrics | null>(null);
  const [isLoadingRisk, setIsLoadingRisk] = useState(false);

  useEffect(() => {
    const fetchRisk = async () => {
      setIsLoadingRisk(true);
      try {
        const res = await api.getRiskMetrics(selectedSymbol);
        setRiskMetrics(res);
      } catch (err) {
        console.error('Failed to load risk metrics:', err);
      } finally {
        setIsLoadingRisk(false);
      }
    };
    fetchRisk();
  }, [selectedSymbol]);

  const validatedCount = strategies.filter((s) => s.status === 'VALIDATED' || s.status === 'APPROVED').length;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Top Banner: Institutional Fund Overview */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between p-5 rounded-xl bg-gradient-to-r from-card via-[#131d36] to-card border border-card-border shadow-lg gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/40 rounded">
              PORTFOLIO DESK
            </span>
            <span className="text-xs text-slate-400 font-mono">Active Symbol: <strong className="text-white">{selectedSymbol}</strong></span>
          </div>
          <h1 className="text-xl font-bold text-slate-100 mt-1">
            Institutional Quantitative Intelligence & Execution Platform
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Durable multi-agent DAG research mesh coupled with sub-millisecond Go deterministic risk engine.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigateTab('alpha')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-blue hover:bg-blue-600 text-white text-xs font-semibold shadow-md shadow-accent-blue/20 transition cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Launch Alpha Studio</span>
          </button>
          <button
            onClick={() => onNavigateTab('intelligence')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-card-border hover:bg-slate-700 text-slate-200 text-xs font-semibold transition cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5 text-accent-cyan" />
            <span>Run Deep Research</span>
          </button>
        </div>
      </div>

      {/* High-Level Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Fund Equity */}
        <div className="p-4 rounded-xl bg-card border border-card-border relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Fund Starting Equity</span>
            <DollarSignIcon className="w-4 h-4 text-accent-emerald" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-100">
            ${(status?.risk_limits.starting_equity || 100000).toLocaleString()}
          </div>
          <div className="mt-1 flex items-center gap-1 text-[11px] text-accent-emerald font-mono">
            <TrendingUp className="w-3 h-3" />
            <span>Max Position: {( (status?.risk_limits.max_position_pct || 0.08) * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Card 2: Institutional 1-Day VaR (95%) */}
        <div className="p-4 rounded-xl bg-card border border-card-border">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>1-Day Parametric VaR (95%)</span>
            <ShieldCheck className="w-4 h-4 text-accent-cyan" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-accent-cyan">
            {isLoadingRisk ? '...' : `$${(riskMetrics?.var_95_usd || 1850).toLocaleString()}`}
          </div>
          <div className="mt-1 text-[11px] text-slate-400 font-mono">
            Expected Shortfall (cVaR): ${isLoadingRisk ? '...' : (riskMetrics?.cvar_95_usd || 2450).toLocaleString()}
          </div>
        </div>

        {/* Card 3: Active Strategies */}
        <div className="p-4 rounded-xl bg-card border border-card-border">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Validated Alpha Models</span>
            <Layers className="w-4 h-4 text-accent-purple" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-100">
            {validatedCount} <span className="text-xs text-slate-400 font-normal">/ {strategies.length} Candidate</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-400 font-mono">
            Annualized Volatility: {isLoadingRisk ? '...' : `${((riskMetrics?.annualized_volatility || 0.16) * 100).toFixed(1)}%`}
          </div>
        </div>

        {/* Card 4: Execution Core Status */}
        <div className="p-4 rounded-xl bg-card border border-card-border">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>OMS / EMS Execution Core</span>
            <Cpu className="w-4 h-4 text-accent-amber" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-emerald opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-accent-emerald"></span>
            </span>
            <span className="text-xl font-bold font-mono text-slate-100">
              {status?.go_engine?.status === 'healthy' ? 'Go Microsecond' : 'Active (Python)'}
            </span>
          </div>
          <div className="mt-1 text-[11px] text-slate-400 font-mono">
            Mode: Paper Broker Safe | Uptime: {status?.go_engine?.uptime_seconds ? `${Math.floor(status.go_engine.uptime_seconds)}s` : 'Active'}
          </div>
        </div>
      </div>

      {/* Main Grid: Strategy Registry & Risk Parameters */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Institutional Alpha Strategies Registry */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-card border border-card-border flex flex-col">
          <div className="flex items-center justify-between pb-4 border-b border-card-border">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-accent-cyan" />
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">Strategy Registry & Validation</h2>
            </div>
            <button
              onClick={() => onNavigateTab('alpha')}
              className="text-xs text-accent-cyan hover:underline flex items-center gap-1 font-mono"
            >
              <span>Explore All Alpha Models</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="mt-4 divide-y divide-card-border/50 flex-1">
            {strategies.map((strat) => (
              <div key={strat.name} className="py-3 flex items-center justify-between hover:bg-background/40 px-2 rounded transition">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs text-slate-100">{strat.name}</span>
                    <span
                      className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${
                        strat.status === 'APPROVED'
                          ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40'
                          : strat.status === 'VALIDATED'
                          ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/40'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {strat.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {strat.spec?.description || 'Algorithmic strategy specification'}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right font-mono text-xs">
                    <div className="text-slate-300">Target Horizon</div>
                    <div className="text-slate-400 text-[11px]">{strat.spec?.target_holding_days || 20} Days</div>
                  </div>

                  <button
                    onClick={() => onNavigateTab('alpha')}
                    className="px-3 py-1 bg-background hover:bg-card-border border border-card-border rounded text-xs font-semibold text-slate-200 transition cursor-pointer"
                  >
                    Backtest
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right 1 Col: Pre-Trade Hard Risk Limits */}
        <div className="p-5 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-4 border-b border-card-border">
              <ShieldCheck className="w-4 h-4 text-accent-emerald" />
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">Pre-Trade Risk Gates</h2>
            </div>

            <div className="mt-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between p-2.5 rounded bg-background/80 border border-card-border">
                <span className="text-slate-400">Max Single Position:</span>
                <span className="font-bold text-slate-200">{((status?.risk_limits.max_position_pct || 0.08) * 100).toFixed(0)}% of Equity</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-background/80 border border-card-border">
                <span className="text-slate-400">Gross Exposure Cap:</span>
                <span className="font-bold text-slate-200">{((status?.risk_limits.max_gross_exposure_pct || 0.60) * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-background/80 border border-card-border">
                <span className="text-slate-400">Min Cash Reserve:</span>
                <span className="font-bold text-slate-200">{((status?.risk_limits.min_cash_reserve_pct || 0.10) * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-background/80 border border-card-border">
                <span className="text-slate-400">Daily Loss Kill Switch:</span>
                <span className="font-bold text-accent-rose">-{((status?.risk_limits.max_daily_loss_pct || 0.02) * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2.5 rounded bg-background/80 border border-card-border">
                <span className="text-slate-400">Max Drawdown Breaker:</span>
                <span className="font-bold text-accent-rose">-{((status?.risk_limits.max_drawdown_pct || 0.10) * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          <div className="mt-5 p-3 rounded bg-accent-blue/10 border border-accent-blue/20 text-[11px] text-slate-300">
            <div className="flex items-center gap-1.5 font-bold text-accent-cyan mb-1">
              <Clock className="w-3.5 h-3.5" />
              <span>Institutional Governance</span>
            </div>
            All orders pass deterministic pre-trade evaluation in sub-millisecond memory before broker submission.
          </div>
        </div>
      </div>
    </div>
  );
};

const DollarSignIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="12" y1="1" x2="12" y2="23"></line>
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
  </svg>
);
