# Runtime and model routing: v1.2

v1.2 adds a durable local execution control plane around the research agents.

## Runtime semantics

Research work is represented as a DAG, not a recursive chain of free-running agents.

```text
technical ─────┐
fundamental ───┼─> market manager ───────────────┐
microtrend ────┤                                 │
megatrend ─────┘                                 │
                                                  ├─> future/falsification -> thesis manager ─┐
web evidence -> contradiction -> evidence manager┘                                           │
                                                                                               ├─> audit -> research manager
                                                                                               └───────────────┘
```

A task has:

- stable task ID and root run ID
- idempotency key
- explicit dependencies
- priority
- attempt count and maximum attempts
- `queued / running / retry / succeeded / dead_letter / cancelled` state
- worker lease and lease expiration
- payload and result JSON
- append-style runtime event history

Workers claim tasks with a SQLite `BEGIN IMMEDIATE` lease transaction. Expired leases are recovered. Retriable failures use exponential backoff and terminal failures go to dead-letter state.

This is appropriate for one-machine research/paper trading. It is **not** a substitute for a distributed queue when running multiple hosts.

## Dependency rule

Coordinator tasks depend on their children. Additional cross-branch dependencies are explicit. For example:

- contradiction checking waits for web evidence;
- future and falsification tasks wait for market + evidence summaries;
- audit waits for market, evidence, and thesis outputs;
- the root research manager runs last.

This prevents summaries from racing ahead of their inputs.

## Model deployment control

Agent code requests a capability tier instead of hard-coding a model:

```text
fast      -> active fast deployment
balanced  -> active balanced deployment
frontier  -> active frontier deployment
```

Each tier has a versioned deployment registry. A candidate model is registered inactive, then explicitly activated.

Deployment health states:

- `healthy`
- `degraded`
- `disabled`

If an active deployment is degraded or disabled, the router may fall back one tier when the task permits degradation. Quality-critical routes can disable degradation.

`model-probe` can run a tiny live API probe. By default the probe only records the result. `--apply-health` is required to modify health state.

## Empirical routing

`task_evaluations` records:

- task type
- concrete model and tier
- success/failure
- quality score
- evidence score
- latency
- input/output tokens
- estimated cost
- evaluator and notes

The evaluation manager computes observed performance by task type and model. It can then produce a **routing recommendation**.

Recommendations never change routing automatically.

```text
observations -> recommendation -> human review -> approved override
```

For `financial_impact >= 0.80`, a normal approved override is ignored unless the override was separately approved with `--capital-approved`.

This prevents a cheap model from taking over critical portfolio review merely because it won a small noisy sample.

## Per-run AI budget

Routed API calls can carry a `run_id`. Their usage and estimated USD cost are logged in `model_routes`.

If current recorded spend reaches `AGENT_USD_BUDGET_PER_RUN`, further routed calls for that run are rejected.

This is a local guardrail, not a billing-system replacement. Keep provider/project spend limits enabled too.

## Memory maintenance

Memory housekeeping is non-destructive:

- due notes become `expired`; they are not deleted;
- checkpoints create new derived notes;
- checkpoint notes cite their source memory IDs (`memory:123`);
- original observations/failures remain in the ledger and Markdown journals.

That lets agents learn from history without rewriting history.
