from types import SimpleNamespace
import pytest
from ai_quant.orchestrator import DelegationRequest, TaskOrchestrator


def cfg(tmp_path):
    return SimpleNamespace(
        db_path=str(tmp_path/'o.sqlite3'), model_fast='luna', model_balanced='terra', model_frontier='sol',
        enable_pro_mode=False, openai_api_key=None,
        agent_max_depth=2, agent_max_children=4, agent_max_tasks_per_run=24,
        agent_token_budget=180000, agent_max_frontier_tasks=6,
    )


def test_research_plan_is_bounded_and_routed(tmp_path):
    o=TaskOrchestrator(cfg(tmp_path))
    nodes=o.plan_research('NVDA')
    assert len(nodes) == 13
    assert max(n.depth for n in nodes) == 2
    leaves=[n for n in nodes if n.depth==2]
    assert all(n.route is not None for n in leaves)
    assert any(n.route.model=='sol' for n in nodes if n.route)
    assert any(n.route.model=='luna' for n in nodes if n.route)


def test_spawn_depth_limit(tmp_path):
    o=TaskOrchestrator(cfg(tmp_path))
    root=o.create_root('manager','root','x')
    child=o.spawn_child(root,DelegationRequest(agent_role='technical_agent',task_type='extract',objective='x'))
    grand=o.spawn_child(child,DelegationRequest(agent_role='fundamental_agent',task_type='extract',objective='x'))
    with pytest.raises(PermissionError):
        o.spawn_child(grand,DelegationRequest(agent_role='microtrend_agent',task_type='extract',objective='x'))
