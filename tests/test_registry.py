import pytest
from ai_quant.registry import Registry
from ai_quant.factors import seed_strategies
from ai_quant.models import StrategyStatus

def test_candidate_cannot_be_approved(tmp_path):
    r=Registry(str(tmp_path/"x.db")); s=seed_strategies()[0]; r.upsert_strategy(s)
    with pytest.raises(PermissionError): r.approve(s.name)

def test_validated_can_be_approved(tmp_path):
    r=Registry(str(tmp_path/"x.db")); s=seed_strategies()[0]; r.upsert_strategy(s,StrategyStatus.VALIDATED); r.approve(s.name); got,status=r.get(s.name,True); assert got.name==s.name and status.value=="approved"
