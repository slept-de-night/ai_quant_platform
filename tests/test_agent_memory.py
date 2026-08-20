from pathlib import Path
from ai_quant.agent_memory import AgentMemoryStore, MemoryKind, MemoryNote


def test_memory_append_supersede_and_markdown(tmp_path):
    db=str(tmp_path/'m.sqlite3')
    md=str(tmp_path/'journals')
    store=AgentMemoryStore(db,md)
    old=store.add(MemoryNote(agent='fundamental_agent',kind=MemoryKind.HYPOTHESIS,symbol='ABC',content='Revenue growth is accelerating.',confidence=.6,importance=.7))
    new=store.add(MemoryNote(agent='fundamental_agent',kind=MemoryKind.LESSON,symbol='ABC',content='New filing showed growth decelerated; old thesis is superseded.',confidence=.95,importance=.9,supersedes_id=old.id))
    notes=store.list_notes(agent='fundamental_agent',limit=10)
    assert any(n.id==old.id and n.status=='superseded' for n in notes)
    assert any(n.id==new.id and n.status=='active' for n in notes)
    p=store.render_agent('fundamental_agent')
    text=p.read_text(encoding='utf-8')
    assert 'SUPERSEDED' in text
    assert 'old thesis is superseded' in text


def test_active_summary_excludes_superseded(tmp_path):
    store=AgentMemoryStore(str(tmp_path/'m.sqlite3'),str(tmp_path/'journals'))
    a=store.add(MemoryNote(agent='a',kind=MemoryKind.TIP,content='old tip'))
    store.add(MemoryNote(agent='a',kind=MemoryKind.LESSON,content='new tip',supersedes_id=a.id))
    s=store.summary('a')
    assert 'new tip' in s
    assert 'old tip' not in s
