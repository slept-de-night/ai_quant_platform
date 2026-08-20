from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
import requests

from ..data.market_data import validate_bars
from .models import Direction, MacroSnapshot, TrendView


def _ret(bars: pd.DataFrame, n: int) -> float:
    b = validate_bars(bars)
    if len(b) <= n:
        return 0.0
    return float(b["close"].iloc[-1] / b["close"].iloc[-1 - n] - 1)


def _dir(score: float) -> Direction:
    if score >= 0.55:
        return Direction.STRONG_BULLISH
    if score >= 0.15:
        return Direction.BULLISH
    if score <= -0.55:
        return Direction.STRONG_BEARISH
    if score <= -0.15:
        return Direction.BEARISH
    return Direction.NEUTRAL


def analyze_microtrend(
    symbol_bars: pd.DataFrame,
    sector_bars: Optional[pd.DataFrame] = None,
    market_bars: Optional[pd.DataFrame] = None,
) -> TrendView:
    """Analyze medium-term relative performance and sector leadership."""
    r20 = _ret(symbol_bars, 20)
    r60 = _ret(symbol_bars, 60)
    r120 = _ret(symbol_bars, 120)

    drivers = [f"symbol 20d {r20:+.1%}", f"symbol 60d {r60:+.1%}", f"symbol 120d {r120:+.1%}"]
    terms = [np.tanh(r20 * 6) * 0.25, np.tanh(r60 * 4) * 0.35, np.tanh(r120 * 3) * 0.40]
    conf = 0.55

    if sector_bars is not None:
        sr60 = _ret(sector_bars, 60)
        sr120 = _ret(sector_bars, 120)
        terms.extend([np.tanh((r60 - sr60) * 5) * 0.25, np.tanh((r120 - sr120) * 4) * 0.25])
        drivers.extend([f"60d relative to sector {r60-sr60:+.1%}", f"120d relative to sector {r120-sr120:+.1%}"])
        conf += 0.15

    if market_bars is not None:
        mr120 = _ret(market_bars, 120)
        terms.append(np.tanh((r120 - mr120) * 4) * 0.20)
        drivers.append(f"120d relative to market {r120-mr120:+.1%}")
        conf += 0.10

    score = float(np.clip(sum(terms) / max(sum(abs(x) > 0 for x in terms), 1) * 2.0, -1, 1))
    regime = "leadership" if score > 0.25 else "lagging" if score < -0.25 else "mixed/transition"
    risks = []
    if abs(r20) > 0.15:
        risks.append("short-horizon move is unusually large and may mean-revert")

    return TrendView(
        horizon="weeks to months",
        score=score,
        confidence=min(0.85, conf),
        direction=_dir(score),
        regime=regime,
        drivers=drivers,
        risks=risks,
    )


class FREDClient:
    """Federal Reserve Economic Data (FRED) API client."""

    def __init__(self, api_key: str, timeout: int = 20):
        self.api_key = api_key
        self.timeout = timeout

    def series(self, series_id: str, limit: int = 80) -> List[Tuple[str, float]]:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        out = []
        for x in reversed(r.json().get("observations", [])):
            try:
                out.append((x["date"], float(x["value"])))
            except Exception:
                pass
        return out

    def snapshot(self) -> MacroSnapshot:
        fed = self.series("FEDFUNDS", 24)
        un = self.series("UNRATE", 24)
        ip = self.series("INDPRO", 24)
        cpi = self.series("CPIAUCSL", 24)
        yc = self.series("T10Y2Y", 24)

        def latest(x):
            return x[-1][1] if x else None

        def yoy(x):
            return x[-1][1] / x[-13][1] - 1 if len(x) >= 13 and x[-13][1] != 0 else None

        dates = [x[-1][0] for x in [fed, un, ip, cpi, yc] if x]
        return MacroSnapshot(
            fed_funds=latest(fed),
            unemployment=latest(un),
            industrial_production_yoy=yoy(ip),
            cpi_yoy=yoy(cpi),
            yield_curve_10y2y=latest(yc),
            as_of=max(dates) if dates else None,
        )


def analyze_megatrend(
    market_bars: pd.DataFrame,
    growth_bars: Optional[pd.DataFrame] = None,
    bond_bars: Optional[pd.DataFrame] = None,
    gold_bars: Optional[pd.DataFrame] = None,
    macro: Optional[MacroSnapshot] = None,
) -> TrendView:
    """Analyze multi-year cross-asset macro trend regimes."""
    m120 = _ret(market_bars, 120)
    m252 = _ret(market_bars, 252)
    drivers = [f"market 120d {m120:+.1%}", f"market 252d {m252:+.1%}"]
    score = np.tanh(m120 * 3) * 0.25 + np.tanh(m252 * 2) * 0.35
    weight = 0.60
    risks = []

    if growth_bars is not None:
        g252 = _ret(growth_bars, 252)
        rel = g252 - m252
        score += np.tanh(rel * 3) * 0.15
        weight += 0.15
        drivers.append(f"growth vs market 252d {rel:+.1%}")

    if bond_bars is not None:
        b120 = _ret(bond_bars, 120)
        score += np.tanh(b120 * 3) * 0.10
        weight += 0.10
        drivers.append(f"long-duration bonds 120d {b120:+.1%}")

    if gold_bars is not None:
        gd120 = _ret(gold_bars, 120)
        drivers.append(f"gold 120d {gd120:+.1%}")
        if gd120 > 0.15 and m120 < 0:
            risks.append("defensive cross-asset leadership")

    if macro is not None:
        if macro.industrial_production_yoy is not None:
            score += np.tanh(macro.industrial_production_yoy * 8) * 0.10
            weight += 0.10
            drivers.append(f"industrial production YoY {macro.industrial_production_yoy:+.1%}")
        if macro.cpi_yoy is not None:
            drivers.append(f"CPI YoY {macro.cpi_yoy:+.1%}")
        if macro.yield_curve_10y2y is not None:
            drivers.append(f"10y-2y spread {macro.yield_curve_10y2y:+.2f}pp")
            if macro.yield_curve_10y2y < 0:
                risks.append("yield curve inversion")

    score = float(np.clip(score / max(weight, 0.01), -1, 1))
    conf = 0.65 if macro is None else 0.78
    regime = (
        "risk-on/secular expansion"
        if score > 0.25
        else "defensive/contractionary"
        if score < -0.25
        else "mixed macro transition"
    )
    return TrendView(
        horizon="months to years",
        score=score,
        confidence=conf,
        direction=_dir(score),
        regime=regime,
        drivers=drivers,
        risks=risks,
    )
