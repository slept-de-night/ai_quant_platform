from types import SimpleNamespace

from ai_quant.deployment import DeploymentStatus, ModelControlPlane


def cfg(tmp_path):
    return SimpleNamespace(db_path=str(tmp_path/'d.sqlite3'),model_fast='luna',model_balanced='terra',model_frontier='sol')


def test_candidate_requires_activation(tmp_path):
    c=ModelControlPlane(cfg(tmp_path))
    did=c.register_candidate('balanced','terra-next','candidate')
    assert c.resolve('balanced').model == 'terra'
    c.activate(did)
    assert c.resolve('balanced').model == 'terra-next'


def test_disabled_frontier_falls_back(tmp_path):
    c=ModelControlPlane(cfg(tmp_path))
    current=[x for x in c.list_deployments() if x['tier']=='frontier' and x['is_active']][0]
    c.set_health(current['id'],DeploymentStatus.DISABLED,'test')
    r=c.resolve('frontier')
    assert r.model == 'terra'
    assert r.fallback_used
