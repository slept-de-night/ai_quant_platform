# Skill: Bounded delegation

## Purpose
Allow an agent to request specialist help when a task is too broad while preventing recursive agent explosions.

## Rules

1. Agents do not directly create arbitrary processes or peer agents.
2. An agent submits a `DelegationRequest` to `TaskOrchestrator.spawn_child()`.
3. Every request declares role, task type, objective, complexity, criticality, ambiguity, financial impact, and estimated token cost.
4. The orchestrator enforces maximum depth, children per parent, total task count, total token budget, and frontier-model task count.
5. Delegated tasks must be narrower than the parent task.
6. Do not delegate deterministic calculations to an LLM if normal code can do them safely.
7. High financial-impact work must not be downgraded merely because the token budget is low. Reduce scope instead.
8. Child agents cannot approve strategies, override risk controls, enable live trading, or edit audit history.
9. If delegation is rejected, the parent must continue with a reduced-scope best effort or mark the work incomplete.
