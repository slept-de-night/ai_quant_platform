from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import pytest

from ai_quant.runtime.facts import ResearchFact
from ai_quant.runtime.snapshot import (
    ResearchSnapshot,
    ResearchSnapshotBuilder,
    SourceState,
    SourceStatus,
)


def _generate_bars_range(start: str, periods: int) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="D", tz=timezone.utc)
    prices = [100.0 + i for i in range(periods)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [100000.0] * periods,
        },
        index=dates,
    )


class MockPITSECClient:
    def __init__(self, reports: List[Any]):
        self.reports = reports

    def snapshot(self, symbol: str, as_of: Optional[datetime] = None) -> Any:
        return SimpleNamespace(
            symbol=symbol.upper(),
            cik=1045810,
            annual_reports=self.reports,
        )


class MockPITFREDClient:
    def __init__(self, supports_pit: bool = False):
        self.supports_pit = supports_pit

    def snapshot(self, as_of: Optional[datetime] = None) -> Any:
        return SimpleNamespace(
            treasury_10y=4.25,
            fed_funds=5.25,
            cpi_yoy=2.8,
            unemployment=4.0,
            yield_curve_10y2y=0.20,
            industrial_production_yoy=0.015,
        )


def test_sec_filing_point_in_time_availability():
    """SEC filing with period end Jan 1 and public acceptance Feb 15:
    - as_of Feb 1 -> INVISIBLE (source UNAVAILABLE, no future facts).
    - as_of Feb 16 -> VISIBLE (observed_at=Jan 1, known_at=Feb 15).
    """
    report = SimpleNamespace(
        fiscal_year=2024,
        end_date="2025-01-01",
        filing_date="2025-02-15",
        revenue_growth_yoy=0.25,
        net_margin=0.30,
    )
    sec_client = MockPITSECClient([report])

    def dummy_loader(sym: str, limit: int = 1000, as_of: Optional[datetime] = None) -> pd.DataFrame:
        return _generate_bars_range("2025-01-01", 10)

    builder = ResearchSnapshotBuilder(
        data_loader=dummy_loader,
        sec_client=sec_client,
    )

    # 1. As of Feb 1, 2025 (before filing acceptance on Feb 15)
    t_before = datetime(2025, 2, 1, 12, 0, tzinfo=timezone.utc)
    snap_before = builder.build("NVDA", "run-before", as_of=t_before)

    assert snap_before.source_status["sec"].status == SourceState.UNAVAILABLE
    assert snap_before.get_fact("fundamental", "revenue_growth_yoy") is None
    assert snap_before.get_fact("fundamental", "net_margin") is None

    # 2. As of Feb 16, 2025 (after filing acceptance)
    t_after = datetime(2025, 2, 16, 12, 0, tzinfo=timezone.utc)
    snap_after = builder.build("NVDA", "run-after", as_of=t_after)

    assert snap_after.source_status["sec"].status == SourceState.AVAILABLE
    fact_rev = snap_after.get_fact("fundamental", "revenue_growth_yoy")
    assert fact_rev is not None
    assert fact_rev.value == 0.25
    assert fact_rev.observed_at == datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert fact_rev.known_at == datetime(2025, 2, 15, 0, 0, tzinfo=timezone.utc)


def test_sec_restatement_point_in_time_resolution():
    """Original 10-K filed Feb 15 with net_margin 0.20.
    10-K/A Restatement filed Apr 20 with net_margin 0.15.
    - as_of Mar 1 -> Sees original (0.20).
    - as_of May 1 -> Sees restated (0.15).
    """
    original_report = SimpleNamespace(
        fiscal_year=2024,
        end_date="2024-12-31",
        filing_date="2025-02-15",
        revenue_growth_yoy=0.18,
        net_margin=0.20,
    )
    restated_report = SimpleNamespace(
        fiscal_year=2024,
        end_date="2024-12-31",
        filing_date="2025-04-20",
        revenue_growth_yoy=0.18,
        net_margin=0.15,
    )
    sec_client = MockPITSECClient([original_report, restated_report])

    def dummy_loader(sym: str, limit: int = 1000, as_of: Optional[datetime] = None) -> pd.DataFrame:
        return _generate_bars_range("2025-01-01", 10)

    builder = ResearchSnapshotBuilder(
        data_loader=dummy_loader,
        sec_client=sec_client,
    )

    # 1. As of Mar 1, 2025: sees original 0.20
    snap_mar = builder.build("AAPL", "run-mar", as_of=datetime(2025, 3, 1, 0, 0, tzinfo=timezone.utc))
    assert snap_mar.get_fact("fundamental", "net_margin").value == 0.20

    # 2. As of May 1, 2025: sees restated 0.15
    snap_may = builder.build("AAPL", "run-may", as_of=datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc))
    assert snap_may.get_fact("fundamental", "net_margin").value == 0.15


def test_market_future_bars_excluded():
    """Market bars spanning Jan 1 to Mar 1 must be strictly truncated at as_of."""
    all_bars = _generate_bars_range("2025-01-01", 60)  # Jan 1 to Mar 1

    def full_loader(sym: str, limit: int = 1000, as_of: Optional[datetime] = None) -> pd.DataFrame:
        # returns full bars regardless to verify builder filtering
        return all_bars

    builder = ResearchSnapshotBuilder(data_loader=full_loader)
    t_as_of = datetime(2025, 1, 20, 0, 0, tzinfo=timezone.utc)
    snap = builder.build("MSFT", "run-mkt", as_of=t_as_of)

    msft_bars = snap.get_bars("MSFT")
    assert msft_bars is not None
    assert msft_bars.index.max() <= t_as_of
    assert snap.get_fact("market", "close").observed_at <= t_as_of


def test_macro_vintage_and_not_pit_capable():
    """Historical run with client lacking vintage reconstruction is marked NOT_PIT_CAPABLE."""
    fred_unsupported = MockPITFREDClient(supports_pit=False)

    def dummy_loader(sym: str, limit: int = 1000, as_of: Optional[datetime] = None) -> pd.DataFrame:
        return _generate_bars_range("2024-01-01", 10)

    builder = ResearchSnapshotBuilder(
        data_loader=dummy_loader,
        fred_client=fred_unsupported,
    )

    t_hist = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    snap_hist = builder.build("SPY", "run-hist", as_of=t_hist)

    assert snap_hist.source_status["macro:fred"].status == SourceState.NOT_PIT_CAPABLE
    assert snap_hist.get_fact("macro", "fed_funds_rate") is None

    # Modern run (today) is allowed AVAILABLE
    t_now = datetime.now(timezone.utc)
    snap_now = builder.build("SPY", "run-now", as_of=t_now)
    assert snap_now.source_status["macro:fred"].status == SourceState.AVAILABLE
    assert snap_now.get_fact("macro", "fed_funds_rate").value == 5.25


def test_source_failure_recording():
    """Exceptions during source fetch record SourceState.ERROR rather than silent success."""
    class FailingSECClient:
        def snapshot(self, symbol: str, as_of: Optional[datetime] = None) -> Any:
            raise ConnectionError("SEC EDGAR gateway timeout 504")

    def dummy_loader(sym: str, limit: int = 1000, as_of: Optional[datetime] = None) -> pd.DataFrame:
        return _generate_bars_range("2025-01-01", 5)

    builder = ResearchSnapshotBuilder(
        data_loader=dummy_loader,
        sec_client=FailingSECClient(),
    )

    snap = builder.build("NVDA", "run-err")
    assert snap.source_status["sec"].status == SourceState.ERROR
    assert "504" in (snap.source_status["sec"].message or "")


def test_missing_values_do_not_become_zero():
    """Missing or NaN market close/volume must never create fabricated 0.0 facts."""
    dates = pd.date_range("2025-01-01", periods=5, freq="D", tz=timezone.utc)
    df_missing = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [95.0, 96.0, 97.0, 98.0, 99.0],
            "close": [100.0, 101.0, 102.0, 103.0, np.nan],  # Last close is NaN
            "volume": [1000.0, 1000.0, 1000.0, 1000.0, None],  # Last volume is None
        },
        index=dates,
    )

    builder = ResearchSnapshotBuilder(
        data_loader=lambda s, limit=1000, as_of=None: df_missing,
    )
    snap = builder.build("NVDA", "run-nan")

    # Invariant: NO fake 0.0 close or volume facts
    close_fact = snap.get_fact("market", "close")
    assert close_fact is None

    vol_fact = snap.get_fact("market", "volume")
    assert vol_fact is None


def test_state_hash_separation_from_provenance():
    """Identical economic facts produce identical state_hash across different run_ids and query times."""
    bars = _generate_bars_range("2025-01-01", 20)

    report = SimpleNamespace(
        fiscal_year=2024,
        end_date="2024-12-31",
        filing_date="2025-02-15",
        revenue_growth_yoy=0.30,
        net_margin=0.35,
    )
    sec_client = MockPITSECClient([report])

    builder = ResearchSnapshotBuilder(
        data_loader=lambda s, limit=1000, as_of=None: bars,
        sec_client=sec_client,
    )

    t_as_of = datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc)

    # Run 1
    snap1 = builder.build("NVDA", run_id="run-alpha-001", as_of=t_as_of)

    # Run 2 on different run_id
    snap2 = builder.build("NVDA", run_id="run-beta-999", as_of=t_as_of)

    # Economic state hash is IDENTICAL
    assert snap1.state_hash == snap2.state_hash
    assert len(snap1.state_hash) == 64

    # Run provenance hash is DIFFERENT
    assert snap1.provenance_hash != snap2.provenance_hash

    # Run 3 with modified economic data produces DIFFERENT state_hash
    report_modified = SimpleNamespace(
        fiscal_year=2024,
        end_date="2024-12-31",
        filing_date="2025-02-15",
        revenue_growth_yoy=0.50,  # changed
        net_margin=0.35,
    )
    builder_mod = ResearchSnapshotBuilder(
        data_loader=lambda s, limit=1000, as_of=None: bars,
        sec_client=MockPITSECClient([report_modified]),
    )
    snap3 = builder_mod.build("NVDA", run_id="run-gamma-100", as_of=t_as_of)
    assert snap3.state_hash != snap1.state_hash
