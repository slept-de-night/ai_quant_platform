from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class PositionSizeResult:
    side: str
    quantity: int
    signed_quantity: int
    notional: float
    equity_fraction: float
    full_kelly_fraction: float
    half_kelly_fraction: float
    signal_strength: float
    realized_vol_daily: float
    realized_vol_annualized: float
    target_vol_annualized: float
    volatility_scale: float
    raw_position_fraction: float
    capped_position_fraction: float
    max_position_fraction: float
    cash_reserve_fraction: float
    capped_by_position_limit: bool


class DynamicPositionSizer:
    """Dynamic institutional position sizing.

    Implements:
    1. Half-Kelly Criterion: f* = 0.5 * (p - (1-p)/b)
    2. Realized Volatility Targeting: scale inversely to target annual volatility (e.g. 15%)
    3. Hard pre-trade limits: max position fraction (8%), cash reserve (10%).
    """

    def __init__(
        self,
        *,
        target_annual_vol: float = 0.15,
        max_position_pct: float = 0.08,
        cash_reserve_pct: float = 0.10,
        trading_days: int = 252,
    ) -> None:
        if not 0 < target_annual_vol < 1:
            raise ValueError("target_annual_vol must be between 0 and 1")
        if not 0 < max_position_pct <= 1:
            raise ValueError("max_position_pct must be in (0, 1]")
        if not 0 <= cash_reserve_pct < 1:
            raise ValueError("cash_reserve_pct must be in [0, 1)")
        if max_position_pct > (1.0 - cash_reserve_pct):
            raise ValueError("max_position_pct exceeds deployable capital")
        if trading_days <= 0:
            raise ValueError("trading_days must be positive")

        self.target_annual_vol = target_annual_vol
        self.max_position_pct = max_position_pct
        self.cash_reserve_pct = cash_reserve_pct
        self.trading_days = trading_days

    @staticmethod
    def _validate_finite(name: str, value: float) -> float:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return value

    def calculate_size(
        self,
        signal_score: float,
        equity: float,
        reference_price: float,
        realized_vol_20d: float,
        win_rate: float = 0.55,
        payoff_ratio: float = 1.6,
    ) -> Dict[str, Any]:
        signal_score = self._validate_finite("signal_score", signal_score)
        equity = self._validate_finite("equity", equity)
        reference_price = self._validate_finite("reference_price", reference_price)
        realized_vol_20d = self._validate_finite("realized_vol_20d", realized_vol_20d)
        win_rate = self._validate_finite("win_rate", win_rate)
        payoff_ratio = self._validate_finite("payoff_ratio", payoff_ratio)

        if equity <= 0:
            raise ValueError("equity must be > 0")
        if reference_price <= 0:
            raise ValueError("reference_price must be > 0")
        if realized_vol_20d <= 0:
            realized_vol_20d = 0.015  # 1.5% fallback daily vol
        if not 0 <= win_rate <= 1:
            raise ValueError("win_rate must be between 0 and 1")
        if payoff_ratio <= 0:
            raise ValueError("payoff_ratio must be > 0")

        # Flat signal => 0 position
        if signal_score == 0:
            return asdict(
                PositionSizeResult(
                    side="FLAT",
                    quantity=0,
                    signed_quantity=0,
                    notional=0.0,
                    equity_fraction=0.0,
                    full_kelly_fraction=0.0,
                    half_kelly_fraction=0.0,
                    signal_strength=0.0,
                    realized_vol_daily=realized_vol_20d,
                    realized_vol_annualized=realized_vol_20d * math.sqrt(self.trading_days),
                    target_vol_annualized=self.target_annual_vol,
                    volatility_scale=0.0,
                    raw_position_fraction=0.0,
                    capped_position_fraction=0.0,
                    max_position_fraction=self.max_position_pct,
                    cash_reserve_fraction=self.cash_reserve_pct,
                    capped_by_position_limit=False,
                )
            )

        # 1. Kelly criterion: f* = p - q / b
        q = 1.0 - win_rate
        full_kelly = max(0.0, win_rate - q / payoff_ratio)
        half_kelly = 0.5 * full_kelly

        # 2. Signal confidence
        signal_strength = min(abs(signal_score), 1.0)

        # 3. Volatility targeting
        realized_annual_vol = realized_vol_20d * math.sqrt(self.trading_days)
        volatility_scale = self.target_annual_vol / max(realized_annual_vol, 0.01)

        # 4. Combined raw sizing fraction
        raw_position_fraction = half_kelly * signal_strength * volatility_scale

        # 5. Hard pre-trade risk limits
        deployable_fraction = 1.0 - self.cash_reserve_pct
        hard_fraction_limit = min(self.max_position_pct, deployable_fraction)
        position_fraction = min(raw_position_fraction, hard_fraction_limit)

        # 6. Convert into executable quantity
        notional_budget = equity * position_fraction
        quantity = math.floor(notional_budget / reference_price)
        notional = quantity * reference_price
        actual_fraction = notional / equity
        side = "LONG" if signal_score > 0 else "SHORT"
        signed_quantity = quantity if signal_score > 0 else -quantity

        result = PositionSizeResult(
            side=side,
            quantity=quantity,
            signed_quantity=signed_quantity,
            notional=notional,
            equity_fraction=actual_fraction,
            full_kelly_fraction=full_kelly,
            half_kelly_fraction=half_kelly,
            signal_strength=signal_strength,
            realized_vol_daily=realized_vol_20d,
            realized_vol_annualized=realized_annual_vol,
            target_vol_annualized=self.target_annual_vol,
            volatility_scale=volatility_scale,
            raw_position_fraction=raw_position_fraction,
            capped_position_fraction=position_fraction,
            max_position_fraction=self.max_position_pct,
            cash_reserve_fraction=self.cash_reserve_pct,
            capped_by_position_limit=(raw_position_fraction > hard_fraction_limit),
        )
        return asdict(result)
