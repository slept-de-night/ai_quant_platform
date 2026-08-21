from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from .facts import ResearchFact
from .pit import PITObservation, PITStore


@dataclass(frozen=True)
class QuantSnapshot:
    """Immutable point-in-time market and feature snapshot with cryptographic provenance.
    
    Attributes:
        decision_time: Exact timestamp of the decision.
        observations: Immutable list of observations known at or before decision_time.
        snapshot_id: Deterministic SHA256 hash of decision_time and observation content hashes.
    """
    decision_time: datetime
    observations: List[PITObservation]
    snapshot_id: str

    @classmethod
    def create(
        cls,
        decision_time: datetime,
        observations: List[PITObservation],
    ) -> QuantSnapshot:
        # Sort observations by observation_id to ensure deterministic hashing
        sorted_obs = sorted(observations, key=lambda x: (x.symbol, x.feature_name, x.effective_at, x.observation_id))
        
        hasher = hashlib.sha256()
        hasher.update(decision_time.isoformat().encode("utf-8"))
        for obs in sorted_obs:
            hasher.update(obs.content_hash.encode("utf-8"))
        snapshot_id = hasher.hexdigest()

        return cls(
            decision_time=decision_time,
            observations=sorted_obs,
            snapshot_id=snapshot_id,
        )

    def get_feature(self, symbol: str, feature_name: str) -> Optional[Any]:
        """Query the latest known value of a feature within this snapshot."""
        symbol = symbol.upper().strip()
        matches = [
            obs for obs in self.observations
            if obs.symbol == symbol and obs.feature_name == feature_name
        ]
        if not matches:
            return None
        # Sort by effective_at ascending, take latest
        matches.sort(key=lambda x: x.effective_at)
        return matches[-1].value

    def get_series(self, symbol: str, feature_name: str) -> List[tuple[datetime, Any]]:
        """Query historical time-series of a feature within this snapshot."""
        symbol = symbol.upper().strip()
        matches = [
            obs for obs in self.observations
            if obs.symbol == symbol and obs.feature_name == feature_name
        ]
        matches.sort(key=lambda x: x.effective_at)
        return [(m.effective_at, m.value) for m in matches]


class SnapshotResolver:
    """Resolves point-in-time QuantSnapshot from a PITStore."""

    def __init__(self, pit_store: PITStore):
        self.store = pit_store

    def build_snapshot(
        self,
        symbols: List[str],
        decision_time: datetime,
    ) -> QuantSnapshot:
        all_obs: List[PITObservation] = []
        for sym in symbols:
            obs = self.store.get_known_at(sym, as_of_time=decision_time)
            all_obs.extend(obs)
        return QuantSnapshot.create(decision_time=decision_time, observations=all_obs)


class ResearchSnapshot(BaseModel):
    """Immutable per-run research snapshot bundling structured facts and raw market contexts.

    Guarantees that within a single research DAG run:
    1. Market data and external sources are fetched once.
    2. All downstream deterministic handlers share identical point-in-time inputs.
    3. Facts are partitioned by category and queryable with zero lookahead.
    """

    snapshot_id: str
    run_id: str
    symbol: str
    as_of: datetime

    dataset_versions: Dict[str, str] = Field(default_factory=dict)
    source_refs: Dict[str, str] = Field(default_factory=dict)
    content_hash: str

    facts: List[ResearchFact] = Field(default_factory=list)
    market_bars: Dict[str, Any] = Field(default_factory=dict)
    sec_snapshot: Optional[Any] = None
    macro_snapshot: Optional[Any] = None

    def get_fact(self, category: str, key: str, symbol: Optional[str] = None) -> Optional[ResearchFact]:
        sym = symbol.upper().strip() if symbol is not None else None
        for f in self.facts:
            if f.category == category and f.key == key:
                if sym is None:
                    return f
                elif f.symbol and f.symbol.upper().strip() == sym:
                    return f
        return None

    def get_facts_by_category(self, category: str) -> List[ResearchFact]:
        return [f for f in self.facts if f.category == category]

    def get_bars(self, symbol: str) -> Optional[Any]:
        return self.market_bars.get(symbol.upper().strip())

    def to_pit_observations(self) -> List[PITObservation]:
        obs_list: List[PITObservation] = []
        for f in self.facts:
            obs_list.append(
                PITObservation(
                    observation_id=f.fact_id,
                    symbol=f.symbol or self.symbol,
                    feature_name=f"{f.category}:{f.key}",
                    value=f.value,
                    effective_at=f.observed_at,
                    known_at=f.known_at,
                    dataset_version=f.dataset_version or "v1.0",
                )
            )
        return obs_list


class ResearchSnapshotBuilder:
    """Builds a deterministic, immutable ResearchSnapshot once per research run."""

    def __init__(
        self,
        data_loader: Callable[[str, int], Any],
        sec_client: Optional[Any] = None,
        fred_client: Optional[Any] = None,
    ):
        self.data_loader = data_loader
        self.sec_client = sec_client
        self.fred_client = fred_client

    def build(
        self,
        symbol: str,
        run_id: str,
        as_of: Optional[datetime] = None,
        benchmarks: Optional[List[str]] = None,
    ) -> ResearchSnapshot:
        symbol = symbol.upper().strip()
        as_of = as_of or datetime.now(timezone.utc)
        benchmarks = [b.upper().strip() for b in (benchmarks or ["SPY", "QQQ", "TLT", "GLD"])]

        market_bars: Dict[str, Any] = {}
        facts: List[ResearchFact] = []
        dataset_versions: Dict[str, str] = {"market": "v1.0", "engine": "v1.3"}
        source_refs: Dict[str, str] = {}

        # 1. Load target symbol bars
        try:
            target_bars = self.data_loader(symbol, 1000)
            market_bars[symbol] = target_bars
            source_refs[f"market:{symbol}"] = f"data_loader({symbol},1000)"
        except Exception:
            target_bars = None

        # 2. Load benchmark bars
        for b in benchmarks:
            if b not in market_bars:
                try:
                    bars = self.data_loader(b, 1000)
                    market_bars[b] = bars
                    source_refs[f"market:{b}"] = f"data_loader({b},1000)"
                except Exception:
                    pass

        # 3. Extract Market & Technical facts for target symbol
        if target_bars is not None and hasattr(target_bars, "empty") and not target_bars.empty:
            last_bar = target_bars.iloc[-1]
            obs_time = getattr(last_bar, "name", as_of)
            if not isinstance(obs_time, datetime):
                obs_time = as_of
            elif obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)

            close_val = float(last_bar.get("close", 0.0))
            vol_val = float(last_bar.get("volume", 0.0))

            facts.append(
                ResearchFact(
                    fact_id=f"mkt-{symbol}-close",
                    symbol=symbol,
                    category="market",
                    key="close",
                    value=close_val,
                    observed_at=obs_time,
                    known_at=obs_time,
                    as_of=as_of,
                    source_type="market_data",
                    source_id=symbol,
                )
            )
            facts.append(
                ResearchFact(
                    fact_id=f"mkt-{symbol}-volume",
                    symbol=symbol,
                    category="market",
                    key="volume",
                    value=vol_val,
                    observed_at=obs_time,
                    known_at=obs_time,
                    as_of=as_of,
                    source_type="market_data",
                    source_id=symbol,
                )
            )

            # Compute technical analysis
            try:
                from ..intelligence.technical import analyze_technical
                tech_view = analyze_technical(target_bars)
                facts.append(
                    ResearchFact(
                        fact_id=f"tech-{symbol}-directional-score",
                        symbol=symbol,
                        category="technical",
                        key="directional_score",
                        value=tech_view.score,
                        observed_at=obs_time,
                        known_at=obs_time,
                        as_of=as_of,
                        source_type="derived_technical",
                        confidence=tech_view.confidence,
                    )
                )
                facts.append(
                    ResearchFact(
                        fact_id=f"tech-{symbol}-trend",
                        symbol=symbol,
                        category="technical",
                        key="trend",
                        value=tech_view.trend,
                        observed_at=obs_time,
                        known_at=obs_time,
                        as_of=as_of,
                        source_type="derived_technical",
                        confidence=tech_view.confidence,
                    )
                )
            except Exception:
                pass

        # 4. Extract SEC Fundamental facts
        sec_snapshot = None
        if self.sec_client:
            try:
                sec_snapshot = self.sec_client.snapshot(symbol)
                dataset_versions["sec"] = "sec-xbrl-v1"
                source_refs["fundamental:sec"] = f"sec_facts({symbol})"
                if hasattr(sec_snapshot, "annual_reports") and sec_snapshot.annual_reports:
                    latest_report = sec_snapshot.annual_reports[-1]
                    try:
                        rep_date = datetime.strptime(latest_report.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except Exception:
                        rep_date = as_of
                    facts.append(
                        ResearchFact(
                            fact_id=f"fund-{symbol}-revenue-growth-yoy",
                            symbol=symbol,
                            category="fundamental",
                            key="revenue_growth_yoy",
                            value=latest_report.revenue_growth_yoy,
                            observed_at=rep_date,
                            known_at=rep_date,
                            as_of=as_of,
                            source_type="sec_edgar",
                            source_id=f"CIK-{getattr(sec_snapshot, 'cik', '')}",
                        )
                    )
                    facts.append(
                        ResearchFact(
                            fact_id=f"fund-{symbol}-net-margin",
                            symbol=symbol,
                            category="fundamental",
                            key="net_margin",
                            value=latest_report.net_margin,
                            observed_at=rep_date,
                            known_at=rep_date,
                            as_of=as_of,
                            source_type="sec_edgar",
                            source_id=f"CIK-{getattr(sec_snapshot, 'cik', '')}",
                        )
                    )
            except Exception:
                sec_snapshot = None

        # 5. Extract FRED Macro facts
        macro_snapshot = None
        if self.fred_client:
            try:
                macro_snapshot = self.fred_client.snapshot()
                dataset_versions["macro"] = "fred-v1"
                source_refs["macro:fred"] = "fred_snapshot()"
                if getattr(macro_snapshot, "treasury_10y", None) is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-treasury-10y",
                            symbol=None,
                            category="macro",
                            key="treasury_10y",
                            value=macro_snapshot.treasury_10y,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
                if getattr(macro_snapshot, "fed_funds", None) is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-fed-funds",
                            symbol=None,
                            category="macro",
                            key="fed_funds_rate",
                            value=macro_snapshot.fed_funds,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
                if getattr(macro_snapshot, "cpi_yoy", None) is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-cpi-yoy",
                            symbol=None,
                            category="macro",
                            key="cpi_yoy",
                            value=macro_snapshot.cpi_yoy,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
                unemp = getattr(macro_snapshot, "unemployment", None) or getattr(macro_snapshot, "unemployment_rate", None)
                if unemp is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-unemployment-rate",
                            symbol=None,
                            category="macro",
                            key="unemployment_rate",
                            value=unemp,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
                if getattr(macro_snapshot, "yield_curve_10y2y", None) is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-yield-curve-10y2y",
                            symbol=None,
                            category="macro",
                            key="yield_curve_10y2y",
                            value=macro_snapshot.yield_curve_10y2y,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
                if getattr(macro_snapshot, "industrial_production_yoy", None) is not None:
                    facts.append(
                        ResearchFact(
                            fact_id="macro-industrial-production-yoy",
                            symbol=None,
                            category="macro",
                            key="industrial_production_yoy",
                            value=macro_snapshot.industrial_production_yoy,
                            observed_at=as_of,
                            known_at=as_of,
                            as_of=as_of,
                            source_type="fred",
                        )
                    )
            except Exception:
                macro_snapshot = None

        # Sort facts deterministically
        sorted_facts = sorted(facts, key=lambda f: (f.category, f.key, f.symbol or "", f.fact_id))

        # Compute cryptographic content hash
        hasher = hashlib.sha256()
        hasher.update(f"{run_id}:{symbol}:{as_of.isoformat()}".encode("utf-8"))
        for f in sorted_facts:
            hasher.update(f.content_hash.encode("utf-8"))
        content_hash = hasher.hexdigest()
        snapshot_id = f"snap-{content_hash[:16]}"

        return ResearchSnapshot(
            snapshot_id=snapshot_id,
            run_id=run_id,
            symbol=symbol,
            as_of=as_of,
            dataset_versions=dataset_versions,
            source_refs=source_refs,
            content_hash=content_hash,
            facts=sorted_facts,
            market_bars=market_bars,
            sec_snapshot=sec_snapshot,
            macro_snapshot=macro_snapshot,
        )
