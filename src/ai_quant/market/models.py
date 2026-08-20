from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"


class InstrumentType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    TRUST = "TRUST"
    ETP = "ETP"
    FUTURE = "FUTURE"
    CRYPTO = "CRYPTO"
    FX_SPOT = "FX_SPOT"


class DataQuality(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    DERIVED = "DERIVED"
    REFERENCE = "REFERENCE"
    UNAVAILABLE = "UNAVAILABLE"


class SourceStamp(BaseModel):
    source: str
    as_of: Optional[datetime] = None
    quality: DataQuality = DataQuality.DERIVED


class MarketQuote(BaseModel):
    price: Optional[float] = None
    previous_close: Optional[float] = None
    change_pct: Optional[float] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    market_time: Optional[datetime] = None


class SearchSuggestion(BaseModel):
    symbol: str
    name: str
    asset_type: AssetType
    instrument_type: InstrumentType
    exchange: Optional[str] = None
    currency: Optional[str] = None
    subtitle: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchSuggestion]


# ============================================================
# EQUITY
# ============================================================


class StatementValue(BaseModel):
    fiscal_year: int
    value: Optional[float] = None
    filed_at: Optional[datetime] = None


class StatementRow(BaseModel):
    key: str
    label: str
    unit: str = "USD"
    values: List[StatementValue] = Field(default_factory=list)


class FinancialStatementMatrix(BaseModel):
    income_statement: List[StatementRow] = Field(default_factory=list)
    balance_sheet: List[StatementRow] = Field(default_factory=list)
    cash_flow: List[StatementRow] = Field(default_factory=list)


class DiagnosticModel(BaseModel):
    name: str
    score: Optional[Union[float, int]] = None
    zone: Optional[str] = None
    available: bool = True
    reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class EquityForensics(BaseModel):
    altman_z: DiagnosticModel
    piotroski_f: DiagnosticModel
    beneish_m: DiagnosticModel
    sloan_accruals: DiagnosticModel


class EquityProfile(BaseModel):
    cik: Optional[str] = None
    sic: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    financials: FinancialStatementMatrix
    forensics: EquityForensics


# ============================================================
# ETF
# ============================================================


class ETFHolding(BaseModel):
    symbol: Optional[str] = None
    name: str
    weight_pct: float
    sector: Optional[str] = None


class SectorWeight(BaseModel):
    sector: str
    weight_pct: float


class ETFProfile(BaseModel):
    fund_aum: Optional[float] = None
    expense_ratio_pct: Optional[float] = None
    replication_method: Optional[str] = None
    tracking_error_1y_pct: Optional[float] = None
    rebalance_schedule: Optional[str] = None
    top_holdings: List[ETFHolding] = Field(default_factory=list)
    sector_exposure: List[SectorWeight] = Field(default_factory=list)


# ============================================================
# COMMODITY
# ============================================================


class CommodityProfile(BaseModel):
    commodity_name: str
    exposure_symbol: Optional[str] = None
    exposure_method: str
    physical_backing_standard: Optional[str] = None
    vault_custodian: Optional[str] = None
    gold_silver_ratio: Optional[float] = None
    real_yield_correlation_3y: Optional[float] = None
    inflation_beta_10y: Optional[float] = None
    futures_curve_regime: Literal["CONTANGO", "BACKWARDATION", "FLAT", "UNKNOWN"] = "UNKNOWN"
    front_month_price: Optional[float] = None
    next_month_price: Optional[float] = None
    implied_roll_yield_pct: Optional[float] = None
    central_bank_reserve_trend: Optional[str] = None


# ============================================================
# CRYPTO
# ============================================================


class CryptoProfile(BaseModel):
    coin_id: Optional[str] = None
    circulating_supply: Optional[float] = None
    max_supply: Optional[float] = None
    hard_cap: Optional[bool] = None
    consensus_mechanism: Optional[str] = None
    ath_price: Optional[float] = None
    ath_drawdown_pct: Optional[float] = None
    realized_vol_30d_annualized: Optional[float] = None
    trades_24_7: bool = True


# ============================================================
# FOREX
# ============================================================


class ForexProfile(BaseModel):
    base_currency: str
    quote_currency: str
    base_policy_rate_pct: Optional[float] = None
    quote_policy_rate_pct: Optional[float] = None
    interest_rate_differential_pct: Optional[float] = None
    annualized_carry_pct: Optional[float] = None
    base_central_bank_cycle: Optional[str] = None
    quote_central_bank_cycle: Optional[str] = None


# ============================================================
# DISCRIMINATED PAYLOADS
# ============================================================


class AssetPayloadBase(BaseModel):
    symbol: str
    name: str
    asset_type: AssetType
    instrument_type: InstrumentType
    quote: MarketQuote
    sources: List[SourceStamp] = Field(default_factory=list)


class EquityAssetPayload(AssetPayloadBase):
    asset_type: Literal[AssetType.EQUITY] = AssetType.EQUITY
    profile: EquityProfile


class ETFAssetPayload(AssetPayloadBase):
    asset_type: Literal[AssetType.ETF] = AssetType.ETF
    profile: ETFProfile


class CommodityAssetPayload(AssetPayloadBase):
    asset_type: Literal[AssetType.COMMODITY] = AssetType.COMMODITY
    profile: CommodityProfile


class CryptoAssetPayload(AssetPayloadBase):
    asset_type: Literal[AssetType.CRYPTO] = AssetType.CRYPTO
    profile: CryptoProfile


class ForexAssetPayload(AssetPayloadBase):
    asset_type: Literal[AssetType.FOREX] = AssetType.FOREX
    profile: ForexProfile


AssetPayload = Annotated[
    Union[
        EquityAssetPayload,
        ETFAssetPayload,
        CommodityAssetPayload,
        CryptoAssetPayload,
        ForexAssetPayload,
    ],
    Field(discriminator="asset_type"),
]
