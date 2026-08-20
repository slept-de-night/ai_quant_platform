# Production gaps before any live-capital discussion

v1.0 is intentionally paper-only. The following remain mandatory before even designing a separate live-money build.

## Data integrity

- survivorship-bias-safe historical universe
- delisted securities
- split/dividend/corporate-action reconciliation
- point-in-time fundamentals with filing availability dates
- restatement tracking
- historical share-count/dilution data
- segment and cash-flow data
- point-in-time valuation ratios
- ALFRED/revision-aware macro backtests rather than using revised FRED history as if it were known in real time
- exchange calendars and symbol lifecycle handling

## Evidence / news

- first-class direct company-IR connector and identity verification
- article publication/event timestamp normalization
- syndicated-story clustering beyond publisher-domain deduplication
- claim-level entailment against the complete primary document
- multilingual evidence normalization
- cryptographic/source-feed provenance where available
- evaluation set containing real financial misinformation and adversarial headlines
- monitoring for source reputation drift and compromised domains

## Quant validation

- purged/embargoed cross-validation for overlapping labels
- broader universe validation rather than single-symbol research
- capacity and liquidity constraints
- short borrow/locate/fees if shorting is ever added
- factor exposure/attribution (market, size, value, momentum, quality, sector)
- multiple-testing/selection-bias correction
- deflated Sharpe / probability-of-backtest-overfitting style diagnostics
- regime stability and structural-break tests

## Execution

- broker streaming order updates
- reconciliation between local intent, broker order, fill and final position
- partial fills
- stale/cancelled/replaced orders
- exchange halts
- idempotent recovery after process restart
- market-impact/slippage model tied to liquidity
- circuit breakers independent from the AI process

## Operations

- secret manager
- append-only audit storage
- structured logs/metrics/tracing
- prompt/model/source versioning
- alerting
- backups
- deployment redundancy
- dependency pinning/SBOM/scanning
- disaster-recovery runbook

## Governance

- paper-trading evidence over multiple regimes
- strategy retirement policy
- model change-control and regression evals
- explicit human approval for production strategy changes
- maximum capital-at-risk policy independent of model output
- legal/tax/compliance review for the actual jurisdiction and broker/account type

Do not remove the paper-only restriction merely because a backtest, AI explanation, or recent streak looks impressive. That is precisely when the restriction is doing useful work.

## v1.1 control-plane gaps

Before treating the orchestration layer as production-grade, add:

- durable distributed task runtime (the current orchestrator is a bounded local control plane)
- real concurrency controls and worker leases
- task retries with idempotency and dead-letter handling
- per-run actual token/cost quotas rather than estimated-token quotas alone
- provider/model health checks and tested fallback models
- measured routing evaluation set so model-tier choices are based on task success, latency, and cost rather than heuristics alone
- cryptographic or append-only external audit storage for high-assurance deployments
- automatic memory consolidation that cannot erase original notes
- stale-memory detection tied to source publication/effective dates
- source references on every material research memory note
- human review of any policy change that can affect capital exposure

Agent spawning remains intentionally constrained to approved roles and task types. Dynamic creation of arbitrary prompt-defined agents is not a production goal.

## v1.2 runtime/evaluation gaps

v1.2 closes several v1.1 control-plane gaps locally: task dependencies, leases, retries, dead-letter state, idempotency, runtime events, model deployment versions, health/fallback state, token/cost logging, evaluation records, and approval-gated empirical routing.

Still required before any serious multi-host production deployment:

- replace SQLite worker leasing with a proven distributed queue/database coordination layer;
- worker identity/authentication and signed task claims;
- durable object storage for large task payloads/results rather than embedding everything in SQLite JSON;
- exactly-once side-effect design where feasible and reconciliation where it is not;
- provider-level rate-limit coordination across workers;
- actual organization/project spend ingestion and reconciliation against local cost estimates;
- long-context/cached-token/tool-call pricing accounting rather than a single configurable short-context estimate;
- automatic but conservative health scoring based on several probes/error windows, not a single request;
- shadow/canary evaluation of candidate model deployments before activation;
- a curated evaluation suite for each agent task type;
- confidence intervals/significance tests before recommending routing changes;
- drift detection so old routing evaluations decay when model snapshots, prompts, tools or market regimes change;
- explicit prompt/tool/schema version IDs attached to every evaluation;
- external append-only/WORM audit storage for high-assurance operation;
- scheduler observability (queue depth, age, lease expiration rate, retries, dead letters, model latency, spend) and alerts;
- disaster recovery and database backup/restore tests.

The learned router remains advisory until reviewed. Do not enable automatic routing-policy mutation for capital-impacting tasks.
