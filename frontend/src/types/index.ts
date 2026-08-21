export interface PlatformStatus {
  version: string;
  openai_configured: boolean;
  web_research_enabled: boolean;
  models: {
    fast: string;
    balanced: string;
    frontier: string;
    pro_mode: boolean;
  };
  spend_limits: {
    usd_budget_per_run: number;
    token_budget: number;
    max_frontier_tasks: number;
  };
  runtime: {
    concurrency: number;
    lease_seconds: number;
    max_attempts: number;
  };
  services: {
    sec_fundamentals: boolean;
    fred_macro: boolean;
    alpaca_configured: boolean;
    data_source: string;
    require_fresh_dossier: boolean;
  };
  risk_limits: {
    starting_equity: number;
    max_position_pct: number;
    max_gross_exposure_pct: number;
    min_cash_reserve_pct: number;
    max_daily_loss_pct: number;
    max_drawdown_pct: number;
  };
  stats: {
    strategies_count: number;
    memory_notes_count: number;
    deployments_count: number;
  };
  go_engine: {
    status: string;
    engine?: string;
    version?: string;
    uptime_seconds?: number;
    alpaca_configured?: boolean;
    execution_mode?: string;
    note?: string;
    is_frozen?: boolean;
  };

  live_trading: string;
}

export interface WatchlistAsset {
  symbol: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  volume: string | null;
  companyName: string | null;
  sector: string | null;
  dataStatus?: 'live' | 'stale' | 'unavailable' | 'demo';
}

export interface StrategyItem {
  name: string;
  status: 'CANDIDATE' | 'VALIDATED' | 'APPROVED' | 'RETIRED';
  updated_at: string;
  spec?: {
    name: string;
    description: string;
    target_holding_days: number;
    rules?: string[];
  };
}

export interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  trades_count: number;
  profit_factor: number;
}

export interface DailyRecord {
  date: string;
  close: number;
  equity: number;
  signal: number;
  return: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  metrics: BacktestMetrics;
  daily: DailyRecord[];
}

export interface ValidationReport {
  strategy_name: string;
  folds_evaluated: number;
  avg_train_sharpe: number;
  avg_test_sharpe: number;
  max_test_drawdown: number;
  robust_score: number;
  passed: boolean;
  reasons: string[];
}

export interface AlphaSearchCandidate {
  strategy: {
    name: string;
    description: string;
    target_holding_days: number;
  };
  report?: ValidationReport;
  error?: string;
  passed: boolean;
}

export interface TaskNode {
  task_id: string;
  root_id: string;
  task_type: string;
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'dead_letter';
  dependencies: string[];
  attempts: number;
  max_attempts: number;
  model_tier?: string;
  model?: string;
  latency_ms?: number;
  tokens_used?: number;
  cost_usd?: number;
  error?: string;
  created_at: string;
  completed_at?: string;
}

export interface RuntimeStatus {
  summary: {
    total: number;
    pending: number;
    running: number;
    completed: number;
    failed: number;
    dead_letter: number;
  };
  tasks: TaskNode[];
}

export interface ModelDeployment {
  id: number;
  tier: 'fast' | 'balanced' | 'frontier';
  model: string;
  status: 'active' | 'candidate' | 'degraded' | 'disabled';
  notes: string;
  registered_at: string;
  activated_at?: string;
  latency_p50_ms?: number;
  error_rate?: number;
}

export interface RouteRecommendation {
  id: number;
  task_type: string;
  current_tier: string;
  recommended_tier: string;
  reason: string;
  status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';
  capital_approved?: boolean;
  created_at: string;
}

export interface MultiYearStatementRow {
  metric: string;
  category: 'header' | 'subtotal' | 'item' | 'highlight' | 'ratio';
  values: string[];
}

export interface MultiYearStatements {
  periods: string[];
  income_statement?: MultiYearStatementRow[];
  balance_sheet?: MultiYearStatementRow[];
  cash_flow?: MultiYearStatementRow[];
  ratios?: MultiYearStatementRow[];
}

export interface DiagnosticAltmanZ {
  z_score: number;
  zone: string;
  zone_color: 'emerald' | 'amber' | 'rose';
  components?: {
    x1_working_cap_to_assets: number;
    x2_retained_earnings_to_assets: number;
    x3_ebit_to_assets: number;
    x4_market_equity_to_liab: number;
    x5_asset_turnover: number;
  };
}

export interface DiagnosticPiotroskiF {
  f_score: number;
  rating: string;
  rating_color: 'emerald' | 'amber' | 'rose';
  checks: string[];
}

export interface MarketConsensus {
  recommendation: string;
  target_mean_price: number;
  target_high_price: number;
  target_low_price: number;
  wall_street_breakdown?: {
    total_analysts: number;
    strong_buy: number;
    buy: number;
    hold: number;
    sell: number;
    strong_sell: number;
  };
  seeking_alpha_consensus?: {
    author_rating: string;
    quant_rating: string;
    valuation_grade?: string;
    growth_grade?: string;
    profitability_grade?: string;
    momentum_grade?: string;
    revisions_grade?: string;
  };
  community_sentiment?: {
    sentiment_score: string;
    message_volume: string;
    retail_momentum: string;
    top_catalyst: string;
  };
}

export interface AssetSearchResult {
  symbol: string;
  name: string;
  asset_type: 'EQUITY' | 'ETF' | 'COMMODITY' | 'CRYPTO' | 'FOREX';
  type_disp?: string;
  exchange?: string;
  sector?: string;
}

export interface ETFHolding {
  symbol: string;
  name: string;
  weight: number;
  sector: string;
}

export interface ETFProfile {
  holdings_count: number;
  top_holdings: ETFHolding[];
  expense_ratio: number;
  aum?: number;
  replication_method: string;
  rebalance_frequency: string;
}

export interface CommodityProfile {
  metal_type: string;
  physical_backing: string;
  vault_custodian: string;
  gold_silver_ratio?: number;
  real_yield_correlation?: number;
  inflation_beta_10y?: number;
  futures_curve?: string;
  central_bank_demand_trend?: string;
}

export interface CryptoProfile {
  asset_name: string;
  circulating_supply: string;
  max_supply: string;
  consensus_mechanism: string;
  ath_price: number;
  ath_drawdown_pct: number;
  volatility_30d_annualized: number;
  network_security: string;
}

export interface StockFundamentals {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  city?: string;
  country?: string;
  employees?: number;
  website?: string;
  business_summary: string;
  asset_type?: 'EQUITY' | 'ETF' | 'COMMODITY' | 'CRYPTO' | 'FOREX';
  is_etf?: boolean;
  is_crypto?: boolean;
  is_commodity?: boolean;
  is_corporate_operating_company?: boolean;
  etf_profile?: ETFProfile;
  commodity_profile?: CommodityProfile;
  crypto_profile?: CryptoProfile;
  valuation: {
    pe_trailing: any;
    pe_forward: any;
    market_cap: any;
    enterprise_value?: any;
    price_to_sales?: any;
    price_to_book?: any;
    nav?: any;
    beta?: any;
  };

  balance_sheet?: {
    total_cash: any;
    total_debt: any;
    net_cash: any;
    debt_to_equity: any;
    current_ratio?: any;
    quick_ratio?: any;
    total_assets?: any;
    total_liabilities?: any;
    working_capital?: any;
    retained_earnings?: any;
  } | null;
  profitability?: {
    total_revenue: any;
    revenue_growth_yoy: any;
    gross_margin: any;
    operating_margin: any;
    net_margin: any;
    roe: any;
    roa: any;
    operating_cashflow?: any;
    free_cashflow?: any;
  } | null;
  market?: MarketConsensus;
  multi_year_statements?: MultiYearStatements | null;
  hexagon?: {
    valuation?: number;
    growth?: number;
    profitability?: number;
    solvency?: number;
    health?: number;
    momentum?: number;
    safety?: number;
    quality?: number;
    overall?: number;
    altman_z?: DiagnosticAltmanZ;
    piotroski_f?: DiagnosticPiotroskiF;
    beneish_m?: any;
    sloan_accrual?: any;
  };

}

export interface ResearchDossier {
  symbol: string;
  created_at: string;
  generated_at?: string;
  confidence?: number;
  thesis_summary?: string;
  catalysts?: string[];
  technical_summary?: {
    momentum_20d: number;
    momentum_60d: number;
    rsi_14: number;
    volatility_20d: number;
    directional_score: number;
    regime: string;
  };
  fundamental_summary?: {
    revenue_growth_yoy: number;
    operating_margin: number;
    net_margin: number;
    debt_to_equity: number;
    pe_ratio?: number;
    pb_ratio?: number;
  };
  hexagon_scores?: {
    profitability: number;
    growth: number;
    value: number;
    solvency: number;
    momentum: number;
    safety: number;
    overall: number;
  };
  macro_summary?: {
    equity_trend: string;
    rate_regime: string;
    inflation_trend: string;
    cross_asset_signal: string;
  };
  verified_claims?: Array<{
    claim: string;
    source_url: string;
    confidence: number;
    verified: boolean;
  }>;
  scenarios?: Array<{
    scenario: string;
    probability: number;
    target_impact_pct: number;
  }>;
  falsification_tests?: Array<{
    hypothesis: string;
    test: string;
    falsified: boolean;
    evidence: string;
  }>;
}

export interface MemoryNote {
  id: number | string;
  agent: string;
  kind: string;
  content: string;
  symbol?: string;
  confidence: number;
  importance: number;
  created_at: string;
  as_of_date?: string;
  point_in_time?: string;
  decision_id?: string;
  claim_direction?: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'RISK_ALERT';
  entities?: {
    symbols?: string[];
    sectors?: string[];
    macro_factors?: string[];
  };
  expires_at?: string;
  status?: string;
  active?: boolean;
}

export interface BrokerHealthSummary {
  active_broker: string;
  environment: string;
  ready: boolean;
  connected: boolean;
  message: string;
  all_registered_brokers: Array<{
    name: string;
    environment: string;
    ready: boolean;
    connected: boolean;
    message: string;
  }>;
}

export interface ReconciliationDiscrepancy {
  type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  symbol: string;
  field: string;
  local_value: string;
  broker_value: string;
  delta: number;
  message: string;
}

export interface ReconciliationReport {
  timestamp: string;
  has_critical: boolean;
  total_count: number;
  critical_count: number;
  discrepancies: ReconciliationDiscrepancy[];
}

export interface InstitutionalRiskMetrics {
  symbol: string;
  equity: number;
  sample_days: number;
  var_95_usd: number;
  var_99_usd: number;
  cvar_95_usd: number;
  annualized_return: number;
  annualized_volatility: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  beta: number;
}

export type TradingReadiness = 'READY' | 'NOT_READY' | 'FROZEN' | 'UNKNOWN';

export interface ReconciliationSummary {
  status: 'UNKNOWN' | 'CLEAN' | 'MISMATCH' | 'FAILED' | 'STALE' | 'WARNING';
  last_run_at?: string;
  critical_count: number;
  total_count: number;
  is_fresh: boolean;
  max_age_seconds: number;
  broker_name?: string;
}

export interface MarketDataSummary {
  status: 'LIVE' | 'DEMO' | 'UNAVAILABLE' | 'STALE';
  updated_at?: string;
  tick_count: number;
}

export interface ReadinessReport {
  process: string;
  trading_ready: boolean;
  trading_readiness: TradingReadiness;
  execution_mode: string;
  active_broker: string;
  broker_configured: boolean;
  broker_connected: boolean;
  broker_ready: boolean;
  journal_ready: boolean;
  reconciliation: ReconciliationSummary;
  is_frozen: boolean;
  freeze_reason?: string;
  frozen_at?: string;
  frozen_by?: string;
  market_data: MarketDataSummary;
  blocking_reasons: string[];
  timestamp: string;
}

