from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from .models import AssetType, InstrumentType


@dataclass(frozen=True)
class CommodityReference:
    commodity_name: str
    exposure_symbol: str
    exposure_method: str
    instrument_type: InstrumentType
    physical_backing_standard: Optional[str] = None
    vault_custodian: Optional[str] = None


COMMODITY_OVERRIDES: Dict[str, CommodityReference] = {
    "GLD": CommodityReference(
        commodity_name="Gold",
        exposure_symbol="GC=F",
        exposure_method="PHYSICAL_TRUST",
        instrument_type=InstrumentType.TRUST,
        physical_backing_standard="LBMA Gold Good Delivery",
        vault_custodian="HSBC Bank plc / JPMorgan Chase Bank, N.A.",
    ),
    "SLV": CommodityReference(
        commodity_name="Silver",
        exposure_symbol="SI=F",
        exposure_method="PHYSICAL_TRUST",
        instrument_type=InstrumentType.TRUST,
        physical_backing_standard="LBMA-eligible silver bullion",
        vault_custodian="JPMorgan Chase Bank N.A., London Branch",
    ),
    "USO": CommodityReference(
        commodity_name="WTI Crude Oil",
        exposure_symbol="CL=F",
        exposure_method="FUTURES",
        instrument_type=InstrumentType.ETP,
    ),
    "GC=F": CommodityReference(
        commodity_name="Gold",
        exposure_symbol="GC=F",
        exposure_method="FUTURES",
        instrument_type=InstrumentType.FUTURE,
    ),
    "SI=F": CommodityReference(
        commodity_name="Silver",
        exposure_symbol="SI=F",
        exposure_method="FUTURES",
        instrument_type=InstrumentType.FUTURE,
    ),
    "CL=F": CommodityReference(
        commodity_name="WTI Crude Oil",
        exposure_symbol="CL=F",
        exposure_method="FUTURES",
        instrument_type=InstrumentType.FUTURE,
    ),
}

CRYPTO_IDS: Dict[str, str] = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "BNB-USD": "binancecoin",
    "XRP-USD": "ripple",
    "DOGE-USD": "dogecoin",
    "ADA-USD": "cardano",
    "AVAX-USD": "avalanche-2",
}

CRYPTO_CONSENSUS: Dict[str, str] = {
    "BTC-USD": "Proof of Work (SHA-256)",
    "ETH-USD": "Proof of Stake",
    "SOL-USD": "Proof of Stake + Proof of History",
    "BNB-USD": "Proof of Staked Authority (PoSA)",
    "XRP-USD": "XRP Ledger Consensus Protocol",
    "DOGE-USD": "Proof of Work (Scrypt)",
    "ADA-USD": "Ouroboros Proof of Stake",
    "AVAX-USD": "Avalanche Snow Consensus",
}


def classify_asset(
    symbol: str,
    yahoo_quote_type: Optional[str],
) -> Tuple[AssetType, InstrumentType]:
    symbol = symbol.upper().strip()
    if symbol in COMMODITY_OVERRIDES:
        ref = COMMODITY_OVERRIDES[symbol]
        return AssetType.COMMODITY, ref.instrument_type

    quote_type = (yahoo_quote_type or "").upper()
    if quote_type in {"CRYPTOCURRENCY", "CRYPTO"}:
        return AssetType.CRYPTO, InstrumentType.CRYPTO

    if quote_type in {"CURRENCY"} or symbol.endswith("=X"):
        return AssetType.FOREX, InstrumentType.FX_SPOT

    if quote_type in {"FUTURE", "FUTURES"}:
        return AssetType.COMMODITY, InstrumentType.FUTURE

    if quote_type == "ETF":
        return AssetType.ETF, InstrumentType.ETF

    if quote_type in {"EQUITY", "STOCK"}:
        return AssetType.EQUITY, InstrumentType.STOCK

    # Suffix fallbacks are secondary to provider metadata.
    if symbol.endswith("-USD") or symbol in {"BTC", "ETH", "SOL", "BNB"}:
        return AssetType.CRYPTO, InstrumentType.CRYPTO

    if symbol.endswith("=F"):
        return AssetType.COMMODITY, InstrumentType.FUTURE

    return AssetType.EQUITY, InstrumentType.STOCK
