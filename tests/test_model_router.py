from types import SimpleNamespace
from ai_quant.model_router import ModelRouter, RouteRequest


def cfg(tmp_path):
    return SimpleNamespace(
        db_path=str(tmp_path/'r.sqlite3'), model_fast='luna', model_balanced='terra', model_frontier='sol',
        enable_pro_mode=True, openai_api_key=None,
    )


def test_router_uses_fast_for_simple_work(tmp_path):
    r=ModelRouter(cfg(tmp_path))
    d=r.decide(RouteRequest(task_type='extract',complexity=.1,criticality=.2))
    assert d.model=='luna'
    assert d.reasoning_effort in {'none','low'}


def test_router_escalates_critical_hypothesis(tmp_path):
    r=ModelRouter(cfg(tmp_path))
    d=r.decide(RouteRequest(task_type='falsification',complexity=.95,criticality=.95,ambiguity=.9,financial_impact=.9,quality_first=True))
    assert d.model=='sol'
    assert d.reasoning_effort in {'xhigh','max'}
