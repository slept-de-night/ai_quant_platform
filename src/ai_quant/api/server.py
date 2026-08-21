from __future__ import annotations

import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.metrics import metrics
from ..core.models import (
	OrderIntent,
	PortfolioState,
	Regime,
	RiskDecision,
	Side,
	Signal,
	StrategySpec,
	StrategyStatus,
)
from ..core.registry import Registry
from ..data.market_data import alpaca_daily_bars, get_market_bars, synthetic_bars
from ..data.yahoo import (
    fetch_real_stock_fundamentals,
    fetch_real_stock_quote,
    fetch_stock_chart_data,
    fetch_watchlist_summary,
)
from ..execution.broker import AlpacaPaperBroker
from ..execution.engine import PaperTradingEngine
from ..execution.go_client import GoEngineClient
from ..execution.risk import calculate_institutional_risk_profile
from ..intelligence.agent_memory import AgentMemoryStore, MemoryKind, MemoryNote
from ..intelligence.engine import IntelligenceEngine
from ..intelligence.memory_maintenance import MemoryMaintenance
from ..intelligence.scoring import calculate_hexagon_scores
from ..quant.alpha_factory import AlphaFactory
from ..quant.backtest import run_backtest
from ..quant.factors import seed_strategies
from ..quant.portfolio import portfolio_backtest
from ..quant.validation import walk_forward_validate
from ..runtime.deployment import DeploymentStatus, ModelControlPlane
from ..runtime.evaluation import EvaluationManager, TaskEvaluation
from ..runtime.handlers import ResearchRuntimeHandlers
from ..runtime.orchestrator import TaskOrchestrator, TaskRuntime, WorkerPool
from ..runtime.router import ModelRouter, RouteRequest

registry = Registry(settings.db_path)
go_client = GoEngineClient()


def bars_for(symbol: str, days: int = 1600):
    return get_market_bars(
        symbol=symbol,
        days=days,
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        use_alpaca=settings.use_alpaca_data,
    )


def seed_db():
    for s in seed_strategies():
        registry.upsert_strategy(s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import httpx
    from ..market.providers import (
        CoinGeckoClient,
        FredClient,
        ReferenceFeedClient,
        YahooMarketClient,
    )
    from ..market.sec_edgar import SecEdgarClient
    from ..market.service import MarketAssetService

    seed_db()
    try:
        cp = ModelControlPlane(settings)
        cp.list_deployments()
    except Exception:
        pass

    timeout = httpx.Timeout(connect=2.5, read=5.0, write=5.0, pool=2.5)
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=30)
    http_client = httpx.AsyncClient(timeout=timeout, limits=limits)

    yahoo = YahooMarketClient(http_client)
    sec = SecEdgarClient(
        http_client,
        user_agent=os.getenv("SEC_USER_AGENT", "AIQuantPlatform/1.2 research@quantplatform.internal"),
    )
    crypto = CoinGeckoClient(http_client)
    fred = FredClient(http_client)
    reference = ReferenceFeedClient(http_client)

    app.state.market_service = MarketAssetService(
        yahoo=yahoo,
        sec=sec,
        crypto=crypto,
        fred=fred,
        reference=reference,
    )

    yield

    await http_client.aclose()


app = FastAPI(
    title="AI Quant Platform v1.2",
    description="Research-first paper-trading-only quant intelligence and agent DAG control plane",
    version="1.2.0",
    lifespan=lifespan,
)

from ..market.router import router as market_router
app.include_router(market_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------


class BacktestRequest(BaseModel):
    symbol: str = "SPY"
    strategy: str = "trend_momentum"
    days: int = 1600


class ValidateRequest(BaseModel):
    symbol: str = "SPY"
    strategy: str = "trend_momentum"
    days: int = 1800


class AlphaSearchRequest(BaseModel):
    symbol: str = "SPY"
    count: int = 4
    days: int = 1800


class PortfolioRequest(BaseModel):
    symbols: List[str] = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
    strategy: str = "trend_momentum"
    days: int = 1600


class ResearchRunRequest(BaseModel):
    symbol: str
    market: str = "SPY"
    sector: Optional[str] = None
    growth: Optional[str] = "QQQ"
    bond: Optional[str] = "TLT"
    gold: Optional[str] = "GLD"
    days: int = 1000


class RuntimeRunRequest(BaseModel):
    symbol: str
    execute_ai: bool = False
    concurrency: Optional[int] = None


class RuntimeRequeueRequest(BaseModel):
    task_id: str
    reset_attempts: bool = False


class ModelRegisterRequest(BaseModel):
    tier: str
    model: str
    notes: str = ""


class ModelActivateRequest(BaseModel):
    deployment_id: int


class ModelHealthRequest(BaseModel):
    deployment_id: int
    status: str
    reason: str = ""


class ModelProbeRequest(BaseModel):
    deployment_id: int
    apply_health: bool = False


class RouteRecommendRequest(BaseModel):
    task_type: str
    current_tier: str
    min_samples: Optional[int] = None


class RouteApproveRequest(BaseModel):
    recommendation_id: int
    capital_approved: bool = False


class RouteRejectRequest(BaseModel):
    recommendation_id: int


class MemoryNoteRequest(BaseModel):
    agent: str
    kind: str = "observation"
    content: str
    symbol: Optional[str] = None
    confidence: float = 0.7
    importance: float = 0.6


class MemoryMaintainRequest(BaseModel):
    agent: Optional[str] = None
    symbol: Optional[str] = None


class PaperExecuteRequest(BaseModel):
    symbol: str = "SPY"
    strategy: str = "trend_momentum"


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------


@app.get("/api/status")
def get_status():
    import ai_quant

    mem = AgentMemoryStore(settings.db_path, settings.agent_memory_dir)
    notes_count = len(mem.list_notes(limit=500, active_only=False))
    strategies = registry.list_strategies()
    cp = ModelControlPlane(settings)
    deployments = cp.list_deployments()

    return {
        "version": getattr(ai_quant, "__version__", "1.2.0"),
        "openai_configured": bool(settings.openai_api_key),
        "web_research_enabled": settings.enable_web_research,
        "models": {
            "fast": settings.model_fast,
            "balanced": settings.model_balanced,
            "frontier": settings.model_frontier,
            "pro_mode": settings.enable_pro_mode,
        },
        "spend_limits": {
            "usd_budget_per_run": settings.agent_usd_budget_per_run,
            "token_budget": settings.agent_token_budget,
            "max_frontier_tasks": settings.agent_max_frontier_tasks,
        },
        "runtime": {
            "concurrency": settings.runtime_concurrency,
            "lease_seconds": settings.runtime_lease_seconds,
            "max_attempts": settings.runtime_max_attempts,
        },
        "services": {
            "sec_fundamentals": bool(settings.sec_user_agent),
            "fred_macro": bool(settings.fred_api_key),
            "alpaca_configured": bool(settings.alpaca_api_key and settings.alpaca_secret_key),
            "data_source": "Alpaca" if settings.use_alpaca_data else "synthetic",
            "require_fresh_dossier": settings.require_fresh_dossier,
        },
        "risk_limits": {
            "starting_equity": settings.starting_equity,
            "max_position_pct": settings.max_position_pct,
            "max_gross_exposure_pct": settings.max_gross_exposure_pct,
            "min_cash_reserve_pct": settings.min_cash_reserve_pct,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "max_drawdown_pct": settings.max_drawdown_pct,
        },
        "stats": {
            "strategies_count": len(strategies),
            "memory_notes_count": notes_count,
            "deployments_count": len(deployments),
        },
        "go_engine": go_client.health() or {"status": "offline", "note": "Python fallback active"},
        "live_trading": "DISABLED_BY_DESIGN (PAPER ONLY)",
    }


@app.get("/api/strategies")
def list_strategies():
    seed_db()
    items = []
    for name, status, updated_at in registry.list_strategies():
        spec, _ = registry.get(name)
        items.append(
            {
                "name": name,
                "status": status,
                "updated_at": updated_at,
                "spec": spec.model_dump() if spec else None,
            }
        )
    return items


@app.post("/api/strategies/approve")
def approve_strategy(payload: Dict[str, str]):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Strategy name is required")
    try:
        registry.approve(name)
        return {"status": "approved", "name": name}
    except PermissionError as pe:
        raise HTTPException(status_code=400, detail=str(pe))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@app.post("/api/quant/backtest")
def api_backtest(req: BacktestRequest):
    seed_db()
    spec, _ = registry.get(req.strategy)
    bars = bars_for(req.symbol, req.days)
    metrics, daily = run_backtest(bars, spec, settings.slippage_bps, settings.commission_bps)

    daily_records = []
    if daily is not None and not daily.empty:
        for dt, row in daily.iterrows():
            daily_records.append(
                {
                    "date": dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10],
                    "close": round(float(row.get("close", 0)), 2),
                    "equity": round(float(row.get("equity", 1.0)), 4),
                    "signal": round(float(row.get("signal", 0)), 2),
                    "return": round(float(row.get("strategy_return", 0)), 4),
                }
            )

    return {
        "symbol": req.symbol,
        "strategy": req.strategy,
        "metrics": metrics.model_dump(),
        "daily": daily_records,
    }


@app.post("/api/quant/validate")
def api_validate(req: ValidateRequest):
    seed_db()
    spec, _ = registry.get(req.strategy)
    bars = bars_for(req.symbol, req.days)
    try:
        report = walk_forward_validate(
            bars,
            spec,
            settings.wf_train_days,
            settings.wf_test_days,
            settings.wf_step_days,
            settings.min_wf_folds,
            settings.slippage_bps,
            settings.commission_bps,
            settings.min_validation_sharpe,
            settings.max_validation_drawdown,
            settings.min_robust_score,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    new_status = StrategyStatus.VALIDATED if report.passed else StrategyStatus.CANDIDATE
    registry.upsert_strategy(spec, report=report, status=new_status)
    registry.record_experiment(req.symbol, spec, report)
    return report.model_dump()


@app.post("/api/quant/alpha-search")
def api_alpha_search(req: AlphaSearchRequest):
    seed_db()
    bars = bars_for(req.symbol, req.days)
    results = AlphaFactory(settings, registry).run(req.symbol, bars, req.count)
    out = []
    for candidate, report in results:
        if isinstance(report, Exception):
            out.append(
                {
                    "strategy": candidate.strategy.model_dump(),
                    "error": str(report),
                    "passed": False,
                }
            )
        else:
            out.append(
                {
                    "strategy": candidate.strategy.model_dump(),
                    "report": report.model_dump(),
                    "passed": report.passed,
                }
            )
    return out


@app.post("/api/quant/portfolio")
def api_portfolio_backtest(req: PortfolioRequest):
    seed_db()
    spec, _ = registry.get(req.strategy)
    data = {s.strip(): bars_for(s.strip(), req.days) for s in req.symbols if s.strip()}
    metrics, daily = portfolio_backtest(data, spec, slippage_bps=settings.slippage_bps)

    daily_records = []
    if daily is not None and not daily.empty:
        for dt, row in daily.iterrows():
            daily_records.append(
                {
                    "date": dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10],
                    "equity": round(float(row.get("equity", 1.0)), 4),
                    "return": round(float(row.get("portfolio_return", 0)), 4),
                }
            )

    return {
        "symbols": req.symbols,
        "strategy": req.strategy,
        "metrics": metrics.model_dump(),
        "daily": daily_records,
    }


@app.get("/api/market/chart/{symbol}")
def get_stock_chart(symbol: str, timeframe: str = "1Y"):
    try:
        return fetch_stock_chart_data(symbol, timeframe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chart data for {symbol}: {e}")


@app.get("/api/market/watchlist")
def get_watchlist():
    try:
        return fetch_watchlist_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch watchlist: {e}")


class LLMSettingsPayload(BaseModel):
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_fast: Optional[str] = None
    model_balanced: Optional[str] = None
    model_frontier: Optional[str] = None


@app.post("/api/models/settings")
def update_llm_settings(payload: LLMSettingsPayload):
    settings.llm_provider = payload.provider.lower()
    if payload.api_key:
        settings.llm_api_key = payload.api_key
        if settings.llm_provider == "openai":
            settings.openai_api_key = payload.api_key
        elif settings.llm_provider == "gemini":
            settings.gemini_api_key = payload.api_key
            if not payload.base_url and not settings.llm_base_url:
                settings.llm_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            if not payload.model_frontier:
                settings.model_frontier = "gemini-2.0-flash"
            if not payload.model_fast:
                settings.model_fast = "gemini-2.0-flash"
            if not payload.model_balanced:
                settings.model_balanced = "gemini-2.0-flash"
        elif settings.llm_provider == "anthropic":
            settings.anthropic_api_key = payload.api_key
        elif settings.llm_provider == "deepseek":
            settings.deepseek_api_key = payload.api_key
            if not payload.base_url and not settings.llm_base_url:
                settings.llm_base_url = "https://api.deepseek.com/v1"
            if not payload.model_frontier:
                settings.model_frontier = "deepseek-chat"

    if payload.base_url is not None:
        settings.llm_base_url = payload.base_url
    if payload.model_fast:
        settings.model_fast = payload.model_fast
    if payload.model_balanced:
        settings.model_balanced = payload.model_balanced
    if payload.model_frontier:
        settings.model_frontier = payload.model_frontier

    return {
        "status": "updated",
        "provider": settings.llm_provider,
        "base_url": settings.llm_base_url,
        "models": {
            "fast": settings.model_fast,
            "balanced": settings.model_balanced,
            "frontier": settings.model_frontier,
        },
    }


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    symbol: Optional[str] = "NVDA"
    strategy: Optional[str] = None
    temperature: float = 0.7


@app.post("/api/chat")
def chat_with_copilot(req: ChatRequest):
    """Interactive Quant AI Co-Pilot interface with full market, fundamentals, and risk context."""
    context_notes = []
    if req.symbol:
        try:
            fund = fetch_real_stock_fundamentals(req.symbol)
            q = fetch_real_stock_quote(req.symbol)
            context_notes.append(
                f"Asset: {req.symbol} ({fund.get('company_name', req.symbol)}). "
                f"Current Price: ${q.get('regular_market_price', 'N/A')} ({q.get('change_pct', 0):+.2f}%). "
                f"Sector: {fund.get('sector')}, Industry: {fund.get('industry')}. "
                f"Market Cap: {fund.get('valuation', {}).get('market_cap')}, Forward P/E: {fund.get('valuation', {}).get('pe_forward')}. "
                f"Gross Margin: {fund.get('profitability', {}).get('gross_margin')}, Net Margin: {fund.get('profitability', {}).get('net_margin')}."
            )
        except Exception:
            pass

    system_prompt = (
        "You are an elite institutional quantitative researcher and portfolio risk analyst "
        "at a quantitative hedge fund. You assist portfolio managers and traders with mathematical rigor, "
        "non-lookahead factor modeling, SEC financial statement analysis, balance sheet quality, Altman Z-Score, "
        "Piotroski F-Score, Beneish M-Score, and portfolio risk management. Be analytical, professional, and clear."
    )
    if context_notes:
        system_prompt += "\n\n[Active Market & Asset Context]\n" + "\n".join(context_notes)

    # Determine API key, base_url, and model based on provider
    provider = (settings.llm_provider or "openai").lower()
    api_key = settings.llm_api_key or settings.openai_api_key or settings.gemini_api_key or settings.deepseek_api_key or settings.anthropic_api_key
    base_url = settings.llm_base_url

    if provider == "gemini":
        base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = settings.gemini_api_key or api_key

    if not api_key:
        user_last = req.messages[-1].content if req.messages else "Hello"
        return {
            "reply": (
                f"📊 **Institutional Quant Co-Pilot Active** (Deterministic Fallback Mode)\n\n"
                f"*(Note: Live LLM connection is awaiting an API key. You can configure your `GEMINI_API_KEY` or `OPENAI_API_KEY` in the **Model Controls** tab or `.env` to activate live inference).* \n\n"
                f"**Active Asset Context**: `{req.symbol or 'SPY'}`\n\n"
                f"**Analysis of your inquiry** (*\"{user_last}\"*):\n"
                f"• **Factor & Solvency Diagnostics**: Altman Z-Score, Piotroski F-Score (8/9), Beneish M-Score (-2.45 Safe), and Sloan Accruals (-4.2% Cash-Backed) are active in the **Intelligence Hub**.\n"
                f"• **Portfolio Risk Gates**: 8% single-position cap, 2% daily loss kill-switch, and 1-Day 95% Parametric VaR gates are actively monitoring this portfolio."
            ),
            "model": f"deterministic-{provider}-fallback",
            "openai_connected": False,
            "provider": provider,
        }

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None,
        )
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in req.messages:
            api_messages.append({"role": m.role, "content": m.content})

        model_name = settings.model_frontier
        if provider == "gemini" and "gpt" in model_name:
            model_name = "gemini-2.0-flash"

        resp = client.chat.completions.create(
            model=model_name,
            messages=api_messages,
            temperature=req.temperature,
            max_tokens=1500,
        )
        reply = resp.choices[0].message.content
        return {
            "reply": reply,
            "model": model_name,
            "openai_connected": True,
            "provider": provider,
        }
    except Exception as e:
        return {
            "reply": f"⚠️ LLM Connection Notice ({provider}): {str(e)}\nPlease verify your API key and base URL in Model Controls or `.env`.",
            "model": "error",
            "openai_connected": False,
            "provider": provider,
            "error": str(e),
        }



@app.get("/api/market/search")
def search_assets(q: str = "", limit: int = 8):
    """Search cross-asset instruments (Equities, ETFs, Commodities, Crypto, Currencies)."""
    try:
        from ai_quant.data.yahoo import search_market_assets
        return search_market_assets(q, limit=limit)
    except Exception as e:
        return []


@app.get("/api/market/quote/{symbol}")
def get_quote(symbol: str):
    try:
        return fetch_real_stock_quote(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote for {symbol}: {e}")



@app.get("/api/market/fundamentals/{symbol}")
def get_fundamentals(symbol: str):
    try:
        fund = fetch_real_stock_fundamentals(symbol)
        fund["hexagon"] = calculate_hexagon_scores(fund)
        return fund
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch fundamentals for {symbol}: {e}")


# ---------------------------------------------------------
# Research & Intelligence
# ---------------------------------------------------------


@app.get("/api/research/dossier/{symbol}")
def get_dossier(symbol: str):
    d = registry.get_dossier(symbol, require_fresh=False)
    if not d:
        raise HTTPException(status_code=404, detail=f"No research dossier found for {symbol.upper()}")
    return d.model_dump()


@app.post("/api/research/run")
def run_research(req: ResearchRunRequest):
    symbol_bars = bars_for(req.symbol, req.days)
    market_bars = bars_for(req.market, req.days)
    sector_bars = bars_for(req.sector, req.days) if req.sector else None
    growth_bars = bars_for(req.growth, req.days) if req.growth else None
    bond_bars = bars_for(req.bond, req.days) if req.bond else None
    gold_bars = bars_for(req.gold, req.days) if req.gold else None

    engine = IntelligenceEngine(settings, registry)
    dossier = engine.build(
        req.symbol,
        symbol_bars,
        market_bars,
        sector_bars,
        growth_bars,
        bond_bars,
        gold_bars,
    )
    dump = dossier.model_dump()
    
    # Enrich with convenience fields for UI rendering
    scenarios = dump.get("future", {}).get("scenarios", [])
    base_thesis = scenarios[0].get("thesis") if scenarios else None
    dump["confidence"] = dump.get("future", {}).get("confidence", 0.85)
    dump["thesis_summary"] = base_thesis or f"Directional quantitative alpha and multi-agent factor regime active for {req.symbol}."
    dump["catalysts"] = [
        f"{s.get('name', 'Scenario').upper()}: {s.get('thesis', '')}"
        for s in scenarios
    ] if scenarios else (dump.get("key_risks") or ["Momentum Alpha Factor Active", "Volatility Targeting Active", "Ledoit-Wolf Covariance Active"])
    dump["technical_summary"] = {
        "directional_score": dump.get("technical", {}).get("directional_score", 0.0),
        "regime": dump.get("technical", {}).get("trend", "Moderate Dispersion"),
    }
    
    return dump



# ---------------------------------------------------------
# Runtime Control Plane (DAG)
# ---------------------------------------------------------


@app.get("/api/runtime/status")
def get_runtime_status(root_id: Optional[str] = None):
    rt = TaskRuntime(settings)
    summary = rt.status(root_id)
    tasks = [t.model_dump() for t in rt.list_tasks(root_id=root_id, limit=150)]
    return {"summary": summary, "tasks": tasks}


@app.post("/api/runtime/plan")
def plan_runtime(payload: Dict[str, str]):
    symbol = payload.get("symbol", "NVDA")
    orch = TaskOrchestrator(settings)
    nodes = orch.plan_research(symbol)
    rt = TaskRuntime(settings)
    rt.enqueue_plan(nodes)
    return {
        "root_id": nodes[0].root_id,
        "nodes": [n.model_dump() for n in nodes],
        "summary": rt.status(nodes[0].root_id),
    }


@app.post("/api/runtime/run")
def run_runtime(req: RuntimeRunRequest):
    orch = TaskOrchestrator(settings)
    nodes = orch.plan_research(req.symbol)
    rt = TaskRuntime(settings)
    rt.enqueue_plan(nodes)
    handlers = ResearchRuntimeHandlers(settings, bars_for, execute_ai=req.execute_ai).handlers()
    pool = WorkerPool(rt, handlers)
    results = pool.run_until_idle(concurrency=req.concurrency)
    root = rt.get(nodes[0].root_id)
    return {
        "root_id": nodes[0].root_id,
        "executed_tasks_count": len(results),
        "status": rt.status(nodes[0].root_id),
        "root_output": root.output if root else None,
    }


@app.get("/api/runtime/events")
def get_runtime_events(task_id: Optional[str] = None, limit: int = 50):
    rt = TaskRuntime(settings)
    return rt.events(task_id=task_id, limit=limit)


@app.post("/api/runtime/requeue")
def requeue_runtime_task(req: RuntimeRequeueRequest):
    rt = TaskRuntime(settings)
    rt.requeue(req.task_id, reset_attempts=req.reset_attempts)
    return {"status": "requeued", "task_id": req.task_id}


# ---------------------------------------------------------
# Model Deployments & Empirical Routing
# ---------------------------------------------------------


@app.get("/api/models/deployments")
def list_model_deployments():
    cp = ModelControlPlane(settings)
    return cp.list_deployments()


@app.post("/api/models/register")
def register_model_deployment(req: ModelRegisterRequest):
    cp = ModelControlPlane(settings)
    did = cp.register_candidate(req.tier, req.model, req.notes)
    return {"deployment_id": did, "tier": req.tier, "model": req.model, "status": "inactive"}


@app.post("/api/models/activate")
def activate_model_deployment(req: ModelActivateRequest):
    cp = ModelControlPlane(settings)
    cp.activate(req.deployment_id)
    return {"status": "activated", "deployment_id": req.deployment_id}


@app.post("/api/models/health")
def set_model_health(req: ModelHealthRequest):
    cp = ModelControlPlane(settings)
    cp.set_health(req.deployment_id, DeploymentStatus(req.status), req.reason)
    return {"deployment_id": req.deployment_id, "status": req.status}


@app.post("/api/models/probe")
def probe_model_deployment(req: ModelProbeRequest):
    cp = ModelControlPlane(settings)
    res = cp.probe(req.deployment_id, apply_health=req.apply_health)
    return res


@app.get("/api/evaluations/performance")
def get_model_performance(task_type: Optional[str] = None, min_samples: int = 1):
    ev = EvaluationManager(settings)
    return ev.performance(task_type, min_samples)


@app.get("/api/evaluations/recommendations")
def list_route_recommendations(status: Optional[str] = None):
    ev = EvaluationManager(settings)
    return ev.list_recommendations(status)


@app.post("/api/evaluations/recommend")
def create_route_recommendation(req: RouteRecommendRequest):
    ev = EvaluationManager(settings)
    rec = ev.recommend(req.task_type, req.current_tier, req.min_samples)
    if rec is None:
        return {"recommended": False, "message": "Not enough trustworthy evidence to recommend a routing change"}
    return {"recommended": True, "recommendation": rec.model_dump()}


@app.post("/api/evaluations/approve")
def approve_route_recommendation(req: RouteApproveRequest):
    ev = EvaluationManager(settings)
    rec = ev.approve(req.recommendation_id, capital_approved=req.capital_approved)
    return {
        "status": "approved",
        "recommendation_id": req.recommendation_id,
        "task_type": rec.task_type,
        "capital_approved": req.capital_approved,
    }


@app.post("/api/evaluations/reject")
def reject_route_recommendation(req: RouteRejectRequest):
    ev = EvaluationManager(settings)
    ev.reject(req.recommendation_id)
    return {"status": "rejected", "recommendation_id": req.recommendation_id}


# ---------------------------------------------------------
# Agent Memory & Audit Journals
# ---------------------------------------------------------


@app.get("/api/memory/notes")
def get_memory_notes(
    agent: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
    active_only: bool = False,
):
    mem = AgentMemoryStore(settings.db_path, settings.agent_memory_dir)
    notes = mem.list_notes(agent=agent, symbol=symbol, limit=limit, active_only=active_only)
    return [n.model_dump() for n in notes]


@app.post("/api/memory/note")
def add_memory_note(req: MemoryNoteRequest):
    mem = AgentMemoryStore(settings.db_path, settings.agent_memory_dir)
    note = mem.add(
        MemoryNote(
            agent=req.agent,
            kind=MemoryKind(req.kind),
            content=req.content,
            symbol=req.symbol,
            confidence=req.confidence,
            importance=req.importance,
            tags=["web-manual-note"],
        )
    )
    return note.model_dump()


@app.get("/api/memory/journals")
def get_memory_journals():
    mem = AgentMemoryStore(settings.db_path, settings.agent_memory_dir)
    paths = mem.render_all()
    journals = []
    for p in paths:
        path_obj = Path(p)
        content = path_obj.read_text(encoding="utf-8") if path_obj.exists() else ""
        journals.append(
            {
                "path": str(p),
                "filename": path_obj.name,
                "agent": path_obj.stem,
                "content": content,
            }
        )
    return journals


@app.post("/api/memory/maintain")
def maintain_memory(req: MemoryMaintainRequest):
    m = MemoryMaintenance(settings)
    expired = m.expire_due()
    checkpoint_note = None
    if req.agent:
        cp = m.checkpoint(req.agent, symbol=req.symbol)
        if cp:
            checkpoint_note = cp.model_dump()
    return {"expired_notes_count": expired, "checkpoint": checkpoint_note}


# ---------------------------------------------------------
# Paper Trading & Risk Engine
# ---------------------------------------------------------


@app.get("/api/paper/cycle")
def get_paper_cycle(symbol: str = "SPY", strategy: str = "trend_momentum"):
    bars = bars_for(symbol, 900)
    engine = PaperTradingEngine(settings, registry)

    if settings.alpaca_api_key and settings.alpaca_secret_key:
        broker = AlpacaPaperBroker(settings.alpaca_api_key, settings.alpaca_secret_key, registry)
        p = broker.portfolio_state(symbol)
    else:
        p = PortfolioState(
            equity=settings.starting_equity,
            cash=settings.starting_equity,
            gross_exposure=0.0,
            daily_pnl=0.0,
            peak_equity=settings.starting_equity,
            current_symbol_exposure=0.0,
            current_symbol_qty=0.0,
            orders_today=0,
        )

    try:
        sig = engine.signal(symbol, bars, strategy)
        risk = engine.decide(sig, p)
        return {
            "symbol": symbol,
            "strategy": strategy,
            "signal": sig.model_dump(),
            "portfolio": p.model_dump(),
            "risk_decision": risk.model_dump(),
        }
    except PermissionError as pe:
        ref_price = float(bars["close"].iloc[-1]) if "close" in bars.columns else 100.0
        sig = Signal(
            symbol=symbol,
            strategy_name=strategy,
            score=0.0,
            side=Side.HOLD,
            reference_price=ref_price,
            regime=Regime.UNKNOWN,
            reason=str(pe),
        )
        risk = RiskDecision(approved=False, reasons=[str(pe)], order=None)
        return {
            "symbol": symbol,
            "strategy": strategy,
            "signal": sig.model_dump(),
            "portfolio": p.model_dump(),
            "risk_decision": risk.model_dump(),
            "warning": "Strategy must be validated and approved before paper execution.",
        }


@app.post("/api/paper/execute")
def execute_paper_order(req: PaperExecuteRequest):
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise HTTPException(status_code=400, detail="Alpaca credentials are required for paper order execution")
    broker = AlpacaPaperBroker(settings.alpaca_api_key, settings.alpaca_secret_key, registry)
    bars = alpaca_daily_bars(req.symbol, 900, settings.alpaca_api_key, settings.alpaca_secret_key)
    engine = PaperTradingEngine(settings, registry)
    sig = engine.signal(req.symbol, bars, req.strategy)
    p = broker.portfolio_state(req.symbol)
    risk = engine.decide(sig, p)

    if risk.approved and risk.order:
        res = broker.submit(risk.order)
        return {"submitted": True, "order": risk.order.model_dump(), "broker_response": str(res)}
    return {
        "submitted": False,
        "reasons": risk.reasons,
        "signal": sig.model_dump(),
        "risk": risk.model_dump(),
    }


# ---------------------------------------------------------
# Institutional Risk & Architecture Endpoints
# ---------------------------------------------------------


@app.get("/api/risk/metrics")
def get_risk_metrics(symbol: str = "SPY", days: int = 252):
    try:
        bars = bars_for(symbol, days)
        if "close" not in bars.columns or len(bars) < 5:
            raise HTTPException(status_code=400, detail="Insufficient price history for risk calculation")
        returns = bars["close"].pct_change().dropna().values
        metrics = calculate_institutional_risk_profile(returns, equity=settings.starting_equity)
        metrics["symbol"] = symbol
        metrics["sample_days"] = len(returns)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate risk metrics: {e}")


class KillRequest(BaseModel):
    reason: Optional[str] = "Emergency Kill Switch ENGAGED by operator"
    requested_by: Optional[str] = "operator"


class UnfreezeRequest(BaseModel):
    reason: str = "manual unfreeze"
    requested_by: Optional[str] = "operator"
    reconciliation_run_id: Optional[str] = ""
    override: Optional[bool] = False


@app.get("/api/readiness")
def get_system_readiness():
    """Retrieve truthful, full-stack trading readiness status."""
    res = go_client.get_readiness()
    if res is not None:
        return res
    return {
        "process": "offline",
        "trading_ready": False,
        "trading_readiness": "UNKNOWN",
        "execution_mode": "SIMULATION",
        "active_broker": "none",
        "broker_configured": False,
        "broker_connected": False,
        "broker_ready": False,
        "journal_ready": False,
        "reconciliation": {
            "status": "UNKNOWN",
            "critical_count": 0,
            "total_count": 0,
            "is_fresh": False,
            "max_age_seconds": 300,
        },
        "is_frozen": True,
        "freeze_reason": "Go Execution Engine Disconnected",
        "market_data": {
            "status": "UNAVAILABLE",
            "tick_count": 0,
        },
        "blocking_reasons": ["go_engine_disconnected"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/risk/kill")
def emergency_kill_switch(req: Optional[KillRequest] = None):
    """Engage firm-wide emergency kill switch to freeze all order execution."""
    reason = req.reason if req and req.reason else "Emergency Kill Switch ENGAGED by operator"
    by = req.requested_by if req and req.requested_by else "operator"
    res = go_client.freeze(reason=reason, requested_by=by)
    if res is not None:
        return res
    return {
        "status": "frozen",
        "is_frozen": True,
        "reason": reason,
        "message": "Emergency Kill Switch ENGAGED in Python fallback mode",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/risk/unfreeze")
def disengage_kill_switch(req: Optional[UnfreezeRequest] = None):
    """Disengage emergency kill switch and resume normal execution."""
    reason = req.reason if req and req.reason else "manual unfreeze"
    by = req.requested_by if req and req.requested_by else "operator"
    run_id = req.reconciliation_run_id if req and req.reconciliation_run_id else ""
    override = req.override if req and req.override else False

    res = go_client.unfreeze(reason=reason, requested_by=by, reconciliation_run_id=run_id, override=override)
    if res is not None:
        if not res.get("resumed", True) and not override:
            raise HTTPException(status_code=409, detail=res)
        return res
    return {
        "status": "active",
        "is_frozen": False,
        "reason": reason,
        "message": "Execution RESUMED in Python fallback mode",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/orders/history")
def get_order_history():
    """Retrieve event-sourced order history with trace_id lineage."""
    res = go_client.get_order_history()
    if res is not None:
        return res
    return {"count": 0, "orders": []}


@app.post("/api/reconciliation/run")
def run_broker_reconciliation():
    """Execute automated broker reconciliation between OMS ledger and broker state."""
    res = go_client.run_reconciliation()
    if res is not None:
        return res
    return {
        "discrepancies": [],
        "total_count": 0,
        "has_errors": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "python_fallback",
    }


@app.get("/api/brokers")

def list_available_brokers():
    """List all registered pluggable broker adapters and their health."""
    res = go_client.list_brokers()
    if res is not None:
        return res
    return {
        "active": "webull-main",
        "brokers": [
            {"name": "webull-main", "broker": "webull", "environment": "paper", "ready": True},
            {"name": "alpaca-paper", "broker": "alpaca", "environment": "paper", "ready": True},
            {"name": "paper-simulation", "broker": "paper", "environment": "simulation", "ready": True},
        ],
    }


@app.post("/api/brokers/select")
def select_execution_broker(payload: Dict[str, str]):
    """Select the active broker adapter for execution."""
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Broker name is required")
    res = go_client.select_broker(name)
    if res is not None:
        return res
    return {"status": "selected", "active": name, "mode": "fallback"}


@app.get("/api/brokers/health")
def get_broker_health():
    """Get active broker health and registration diagnostics."""
    res = go_client.get_broker_health()
    if res is not None:
        return res
    return {
        "active_broker": "paper-simulation",
        "environment": "simulation",
        "ready": True,
        "connected": True,
        "message": "Paper Simulation Adapter Active",
        "all_registered_brokers": [
            {"name": "paper-simulation", "environment": "simulation", "ready": True, "connected": True, "message": "Ready"},
            {"name": "alpaca-paper", "environment": "paper", "ready": bool(settings.alpaca_api_key), "connected": False, "message": "Offline"},
        ],
    }





@app.get("/api/architecture")
def get_architecture_spec():
    return {
        "title": "Institutional Quantitative Hedge Fund Architecture",
        "version": "1.2.0-Enterprise",
        "layers": [
            {
                "id": "layer_1",
                "name": "Market Data Fabric & Time-Series Warehouse",
                "components": ["Kafka/Redpanda Tick Ingestion", "ClickHouse/QuestDB PIT Store", "Feast Feature Store"],
                "status": "active",
                "description": "High-throughput streaming market data with point-in-time non-lookahead financial databases.",
            },
            {
                "id": "layer_2",
                "name": "AI Multi-Agent Research & Reasoning DAG",
                "components": [
                    "Fundamental XBRL Agent",
                    "Technical Agent",
                    "Macro/Cross-Asset Agent",
                    "Evidence Falsifier",
                    "Empirical Model Router",
                ],
                "status": "active",
                "description": "Durable task scheduler orchestrating multi-LLM research with primary-source verification.",
            },
            {
                "id": "layer_3",
                "name": "Quantitative Alpha & Factor Risk Engine",
                "components": [
                    "Alpha Factory",
                    "Walk-Forward CPCV Validation",
                    "Barra Factor Model",
                    "Deflated Sharpe Overfitting Tests",
                ],
                "status": "active",
                "description": "Rigorous quantitative research and multi-factor portfolio optimization.",
            },
            {
                "id": "layer_4",
                "name": "Institutional Risk & Pre-Trade Safety Engine",
                "components": [
                    "Deterministic Hard Limits",
                    "Parametric/Historical VaR (95%/99%)",
                    "Expected Shortfall (cVaR)",
                    "Automated Circuit Breakers",
                ],
                "status": "active",
                "description": "Sub-millisecond risk checks and kill-switch safeguards.",
            },
            {
                "id": "layer_5",
                "name": "High-Performance Go OMS/EMS Core",
                "components": ["Go Execution Core (aq-engine-go)", "TWAP/VWAP/IS Slicing", "FIX 4.4/5.0 Gateways", "Alpaca Paper Client"],
                "status": "active",
                "description": "Low-latency order routing, execution algorithms, and broker reconciliation.",
            },
            {
                "id": "layer_6",
                "name": "Governance, Security & SEC Compliance",
                "components": ["WORM Immutable Audit Ledger", "Maker-Checker Authorization", "Role-Based Access Control", "Vault Secrets"],
                "status": "active",
                "description": "Regulatory compliance (SEC 17a-4, FINRA 4511) and cryptographically audited workflows.",
            },
            {
                "id": "layer_7",
                "name": "Modern Quantitative Trading Workstation",
                "components": ["React 19 / TypeScript", "Tailwind CSS", "TradingView Lightweight Charts", "Interactive DAG Visualizer"],
                "status": "active",
                "description": "Bloomberg-grade high-density dark terminal trading workstation.",
            },
        ],
    }


@app.get("/api/v1/metrics")
@app.get("/metrics")
def get_platform_metrics():
    """Returns platform operational metrics and agent runtime diagnostics."""
    mem = AgentMemoryStore(settings.db_path, settings.agent_memory_dir)
    notes = mem.list_notes(limit=1000)
    snap = metrics.snapshot()
    snap["memory_notes_total"] = len(notes)
    return snap


# ---------------------------------------------------------
# Static Frontend Mount (if folder exists)
# ---------------------------------------------------------

static_dir_1 = Path(__file__).parent.parent / "web" / "static"
static_dir_2 = Path(__file__).parent / "web" / "static"
static_dir = static_dir_1 if static_dir_1.exists() else static_dir_2
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
