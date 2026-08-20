from types import SimpleNamespace

from ai_quant.evaluation import EvaluationManager, TaskEvaluation
from ai_quant.model_router import ModelRouter, RouteRequest


def cfg(tmp_path):
    return SimpleNamespace(
        db_path=str(tmp_path/'e.sqlite3'),model_fast='luna',model_balanced='terra',model_frontier='sol',
        enable_pro_mode=False,openai_api_key=None,
        model_fast_input_usd_per_m=.1,model_fast_output_usd_per_m=.6,
        model_balanced_input_usd_per_m=1.0,model_balanced_output_usd_per_m=6.0,
        model_frontier_input_usd_per_m=2.5,model_frontier_output_usd_per_m=15.0,
        router_learning_min_samples=3,router_learning_min_quality=.7,router_learning_min_success=.8,
    )


def test_evaluation_recommends_observed_winner_and_requires_approval(tmp_path):
    c=cfg(tmp_path); ev=EvaluationManager(c)
    for _ in range(3):
        ev.record(TaskEvaluation(task_type='web_research',model='luna',tier='fast',success=True,quality_score=.84,evidence_score=.90,latency_ms=100,input_tokens=1000,output_tokens=200))
        ev.record(TaskEvaluation(task_type='web_research',model='terra',tier='balanced',success=True,quality_score=.85,evidence_score=.91,latency_ms=400,input_tokens=1000,output_tokens=200))
    rec=ev.recommend('web_research','balanced',min_samples=3)
    assert rec is not None
    # Luna is almost as good, but cheaper/faster, so utility should prefer it.
    assert rec.recommended_tier == 'fast'

    router=ModelRouter(c)
    before=router.decide(RouteRequest(task_type='web_research',complexity=.6,criticality=.6))
    assert before.policy_source == 'heuristic'
    ev.approve(rec.id)
    after=router.decide(RouteRequest(task_type='web_research',complexity=.6,criticality=.6))
    assert after.policy_source == 'approved_empirical_override'
    assert after.model == 'luna'


def test_capital_impact_ignores_noncapital_override(tmp_path):
    c=cfg(tmp_path); ev=EvaluationManager(c)
    for _ in range(3):
        ev.record(TaskEvaluation(task_type='promotion_review',model='luna',tier='fast',success=True,quality_score=.95,evidence_score=.95))
    rec=ev.recommend('promotion_review','frontier',min_samples=3)
    assert rec is not None
    ev.approve(rec.id,capital_approved=False)
    d=ModelRouter(c).decide(RouteRequest(task_type='promotion_review',complexity=.9,criticality=.95,financial_impact=.95))
    assert d.policy_source == 'heuristic'
    assert d.model == 'sol'
