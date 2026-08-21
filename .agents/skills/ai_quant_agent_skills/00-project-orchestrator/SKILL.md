---
name: ai-quant-project-orchestrator
description: Coordinate development of AI Quant Platform v1.4 safely. Use for any cross-cutting task, roadmap task, or when deciding what to inspect, test, edit, commit, and report.
---

# AI Quant Project Orchestrator

## Purpose

Use this skill whenever work spans more than one subsystem or when the correct next task is unclear.

The project is a real-money-capable quantitative research and execution workstation. The architecture must preserve strict separation between research intelligence and execution authority.

## Architectural boundary

```text
DATA / BROKER TRUTH
        ↓
RESEARCH / SIGNAL
        ↓
EXPLANATION
        ↓
DETERMINISTIC RISK
        ↓
DURABLE OMS
        ↓
BROKER ADAPTER
        ↓
BROKER
        ↓
EVENTS + RECONCILIATION
```

AI may assist research, synthesis, coding, and explanation.

AI must never:
- directly submit broker orders;
- bypass deterministic risk;
- bypass reconciliation;
- automatically unfreeze execution;
- modify hard live-capital limits;
- fabricate broker, market, or portfolio state.

## Baseline workflow

Before editing:

```bash
git status --short
git diff
git diff --cached
git log --oneline -20
git branch --show-current
```

Run:

```bash
cd services/aq-engine-go
go vet ./...
go test -race -count=1 ./...
cd ../..

python -m pytest

cd frontend
npm ci
npm run build
cd ..
```

If baseline is red, fix or isolate the baseline issue before adding unrelated work.

## Local repository authority

The local Git checkout is authoritative.

Do not assume:
- roadmap documents are current;
- README reflects implementation;
- prior AI instructions are newer than HEAD;
- public GitHub indexing is fully synchronized.

Verify the code.

## Change discipline

For every task:
1. inspect relevant implementation;
2. identify invariants;
3. write or update tests;
4. implement the smallest coherent change;
5. run focused tests;
6. run full validation before push;
7. inspect `git diff`;
8. stage explicit files;
9. inspect `git diff --cached`;
10. commit one concern.

Avoid:
```bash
git add .
git add -A
```
unless every changed file has been reviewed.

## Execution stages

Never casually enable live trading.

Allowed progression:

```text
SIMULATION
→ WEBULL_SANDBOX
→ WEBULL_LIVE_READ_ONLY
→ WEBULL_LIVE_SHADOW
→ WEBULL_LIVE_MANUAL
→ WEBULL_LIVE_LIMITED
```

No stage may be skipped because "tests pass."

## Truth invariants

```text
UNKNOWN != READY
MISSING != ZERO
TIMEOUT != REJECTED
REQUESTED != CONFIRMED
SUBMITTED != FILLED
CANCEL_REQUESTED != CANCELED
CONFIGURED != CONNECTED
CONNECTED != READY
PAPER != LIVE
CURRENT DATA != PIT-SAFE HISTORICAL DATA
```

## Required completion report

After each phase report:

```text
HEAD before:
HEAD after:

Problem:
Invariant protected:

Files changed:
Tests added:
Commands executed:
Results:

git diff summary:
Commit SHA:
Push result:
CI result:

Remaining P0:
```

Never print secrets.
