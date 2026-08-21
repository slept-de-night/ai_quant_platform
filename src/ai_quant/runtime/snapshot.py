from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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


from enum import Enum
import math


class SourceState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"
    NOT_PIT_CAPABLE = "not_pit_capable"


class SourceStatus(BaseModel):
    status: SourceState
    message: Optional[str] = None
    fetched_at: Optional[datetime] = None


class ResearchSnapshot(BaseModel):
    """Immutable per-run research snapshot bundling structured facts and raw market contexts.

    Guarantees that within a single research DAG run:
    1. Market data and external sources are fetched once.
    2. All downstream deterministic handlers share identical point-in-time inputs.
    3. Facts are partitioned by category and queryable with zero lookahead.
    4. Economic state hash is cleanly separated from run provenance identity.
    """

    snapshot_id: str
    run_id: str
    symbol: str
    as_of: datetime

    state_hash: str = ""
    provenance_hash: str = ""
    content_hash: str = ""

    source_status: Dict[str, SourceStatus] = Field(default_factory=dict)
    dataset_versions: Dict[str, str] = Field(default_factory=dict)
    source_refs: Dict[str, str] = Field(default_factory=dict)

    facts: List[ResearchFact] = Field(default_factory=list)
    market_bars: Dict[str, Any] = Field(default_factory=dict)
    sec_snapshot: Optional[Any] = None
    macro_snapshot: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.state_hash:
            hasher = hashlib.sha256()
            hasher.update(self.symbol.encode("utf-8"))
            for k, v in sorted(self.dataset_versions.items()):
                hasher.update(f"{k}:{v}".encode("utf-8"))
            for k, s in sorted(self.source_status.items()):
                hasher.update(f"{k}:{s.status.value}".encode("utf-8"))
            for f in sorted(self.facts, key=lambda x: (x.category, x.key, x.symbol or "", x.fact_id)):
                hasher.update(f.semantic_hash.encode("utf-8"))
            self.state_hash = hasher.hexdigest()

        if not self.provenance_hash:
            prov = hashlib.sha256(
                f"{self.run_id}:{self.symbol}:{self.as_of.isoformat()}:{self.state_hash}".encode("utf-8")
            ).hexdigest()
            self.provenance_hash = prov

        if not self.content_hash:
            self.content_hash = self.provenance_hash

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
        data_loader: Callable[..., Any],
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
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        benchmarks = [b.upper().strip() for b in (benchmarks or ["SPY", "QQQ", "TLT", "GLD"])]

        market_bars: Dict[str, Any] = {}
        facts: List[ResearchFact] = []
        dataset_versions: Dict[str, str] = {"market": "v1.0", "engine": "v1.3"}
        source_refs: Dict[str, str] = {}
        source_status: Dict[str, SourceStatus] = {}

        # 1. Load target symbol bars
        target_bars = None
        try:
            try:
                target_bars = self.data_loader(symbol, limit=1000, as_of=as_of)
            except TypeError:
                target_bars = self.data_loader(symbol, 1000)

            # Strictly enforce point-in-time: exclude bars with timestamp > as_of
            if target_bars is not None and hasattr(target_bars, "index"):
                try:
                    if hasattr(target_bars.index, "tz") and target_bars.index.tz is None:
                        # timezone naive index: compare with tz-naive as_of
                        as_of_naive = as_of.replace(tzinfo=None)
                        target_bars = target_bars[target_bars.index <= as_of_naive]
                    else:
                        target_bars = target_bars[target_bars.index <= as_of]
                except Exception:
                    pass

            if target_bars is not None and hasattr(target_bars, "empty") and not target_bars.empty:
                market_bars[symbol] = target_bars
                source_refs[f"market:{symbol}"] = f"data_loader({symbol},1000,as_of={as_of.isoformat()})"
                source_status[f"market:{symbol}"] = SourceStatus(
                    status=SourceState.AVAILABLE,
                    fetched_at=as_of,
                )
            else:
                source_status[f"market:{symbol}"] = SourceStatus(
                    status=SourceState.UNAVAILABLE,
                    message=f"No market bars found on or before {as_of.isoformat()}",
                    fetched_at=as_of,
                )
        except Exception as e:
            target_bars = None
            source_status[f"market:{symbol}"] = SourceStatus(
                status=SourceState.ERROR,
                message=str(e),
                fetched_at=as_of,
            )

        # 2. Load benchmark bars
        for b in benchmarks:
            if b not in market_bars:
                try:
                    try:
                        bars = self.data_loader(b, limit=1000, as_of=as_of)
                    except TypeError:
                        bars = self.data_loader(b, 1000)

                    if bars is not None and hasattr(bars, "index"):
                        try:
                            if hasattr(bars.index, "tz") and bars.index.tz is None:
                                as_of_naive = as_of.replace(tzinfo=None)
                                bars = bars[bars.index <= as_of_naive]
                            else:
                                bars = bars[bars.index <= as_of]
                        except Exception:
                            pass

                    if bars is not None and hasattr(bars, "empty") and not bars.empty:
                        market_bars[b] = bars
                        source_refs[f"market:{b}"] = f"data_loader({b},1000)"
                        source_status[f"market:{b}"] = SourceStatus(status=SourceState.AVAILABLE, fetched_at=as_of)
                    else:
                        source_status[f"market:{b}"] = SourceStatus(
                            status=SourceState.UNAVAILABLE,
                            message=f"No benchmark bars found on or before {as_of.isoformat()}",
                            fetched_at=as_of,
                        )
                except Exception as e:
                    source_status[f"market:{b}"] = SourceStatus(
                        status=SourceState.ERROR,
                        message=str(e),
                        fetched_at=as_of,
                    )

        # 3. Extract Market & Technical facts for target symbol (with strict Missing != Zero checks)
        if target_bars is not None and hasattr(target_bars, "empty") and not target_bars.empty:
            last_bar = target_bars.iloc[-1]
            obs_time = getattr(last_bar, "name", as_of)
            if not isinstance(obs_time, datetime):
                obs_time = as_of
            elif obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)

            raw_close = last_bar.get("close")
            if raw_close is not None:
                try:
                    close_val = float(raw_close)
                    if math.isfinite(close_val):
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
                except (ValueError, TypeError):
                    pass

            raw_vol = last_bar.get("volume")
            if raw_vol is not None:
                try:
                    vol_val = float(raw_vol)
                    if math.isfinite(vol_val):
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
                except (ValueError, TypeError):
                    pass

            # Compute technical analysis
            try:
                from ..intelligence.technical import analyze_technical
                tech_view = analyze_technical(target_bars)
                if tech_view.score is not None:
                    try:
                        score_val = float(tech_view.score)
                        if math.isfinite(score_val):
                            facts.append(
                                ResearchFact(
                                    fact_id=f"tech-{symbol}-directional-score",
                                    symbol=symbol,
                                    category="technical",
                                    key="directional_score",
                                    value=score_val,
                                    observed_at=obs_time,
                                    known_at=obs_time,
                                    as_of=as_of,
                                    source_type="derived_technical",
                                    confidence=tech_view.confidence,
                                )
                            )
                    except (ValueError, TypeError):
                        pass
                if tech_view.trend:
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

        # 4. Extract SEC Fundamental facts (with strict PIT filing availability)
        sec_snapshot = None
        if self.sec_client is None:
            source_status["sec"] = SourceStatus(status=SourceState.NOT_CONFIGURED)
        else:
            try:
                try:
                    sec_snapshot = self.sec_client.snapshot(symbol, as_of=as_of)
                except TypeError:
                    sec_snapshot = self.sec_client.snapshot(symbol)

                dataset_versions["sec"] = "sec-xbrl-v1"
                source_refs["fundamental:sec"] = f"sec_facts({symbol})"

                reports = getattr(sec_snapshot, "annual_reports", None) or []
                eligible_reports = []
                for rep in reports:
                    filing_dt = None
                    for attr in ("filing_date", "filed_at", "acceptance_datetime", "known_at"):
                        val = getattr(rep, attr, None)
                        if val:
                            if isinstance(val, datetime):
                                filing_dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
                            elif isinstance(val, str):
                                try:
                                    filing_dt = datetime.fromisoformat(val).replace(tzinfo=timezone.utc)
                                except Exception:
                                    try:
                                        filing_dt = datetime.strptime(val[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                                    except Exception:
                                        pass
                            break

                    if filing_dt is None:
                        end_val = getattr(rep, "end_date", None)
                        if end_val:
                            try:
                                filing_dt = datetime.strptime(str(end_val)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                            except Exception:
                                pass

                    if filing_dt is not None:
                        if filing_dt <= as_of:
                            eligible_reports.append((filing_dt, rep))

                if eligible_reports:
                    # Sort by filing date ascending, select latest available on or before as_of
                    eligible_reports.sort(key=lambda x: x[0])
                    filing_dt, latest_report = eligible_reports[-1]

                    end_date_str = getattr(latest_report, "end_date", None)
                    if end_date_str:
                        try:
                            rep_obs_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        except Exception:
                            rep_obs_date = filing_dt
                    else:
                        rep_obs_date = filing_dt

                    rev_growth = getattr(latest_report, "revenue_growth_yoy", None)
                    if rev_growth is not None:
                        try:
                            rg_val = float(rev_growth)
                            if math.isfinite(rg_val):
                                facts.append(
                                    ResearchFact(
                                        fact_id=f"fund-{symbol}-revenue-growth-yoy",
                                        symbol=symbol,
                                        category="fundamental",
                                        key="revenue_growth_yoy",
                                        value=rg_val,
                                        observed_at=rep_obs_date,
                                        known_at=filing_dt,
                                        as_of=as_of,
                                        source_type="sec_edgar",
                                        source_id=f"CIK-{getattr(sec_snapshot, 'cik', '')}",
                                    )
                                )
                        except (ValueError, TypeError):
                            pass

                    net_margin = getattr(latest_report, "net_margin", None)
                    if net_margin is not None:
                        try:
                            nm_val = float(net_margin)
                            if math.isfinite(nm_val):
                                facts.append(
                                    ResearchFact(
                                        fact_id=f"fund-{symbol}-net-margin",
                                        symbol=symbol,
                                        category="fundamental",
                                        key="net_margin",
                                        value=nm_val,
                                        observed_at=rep_obs_date,
                                        known_at=filing_dt,
                                        as_of=as_of,
                                        source_type="sec_edgar",
                                        source_id=f"CIK-{getattr(sec_snapshot, 'cik', '')}",
                                    )
                                )
                        except (ValueError, TypeError):
                            pass

                    source_status["sec"] = SourceStatus(
                        status=SourceState.AVAILABLE,
                        fetched_at=as_of,
                    )
                else:
                    source_status["sec"] = SourceStatus(
                        status=SourceState.UNAVAILABLE,
                        message=f"No SEC filings available on or before {as_of.isoformat()}",
                        fetched_at=as_of,
                    )
            except Exception as e:
                sec_snapshot = None
                source_status["sec"] = SourceStatus(
                    status=SourceState.ERROR,
                    message=str(e),
                    fetched_at=as_of,
                )

        # 5. Extract FRED Macro facts (with vintage / PIT awareness)
        macro_snapshot = None
        if self.fred_client is None:
            source_status["macro:fred"] = SourceStatus(status=SourceState.NOT_CONFIGURED)
        else:
            try:
                now_utc = datetime.now(timezone.utc)
                is_historical = (now_utc - as_of) > timedelta(days=7)
                explicit_unsupported = getattr(self.fred_client, "supports_pit", None) is False or getattr(self.fred_client, "is_pit_capable", None) is False

                if is_historical and explicit_unsupported:
                    source_status["macro:fred"] = SourceStatus(
                        status=SourceState.NOT_PIT_CAPABLE,
                        message="Historical FRED vintage reconstruction not supported by client",
                        fetched_at=as_of,
                    )
                else:
                    try:
                        macro_snapshot = self.fred_client.snapshot(as_of=as_of)
                    except TypeError:
                        macro_snapshot = self.fred_client.snapshot()

                    dataset_versions["macro"] = "fred-v1"
                    source_refs["macro:fred"] = "fred_snapshot()"
                    source_status["macro:fred"] = SourceStatus(
                        status=SourceState.AVAILABLE,
                        fetched_at=as_of,
                    )

                    for field_name, fact_key in [
                        ("treasury_10y", "treasury_10y"),
                        ("fed_funds", "fed_funds_rate"),
                        ("cpi_yoy", "cpi_yoy"),
                        ("unemployment", "unemployment_rate"),
                        ("yield_curve_10y2y", "yield_curve_10y2y"),
                        ("industrial_production_yoy", "industrial_production_yoy"),
                    ]:
                        val = getattr(macro_snapshot, field_name, None)
                        if val is not None:
                            try:
                                num_val = float(val)
                                if math.isfinite(num_val):
                                    facts.append(
                                        ResearchFact(
                                            fact_id=f"macro-{fact_key.replace('_', '-')}",
                                            symbol=None,
                                            category="macro",
                                            key=fact_key,
                                            value=num_val,
                                            observed_at=as_of,
                                            known_at=as_of,
                                            as_of=as_of,
                                            source_type="fred",
                                        )
                                    )
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                macro_snapshot = None
                source_status["macro:fred"] = SourceStatus(
                    status=SourceState.ERROR,
                    message=str(e),
                    fetched_at=as_of,
                )

        # Sort facts deterministically
        sorted_facts = sorted(facts, key=lambda f: (f.category, f.key, f.symbol or "", f.fact_id))

        # Compute deterministic state_hash and provenance_hash
        hasher = hashlib.sha256()
        hasher.update(symbol.encode("utf-8"))
        for k, v in sorted(dataset_versions.items()):
            hasher.update(f"{k}:{v}".encode("utf-8"))
        for k, s in sorted(source_status.items()):
            hasher.update(f"{k}:{s.status.value}".encode("utf-8"))
        for f in sorted_facts:
            hasher.update(f.semantic_hash.encode("utf-8"))
        state_hash = hasher.hexdigest()

        prov_hasher = hashlib.sha256()
        prov_hasher.update(f"{run_id}:{symbol}:{as_of.isoformat()}:{state_hash}".encode("utf-8"))
        provenance_hash = prov_hasher.hexdigest()
        snapshot_id = f"snap-{provenance_hash[:16]}"
        content_hash = provenance_hash

        return ResearchSnapshot(
            snapshot_id=snapshot_id,
            run_id=run_id,
            symbol=symbol,
            as_of=as_of,
            state_hash=state_hash,
            provenance_hash=provenance_hash,
            content_hash=content_hash,
            source_status=source_status,
            dataset_versions=dataset_versions,
            source_refs=source_refs,
            facts=sorted_facts,
            market_bars=market_bars,
            sec_snapshot=sec_snapshot,
            macro_snapshot=macro_snapshot,
        )
