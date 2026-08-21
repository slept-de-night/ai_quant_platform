import React, { useEffect, useState } from 'react';
import { StrategyItem, BrokerHealthSummary, ReconciliationReport } from '../../types';
import { api } from '../../services/api';
import {
  ShieldCheck,
  Play,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Zap,
  TrendingUp,
  Cpu,
  Lock,
  RefreshCw,
  Power,
  Server,
  Activity,
  Layers
} from 'lucide-react';

interface PaperTradingDeskViewProps {
  selectedSymbol: string;
  strategies: StrategyItem[];
}

export const PaperTradingDeskView: React.FC<PaperTradingDeskViewProps> = ({
  selectedSymbol,
  strategies,
}) => {
  const [selectedStrategy, setSelectedStrategy] = useState<string>('trend_momentum');
  const [cycleData, setCycleData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Broker & Reconciliation Operational State
  const [brokerHealth, setBrokerHealth] = useState<BrokerHealthSummary | null>(null);
  const [reconciliation, setReconciliation] = useState<ReconciliationReport | null>(null);
  const [isReconciling, setIsReconciling] = useState(false);
  const [isTogglingKill, setIsTogglingKill] = useState(false);

  const fetchCycle = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [cycleRes, healthRes] = await Promise.all([
        api.getPaperCycle(selectedSymbol, selectedStrategy),
        api.getBrokerHealth().catch(() => null),
      ]);
      setCycleData(cycleRes);
      if (healthRes) setBrokerHealth(healthRes);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch paper trading cycle');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCycle();
  }, [selectedSymbol, selectedStrategy]);

  const handleExecuteOrder = async () => {
    setIsExecuting(true);
    setError(null);
    try {
      const res = await api.executePaperOrder(selectedSymbol, selectedStrategy);
      setExecutionResult(res);
      await fetchCycle();
    } catch (err: any) {
      setError(err.message || 'Failed to submit paper order');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleRunReconciliation = async () => {
    setIsReconciling(true);
    try {
      const res = await api.runReconciliation();
      setReconciliation(res);
      await fetchCycle();
    } catch (err: any) {
      setError(err.message || 'Reconciliation run failed');
    } finally {
      setIsReconciling(false);
    }
  };

  const handleBrokerSwitch = async (name: string) => {
    try {
      await api.selectBroker(name);
      await fetchCycle();
    } catch (err: any) {
      setError(err.message || 'Failed to switch broker');
    }
  };

  const handleToggleKillSwitch = async () => {
    setIsTogglingKill(true);
    try {
      if (cycleData?.portfolio?.is_frozen) {
        await api.disengageKillSwitch('Operator trading desk unfreeze', 'operator');
      } else {
        await api.engageKillSwitch('Operator trading desk emergency kill', 'operator');
      }
      await fetchCycle();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle kill switch');
    } finally {
      setIsTogglingKill(false);
    }
  };

  const isFrozen = cycleData?.portfolio?.is_frozen || false;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded">
              EXECUTION DESK
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Broker: <strong className="text-white">{brokerHealth?.active_broker || 'Paper Sim / Go Core'}</strong>
            </span>
            {isFrozen ? (
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-rose/20 text-accent-rose border border-accent-rose/40 rounded animate-pulse">
                OMS FROZEN
              </span>
            ) : (
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 rounded">
                OMS READY
              </span>
            )}
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Pre-Trade Hard Risk Evaluation & Paper Blotter
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value)}
            className="bg-background border border-card-border rounded px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-accent-cyan transition cursor-pointer"
          >
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} ({s.status})
              </option>
            ))}
          </select>

          <button
            onClick={fetchCycle}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-background hover:bg-card-border border border-card-border text-slate-200 rounded text-xs font-semibold transition cursor-pointer"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Evaluate Cycle</span>
          </button>
        </div>
      </div>

      {/* Freeze / Kill Switch Emergency Alert Banner */}
      {isFrozen && (
        <div className="p-4 rounded-xl bg-accent-rose/15 border border-accent-rose/40 flex items-center justify-between gap-4 text-xs font-mono text-accent-rose">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <div>
              <div className="font-bold">ENGINE FROZEN IN RECONCILIATION / KILL-SWITCH SAFETY STATE</div>
              <div className="text-[11px] text-slate-300 mt-0.5">
                All automated order submissions are blocked. Read-only risk checks and reconciliations remain available.
              </div>
            </div>
          </div>
          <button
            onClick={handleToggleKillSwitch}
            disabled={isTogglingKill}
            className="px-4 py-2 bg-accent-rose hover:bg-rose-600 text-white font-bold rounded text-xs transition cursor-pointer flex-shrink-0"
          >
            {isTogglingKill ? 'Processing...' : 'Manual Unfreeze'}
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-xs font-mono">
          {error}
        </div>
      )}

      {/* Operational Controls: Broker Selector, Health Diagnostics, and Reconciliation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pluggable Broker Management */}
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-accent-cyan" />
              <span className="font-bold text-slate-100 uppercase">Execution Broker</span>
            </div>
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
              brokerHealth?.ready ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-amber/20 text-accent-amber'
            }`}>
              {brokerHealth?.ready ? 'CONNECTED' : 'OFFLINE'}
            </span>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] text-slate-400">Select Active Execution Adapter</label>
            <select
              value={brokerHealth?.active_broker || 'paper-simulation'}
              onChange={(e) => handleBrokerSwitch(e.target.value)}
              className="w-full bg-background border border-card-border rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-accent-cyan cursor-pointer"
            >
              {brokerHealth?.all_registered_brokers?.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name} ({b.environment.toUpperCase()}) {b.ready ? '● Ready' : '○ Standby'}
                </option>
              )) || <option value="paper-simulation">paper-simulation (SIMULATION)</option>}
            </select>
          </div>

          <div className="p-3 rounded bg-background border border-card-border space-y-1 text-[11px]">
            <div className="flex justify-between text-slate-400">
              <span>Environment</span>
              <span className="text-slate-200 font-bold">{brokerHealth?.environment?.toUpperCase() || 'SIMULATION'}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Adapter Status</span>
              <span className="text-slate-200">{brokerHealth?.message || 'Ready'}</span>
            </div>
          </div>
        </div>

        {/* Real Broker Reconciliation Gate */}
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-accent-amber" />
              <span className="font-bold text-slate-100 uppercase">State Reconciliation</span>
            </div>
            <button
              onClick={handleRunReconciliation}
              disabled={isReconciling}
              className="px-2.5 py-1 bg-accent-amber/20 hover:bg-accent-amber/30 text-accent-amber border border-accent-amber/40 rounded text-[10px] font-bold transition cursor-pointer"
            >
              {isReconciling ? 'Reconciling...' : 'Run Audit'}
            </button>
          </div>

          <div className="p-3 rounded bg-background border border-card-border space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Discrepancy Count:</span>
              <span className={`font-bold ${
                reconciliation?.total_count ? 'text-accent-rose' : 'text-accent-emerald'
              }`}>
                {reconciliation?.total_count || 0} Total ({reconciliation?.critical_count || 0} Critical)
              </span>
            </div>
            <div className="flex justify-between items-center text-[10px] text-slate-400">
              <span>Audit Status:</span>
              <span className="text-slate-300">
                {reconciliation?.has_critical ? 'CRITICAL DISCREPANCY DETECTED' : 'LEDGER MATCHES BROKER'}
              </span>
            </div>
          </div>

          {reconciliation?.discrepancies && reconciliation.discrepancies.length > 0 && (
            <div className="max-h-24 overflow-y-auto space-y-1 text-[10px]">
              {reconciliation.discrepancies.slice(0, 3).map((d, i) => (
                <div key={i} className="p-1.5 rounded bg-accent-rose/10 border border-accent-rose/30 text-accent-rose">
                  [{d.severity}] {d.type} {d.symbol}: {d.message}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Firm-Wide Emergency Controls */}
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-4 font-mono text-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-card-border mb-3">
              <div className="flex items-center gap-2">
                <Power className="w-4 h-4 text-accent-rose" />
                <span className="font-bold text-slate-100 uppercase">Emergency Control</span>
              </div>
              <Lock className="w-4 h-4 text-slate-400" />
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
              Immediate firm-wide kill switch disables order routing and isolates open exposure without liquidating confirmed fills.
            </p>
          </div>

          <button
            onClick={handleToggleKillSwitch}
            disabled={isTogglingKill}
            className={`w-full py-2.5 rounded font-bold transition cursor-pointer shadow-md ${
              isFrozen
                ? 'bg-accent-emerald hover:bg-emerald-600 text-slate-950'
                : 'bg-accent-rose hover:bg-rose-600 text-white'
            }`}
          >
            {isTogglingKill ? 'Processing...' : isFrozen ? 'Disengage Kill Switch' : 'Engage Firm Kill Switch'}
          </button>
        </div>
      </div>

      {/* Grid: Signal State, Risk Decision, and Execution Confirmation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signal Generation */}
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <span className="font-bold text-slate-100 uppercase">Quant Signal State</span>
            <span className="text-[10px] text-accent-cyan">{selectedSymbol}</span>
          </div>

          <div className="p-3 rounded bg-background border border-card-border">
            <div className="text-[10px] text-slate-400">Directional Side</div>
            <div className={`text-base font-bold mt-0.5 ${
              cycleData?.signal?.side === 'BUY' ? 'text-accent-emerald' : cycleData?.signal?.side === 'SELL' ? 'text-accent-rose' : 'text-slate-300'
            }`}>
              {cycleData?.signal?.side || 'HOLD'}
            </div>
          </div>

          <div className="p-3 rounded bg-background border border-card-border">
            <div className="text-[10px] text-slate-400">Signal Score</div>
            <div className="text-sm font-bold text-slate-100 mt-0.5">
              {cycleData?.signal?.score !== undefined ? cycleData.signal.score.toFixed(3) : '0.000'}
            </div>
          </div>

          <div className="p-3 rounded bg-background border border-card-border">
            <div className="text-[10px] text-slate-400">Reference Price</div>
            <div className="text-sm font-bold text-slate-100 mt-0.5">
              ${cycleData?.signal?.reference_price?.toFixed(2) || '0.00'}
            </div>
          </div>
        </div>

        {/* Deterministic Hard Risk Gate */}
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <span className="font-bold text-slate-100 uppercase">Pre-Trade Hard Risk Check</span>
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
              cycleData?.risk_decision?.approved ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-rose/20 text-accent-rose'
            }`}>
              {cycleData?.risk_decision?.approved ? 'RISK APPROVED' : 'GATED'}
            </span>
          </div>

          <div className="p-3 rounded bg-background border border-card-border">
            <div className="text-[10px] text-slate-400">Decision Outcome</div>
            <div className="text-slate-200 mt-1 leading-relaxed">
              {cycleData?.risk_decision?.reasons?.join(', ') || 'Evaluating risk limits...'}
            </div>
          </div>

          {cycleData?.risk_decision?.order && (
            <div className="p-3 rounded bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Risk Sized Quantity</div>
              <div className="text-sm font-bold text-accent-cyan mt-0.5">
                {cycleData.risk_decision.order.qty} Shares (${cycleData.risk_decision.order.notional?.toFixed(2) || '0.00'})
              </div>
            </div>
          )}
        </div>

        {/* Paper Execution Trigger */}
        <div className="p-5 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-card-border mb-4">
              <span className="text-xs font-bold text-slate-100 uppercase">Order Execution</span>
              <Lock className="w-4 h-4 text-accent-amber" />
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Submits paper order to {brokerHealth?.active_broker || 'Selected Broker Adapter'} only if all pre-trade risk gates are verified and OMS is unfrozen.
            </p>
          </div>

          <div className="mt-6">
            <button
              onClick={handleExecuteOrder}
              disabled={isExecuting || !cycleData?.risk_decision?.approved || isFrozen}
              className="w-full py-2.5 bg-accent-emerald hover:bg-emerald-600 text-slate-950 font-bold rounded-lg text-xs shadow-md transition cursor-pointer disabled:opacity-40"
            >
              {isExecuting ? 'Submitting Order...' : 'Submit Paper Order'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
