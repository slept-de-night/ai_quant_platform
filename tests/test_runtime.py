from datetime import timedelta
from types import SimpleNamespace
import sqlite3

from ai_quant.runtime import RuntimeStatus, TaskRuntime, WorkerPool


def cfg(tmp_path):
    return SimpleNamespace(
        db_path=str(tmp_path/'runtime.sqlite3'),
        runtime_concurrency=3,
        runtime_lease_seconds=1,
        runtime_max_attempts=2,
        runtime_retry_base_seconds=0,
        runtime_max_retry_delay_seconds=0,
    )


def test_idempotent_enqueue(tmp_path):
    rt=TaskRuntime(cfg(tmp_path))
    a=rt.enqueue(task_id=None,root_id=None,parent_id=None,agent_role='a',task_type='x',objective='same',idempotency_key='same')
    b=rt.enqueue(task_id=None,root_id=None,parent_id=None,agent_role='a',task_type='x',objective='same',idempotency_key='same')
    assert a.task_id == b.task_id
    assert len(rt.list_tasks()) == 1


def test_dependency_blocks_parent_until_child_done(tmp_path):
    rt=TaskRuntime(cfg(tmp_path))
    child=rt.enqueue(task_id='child',root_id='root',parent_id='root',agent_role='child',task_type='leaf',objective='leaf',idempotency_key='child')
    parent=rt.enqueue(task_id='root',root_id='root',parent_id=None,agent_role='manager',task_type='manager',objective='manager',idempotency_key='root',depends_on=['child'])

    leased=rt.lease('w',limit=10)
    assert [x.task_id for x in leased] == ['child']
    rt.complete('child','w',{'ok':True})
    leased=rt.lease('w2',limit=10)
    assert [x.task_id for x in leased] == ['root']


def test_retry_then_dead_letter(tmp_path):
    rt=TaskRuntime(cfg(tmp_path))
    t=rt.enqueue(task_id='t',root_id='t',parent_id=None,agent_role='a',task_type='boom',objective='boom',idempotency_key='t')
    rt.lease('w',1)
    assert rt.fail('t','w','first') == RuntimeStatus.RETRY
    rt.lease('w2',1)
    assert rt.fail('t','w2','second') == RuntimeStatus.DEAD_LETTER
    assert rt.get('t').attempts == 2


def test_worker_pool_executes_dag(tmp_path):
    rt=TaskRuntime(cfg(tmp_path))
    rt.enqueue(task_id='a',root_id='root',parent_id='root',agent_role='a',task_type='leaf',objective='a',idempotency_key='a')
    rt.enqueue(task_id='b',root_id='root',parent_id='root',agent_role='b',task_type='leaf',objective='b',idempotency_key='b')
    rt.enqueue(task_id='root',root_id='root',parent_id=None,agent_role='m',task_type='manager',objective='m',idempotency_key='root',depends_on=['a','b'])

    def leaf(task,deps): return {'name':task.task_id}
    def manager(task,deps): return {'children':sorted(x['name'] for x in deps.values())}
    WorkerPool(rt,{'leaf':leaf,'manager':manager}).run_until_idle(concurrency=3)
    root=rt.get('root')
    assert root.status == RuntimeStatus.SUCCEEDED
    assert root.output['children'] == ['a','b']
