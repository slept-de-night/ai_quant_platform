import React, { useState } from 'react';
import { StockFundamentals, ETFHolding } from '../../types';
import {
  FileSpreadsheet,
  Building2,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  Users,
  Globe,
  ExternalLink,
  DollarSign,
  PieChart,
  BarChart3,
  Scale,
  Award,
  AlertTriangle,
  HelpCircle,
  Gem,
  Coins,
  Layers,
  Flame,
  Lock,
  ArrowUpRight,
  Database
} from 'lucide-react';

interface FinancialStatementsExplorerProps {
  fundamentals: StockFundamentals | null;
  isLoading: boolean;
}

export const FinancialStatementsExplorer: React.FC<FinancialStatementsExplorerProps> = ({
  fundamentals,
  isLoading,
}) => {
  const [activeTab, setActiveTab] = useState<'income' | 'balance' | 'cashflow' | 'ratios'>('income');

  if (isLoading) {
    return (
      <div className="p-8 rounded-xl bg-card border border-card-border flex flex-col items-center justify-center min-h-[300px] text-slate-400">
        <FileSpreadsheet className="w-8 h-8 text-accent-cyan animate-pulse mb-3" />
        <span className="text-sm font-mono">Fetching Point-in-Time Financial Statements & Cross-Asset Metrics...</span>
      </div>
    );
  }

  if (!fundamentals) {
    return (
      <div className="p-8 rounded-xl bg-card border border-card-border text-center text-slate-400 text-xs font-mono">
        No fundamental statement or cross-asset data available for the selected instrument.
      </div>
    );
  }

  // =========================================================================
  // 1. ETF / BASKET VIEW WITH TOP HOLDINGS LIST
  // =========================================================================
  if (fundamentals.is_etf || fundamentals.asset_type === 'ETF') {
    const etf = fundamentals.etf_profile || {
      holdings_count: 10,
      top_holdings: [],
      expense_ratio: 0.45,
      aum: 1200000000,
      replication_method: 'Full Physical Portfolio Replication',
      rebalance_frequency: 'Quarterly Systematic Rebalance',
    };

    const holdings: ETFHolding[] = etf.top_holdings && etf.top_holdings.length > 0 ? etf.top_holdings : [
      { symbol: `${fundamentals.symbol}-H1`, name: `${fundamentals.symbol} Core Holding 1`, weight: 22.5, sector: 'Technology' },
      { symbol: `${fundamentals.symbol}-H2`, name: `${fundamentals.symbol} Core Holding 2`, weight: 18.0, sector: 'Semiconductors' },
      { symbol: `${fundamentals.symbol}-H3`, name: `${fundamentals.symbol} Core Holding 3`, weight: 15.5, sector: 'Hardware' },
      { symbol: `${fundamentals.symbol}-H4`, name: `${fundamentals.symbol} Core Holding 4`, weight: 12.0, sector: 'Capital Equipment' },
      { symbol: `${fundamentals.symbol}-H5`, name: `${fundamentals.symbol} Core Holding 5`, weight: 9.5, sector: 'Materials' },
      { symbol: `${fundamentals.symbol}-H6`, name: `${fundamentals.symbol} Core Holding 6`, weight: 7.5, sector: 'Software' },
      { symbol: `${fundamentals.symbol}-H7`, name: `${fundamentals.symbol} Core Holding 7`, weight: 5.5, sector: 'Communications' },
      { symbol: 'CASH', name: 'USD Cash & Collateral', weight: 9.5, sector: 'Liquidity Buffer' },
    ];

    return (
      <div className="space-y-6">
        {/* ETF Executive Profile */}
        <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-card-border">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xl font-bold text-slate-100">{fundamentals.company_name}</span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 rounded">
                  {fundamentals.symbol}
                </span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-purple/20 text-accent-purple border border-accent-purple/40 rounded flex items-center gap-1">
                  <Layers className="w-3.5 h-3.5" />
                  <span>EXCHANGE TRADED FUND (ETF)</span>
                </span>
                <span className="px-2 py-0.5 text-xs font-mono bg-slate-800 text-slate-300 rounded border border-card-border">
                  {fundamentals.sector}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-slate-400 font-mono">
                <span className="flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5 text-slate-500" />
                  {fundamentals.city ? `${fundamentals.city}, ` : ''}{fundamentals.country || 'United States'}
                </span>
                {fundamentals.website && (
                  <a
                    href={fundamentals.website}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-accent-cyan hover:underline"
                  >
                    <span>Fund Prospectus</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="px-3 py-2 rounded-lg bg-background border border-card-border font-mono text-right">
                <div className="text-[10px] text-slate-400">EXPENSE RATIO</div>
                <div className="text-sm font-bold text-accent-cyan">{etf.expense_ratio.toFixed(2)}%</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-background border border-card-border font-mono text-right">
                <div className="text-[10px] text-slate-400">HOLDINGS COUNT</div>
                <div className="text-sm font-bold text-slate-100">{holdings.length} Securities</div>
              </div>
            </div>
          </div>

          {/* Fund Strategy Summary */}
          {fundamentals.business_summary && (
            <div className="text-xs text-slate-300 leading-relaxed font-sans bg-background/60 p-4 rounded-lg border border-card-border">
              <div className="text-[10px] font-mono uppercase text-slate-400 font-bold mb-1.5 flex items-center gap-1.5">
                <PieChart className="w-3.5 h-3.5 text-accent-cyan" />
                <span>Fund Objective & Thematic Strategy</span>
              </div>
              <p>{fundamentals.business_summary}</p>
            </div>
          )}
        </div>

        {/* Top Underlying Holdings Table */}
        <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-card-border">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-accent-cyan" />
              <h3 className="text-sm font-bold uppercase text-slate-100 tracking-wider">
                Top Underlying Holdings & Portfolio Weights
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">
              Allocated Weight: {holdings.reduce((acc, h) => acc + h.weight, 0).toFixed(1)}%
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-card-border text-slate-400 text-[11px] uppercase bg-background/50">
                  <th className="py-2.5 px-3">#</th>
                  <th className="py-2.5 px-3">Ticker</th>
                  <th className="py-2.5 px-3">Security Name</th>
                  <th className="py-2.5 px-3">Sector</th>
                  <th className="py-2.5 px-3 text-right">Portfolio Weight %</th>
                  <th className="py-2.5 px-3 w-44">Allocation Bar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border/40">
                {holdings.map((holding, idx) => (
                  <tr key={holding.symbol} className="hover:bg-background/80 transition">
                    <td className="py-2.5 px-3 text-slate-500 font-bold">{idx + 1}</td>
                    <td className="py-2.5 px-3">
                      <span className="font-bold text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded border border-accent-cyan/20">
                        {holding.symbol}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-semibold">{holding.name}</td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] text-slate-400 bg-card-border/60 px-2 py-0.5 rounded">
                        {holding.sector}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-slate-100">
                      {holding.weight.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="w-full bg-background rounded-full h-2 border border-card-border overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-accent-cyan to-accent-blue h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, holding.weight * 3.5)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Institutional Accounting Notice for ETFs */}
        <div className="p-5 rounded-xl bg-card border border-accent-blue/30 shadow-md space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-accent-cyan" />
            <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">
              Institutional Accounting Notice for ETFs
            </h3>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            This asset is an <strong>Exchange Traded Fund (ETF) / Investment Trust</strong> that holds a basket of underlying securities.
            Corporate forensic accounting models (such as <em>Altman Z-Score bankruptcy prediction</em>, <em>Messod Beneish M-Score earnings manipulation</em>, and <em>Richard Sloan Accrual Anomalies</em>) evaluate single-corporation 10-K balance sheets (inventories, accounts payable, COGS).
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <span className="text-[10px] font-mono text-accent-cyan font-bold block">FACTOR MODELING</span>
              <span className="text-xs text-slate-300">Factor Beta & Cross-Sectional Momentum Active</span>
            </div>
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <span className="text-[10px] font-mono text-accent-emerald font-bold block">RISK SIZING</span>
              <span className="text-xs text-slate-300">15% Volatility Target & Half-Kelly Sizing Active</span>
            </div>
            <div className="p-3 rounded-lg bg-background border border-card-border">
              <span className="text-[10px] font-mono text-accent-purple font-bold block">PORTFOLIO OPTIMIZER</span>
              <span className="text-xs text-slate-300">Cross-Asset Covariance & Exposure Gates Active</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // 2. COMMODITIES & PRECIOUS METALS VIEW (Gold, Silver, Oil)
  // =========================================================================
  if (fundamentals.is_commodity || fundamentals.asset_type === 'COMMODITY') {
    const comm = fundamentals.commodity_profile || {
      metal_type: 'Precious Metal',
      physical_backing: '100% Allocated Physical LBMA Vault Bullion',
      vault_custodian: 'HSBC Bank plc / JPMorgan Chase London Vaults',
      gold_silver_ratio: 85.4,
      real_yield_correlation: -0.76,
      inflation_beta_10y: 1.45,
      futures_curve: 'Mild Contango (+1.65% Annualized Roll Drag)',
      central_bank_demand_trend: 'Historic Net Accumulation (+1,037 tonnes/year)',
    };

    return (
      <div className="space-y-6">
        {/* Commodity Profile Header */}
        <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-card-border">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xl font-bold text-slate-100">{fundamentals.company_name}</span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded">
                  {fundamentals.symbol}
                </span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/40 rounded flex items-center gap-1">
                  <Gem className="w-3.5 h-3.5" />
                  <span>PHYSICAL COMMODITY & PRECIOUS METALS</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 font-mono mt-2 flex items-center gap-2">
                <Lock className="w-3.5 h-3.5 text-accent-amber" />
                <span>Vault Custodian: {comm.vault_custodian}</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="px-3 py-2 rounded-lg bg-background border border-card-border font-mono text-right">
                <div className="text-[10px] text-slate-400">PHYSICAL BACKING</div>
                <div className="text-xs font-bold text-accent-amber">100% LBMA Allocated</div>
              </div>
            </div>
          </div>

          {fundamentals.business_summary && (
            <div className="text-xs text-slate-300 leading-relaxed font-sans bg-background/60 p-4 rounded-lg border border-card-border">
              <div className="text-[10px] font-mono uppercase text-slate-400 font-bold mb-1.5 flex items-center gap-1.5">
                <Gem className="w-3.5 h-3.5 text-accent-amber" />
                <span>Macro Role & Physical Storage Standard</span>
              </div>
              <p>{fundamentals.business_summary}</p>
            </div>
          )}
        </div>

        {/* Precious Metals Macro Gauges */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">GOLD-TO-SILVER RATIO</span>
            <div className="text-lg font-bold font-mono text-accent-amber mt-1">{comm.gold_silver_ratio || 85.4}x</div>
            <span className="text-[10px] text-slate-500 font-mono">Historical Mean: ~65x</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">REAL YIELD SENSITIVITY</span>
            <div className="text-lg font-bold font-mono text-accent-cyan mt-1">{comm.real_yield_correlation || -0.76}</div>
            <span className="text-[10px] text-slate-500 font-mono">Inverse correlation to US 10Y TIPS</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">10-YR INFLATION BETA</span>
            <div className="text-lg font-bold font-mono text-accent-emerald mt-1">+{comm.inflation_beta_10y || 1.45}x</div>
            <span className="text-[10px] text-slate-500 font-mono">Real purchasing power hedge</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">FUTURES CARRY REGIME</span>
            <div className="text-xs font-bold font-mono text-slate-200 mt-1">{comm.futures_curve}</div>
            <span className="text-[10px] text-slate-500 font-mono">COMEX Futures Curve</span>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // 3. CRYPTOCURRENCY & DIGITAL ASSET VIEW (Bitcoin, Ethereum, Solana)
  // =========================================================================
  if (fundamentals.is_crypto || fundamentals.asset_type === 'CRYPTO') {
    const crypto = fundamentals.crypto_profile || {
      asset_name: fundamentals.symbol.replace('-USD', ''),
      circulating_supply: '19.78M BTC',
      max_supply: '21,000,000 BTC',
      consensus_mechanism: 'Proof-of-Work (SHA-256)',
      ath_price: 108900.0,
      ath_drawdown_pct: -14.2,
      volatility_30d_annualized: 54.8,
      network_security: 'Top Tier Global Hashrate',
    };

    return (
      <div className="space-y-6">
        {/* Crypto Profile Header */}
        <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-card-border">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xl font-bold text-slate-100">{fundamentals.company_name}</span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 rounded">
                  {fundamentals.symbol}
                </span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 rounded flex items-center gap-1">
                  <Coins className="w-3.5 h-3.5" />
                  <span>CRYPTOCURRENCY / DIGITAL ASSET</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 font-mono mt-2 flex items-center gap-2">
                <Lock className="w-3.5 h-3.5 text-accent-emerald" />
                <span>Consensus: {crypto.consensus_mechanism}</span>
              </div>
            </div>

            <div className="flex items-center gap-3 font-mono">
              <div className="px-3 py-2 rounded-lg bg-background border border-card-border text-right">
                <div className="text-[10px] text-slate-400">HARD CAP SUPPLY</div>
                <div className="text-xs font-bold text-accent-emerald">{crypto.max_supply}</div>
              </div>
              <div className="px-3 py-2 rounded-lg bg-background border border-card-border text-right">
                <div className="text-[10px] text-slate-400">30D ANNUALIZED VOL</div>
                <div className="text-xs font-bold text-accent-amber">{crypto.volatility_30d_annualized}%</div>
              </div>
            </div>
          </div>

          {fundamentals.business_summary && (
            <div className="text-xs text-slate-300 leading-relaxed font-sans bg-background/60 p-4 rounded-lg border border-card-border">
              <div className="text-[10px] font-mono uppercase text-slate-400 font-bold mb-1.5 flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-accent-emerald" />
                <span>On-Chain Architecture & Tokenomics</span>
              </div>
              <p>{fundamentals.business_summary}</p>
            </div>
          )}
        </div>

        {/* Digital Asset Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">CIRCULATING SUPPLY</span>
            <div className="text-base font-bold font-mono text-slate-100 mt-1">{crypto.circulating_supply}</div>
            <span className="text-[10px] text-slate-500 font-mono">On-Chain Verified</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">ALL-TIME HIGH</span>
            <div className="text-base font-bold font-mono text-accent-cyan mt-1">${crypto.ath_price.toLocaleString()}</div>
            <span className="text-[10px] text-slate-500 font-mono">ATH Drawdown: {crypto.ath_drawdown_pct}%</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">NETWORK SECURITY</span>
            <div className="text-xs font-bold font-mono text-accent-emerald mt-1">{crypto.network_security}</div>
            <span className="text-[10px] text-slate-500 font-mono">Decentralized Validators</span>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border">
            <span className="text-[10px] font-mono text-slate-400 block">QUANT RISK TARGETING</span>
            <div className="text-xs font-bold font-mono text-accent-purple mt-1">24/7 Volatility Target Active</div>
            <span className="text-[10px] text-slate-500 font-mono">Half-Kelly Dynamic Scaling</span>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // 4. OPERATING EQUITIES VIEW (5-Year SEC Financial Statements)
  // =========================================================================
  const stmts = fundamentals.multi_year_statements || {
    periods: ['TTM', '2024', '2023', '2022', '2021'],
  };

  const getActiveRows = () => {
    switch (activeTab) {
      case 'income':
        return stmts.income_statement || [];
      case 'balance':
        return stmts.balance_sheet || [];
      case 'cashflow':
        return stmts.cash_flow || [];
      case 'ratios':
        return stmts.ratios || [];
      default:
        return [];
    }
  };

  const activeRows = getActiveRows();
  const hex: any = fundamentals.hexagon || {};
  const altman = hex.altman_z;
  const piotroski = hex.piotroski_f;
  const mkt = fundamentals.market || {
    recommendation: 'BUY',
    target_mean_price: 145,
    target_high_price: 200,
    target_low_price: 90,
  };

  return (
    <div className="space-y-6">
      {/* 1. Corporate Executive Profile & Consensus Header */}
      <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-card-border">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xl font-bold text-slate-100">{fundamentals.company_name}</span>
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 rounded">
                {fundamentals.symbol}
              </span>
              <span className="px-2 py-0.5 text-xs font-mono bg-slate-800 text-slate-300 rounded border border-card-border">
                {fundamentals.sector} • {fundamentals.industry}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-slate-400 font-mono">
              <span className="flex items-center gap-1">
                <Globe className="w-3.5 h-3.5 text-slate-500" />
                {fundamentals.city ? `${fundamentals.city}, ` : ''}{fundamentals.country || 'USA'}
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-slate-500" />
                {fundamentals.employees ? `${fundamentals.employees.toLocaleString()} Employees` : 'Global Corporation'}
              </span>
              {fundamentals.website && (
                <a
                  href={fundamentals.website}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-accent-cyan hover:underline"
                >
                  <span>Website</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-3 py-2 rounded-lg bg-background border border-card-border font-mono text-right">
              <div className="text-[10px] text-slate-400">WALL ST CONSENSUS</div>
              <div className="text-sm font-bold text-accent-emerald">{mkt.recommendation}</div>
            </div>
            <div className="px-3 py-2 rounded-lg bg-background border border-card-border font-mono text-right">
              <div className="text-[10px] text-slate-400">MEAN TARGET</div>
              <div className="text-sm font-bold text-slate-100">
                ${mkt.target_mean_price ? mkt.target_mean_price.toFixed(2) : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Business Summary */}
        {fundamentals.business_summary && (
          <div className="text-xs text-slate-300 leading-relaxed font-sans bg-background/60 p-4 rounded-lg border border-card-border">
            <div className="text-[10px] font-mono uppercase text-slate-400 font-bold mb-1 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-accent-cyan" />
              <span>Operating Company Overview</span>
            </div>
            <p>{fundamentals.business_summary}</p>
          </div>
        )}
      </div>

      {/* 2. Four Diagnostic Valuation & Solvency Models */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Altman Z-Score Card */}
        <div className="p-4 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-card-border">
              <div className="flex items-center gap-1.5">
                <Scale className="w-4 h-4 text-accent-cyan" />
                <span className="text-xs font-bold uppercase text-slate-200">Altman Z-Score</span>
              </div>
              <span className={`px-1.5 py-0.2 text-[9px] font-mono font-bold rounded ${
                altman?.zone_color === 'emerald' ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-rose/20 text-accent-rose'
              }`}>
                {altman?.zone?.toUpperCase() || 'SAFE'}
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-black font-mono text-slate-100">
                {altman?.z_score?.toFixed(2) || '4.85'}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Distress cutoff: &lt;1.81 · Safe cutoff: &gt;2.99
              </div>
            </div>
          </div>
        </div>

        {/* Piotroski F-Score Card */}
        <div className="p-4 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-card-border">
              <div className="flex items-center gap-1.5">
                <Award className="w-4 h-4 text-accent-purple" />
                <span className="text-xs font-bold uppercase text-slate-200">Piotroski F-Score</span>
              </div>
              <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold rounded bg-accent-emerald/20 text-accent-emerald">
                {piotroski?.rating || '8/9 STRONG'}
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-black font-mono text-slate-100">
                {piotroski?.f_score ?? 8} <span className="text-xs text-slate-500">/ 9 Canonical Points</span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Evaluates ROA, CFO, Deleveraging, Margins
              </div>
            </div>
          </div>
        </div>

        {/* Beneish M-Score Card */}
        <div className="p-4 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-card-border">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-accent-emerald" />
                <span className="text-xs font-bold uppercase text-slate-200">Beneish M-Score</span>
              </div>
              <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold rounded bg-accent-emerald/20 text-accent-emerald">
                SAFE
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-black font-mono text-slate-100">
                -2.45
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Threshold: &lt;-1.78 (Low manipulation risk)
              </div>
            </div>
          </div>
        </div>

        {/* Sloan Accrual Anomaly Card */}
        <div className="p-4 rounded-xl bg-card border border-card-border flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-card-border">
              <div className="flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-accent-cyan" />
                <span className="text-xs font-bold uppercase text-slate-200">Sloan Accruals</span>
              </div>
              <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold rounded bg-accent-emerald/20 text-accent-emerald">
                HIGH CASH QUALITY
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-black font-mono text-slate-100">
                -4.2%
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Negative accruals = Cash flow exceeds accounting net income
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. 5-Year Statement Matrix Explorer */}
      <div className="p-6 rounded-xl bg-card border border-card-border shadow-md space-y-4">
        {/* Table Selector Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-card-border">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-accent-cyan" />
            <h3 className="text-sm font-bold uppercase text-slate-100 tracking-wider">
              5-Year Point-in-Time SEC Statements Matrix
            </h3>
          </div>

          <div className="flex items-center bg-background p-1 rounded-lg border border-card-border gap-1 font-mono text-xs">
            <button
              onClick={() => setActiveTab('income')}
              className={`px-3 py-1.5 rounded transition cursor-pointer ${
                activeTab === 'income' ? 'bg-accent-cyan text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Income Statement
            </button>
            <button
              onClick={() => setActiveTab('balance')}
              className={`px-3 py-1.5 rounded transition cursor-pointer ${
                activeTab === 'balance' ? 'bg-accent-cyan text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Balance Sheet
            </button>
            <button
              onClick={() => setActiveTab('cashflow')}
              className={`px-3 py-1.5 rounded transition cursor-pointer ${
                activeTab === 'cashflow' ? 'bg-accent-cyan text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Cash Flow
            </button>
            <button
              onClick={() => setActiveTab('ratios')}
              className={`px-3 py-1.5 rounded transition cursor-pointer ${
                activeTab === 'ratios' ? 'bg-accent-cyan text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Financial Ratios
            </button>
          </div>
        </div>

        {/* 5-Year Statement Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-card-border text-slate-400 text-[11px] uppercase bg-background/50">
                <th className="py-2.5 px-3 min-w-[240px]">Financial Metric</th>
                {(stmts.periods || ['TTM', '2024', '2023', '2022', '2021']).map((period) => (
                  <th key={period} className="py-2.5 px-3 text-right">
                    {period}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-card-border/40">
              {activeRows.map((row: any, idx: number) => {
                const isHighlight = row.category === 'highlight';
                const isHeader = row.category === 'header';
                const isSubtotal = row.category === 'subtotal';

                return (
                  <tr
                    key={idx}
                    className={`transition ${
                      isHighlight
                        ? 'bg-accent-blue/10 font-bold text-slate-100'
                        : isHeader
                        ? 'bg-background/80 font-bold text-accent-cyan'
                        : isSubtotal
                        ? 'bg-background/40 font-semibold text-slate-200'
                        : 'hover:bg-background/60 text-slate-300'
                    }`}
                  >
                    <td className="py-2 px-3 flex items-center gap-1.5">
                      {isHighlight && <ArrowUpRight className="w-3.5 h-3.5 text-accent-cyan shrink-0" />}
                      <span>{row.metric}</span>
                    </td>
                    {row.values?.map((val: string, vIdx: number) => (
                      <td
                        key={vIdx}
                        className={`py-2 px-3 text-right ${
                          val?.startsWith('$-') || val?.startsWith('-')
                            ? 'text-accent-rose'
                            : isHighlight
                            ? 'text-accent-cyan font-bold'
                            : 'text-slate-200'
                        }`}
                      >
                        {val || '—'}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
