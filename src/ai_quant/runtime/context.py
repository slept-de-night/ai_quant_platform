from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from .clock import QuantClock
from .snapshot import QuantSnapshot
from ..core.models import PortfolioState


class RuntimeMode(str, Enum):
    BACKTEST = "backtest"
    REPLAY = "replay"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class DecisionContext:
    """Unified execution and decision context provided to alpha strategies.
    
    Attributes:
        run_id: Unique batch/execution run identifier.
        decision_id: Unique identifier for this discrete strategy decision.
        trace_id: Distributed trace ID across the entire decision lifecycle.
        mode: Execution mode (BACKTEST, REPLAY, PAPER, LIVE).
        clock: Time provider.
        snapshot: Cryptographically immutable market and fundamental data snapshot.
        portfolio: Current portfolio state (cash, positions, daily PnL).
        strategy_version: Version identifier of the strategy being evaluated.
        parameters: Strategy hyperparameter configuration.
    """
    run_id: str
    decision_id: str
    trace_id: str
    mode: RuntimeMode
    clock: QuantClock
    snapshot: QuantSnapshot
    portfolio: PortfolioState
    strategy_version: str = "v1.0"
    parameters: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        mode: RuntimeMode,
        clock: QuantClock,
        snapshot: QuantSnapshot,
        portfolio: PortfolioState,
        strategy_version: str = "v1.0",
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DecisionContext:
        return cls(
            run_id=run_id or uuid.uuid4().hex,
            decision_id=uuid.uuid4().hex,
            trace_id=trace_id or uuid.uuid4().hex,
            mode=mode,
            clock=clock,
            snapshot=snapshot,
            portfolio=portfolio,
            strategy_version=strategy_version,
            parameters=parameters or {},
        )


@dataclass(frozen=True)
class CompiledResearchContext:
    """Token-efficient, immutable compiled context prepared for AI reasoning routes."""
    symbol: str
    as_of: datetime
    snapshot_hash: str
    facts_summary: List[Dict[str, Any]]
    market_context: Dict[str, Any]
    fundamental_context: Dict[str, Any]
    macro_context: Dict[str, Any]
    rendered_prompt_text: str
    estimated_tokens: int


class ContextCompiler:
    """Deterministic, token-bounded compiler that transforms raw ResearchSnapshot and facts into compact LLM context."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Heuristic token estimator (~4 characters per token)."""
        return max(1, len(text) // 4)

    @classmethod
    def compile(
        cls,
        snapshot: Any,
        task_type: str = "general",
        max_tokens: int = 1500,
    ) -> CompiledResearchContext:
        """Compile a compact, token-bounded research prompt context from a ResearchSnapshot."""
        from datetime import datetime, timezone

        symbol = getattr(snapshot, "symbol", "UNKNOWN")
        as_of = getattr(snapshot, "as_of", datetime.now(timezone.utc))
        snapshot_hash = getattr(snapshot, "content_hash", getattr(snapshot, "snapshot_id", ""))
        facts = getattr(snapshot, "facts", []) or []

        # 1. Market metrics
        bars_data = getattr(snapshot, "market_bars", None)
        bars: List[Any] = []
        if isinstance(bars_data, dict):
            b = bars_data.get(symbol.upper().strip())
            if b is None:
                b = bars_data.get(symbol)
            if b is not None:
                bars = b
        elif isinstance(bars_data, list):
            bars = bars_data

        if hasattr(bars, "to_dict"):
            bars = bars.to_dict(orient="records")
        elif not isinstance(bars, list):
            bars = list(bars)

        market_ctx: Dict[str, Any] = {}
        if bars:
            last_bar = bars[-1]
            close = getattr(last_bar, "close", None) if not isinstance(last_bar, dict) else last_bar.get("close")
            vol = getattr(last_bar, "volume", None) if not isinstance(last_bar, dict) else last_bar.get("volume")
            market_ctx = {
                "latest_close": close,
                "latest_volume": vol,
                "bar_count": len(bars),
            }

        # 2. Fundamental metrics
        financials = getattr(snapshot, "sec_snapshot", getattr(snapshot, "financial_statements", None))
        fund_ctx: Dict[str, Any] = {}
        if financials:
            fund_ctx = {
                "has_income_stmt": bool(getattr(financials, "income_statement", None)),
                "has_balance_sheet": bool(getattr(financials, "balance_sheet", None)),
                "has_cash_flow": bool(getattr(financials, "cash_flow", None)),
            }

        # 3. Macro metrics
        macro = getattr(snapshot, "macro_snapshot", None) or {}
        macro_ctx: Dict[str, Any] = {
            "cycle": macro.get("cycle") or macro.get("regime") or "neutral",
            "fed_rate": macro.get("fed_rate") or macro.get("policy_rate"),
        }

        # 4. Format atomic facts
        facts_summary = []
        for f in facts[:20]:  # Top 20 facts
            facts_summary.append({
                "source": getattr(f, "source_type", getattr(f, "source", "")),
                "dimension": getattr(f, "category", getattr(f, "dimension", "")),
                "metric": getattr(f, "key", getattr(f, "metric_name", "")),
                "value": getattr(f, "value", getattr(f, "metric_value", None)),
            })

        # 5. Render prompt markdown
        lines = [
            f"# Point-in-Time Research Context: {symbol}",
            f"- As of: {as_of.isoformat() if hasattr(as_of, 'isoformat') else str(as_of)}",
            f"- Snapshot Hash: {snapshot_hash[:12]}...",
            f"- Task: {task_type}",
            "",
            "## Verified Objective Facts:",
        ]
        for f in facts_summary:
            lines.append(f"- [{f['source']}] {f['dimension']}.{f['metric']} = {f['value']}")

        if market_ctx:
            lines.append("")
            lines.append("## Market Baseline:")
            lines.append(f"- Latest Close: {market_ctx.get('latest_close')}")
            lines.append(f"- Volume: {market_ctx.get('latest_volume')}")

        if macro_ctx:
            lines.append("")
            lines.append(f"## Macro Regime: {macro_ctx.get('cycle')}")

        rendered_text = "\n".join(lines)
        tokens = cls.estimate_tokens(rendered_text)

        if tokens > max_tokens:
            rendered_text = rendered_text[: max_tokens * 4] + "\n... [Context truncated to token budget]"
            tokens = max_tokens

        return CompiledResearchContext(
            symbol=symbol,
            as_of=as_of if isinstance(as_of, datetime) else datetime.now(timezone.utc),
            snapshot_hash=snapshot_hash,
            facts_summary=facts_summary,
            market_context=market_ctx,
            fundamental_context=fund_ctx,
            macro_context=macro_ctx,
            rendered_prompt_text=rendered_text,
            estimated_tokens=tokens,
        )
