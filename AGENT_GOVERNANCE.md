# Agent governance: v1.2

This platform treats agents as bounded research workers, not autonomous principals.

## Control hierarchy

```text
Research Manager
├── Market Structure Manager
│   ├── Technical Agent
│   ├── Fundamental Agent
│   ├── Microtrend Agent
│   └── Megatrend Agent
├── Evidence Manager
│   ├── Web Research Agent
│   └── Contradiction Agent
├── Thesis Manager
│   ├── Future Scenario Agent
│   └── Falsification Agent
└── Audit Agent
```

The hierarchy is a task graph. A child task can be created only through the orchestrator and only inside declared budgets.

## Memory architecture

```text
Agent result
   ↓
Memory policy
   ↓
SQLite append ledger  ← source of truth
   ↓
Generated Markdown journal
   ↓
Human audit / bounded retrieval
```

Markdown is deliberately a projection rather than the database. Letting agents rewrite their own Markdown memory in place would destroy the audit trail.

## Model deployment architecture

```text
Task request
   ↓
complexity / criticality / ambiguity / financial impact / budget
   ↓
ModelRouter
   ├── Fast     → MODEL_FAST
   ├── Balanced → MODEL_BALANCED
   └── Frontier → MODEL_FRONTIER
             ↓
       reasoning effort
 none / low / medium / high / xhigh / max
```

The router logs decisions to SQLite. Agents do not hard-code their preferred model.

## Non-negotiable boundaries

- no live trading switch
- no agent can approve a failed strategy
- no agent can override the hard risk engine
- no silent memory rewriting
- no unbounded recursive spawning
- no unverified news increasing exposure
- no model result treated as a price oracle

## v1.2 runtime governance

Planning and execution are separate. The orchestrator may create an approved bounded DAG; only the runtime may lease executable work to workers.

A worker lease is temporary authority over one task, not authority over another agent, strategy registry, risk engine, or broker. Duplicate logical work is constrained with idempotency keys. Expired leases are recovered and repeated failures enter dead-letter state.

Cross-agent ordering is explicit. Evidence must exist before contradiction checking; market/evidence summaries must exist before thesis/falsification work; the audit stage waits for the research branches it reviews.

## v1.2 model deployment governance

Agents request a tier (`fast`, `balanced`, `frontier`). They do not choose an arbitrary model ID.

Concrete model versions live in the deployment registry. Candidate deployments are inactive until explicitly activated. Health state may cause safe fallback to a lower tier when task policy permits degradation.

Empirical routing data may create a recommendation, but never a silent policy change. A human/controller must approve the recommendation. If a request has `financial_impact >= 0.80`, the override must also have explicit capital-impact approval.

Provider/model probes record health evidence. A probe does not change health status unless explicitly invoked with the health-application flag.

## v1.2 evaluation governance

Self-confidence is not an evaluation metric. Prefer external evidence:

- walk-forward/robustness outcomes for generated alpha;
- deterministic correctness checks;
- source/evidence verification;
- downstream task success;
- blinded review when objective metrics are unavailable.

Failed runs remain in the dataset. Do not train routing policy only on successes.

## v1.2 memory maintenance

Expiry is a status change, not deletion. Consolidation produces a new derived checkpoint citing original memory IDs. Original failures, observations and superseded notes remain available to audit what the system believed at each date.
