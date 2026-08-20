export type AssetType = "EQUITY" | "ETF" | "COMMODITY" | "CRYPTO" | "FOREX";

export type InstrumentType = "STOCK" | "ETF" | "TRUST" | "ETP" | "FUTURE" | "CRYPTO" | "FX_SPOT";

export interface SearchSuggestion {
  symbol: string;
  name: string;
  asset_type: AssetType;
  instrument_type: InstrumentType;
  exchange: string | null;
  currency: string | null;
  subtitle: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchSuggestion[];
}

export interface MarketQuote {
  price: number | null;
  previous_close: number | null;
  change_pct: number | null;
  currency: string | null;
  exchange: string | null;
  market_time: string | null;
}

export interface SourceStamp {
  source: string;
  as_of: string | null;
  quality: "LIVE" | "DELAYED" | "DERIVED" | "REFERENCE" | "UNAVAILABLE";
}

export interface BaseAssetPayload {
  symbol: string;
  name: string;
  asset_type: AssetType;
  instrument_type: InstrumentType;
  quote: MarketQuote;
  sources: SourceStamp[];
}

// ============================================================
// EQUITY
// ============================================================

export interface StatementValue {
  fiscal_year: number;
  value: number | null;
  filed_at: string | null;
}

export interface StatementRow {
  key: string;
  label: string;
  unit: string;
  values: StatementValue[];
}

export interface FinancialStatementMatrix {
  income_statement: StatementRow[];
  balance_sheet: StatementRow[];
  cash_flow: StatementRow[];
}

export interface DiagnosticModel {
  name: string;
  score: number | null;
  zone: string | null;
  available: boolean;
  reason: string | null;
  details: Record<string, number | string | boolean | null>;
}

export interface EquityProfile {
  cik: string | null;
  sic: string | null;
  sector: string | null;
  industry: string | null;
  financials: FinancialStatementMatrix;
  forensics: {
    altman_z: DiagnosticModel;
    piotroski_f: DiagnosticModel;
    beneish_m: DiagnosticModel;
    sloan_accruals: DiagnosticModel;
  };
}

export interface EquityPayload extends BaseAssetPayload {
  asset_type: "EQUITY";
  profile: EquityProfile;
}

// ============================================================
// ETF
// ============================================================

export interface ETFHolding {
  symbol: string | null;
  name: string;
  weight_pct: number;
  sector: string | null;
}

export interface SectorWeight {
  sector: string;
  weight_pct: number;
}

export interface ETFProfile {
  fund_aum: number | null;
  expense_ratio_pct: number | null;
  replication_method: string | null;
  tracking_error_1y_pct: number | null;
  rebalance_schedule: string | null;
  top_holdings: ETFHolding[];
  sector_exposure: SectorWeight[];
}

export interface ETFPayload extends BaseAssetPayload {
  asset_type: "ETF";
  profile: ETFProfile;
}

// ============================================================
// COMMODITY
// ============================================================

export interface CommodityProfile {
  commodity_name: string;
  exposure_symbol: string | null;
  exposure_method: string;
  physical_backing_standard: string | null;
  vault_custodian: string | null;
  gold_silver_ratio: number | null;
  real_yield_correlation_3y: number | null;
  inflation_beta_10y: number | null;
  futures_curve_regime: "CONTANGO" | "BACKWARDATION" | "FLAT" | "UNKNOWN";
  front_month_price: number | null;
  next_month_price: number | null;
  implied_roll_yield_pct: number | null;
  central_bank_reserve_trend: string | null;
}

export interface CommodityPayload extends BaseAssetPayload {
  asset_type: "COMMODITY";
  profile: CommodityProfile;
}

// ============================================================
// CRYPTO
// ============================================================

export interface CryptoProfile {
  coin_id: string | null;
  circulating_supply: number | null;
  max_supply: number | null;
  hard_cap: boolean | null;
  consensus_mechanism: string | null;
  ath_price: number | null;
  ath_drawdown_pct: number | null;
  realized_vol_30d_annualized: number | null;
  trades_24_7: boolean;
}

export interface CryptoPayload extends BaseAssetPayload {
  asset_type: "CRYPTO";
  profile: CryptoProfile;
}

// ============================================================
// FOREX
// ============================================================

export interface ForexProfile {
  base_currency: string;
  quote_currency: string;
  base_policy_rate_pct: number | null;
  quote_policy_rate_pct: number | null;
  interest_rate_differential_pct: number | null;
  annualized_carry_pct: number | null;
  base_central_bank_cycle: string | null;
  quote_central_bank_cycle: string | null;
}

export interface ForexPayload extends BaseAssetPayload {
  asset_type: "FOREX";
  profile: ForexProfile;
}

export type AssetPayload =
  | EquityPayload
  | ETFPayload
  | CommodityPayload
  | CryptoPayload
  | ForexPayload;
