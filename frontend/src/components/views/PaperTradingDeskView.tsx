import React, { useEffect, useState } from 'react';
import { StrategyItem } from '../../types';
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
  Lock
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

  const fetchCycle = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getPaperCycle(selectedSymbol, selectedStrategy);
      setCycleData(res);
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

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded">
              EXECUTION DESK
            </span>
            <span className="text-xs text-slate-400 font-mono">Broker: <strong className="text-white">Alpaca Paper / Go Core</strong></span>
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

      {error && (
        <div className="p-4 rounded-xl bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-xs font-mono">
          {error}
        </div>
      )}

      {cycleData?.warning && (
        <div className="p-4 rounded-xl bg-accent-amber/10 border border-accent-amber/30 text-accent-amber text-xs font-mono">
          {cycleData.warning}
        </div>
      )}

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
                {cycleData.risk_decision.order.qty} Shares (${cycleData.risk_decision.order.notional.toFixed(2)})
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
              Submits paper order to Alpaca Paper Brokerage / Go Core OMS only if all pre-trade risk gates are verified.
            </p>
          </div>

          <div className="mt-6">
            <button
              onClick={handleExecuteOrder}
              disabled={isExecuting || !cycleData?.risk_decision?.approved}
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
