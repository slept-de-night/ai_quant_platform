from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .snapshot import ResearchSnapshot


class ChangeCategory(str, Enum):
    PRICE_MOVE = "price_move"
    VOLUME_SHOCK = "volume_shock"
    FILING_DISCLOSURE = "filing_disclosure"
    MACRO_REGIME = "macro_regime"
    CONTRADICTION = "contradiction"
    STRUCTURAL = "structural"
    NONE = "none"


class ChangeItem(BaseModel):
    category: ChangeCategory
    field: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    delta: Optional[float] = None
    is_material: bool = False
    description: str


def _extract_bars(snapshot: ResearchSnapshot, symbol: str) -> List[Any]:
    if isinstance(snapshot.market_bars, dict):
        bars = snapshot.market_bars.get(symbol.upper().strip())
        if bars is None:
            bars = snapshot.market_bars.get(symbol)
        if bars is None:
            bars = []
    elif isinstance(snapshot.market_bars, list):
        bars = snapshot.market_bars
    else:
        bars = []
    if hasattr(bars, "to_dict"):
        return bars.to_dict(orient="records")
    return list(bars)


class ChangeSet(BaseModel):
    symbol: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_snapshot_hash: Optional[str] = None
    current_snapshot_hash: Optional[str] = None
    items: List[ChangeItem] = Field(default_factory=list)
    is_material: bool = False
    materiality_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)

    @classmethod
    def detect(
        cls,
        current: ResearchSnapshot,
        previous: Optional[ResearchSnapshot] = None,
        price_threshold: float = 0.015,
        volume_shock_threshold: float = 2.0,
    ) -> ChangeSet:
        """Detect deterministic changes and evaluate materiality between research snapshots."""
        items: List[ChangeItem] = []
        reasons: List[str] = []
        materiality = 0.0

        curr_hash = getattr(current, "content_hash", getattr(current, "snapshot_id", ""))

        if previous is None:
            # First observation is considered a baseline establishment
            return cls(
                symbol=current.symbol,
                previous_snapshot_hash=None,
                current_snapshot_hash=curr_hash,
                items=[
                    ChangeItem(
                        category=ChangeCategory.STRUCTURAL,
                        field="initial_snapshot",
                        old_value=None,
                        new_value=curr_hash,
                        is_material=True,
                        description="Initial baseline research snapshot established",
                    )
                ],
                is_material=True,
                materiality_score=0.5,
                reasons=["Initial baseline snapshot"],
            )

        prev_hash = getattr(previous, "content_hash", getattr(previous, "snapshot_id", ""))

        # 1. Price Move Detection
        curr_bars = _extract_bars(current, current.symbol)
        prev_bars = _extract_bars(previous, previous.symbol)
        if curr_bars and prev_bars:
            curr_close = curr_bars[-1].close if hasattr(curr_bars[-1], "close") else curr_bars[-1].get("close", 0.0)
            prev_close = prev_bars[-1].close if hasattr(prev_bars[-1], "close") else prev_bars[-1].get("close", 0.0)

            if prev_close > 0:
                ret = (curr_close - prev_close) / prev_close
                is_mat = abs(ret) >= price_threshold
                if is_mat:
                    materiality = max(materiality, min(1.0, abs(ret) * 10.0))
                    reasons.append(f"Price move {ret:+.2%} exceeds {price_threshold:.1%} threshold")
                items.append(
                    ChangeItem(
                        category=ChangeCategory.PRICE_MOVE,
                        field="close_price",
                        old_value=prev_close,
                        new_value=curr_close,
                        delta=ret,
                        is_material=is_mat,
                        description=f"Price moved from {prev_close:.2f} to {curr_close:.2f} ({ret:+.2%})",
                    )
                )

            # Volume Shock Detection
            curr_vol = curr_bars[-1].volume if hasattr(curr_bars[-1], "volume") else curr_bars[-1].get("volume", 0.0)
            prev_vols = [
                b.volume if hasattr(b, "volume") else b.get("volume", 0.0) for b in prev_bars[-20:]
            ]
            avg_vol = (sum(prev_vols) / len(prev_vols)) if prev_vols else 0.0
            if avg_vol > 0:
                vol_ratio = curr_vol / avg_vol
                is_shock = vol_ratio >= volume_shock_threshold
                if is_shock:
                    materiality = max(materiality, min(1.0, vol_ratio * 0.25))
                    reasons.append(f"Volume shock {vol_ratio:.1f}x exceeds {volume_shock_threshold:.1f}x baseline")
                items.append(
                    ChangeItem(
                        category=ChangeCategory.VOLUME_SHOCK,
                        field="volume",
                        old_value=avg_vol,
                        new_value=curr_vol,
                        delta=vol_ratio,
                        is_material=is_shock,
                        description=f"Volume {curr_vol:.0f} vs 20-bar avg {avg_vol:.0f} ({vol_ratio:.1f}x)",
                    )
                )

        # 2. Fundamental / SEC Filings Change
        curr_facts = {f.fact_id: f for f in current.facts}
        prev_facts = {f.fact_id: f for f in previous.facts}

        new_fact_ids = set(curr_facts.keys()) - set(prev_facts.keys())
        new_sec_facts = [
            curr_facts[fid] for fid in new_fact_ids
            if curr_facts[fid].source_type in {"sec_edgar", "SEC_EDGAR"} or curr_facts[fid].category in {"fundamental", "sec"}
        ]
        if new_sec_facts:
            materiality = max(materiality, 0.70)
            reasons.append(f"New SEC filing disclosures ({len(new_sec_facts)} new facts)")
            items.append(
                ChangeItem(
                    category=ChangeCategory.FILING_DISCLOSURE,
                    field="sec_filings",
                    old_value=None,
                    new_value=len(new_sec_facts),
                    is_material=True,
                    description=f"{len(new_sec_facts)} new SEC fact disclosures observed",
                )
            )

        # 3. Macro Regime Shifts
        if current.macro_snapshot and previous.macro_snapshot:
            curr_regime = current.macro_snapshot.get("regime") or current.macro_snapshot.get("cycle")
            prev_regime = previous.macro_snapshot.get("regime") or previous.macro_snapshot.get("cycle")
            if curr_regime and prev_regime and curr_regime != prev_regime:
                materiality = max(materiality, 0.65)
                reasons.append(f"Macro regime shifted from {prev_regime} to {curr_regime}")
                items.append(
                    ChangeItem(
                        category=ChangeCategory.MACRO_REGIME,
                        field="macro_regime",
                        old_value=prev_regime,
                        new_value=curr_regime,
                        is_material=True,
                        description=f"Macro regime shift from {prev_regime} to {curr_regime}",
                    )
                )

        is_mat = len(reasons) > 0 or materiality >= 0.30

        return cls(
            symbol=current.symbol,
            previous_snapshot_hash=prev_hash,
            current_snapshot_hash=curr_hash,
            items=items,
            is_material=is_mat,
            materiality_score=round(materiality, 4),
            reasons=reasons,
        )
