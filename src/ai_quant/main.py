from __future__ import annotations
import argparse, json
from .alpha_factory import AlphaFactory
from .agent_memory import AgentMemoryStore, MemoryKind, MemoryNote
from .model_router import ModelRouter, RouteRequest
from .orchestrator import TaskOrchestrator
from .deployment import ModelControlPlane, DeploymentStatus
from .evaluation import EvaluationManager, TaskEvaluation
from .runtime import TaskRuntime, WorkerPool
from .runtime_handlers import ResearchRuntimeHandlers
from .memory_maintenance import MemoryMaintenance
from .backtest import run_backtest
from .broker import AlpacaPaperBroker
from .config import settings
from .data import alpaca_daily_bars, synthetic_bars
from .engine import PaperTradingEngine
from .factors import seed_strategies
from .intelligence import IntelligenceEngine
from .portfolio import portfolio_backtest
from .registry import Registry
from .validation import walk_forward_validate

registry=Registry(settings.db_path)

def bars_for(symbol,days=1600):
    if settings.use_alpaca_data:
        if not settings.alpaca_api_key or not settings.alpaca_secret_key: raise RuntimeError("USE_ALPACA_DATA=true but Alpaca credentials are missing")
        return alpaca_daily_bars(symbol,days,settings.alpaca_api_key,settings.alpaca_secret_key)
    return synthetic_bars(symbol,days)

def show(obj):
    if hasattr(obj,"model_dump"): print(json.dumps(obj.model_dump(mode="json"),indent=2,default=str))
    else: print(obj)

def seed_registry():
    for s in seed_strategies(): registry.upsert_strategy(s)

def cmd_memory_list(agent=None,symbol=None,limit=30):
    mem=AgentMemoryStore(settings.db_path,settings.agent_memory_dir)
    notes=mem.list_notes(agent=agent,symbol=symbol,limit=limit,active_only=False)
    if not notes:
        print("No agent memory notes found")
        return
    for n in notes:
        print(f"{n.id:5} {n.created_at.isoformat()} {n.agent:24} {n.kind.value:12} {n.symbol or 'GLOBAL':8} {n.status:10} conf={n.confidence:.2f} imp={n.importance:.2f} | {n.content[:180]}")

def cmd_memory_render():
    mem=AgentMemoryStore(settings.db_path,settings.agent_memory_dir)
    paths=mem.render_all()
    print(f"Rendered {len(paths)} agent journals to {settings.agent_memory_dir}/")
    for p in paths: print(p)

def cmd_agent_note(agent,kind,content,symbol=None,confidence=.7,importance=.6):
    mem=AgentMemoryStore(settings.db_path,settings.agent_memory_dir)
    note=mem.add(MemoryNote(agent=agent,kind=MemoryKind(kind),content=content,symbol=symbol,confidence=confidence,importance=importance,tags=["manual-note"]))
    print(f"Added memory note {note.id}; journal refreshed")

def cmd_route_preview(task_type,complexity,criticality,ambiguity,financial_impact,quality_first):
    router=ModelRouter(settings)
    req=RouteRequest(task_type=task_type,complexity=complexity,criticality=criticality,ambiguity=ambiguity,financial_impact=financial_impact,quality_first=quality_first)
    show(router.decide(req))

def cmd_orchestrator_plan(symbol):
    orch=TaskOrchestrator(settings)
    nodes=orch.plan_research(symbol)
    by_parent={}
    for n in nodes: by_parent.setdefault(n.parent_id,[]).append(n)
    def walk(node,prefix=""):
        route=f" -> {node.route.model}/{node.route.reasoning_effort}" if node.route else ""
        print(f"{prefix}{node.agent_role} [{node.task_type}]{route} | est={node.estimated_tokens} tokens")
        for c in by_parent.get(node.task_id,[]): walk(c,prefix+"  ")
    walk(nodes[0])
    print(f"root_task_id: {nodes[0].root_id}")

def cmd_runtime_plan(symbol):
    orch=TaskOrchestrator(settings)
    nodes=orch.plan_research(symbol)
    rt=TaskRuntime(settings)
    rt.enqueue_plan(nodes)
    print(f"runtime root: {nodes[0].root_id}")
    print(json.dumps(rt.status(nodes[0].root_id),indent=2))

def cmd_runtime_run(symbol,execute_ai=False,concurrency=None):
    orch=TaskOrchestrator(settings)
    nodes=orch.plan_research(symbol)
    rt=TaskRuntime(settings)
    rt.enqueue_plan(nodes)
    handlers=ResearchRuntimeHandlers(settings,bars_for,execute_ai=execute_ai).handlers()
    pool=WorkerPool(rt,handlers)
    results=pool.run_until_idle(concurrency=concurrency)
    print(f"runtime root: {nodes[0].root_id}")
    print(f"executed tasks: {len(results)}")
    print(json.dumps(rt.status(nodes[0].root_id),indent=2))
    root=rt.get(nodes[0].root_id)
    if root.output:
        print("ROOT OUTPUT")
        print(json.dumps(root.output,indent=2,default=str)[:12000])

def cmd_runtime_status(root_id=None):
    rt=TaskRuntime(settings)
    print(json.dumps(rt.status(root_id),indent=2))
    for t in rt.list_tasks(root_id=root_id,limit=100):
        print(f"{t.task_id[:8]} {t.status.value:12} attempts={t.attempts}/{t.max_attempts} {t.agent_role:24} {t.task_type:20} {t.symbol or '-'}")

def cmd_runtime_events(task_id=None,limit=50):
    rt=TaskRuntime(settings)
    print(json.dumps(rt.events(task_id=task_id,limit=limit),indent=2,default=str))

def cmd_runtime_requeue(task_id,reset_attempts=False):
    rt=TaskRuntime(settings); rt.requeue(task_id,reset_attempts=reset_attempts)
    print(f"requeued {task_id}")

def cmd_model_deployments():
    cp=ModelControlPlane(settings)
    print(json.dumps(cp.list_deployments(),indent=2,default=str))

def cmd_model_register(tier,model,notes):
    cp=ModelControlPlane(settings); did=cp.register_candidate(tier,model,notes)
    print(f"registered deployment {did}; inactive until model-activate")

def cmd_model_activate(deployment_id):
    ModelControlPlane(settings).activate(deployment_id); print(f"activated deployment {deployment_id}")

def cmd_model_health(deployment_id,status,reason):
    ModelControlPlane(settings).set_health(deployment_id,DeploymentStatus(status),reason)
    print(f"deployment {deployment_id} -> {status}")

def cmd_model_probe(deployment_id,apply_health=False):
    print(json.dumps(ModelControlPlane(settings).probe(deployment_id,apply_health=apply_health),indent=2,default=str))

def cmd_eval_record(task_type,model,tier,success,quality,evidence,latency_ms,input_tokens,output_tokens,notes):
    ev=EvaluationManager(settings)
    eid=ev.record(TaskEvaluation(task_type=task_type,model=model,tier=tier,success=success,quality_score=quality,evidence_score=evidence,latency_ms=latency_ms,input_tokens=input_tokens,output_tokens=output_tokens,evaluator="manual",notes=notes))
    print(f"evaluation {eid} recorded")

def cmd_model_performance(task_type=None,min_samples=1):
    print(json.dumps(EvaluationManager(settings).performance(task_type,min_samples),indent=2,default=str))

def cmd_route_recommend(task_type,current_tier,min_samples=None):
    rec=EvaluationManager(settings).recommend(task_type,current_tier,min_samples)
    if rec is None: print("Not enough trustworthy evidence to recommend a routing change")
    else: show(rec)

def cmd_route_recommendations(status=None):
    print(json.dumps(EvaluationManager(settings).list_recommendations(status),indent=2,default=str))

def cmd_route_approve(rec_id,capital_approved=False):
    rec=EvaluationManager(settings).approve(rec_id,capital_approved=capital_approved)
    print(f"approved routing recommendation {rec_id} for {rec.task_type}; capital_approved={capital_approved}")

def cmd_route_reject(rec_id):
    EvaluationManager(settings).reject(rec_id); print(f"rejected routing recommendation {rec_id}")

def cmd_memory_maintain(agent=None,symbol=None):
    m=MemoryMaintenance(settings)
    expired=m.expire_due(); print(f"expired due notes: {expired}")
    if agent:
        note=m.checkpoint(agent,symbol=symbol)
        print(f"checkpoint: {note.id if note else 'not enough active notes'}")

def cmd_doctor():
    import ai_quant
    print(f"ai-quant {ai_quant.__version__}")
    print(f"OpenAI configured: {bool(settings.openai_api_key)}")
    print(f"OpenAI web research: {settings.enable_web_research}")
    print(f"Model routing: fast={settings.model_fast}, balanced={settings.model_balanced}, frontier={settings.model_frontier}")
    print(f"Agent delegation: depth<={settings.agent_max_depth}, children<={settings.agent_max_children}, tasks<={settings.agent_max_tasks_per_run}, token_budget={settings.agent_token_budget}")
    print(f"Agent memory journals: {settings.agent_memory_dir}/")
    print(f"Runtime: concurrency={settings.runtime_concurrency}, lease={settings.runtime_lease_seconds}s, attempts={settings.runtime_max_attempts}")
    print(f"Router learning: min_samples={settings.router_learning_min_samples}, min_quality={settings.router_learning_min_quality:.2f}, min_success={settings.router_learning_min_success:.2f}")
    print(f"SEC fundamentals configured: {bool(settings.sec_user_agent)}")
    print(f"FRED macro configured: {bool(settings.fred_api_key)}")
    print(f"Alpaca configured: {bool(settings.alpaca_api_key and settings.alpaca_secret_key)}")
    print(f"Data source: {'Alpaca' if settings.use_alpaca_data else 'synthetic'}")
    print(f"Fresh dossier required for new paper buys: {settings.require_fresh_dossier}")
    print("Live-money trading: DISABLED BY DESIGN")
    seed_registry(); print(f"Registry: {settings.db_path}")

def cmd_backtest(symbol,strategy,days):
    seed_registry(); spec,_=registry.get(strategy); m,_=run_backtest(bars_for(symbol,days),spec,settings.slippage_bps,settings.commission_bps); show(m)

def cmd_validate(symbol,strategy,days):
    seed_registry(); spec,_=registry.get(strategy); r=walk_forward_validate(bars_for(symbol,days),spec,settings.wf_train_days,settings.wf_test_days,settings.wf_step_days,settings.min_wf_folds,settings.slippage_bps,settings.commission_bps,settings.min_validation_sharpe,settings.max_validation_drawdown,settings.min_robust_score); registry.upsert_strategy(spec,report=r,status=(__import__('ai_quant.models',fromlist=['StrategyStatus']).StrategyStatus.VALIDATED if r.passed else __import__('ai_quant.models',fromlist=['StrategyStatus']).StrategyStatus.CANDIDATE)); registry.record_experiment(symbol,spec,r); show(r)

def cmd_alpha(symbol,count,days):
    seed_registry(); results=AlphaFactory(settings,registry).run(symbol,bars_for(symbol,days),count)
    for c,r in results:
        print(f"\n### {c.strategy.name}\n{c.strategy.hypothesis}")
        if isinstance(r,Exception): print("ERROR:",r)
        else: print(f"passed={r.passed} robust={r.robust_score:.3f} median_sharpe={r.median_sharpe:.3f} worst_dd={r.worst_drawdown:.1%}")

def cmd_list():
    seed_registry()
    for n,s,t in registry.list_strategies(): print(f"{n:32} {s:10} {t}")

def cmd_approve(name): registry.approve(name); print(f"Approved: {name}")

def cmd_portfolio(symbols,strategy,days):
    seed_registry(); spec,_=registry.get(strategy); data={s:bars_for(s,days) for s in symbols}; m,_=portfolio_backtest(data,spec,slippage_bps=settings.slippage_bps); show(m)

def cmd_deep_research(symbol,market,sector,growth,bond,gold,days):
    symbol_bars=bars_for(symbol,days)
    market_bars=bars_for(market,days)
    sector_bars=bars_for(sector,days) if sector else None
    growth_bars=bars_for(growth,days) if growth else None
    bond_bars=bars_for(bond,days) if bond else None
    gold_bars=bars_for(gold,days) if gold else None
    dossier=IntelligenceEngine(settings,registry).build(symbol,symbol_bars,market_bars,sector_bars,growth_bars,bond_bars,gold_bars)
    show(dossier)

def cmd_research_status(symbol):
    d=registry.get_dossier(symbol,require_fresh=False)
    if not d: print(f"No research dossier for {symbol.upper()}"); return
    print(f"symbol: {d.symbol}")
    print(f"generated_at: {d.generated_at.isoformat()}")
    print(f"expires_at: {d.expires_at.isoformat()}")
    print(f"evidence trust: {d.evidence.overall_trust:.2f}")
    print(f"verified claim ratio: {d.evidence.verified_claim_ratio:.2f}")
    print(f"technical: {d.technical.direction.value} ({d.technical.score:+.2f})")
    print(f"fundamental: {d.fundamental.direction.value} ({d.fundamental.score:+.2f})")
    print(f"microtrend: {d.microtrend.direction.value} ({d.microtrend.score:+.2f})")
    print(f"megatrend: {d.megatrend.direction.value} ({d.megatrend.score:+.2f})")
    print(f"future: {d.future.score:+.2f} confidence={d.future.confidence:.2f}")
    print(f"context sizing multiplier: {d.adjustment.multiplier:.2f}")
    if d.adjustment.reasons: print("gate: " + " | ".join(d.adjustment.reasons))

def cmd_paper(symbol,strategy,execute):
    if not settings.alpaca_api_key or not settings.alpaca_secret_key: raise RuntimeError("Alpaca credentials required")
    broker=AlpacaPaperBroker(settings.alpaca_api_key,settings.alpaca_secret_key,registry); bars=alpaca_daily_bars(symbol,900,settings.alpaca_api_key,settings.alpaca_secret_key)
    engine=PaperTradingEngine(settings,registry); sig=engine.signal(symbol,bars,strategy); p=broker.portfolio_state(symbol); risk=engine.decide(sig,p)
    print("SIGNAL"); show(sig); print("RISK"); show(risk)
    if execute and risk.approved and risk.order: print(broker.submit(risk.order))
    elif execute: print("No order submitted")
    else: print("Dry run only. Pass --execute to submit to ALPACA PAPER account.")

def cmd_web(host="0.0.0.0", port=8000):
    import uvicorn
    from .server import app
    print(f"Starting AI Quant Web Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

def main():
    ap=argparse.ArgumentParser(description="AI Quant Platform v1.2 - durable task runtime + model deployment control + empirical routing evaluation + auditable quant research")
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("doctor")
    p=sub.add_parser("web"); p.add_argument("--host",default="0.0.0.0"); p.add_argument("--port",type=int,default=8000)
    p=sub.add_parser("backtest"); p.add_argument("--symbol",default="SPY"); p.add_argument("--strategy",default="trend_momentum"); p.add_argument("--days",type=int,default=1600)
    p=sub.add_parser("validate"); p.add_argument("--symbol",default="SPY"); p.add_argument("--strategy",default="trend_momentum"); p.add_argument("--days",type=int,default=1800)
    p=sub.add_parser("alpha-search"); p.add_argument("--symbol",default="SPY"); p.add_argument("--count",type=int,default=None); p.add_argument("--days",type=int,default=1800)
    sub.add_parser("list-strategies")
    p=sub.add_parser("approve"); p.add_argument("name")
    p=sub.add_parser("portfolio-backtest"); p.add_argument("--symbols",default="SPY,QQQ,IWM,GLD,TLT"); p.add_argument("--strategy",default="trend_momentum"); p.add_argument("--days",type=int,default=1600)
    p=sub.add_parser("deep-research"); p.add_argument("--symbol",required=True); p.add_argument("--market",default="SPY"); p.add_argument("--sector",default=None); p.add_argument("--growth",default="QQQ"); p.add_argument("--bond",default="TLT"); p.add_argument("--gold",default="GLD"); p.add_argument("--days",type=int,default=1000)
    p=sub.add_parser("research-status"); p.add_argument("--symbol",required=True)
    p=sub.add_parser("paper-cycle"); p.add_argument("--symbol",default="SPY"); p.add_argument("--strategy",required=True); p.add_argument("--execute",action="store_true")
    p=sub.add_parser("memory-list"); p.add_argument("--agent",default=None); p.add_argument("--symbol",default=None); p.add_argument("--limit",type=int,default=30)
    sub.add_parser("memory-render")
    p=sub.add_parser("agent-note"); p.add_argument("--agent",required=True); p.add_argument("--kind",choices=[x.value for x in MemoryKind],default="observation"); p.add_argument("--content",required=True); p.add_argument("--symbol",default=None); p.add_argument("--confidence",type=float,default=.7); p.add_argument("--importance",type=float,default=.6)
    p=sub.add_parser("route-preview"); p.add_argument("--task-type",default="web_research"); p.add_argument("--complexity",type=float,default=.5); p.add_argument("--criticality",type=float,default=.5); p.add_argument("--ambiguity",type=float,default=.3); p.add_argument("--financial-impact",type=float,default=.0); p.add_argument("--quality-first",action="store_true")
    p=sub.add_parser("orchestrator-plan"); p.add_argument("--symbol",required=True)
    p=sub.add_parser("runtime-plan"); p.add_argument("--symbol",required=True)
    p=sub.add_parser("runtime-run"); p.add_argument("--symbol",required=True); p.add_argument("--execute-ai",action="store_true"); p.add_argument("--concurrency",type=int,default=None)
    p=sub.add_parser("runtime-status"); p.add_argument("--root",default=None)
    p=sub.add_parser("runtime-events"); p.add_argument("--task",default=None); p.add_argument("--limit",type=int,default=50)
    p=sub.add_parser("runtime-requeue"); p.add_argument("task_id"); p.add_argument("--reset-attempts",action="store_true")
    sub.add_parser("model-deployments")
    p=sub.add_parser("model-register"); p.add_argument("--tier",choices=["fast","balanced","frontier"],required=True); p.add_argument("--model",required=True); p.add_argument("--notes",default="")
    p=sub.add_parser("model-activate"); p.add_argument("deployment_id",type=int)
    p=sub.add_parser("model-health"); p.add_argument("deployment_id",type=int); p.add_argument("--status",choices=[x.value for x in DeploymentStatus],required=True); p.add_argument("--reason",default="")
    p=sub.add_parser("model-probe"); p.add_argument("deployment_id",type=int); p.add_argument("--apply-health",action="store_true")
    p=sub.add_parser("eval-record"); p.add_argument("--task-type",required=True); p.add_argument("--model",required=True); p.add_argument("--tier",required=True); p.add_argument("--success",action="store_true"); p.add_argument("--quality",type=float,default=.5); p.add_argument("--evidence",type=float,default=.5); p.add_argument("--latency-ms",type=float,default=0); p.add_argument("--input-tokens",type=int,default=0); p.add_argument("--output-tokens",type=int,default=0); p.add_argument("--notes",default="")
    p=sub.add_parser("model-performance"); p.add_argument("--task-type",default=None); p.add_argument("--min-samples",type=int,default=1)
    p=sub.add_parser("route-recommend"); p.add_argument("--task-type",required=True); p.add_argument("--current-tier",choices=["fast","balanced","frontier"],required=True); p.add_argument("--min-samples",type=int,default=None)
    p=sub.add_parser("route-recommendations"); p.add_argument("--status",choices=["proposed","approved","rejected"],default=None)
    p=sub.add_parser("route-approve"); p.add_argument("recommendation_id",type=int); p.add_argument("--capital-approved",action="store_true")
    p=sub.add_parser("route-reject"); p.add_argument("recommendation_id",type=int)
    p=sub.add_parser("memory-maintain"); p.add_argument("--agent",default=None); p.add_argument("--symbol",default=None)
    a=ap.parse_args()
    if a.cmd=="doctor": cmd_doctor()
    elif a.cmd=="web": cmd_web(a.host, a.port)
    elif a.cmd=="backtest": cmd_backtest(a.symbol,a.strategy,a.days)
    elif a.cmd=="validate": cmd_validate(a.symbol,a.strategy,a.days)
    elif a.cmd=="alpha-search": cmd_alpha(a.symbol,a.count,a.days)
    elif a.cmd=="list-strategies": cmd_list()
    elif a.cmd=="approve": cmd_approve(a.name)
    elif a.cmd=="portfolio-backtest": cmd_portfolio([x.strip() for x in a.symbols.split(',') if x.strip()],a.strategy,a.days)
    elif a.cmd=="deep-research": cmd_deep_research(a.symbol,a.market,a.sector,a.growth,a.bond,a.gold,a.days)
    elif a.cmd=="research-status": cmd_research_status(a.symbol)
    elif a.cmd=="paper-cycle": cmd_paper(a.symbol,a.strategy,a.execute)
    elif a.cmd=="memory-list": cmd_memory_list(a.agent,a.symbol,a.limit)
    elif a.cmd=="memory-render": cmd_memory_render()
    elif a.cmd=="agent-note": cmd_agent_note(a.agent,a.kind,a.content,a.symbol,a.confidence,a.importance)
    elif a.cmd=="route-preview": cmd_route_preview(a.task_type,a.complexity,a.criticality,a.ambiguity,a.financial_impact,a.quality_first)
    elif a.cmd=="orchestrator-plan": cmd_orchestrator_plan(a.symbol)
    elif a.cmd=="runtime-plan": cmd_runtime_plan(a.symbol)
    elif a.cmd=="runtime-run": cmd_runtime_run(a.symbol,a.execute_ai,a.concurrency)
    elif a.cmd=="runtime-status": cmd_runtime_status(a.root)
    elif a.cmd=="runtime-events": cmd_runtime_events(a.task,a.limit)
    elif a.cmd=="runtime-requeue": cmd_runtime_requeue(a.task_id,a.reset_attempts)
    elif a.cmd=="model-deployments": cmd_model_deployments()
    elif a.cmd=="model-register": cmd_model_register(a.tier,a.model,a.notes)
    elif a.cmd=="model-activate": cmd_model_activate(a.deployment_id)
    elif a.cmd=="model-health": cmd_model_health(a.deployment_id,a.status,a.reason)
    elif a.cmd=="model-probe": cmd_model_probe(a.deployment_id,a.apply_health)
    elif a.cmd=="eval-record": cmd_eval_record(a.task_type,a.model,a.tier,a.success,a.quality,a.evidence,a.latency_ms,a.input_tokens,a.output_tokens,a.notes)
    elif a.cmd=="model-performance": cmd_model_performance(a.task_type,a.min_samples)
    elif a.cmd=="route-recommend": cmd_route_recommend(a.task_type,a.current_tier,a.min_samples)
    elif a.cmd=="route-recommendations": cmd_route_recommendations(a.status)
    elif a.cmd=="route-approve": cmd_route_approve(a.recommendation_id,a.capital_approved)
    elif a.cmd=="route-reject": cmd_route_reject(a.recommendation_id)
    elif a.cmd=="memory-maintain": cmd_memory_maintain(a.agent,a.symbol)

if __name__=="__main__": main()
