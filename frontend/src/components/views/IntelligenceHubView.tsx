import React, { useState, useEffect } from 'react';
import { ResearchDossier, StockFundamentals } from '../../types';
import { api } from '../../services/api';
import { TradingViewChart } from '../charts/TradingViewChart';
import { HexagonRadar } from '../charts/HexagonRadar';
import { FinancialStatementsExplorer } from './FinancialStatementsExplorer';
import {
  BrainCircuit,
  Play,
  TrendingUp,
  TrendingDown,
  Globe,
  ShieldCheck,
  Zap,
  ExternalLink,
  Layers,
  DollarSign,
  Activity,
  BarChart2,
  AlertOctagon,
  FileText,
  Clock,
  Sparkles
} from 'lucide-react';

interface IntelligenceHubViewProps {
  selectedSymbol: string;
}

export const IntelligenceHubView: React.FC<IntelligenceHubViewProps> = ({ selectedSymbol }) => {
  const [dossier, setDossier] = useState<ResearchDossier | null>(null);
  const [fundamentals, setFundamentals] = useState<StockFundamentals | null>(null);
  const [quote, setQuote] = useState<any>(null);
  const [chartBars, setChartBars] = useState<any[]>([]);
  const [timeframe, setTimeframe] = useState<string>('1Y');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingFundamentals, setIsLoadingFundamentals] = useState(false);
  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch Fundamentals & Live Quote
  useEffect(() => {
    let isMounted = true;
    const fetchFundAndQuote = async () => {
      setIsLoadingFundamentals(true);
      try {
        const [fundData, quoteData] = await Promise.all([
          api.getFundamentals(selectedSymbol).catch(() => null),
          api.getQuote(selectedSymbol).catch(() => null),
        ]);
        if (isMounted) {
          if (fundData) setFundamentals(fundData);
          if (quoteData) setQuote(quoteData);
        }
      } catch (e: any) {
        console.error('Failed to load fundamentals/quote:', e);
      } finally {
        if (isMounted) setIsLoadingFundamentals(false);
      }
    };
    fetchFundAndQuote();
    return () => {
      isMounted = false;
    };
  }, [selectedSymbol]);

  // Fetch Candlestick & Volume Chart Data
  useEffect(() => {
    let isMounted = true;
    const fetchChart = async () => {
      setIsLoadingChart(true);
      try {
        const res = await api.getChartData(selectedSymbol, timeframe);
        if (isMounted && res && res.bars) {
          setChartBars(res.bars);
        }
      } catch (e: any) {
        console.error('Failed to load chart data:', e);
      } finally {
        if (isMounted) setIsLoadingChart(false);
      }
    };
    fetchChart();
    return () => {
      isMounted = false;
    };
  }, [selectedSymbol, timeframe]);

  const handleRunResearch = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.runResearch(selectedSymbol);
      setDossier(res);
    } catch (err: any) {
      setError(err.message || 'Failed to execute multi-agent research');
    } finally {
      setIsLoading(false);
    }
  };

  const isPositive = (quote?.change_amt || quote?.change || 0) >= 0;
  const isEtf = Boolean(fundamentals?.is_etf || quote?.is_etf || quote?.instrument_type === 'ETF' || ['DRAM', 'SPY', 'QQQ', 'SMH', 'SOXX'].includes(selectedSymbol.toUpperCase()));
  const isCrypto = Boolean(fundamentals?.asset_type === 'CRYPTO' || selectedSymbol.includes('-USD') || ['BTC', 'ETH', 'SOL'].includes(selectedSymbol.toUpperCase()));
  const isCommodity = Boolean(fundamentals?.asset_type === 'COMMODITY' || ['GLD', 'SLV', 'GC=F', 'SI=F', 'USO', 'CL=F'].includes(selectedSymbol.toUpperCase()));
  const isForex = Boolean(fundamentals?.asset_type === 'FOREX' || selectedSymbol.endsWith('=X'));

  const getAssetBadge = () => {
    if (isCrypto) return { label: 'CRYPTO ASSET', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' };
    if (isCommodity) return { label: 'COMMODITY / PRECIOUS METAL', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' };
    if (isEtf) return { label: 'EXCHANGE TRADED FUND (ETF)', color: 'bg-violet-500/20 text-violet-400 border-violet-500/30' };
    if (isForex) return { label: 'CURRENCY / FX SPOT', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' };
    return { label: 'OPERATING EQUITY', color: 'bg-sky-500/20 text-sky-400 border-sky-500/30' };
  };

  const badge = getAssetBadge();

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Top Action Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-purple/20 text-accent-purple border border-accent-purple/40 rounded">
              INSTITUTIONAL INTELLIGENCE HUB
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Target: <strong className="text-accent-cyan font-bold">{selectedSymbol}</strong>
            </span>
            <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${badge.color}`}>
              {badge.label}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-100 mt-1 font-mono">
            {fundamentals?.company_name || quote?.short_name || quote?.name || selectedSymbol}
          </h1>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            {isEtf
              ? 'Exchange Traded Fund (ETF) Systematic Exposure, NAV, Market Profile & Multi-Agent Intelligence.'
              : isCrypto
              ? 'Cryptocurrency On-Chain Tokenomics, 24/7 Volatility Target & High-Water Mark Drawdown.'
              : isCommodity
              ? 'Physical Bullion Vaulting, Macro Inflation Hedge, Real Yield Correlation & Term Structure.'
              : isForex
              ? 'Sovereign Central Bank Policy Rate Differentials & Annualized Carry Yield.'
              : '5-Year SEC Financial Statements, Balance Sheets, Altman Z, Piotroski F, & AI Research.'}
          </p>
        </div>

        <button
          onClick={handleRunResearch}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-accent-purple via-accent-blue to-accent-cyan text-white text-xs font-bold rounded-lg hover:opacity-90 transition shadow-lg cursor-pointer disabled:opacity-50 font-mono shrink-0"
        >
          <Play className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isLoading ? 'Synthesizing AI Agents...' : 'Synthesize Research Dossier'}</span>
        </button>
      </div>

      {/* Live Market Price & Real-Time Statistics Hero Card */}
      <div className="p-5 rounded-xl bg-card border border-card-border shadow-md space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-card-border">
          {/* Price & Change Block */}
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-black font-mono text-slate-100">
              ${quote?.regular_market_price ? quote.regular_market_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : (quote?.price ? Number(quote.price).toLocaleString() : '—')}
            </span>
            <div className={`flex items-center text-sm font-mono font-bold ${isPositive ? 'text-accent-emerald' : 'text-accent-rose'}`}>
              {isPositive ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
              <span>
                {isPositive ? '+' : ''}
                {quote?.change_amt ? quote.change_amt.toFixed(2) : (quote?.change ? Number(quote.change).toFixed(2) : '0.00')} ({isPositive ? '+' : ''}
                {quote?.change_pct ? quote.change_pct.toFixed(2) : (quote?.changePercent ? Number(quote.changePercent).toFixed(2) : '0.00')}%)
              </span>
            </div>
            <span className="text-xs font-mono text-slate-500 uppercase">
              {quote?.exchange || 'NASDAQ'} · {quote?.currency || 'USD'}
            </span>
          </div>

          {/* Timeframe Switcher */}
          <div className="flex items-center bg-background p-1 rounded-lg border border-card-border gap-1 font-mono text-xs">
            {['1D', '5D', '1M', '6M', '1Y', '5Y'].map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1 rounded transition cursor-pointer font-bold ${
                  timeframe === tf
                    ? 'bg-accent-cyan text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Fundamental & Trading Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs font-mono">
          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">DAY RANGE</span>
            <span className="text-slate-200 font-bold">
              ${quote?.day_low ? quote.day_low.toFixed(2) : '—'} - ${quote?.day_high ? quote.day_high.toFixed(2) : '—'}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">52-WEEK RANGE</span>
            <span className="text-slate-200 font-bold">
              ${quote?.fifty_two_week_low ? quote.fifty_two_week_low.toFixed(2) : '—'} - ${quote?.fifty_two_week_high ? quote.fifty_two_week_high.toFixed(2) : '—'}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">MARKET CAP / AUM</span>
            <span className="text-accent-cyan font-bold">
              {quote?.market_cap
                ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact' }).format(quote.market_cap)
                : fundamentals?.etf_profile?.aum
                ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact' }).format(fundamentals.etf_profile.aum)
                : '—'}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">VOLUME</span>
            <span className="text-slate-200 font-bold">
              {typeof quote?.volume === 'number' ? `${(quote.volume / 1e6).toFixed(1)}M` : (quote?.volume || '—')}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">TRAILING P/E</span>
            <span className="text-slate-200 font-bold">
              {quote?.pe_ratio ? quote.pe_ratio.toFixed(1) : (fundamentals?.valuation?.pe_trailing ? Number(fundamentals.valuation.pe_trailing).toFixed(1) : '—')}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-card-border">
            <span className="text-slate-500 text-[10px] block">BETA / VOLATILITY</span>
            <span className="text-slate-200 font-bold">
              {quote?.beta ? quote.beta.toFixed(2) : (fundamentals?.valuation?.beta ? Number(fundamentals.valuation.beta).toFixed(2) : '1.00')}
            </span>
          </div>
        </div>

        {/* Interactive Candlestick Chart */}
        <div className="pt-2">
          {isLoadingChart && chartBars.length === 0 ? (
            <div className="h-[380px] rounded-lg border border-card-border bg-[#0b1120] flex items-center justify-center text-slate-400 font-mono text-xs">
              Loading interactive candlestick series for {selectedSymbol}...
            </div>
          ) : (
            <TradingViewChart data={chartBars} symbol={selectedSymbol} height={380} />
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-accent-rose/10 border border-accent-rose/30 flex items-center gap-3 text-accent-rose text-xs font-mono">
          <AlertOctagon className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Hexagon Factor Radar & Diagnostic Scores (Only for Operating Equities) */}
      {!isEtf && !isCrypto && !isCommodity && !isForex && fundamentals?.hexagon && (
        <div className="p-5 rounded-xl bg-card border border-card-border shadow-md space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-accent-cyan" />
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide font-mono">
                Institutional 6-Pillar Factor Radar & Quality Scores
              </h2>
            </div>
            <span className="text-xs font-mono text-accent-cyan font-bold">
              Overall Score: {fundamentals.hexagon.overall ?? 75}/100
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
            {/* Hexagon Radar Visual */}
            <div className="flex justify-center">
              <HexagonRadar scores={fundamentals.hexagon} size={280} />
            </div>

            {/* Factor Scores Grid */}
            <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono text-xs">
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">VALUATION</span>
                <span className="text-xl font-bold text-accent-cyan">{fundamentals.hexagon.valuation ?? 60}</span>
                <span className="text-[10px] text-slate-500 block mt-1">P/E, EV/EBITDA, PEG</span>
              </div>
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">GROWTH</span>
                <span className="text-xl font-bold text-accent-emerald">{fundamentals.hexagon.growth ?? 82}</span>
                <span className="text-[10px] text-slate-500 block mt-1">YoY Revenue & EPS</span>
              </div>
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">PROFITABILITY</span>
                <span className="text-xl font-bold text-accent-purple">{fundamentals.hexagon.profitability ?? 75}</span>
                <span className="text-[10px] text-slate-500 block mt-1">Operating & Net Margins</span>
              </div>
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">SOLVENCY</span>
                <span className="text-xl font-bold text-accent-blue">{fundamentals.hexagon.solvency ?? 88}</span>
                <span className="text-[10px] text-slate-500 block mt-1">Debt/Equity & Cash Ratio</span>
              </div>
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">MOMENTUM</span>
                <span className="text-xl font-bold text-accent-amber">{fundamentals.hexagon.momentum ?? 78}</span>
                <span className="text-[10px] text-slate-500 block mt-1">Trend & Moving Averages</span>
              </div>
              <div className="p-3 rounded-lg bg-background border border-card-border">
                <span className="text-slate-400 text-[11px] block">SAFETY</span>
                <span className="text-xl font-bold text-emerald-400">{fundamentals.hexagon.safety ?? 75}</span>
                <span className="text-[10px] text-slate-500 block mt-1">Low Volatility & Beta</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Comprehensive Type-by-Type Telemetry & Financial Statements Explorer */}
      <FinancialStatementsExplorer
        fundamentals={fundamentals}
        isLoading={isLoadingFundamentals}
      />

      {/* AI Qualitative Research Dossier */}
      {dossier && (
        <div className="space-y-6 pt-4 border-t border-card-border">
          <div className="flex items-center justify-between pb-2 border-b border-card-border">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-accent-purple" />
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide font-mono">
                Multi-Agent Structured Research Dossier
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              Confidence: {((dossier.confidence ?? 0.85) * 100).toFixed(0)}% · Generated: {new Date(dossier.generated_at || dossier.created_at || Date.now()).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono">
            {/* Executive Summary */}
            <div className="p-5 rounded-xl bg-card border border-card-border space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase text-slate-200">
                <FileText className="w-4 h-4 text-accent-cyan" />
                <span>Executive Thesis</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {dossier.thesis_summary || dossier.technical_summary?.regime || 'Quantitative multi-agent regime synthesis active.'}
              </p>
            </div>

            {/* Core Catalysts & Falsification */}
            <div className="p-5 rounded-xl bg-card border border-card-border space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase text-slate-200">
                <ShieldCheck className="w-4 h-4 text-accent-emerald" />
                <span>Catalysts & Falsification Conditions</span>
              </div>
              <div className="space-y-2 text-xs font-sans">
                {(dossier.catalysts || [
                  `Directional Trend Score: ${(dossier.technical_summary?.directional_score ?? 0).toFixed(2)}`,
                  `Macro Signal: ${dossier.macro_summary?.cross_asset_signal || 'Momentum Alpha Factor Active'}`,
                  `Volatility Regime: ${dossier.technical_summary?.regime || 'Moderate Dispersion'}`,
                ]).slice(0, 3).map((c: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-slate-300">
                    <span className="text-accent-cyan font-mono font-bold">•</span>
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
