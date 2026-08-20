from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from ai_quant.agent_memory import AgentMemoryStore, MemoryKind, MemoryNote
from ai_quant.memory_maintenance import MemoryMaintenance


def cfg(tmp_path):
    return SimpleNamespace(
        db_path=str(tmp_path/'m.sqlite3'),agent_memory_dir=str(tmp_path/'journals'),openai_api_key=None,
        model_fast='luna',model_balanced='terra',model_frontier='sol',enable_pro_mode=False,
    )


def test_expiry_is_non_destructive_and_checkpoint_cites_sources(tmp_path):
    c=cfg(tmp_path); store=AgentMemoryStore(c.db_path,c.agent_memory_dir)
    old=store.add(MemoryNote(agent='a',kind=MemoryKind.OBSERVATION,content='expired observation',expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
    n1=store.add(MemoryNote(agent='a',kind=MemoryKind.LESSON,content='lesson one',importance=.8,confidence=.8))
    n2=store.add(MemoryNote(agent='a',kind=MemoryKind.FAILURE,content='failure two',importance=.9,confidence=.9))
    m=MemoryMaintenance(c)
    assert m.expire_due() == 1
    notes=store.list_notes(agent='a',limit=10)
    assert any(n.id==old.id and n.status=='expired' for n in notes)
    cp=m.checkpoint('a')
    assert cp is not None
    assert f'memory:{n1.id}' in cp.sources and f'memory:{n2.id}' in cp.sources
    # Originals are still present and active.
    active=store.list_notes(agent='a',active_only=True,limit=20)
    assert any(n.id==n1.id for n in active)
    assert any(n.id==n2.id for n in active)
