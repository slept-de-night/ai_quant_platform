import React, { useEffect, useState } from 'react';
import { RuntimeStatus, TaskNode } from '../../types';
import { api } from '../../services/api';
import {
  GitFork,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  Flame
} from 'lucide-react';

interface RuntimeDAGViewProps {
  selectedSymbol: string;
}

export const RuntimeDAGView: React.FC<RuntimeDAGViewProps> = ({ selectedSymbol }) => {
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRunningPlan, setIsRunningPlan] = useState(false);
  const [executeAi, setExecuteAi] = useState(false);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const res = await api.getRuntimeStatus();
      setRuntimeStatus(res);
    } catch (err) {
      console.error('Failed to load runtime status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  const handlePlanAndRun = async () => {
    setIsRunningPlan(true);
    try {
      await api.runRuntimeDAG(selectedSymbol, executeAi, 4);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to run DAG:', err);
    } finally {
      setIsRunningPlan(false);
    }
  };

  const handleRequeue = async (taskId: string) => {
    try {
      await api.requeueTask(taskId, true);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to requeue task:', err);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
      {/* Control Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-xl bg-card border border-card-border shadow-md gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-mono font-bold bg-accent-blue/20 text-accent-blue border border-accent-blue/40 rounded">
              CONTROL PLANE
            </span>
            <span className="text-xs text-slate-400 font-mono">Durable DAG Runtime</span>
          </div>
          <h1 className="text-lg font-bold text-slate-100 mt-1">
            Multi-Agent Task Dependency Graph & Worker Pool
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Durable task execution with worker leases, exponential backoff retries, and dead-letter safety.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-slate-300 cursor-pointer bg-background px-3 py-2 rounded border border-card-border">
            <input
              type="checkbox"
              checked={executeAi}
              onChange={(e) => setExecuteAi(e.target.checked)}
              className="rounded accent-accent-cyan"
            />
            <span>Execute Live AI / Web</span>
          </label>

          <button
            onClick={handlePlanAndRun}
            disabled={isRunningPlan}
            className="flex items-center gap-2 px-4 py-2 bg-accent-blue hover:bg-blue-600 text-white font-semibold rounded-lg shadow-md transition cursor-pointer disabled:opacity-50 text-xs"
          >
            {isRunningPlan ? (
              <>
                <Cpu className="w-3.5 h-3.5 animate-spin" />
                <span>Executing Workers...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Dispatch DAG ({selectedSymbol})</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* DAG Summary Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Total Tasks</div>
          <div className="text-xl font-bold text-slate-100 mt-1">{runtimeStatus?.summary.total || 0}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Completed</div>
          <div className="text-xl font-bold text-accent-emerald mt-1">{runtimeStatus?.summary.completed || 0}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Running</div>
          <div className="text-xl font-bold text-accent-cyan mt-1">{runtimeStatus?.summary.running || 0}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Pending</div>
          <div className="text-xl font-bold text-slate-300 mt-1">{runtimeStatus?.summary.pending || 0}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Failed</div>
          <div className="text-xl font-bold text-accent-amber mt-1">{runtimeStatus?.summary.failed || 0}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-card border border-card-border font-mono text-center">
          <div className="text-[10px] text-slate-400">Dead Letters</div>
          <div className="text-xl font-bold text-accent-rose mt-1">{runtimeStatus?.summary.dead_letter || 0}</div>
        </div>
      </div>

      {/* Task Dependency Node Stream */}
      <div className="p-5 rounded-xl bg-card border border-card-border">
        <div className="flex items-center justify-between pb-4 border-b border-card-border mb-4">
          <div className="flex items-center gap-2">
            <GitFork className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
              Task Execution Stream & Dependency Trace
            </h2>
          </div>
          <button
            onClick={fetchStatus}
            disabled={isLoading}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-mono cursor-pointer"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Poll Stream</span>
          </button>
        </div>

        <div className="divide-y divide-card-border/40 font-mono text-xs">
          {(!runtimeStatus?.tasks || runtimeStatus.tasks.length === 0) ? (
            <div className="py-8 text-center text-slate-500">
              No tasks currently queued. Click 'Dispatch DAG' to orchestrate a new multi-agent research workflow.
            </div>
          ) : (
            runtimeStatus.tasks.map((task) => (
              <div key={task.task_id} className="py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:bg-background/40 px-2 rounded">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">
                    {task.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-accent-emerald" />
                    ) : task.status === 'running' ? (
                      <Cpu className="w-4 h-4 text-accent-cyan animate-spin" />
                    ) : task.status === 'dead_letter' ? (
                      <Flame className="w-4 h-4 text-accent-rose" />
                    ) : (
                      <Clock className="w-4 h-4 text-slate-500" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-200">{task.task_type}</span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-background border border-card-border text-accent-cyan">
                        {task.agent}
                      </span>
                      <span
                        className={`px-1.5 py-0.2 text-[9px] font-bold rounded ${
                          task.status === 'completed'
                            ? 'bg-accent-emerald/20 text-accent-emerald'
                            : task.status === 'running'
                            ? 'bg-accent-cyan/20 text-accent-cyan'
                            : task.status === 'dead_letter'
                            ? 'bg-accent-rose/20 text-accent-rose'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {task.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Task ID: <span className="text-slate-300">{task.task_id}</span> | Attempts: {task.attempts}/{task.max_attempts}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {task.latency_ms && (
                    <div className="text-slate-400 text-[11px]">
                      {task.latency_ms}ms
                    </div>
                  )}

                  {task.status === 'dead_letter' && (
                    <button
                      onClick={() => handleRequeue(task.task_id)}
                      className="px-2.5 py-1 bg-accent-rose/20 hover:bg-accent-rose/30 text-accent-rose border border-accent-rose/40 rounded text-[11px] font-bold transition cursor-pointer"
                    >
                      Requeue
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
