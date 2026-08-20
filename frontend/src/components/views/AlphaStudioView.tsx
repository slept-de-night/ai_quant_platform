import React, { useEffect, useState } from 'react';
import { StrategyItem, BacktestResponse, ValidationReport, AlphaSearchCandidate } from '../../types';
import { api } from '../../services/api';
import { TradingViewChart } from '../charts/TradingViewChart';
import { EquityChart } from '../charts/EquityChart';
import {
  LineChart,
  Play,
  CheckCircle2,
  AlertTriangle,
  Zap,
  TrendingUp,
  RotateCcw,
  Sparkles,
  ShieldCheck,
  Award
} from 'lucide-react';

interface AlphaStudioViewProps {
  selectedSymbol: string;
  strategies: StrategyItem[];
  onRefreshStrategies: () => void;
}

export const AlphaStudioView: React.FC<AlphaStudioViewProps> = ({
  selectedSymbol,
  strategies,
  onRefreshStrategies,
}) => {
  const [selectedStrategy, setSelectedStrategy] = useState<string>('trend_momentum');
  const [chartData, setChartData] = useState<any[]>([]);
  const [backtestResult, setBacktestResult] = useState<BacktestResponse | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationReport | null>(null);
  const [alphaCandidates, setAlphaCandidates] = useState<AlphaSearchCandidate[]>([]);

  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isSearchingAlpha, setIsSearchingAlpha] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch Market Candlestick Data
  useEffect(() => {
    const fetchCandles = async () => {
      setIsLoadingChart(true);
      try {
        const res = await api.getChartData(selectedSymbol, '1Y');
        if (res?.bars) {
          setChartData(res.bars);
        }
      } catch (err) {
        console.error('Failed to load chart data:', err);
      } finally {
        setIsLoadingChart(false);
      }
    };
    fetchCandles();
  }, [selectedSymbol]);

  // Run Backtest
  const handleRunBacktest = async () => {
    setIsBacktesting(true);
    setError(null);
    try {
      const res = await api.runBacktest(selectedSymbol, selectedStrategy, 1600);
      setBacktestResult(res);
    } catch (err: any) {
      setError(err.message || 'Backtest failed');
    } finally {
      setIsBacktesting(false);
    }
  };

  // Run Walk-Forward Validation
  const handleRunValidation = async () => {
    setIsValidating(true);
    setError(null);
    try {
      const res = await api.runValidation(selectedSymbol, selectedStrategy, 1800);
      setValidationResult(res);
      onRefreshStrategies();
    } catch (err: any) {
      setError(err.message || 'Validation failed');
    } finally {
      setIsValidating(false);
    }
  };

  // Run Alpha Factory Search
  const handleRunAlphaSearch = async () => {
    setIsSearchingAlpha(true);
    setError(null);
    try {
      const res = await api.runAlphaSearch(selectedSymbol, 4, 1800);
      setAlphaCandidates(res);
      onRefreshStrategies();
    } catch (err: any) {
      setError(err.message || 'Alpha search failed');
    } finally {
      setIsSearchingAlpha(false);
    }
  };

  // Maker-Checker Strategy Approval
  const handleApproveStrategy = async (name: string) => {
    try {
      await api.approveStrategy(name);
      onRefreshStrategies();
    } catch (err: any) {
      setError(err.message || 'Strategy approval failed');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Control Action Bar */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 rounded">
              QUANT STUDIO
            </span>
            <span className="text-xs text-slate-400 font-mono">Symbol: <strong className="text-accent-cyan font-bold">{selectedSymbol}</strong></span>
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Algorithmic Alpha Research, Backtesting & Walk-Forward Validation
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Strategy Dropdown */}
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

          {/* Action 1: Backtest */}
          <button
            onClick={handleRunBacktest}
            disabled={isBacktesting}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-accent-blue hover:bg-blue-600 text-white rounded text-xs font-semibold shadow-sm transition cursor-pointer disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isBacktesting ? 'Simulating...' : 'Run Backtest'}</span>
          </button>

          {/* Action 2: Walk-Forward Validate */}
          <button
            onClick={handleRunValidation}
            disabled={isValidating}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-accent-cyan hover:bg-cyan-500 text-slate-950 rounded text-xs font-bold shadow-sm transition cursor-pointer disabled:opacity-50"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{isValidating ? 'Purging Folds...' : 'Walk-Forward Validate'}</span>
          </button>

          {/* Action 3: Alpha Factory Search */}
          <button
            onClick={handleRunAlphaSearch}
            disabled={isSearchingAlpha}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-accent-purple hover:bg-purple-600 text-white rounded text-xs font-semibold shadow-sm transition cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{isSearchingAlpha ? 'Searching Alphas...' : 'Alpha Factory'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-xs font-mono">
          {error}
        </div>
      )}

      {/* Candlestick Market Chart */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <div className="flex items-center justify-between pb-3 border-b border-card-border mb-3">
          <div className="flex items-center gap-2">
            <LineChart className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Market Price Action (TradingView Canvas)
            </h2>
          </div>
          <span className="text-[10px] font-mono text-slate-400">1-Year Daily OHLCV</span>
        </div>
        <TradingViewChart data={chartData} symbol={selectedSymbol} height={380} />
      </div>

      {/* Backtest & Equity Curve Results */}
      {backtestResult && (
        <div className="p-5 rounded-xl bg-card border border-card-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-accent-emerald" />
              <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
                Backtest Performance: {backtestResult.strategy}
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              {backtestResult.daily.length} Trading Days
            </span>
          </div>

          {/* Metric Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Total Return</div>
              <div className="text-sm font-bold text-accent-emerald mt-1">
                {(backtestResult.metrics.total_return * 100).toFixed(1)}%
              </div>
            </div>

            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Sharpe Ratio</div>
              <div className="text-sm font-bold text-accent-cyan mt-1">
                {backtestResult.metrics.sharpe_ratio.toFixed(2)}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Sortino Ratio</div>
              <div className="text-sm font-bold text-slate-200 mt-1">
                {backtestResult.metrics.sortino_ratio.toFixed(2)}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Max Drawdown</div>
              <div className="text-sm font-bold text-accent-rose mt-1">
                -{(backtestResult.metrics.max_drawdown * 100).toFixed(1)}%
              </div>
            </div>

            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Win Rate</div>
              <div className="text-sm font-bold text-slate-200 mt-1">
                {(backtestResult.metrics.win_rate * 100).toFixed(0)}%
              </div>
            </div>

            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Total Trades</div>
              <div className="text-sm font-bold text-slate-200 mt-1">
                {backtestResult.metrics.trades_count}
              </div>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <EquityChart
            daily={backtestResult.daily}
            strategyName={backtestResult.strategy}
            symbol={selectedSymbol}
            height={320}
          />
        </div>
      )}

      {/* Walk-Forward Validation Report */}
      {validationResult && (
        <div className="p-5 rounded-xl bg-card border border-card-border">
          <div className="flex items-center justify-between pb-3 border-b border-card-border mb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-accent-cyan" />
              <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
                Purged Walk-Forward Cross-Validation Report
              </h2>
            </div>
            <span className={`px-2 py-0.5 text-xs font-mono font-bold rounded ${
              validationResult.passed ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-rose/20 text-accent-rose'
            }`}>
              {validationResult.passed ? 'PASSED ROBUSTNESS GATE' : 'FAILED ROBUSTNESS'}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Folds Evaluated</div>
              <div className="text-sm font-bold text-slate-200 mt-1">{validationResult.folds_evaluated} Folds</div>
            </div>
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Avg Train Sharpe</div>
              <div className="text-sm font-bold text-slate-200 mt-1">{validationResult.avg_train_sharpe.toFixed(2)}</div>
            </div>
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Avg Out-of-Sample Sharpe</div>
              <div className="text-sm font-bold text-accent-cyan mt-1">{validationResult.avg_test_sharpe.toFixed(2)}</div>
            </div>
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <div className="text-[10px] text-slate-400">Robustness Score</div>
              <div className="text-sm font-bold text-accent-emerald mt-1">{validationResult.robust_score.toFixed(2)}</div>
            </div>
          </div>

          {validationResult.passed && (
            <div className="mt-4 flex items-center justify-between p-3 rounded-lg bg-accent-emerald/10 border border-accent-emerald/30">
              <span className="text-xs text-slate-200">
                Strategy meets institutional standards. Approve to promote to Paper Execution.
              </span>
              <button
                onClick={() => handleApproveStrategy(validationResult.strategy_name)}
                className="px-3 py-1.5 bg-accent-emerald hover:bg-emerald-600 text-slate-950 font-bold rounded text-xs transition cursor-pointer"
              >
                Maker-Checker Approve
              </button>
            </div>
          )}
        </div>
      )}

      {/* Alpha Search Candidates */}
      {alphaCandidates.length > 0 && (
        <div className="p-5 rounded-xl bg-card border border-card-border">
          <div className="flex items-center gap-2 pb-3 border-b border-card-border mb-3">
            <Sparkles className="w-4 h-4 text-accent-purple" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Alpha Factory Genetic Candidates
            </h2>
          </div>

          <div className="space-y-3">
            {alphaCandidates.map((cand, idx) => (
              <div key={idx} className="p-3.5 rounded-lg bg-background border border-card-border flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs text-slate-100">{cand.strategy.name}</span>
                    <span className={`px-1.5 py-0.2 text-[9px] font-bold rounded ${
                      cand.passed ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {cand.passed ? 'VALIDATED' : 'CANDIDATE'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {cand.strategy.description}
                  </div>
                </div>

                {cand.passed && (
                  <button
                    onClick={() => handleApproveStrategy(cand.strategy.name)}
                    className="px-3 py-1 bg-accent-cyan hover:bg-cyan-500 text-slate-950 rounded text-xs font-bold transition cursor-pointer"
                  >
                    Approve
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
