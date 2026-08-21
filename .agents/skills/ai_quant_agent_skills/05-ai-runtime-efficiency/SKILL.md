---
name: ai-runtime-efficiency
description: Reduce unnecessary model calls through deterministic routing, change detection, materiality, context compilation, caching, and structured agent outputs.
---

# AI Runtime Efficiency

## Principle

```text
Code determines what happened.
Rules determine whether it matters.
AI determines what it means.
```

AI is not the default implementation tool inside the runtime.

## Execution gate

Preserve explicit decisions:

```text
SKIP
DETERMINISTIC
CACHE
AI
```

`execute_ai=true` means AI is permitted.
It does not mean force AI.

`force_refresh=true` must be separate and explicit.

## Cache semantics

A cache key is not a cache hit.

Required:

```text
cache_key + verified stored result
→ CACHE
```

A key alone:
```text
→ continue evaluation
```

## Deterministic work

Keep deterministic:
- indicators;
- XBRL parsing;
- normalization;
- deduplication;
- source metadata;
- change detection;
- materiality thresholds;
- scheduling;
- risk;
- reconciliation.

Use AI for:
- semantic evidence interpretation;
- synthesis;
- scenario reasoning;
- falsification;
- hypothesis generation;
- ambiguous contradiction analysis.

## Run-scoped reuse

Build/reuse one PIT-safe research snapshot per run.

Avoid fetching the same:
- symbol bars;
- SPY/QQQ/TLT/GLD;
- SEC filing;
- macro snapshot

multiple times in one DAG.

## Change detection

Compare prior vs current structured state.

Examples:
- price move;
- volatility regime;
- trend regime;
- new filing;
- fundamental change;
- evidence change;
- contradiction change;
- macro change;
- position change.

AI does not decide whether data changed.

## Materiality

Use configurable deterministic rules.

Tiny price change with no other event:
```text
→ not material
```

New filing / regime transition / thesis-critical contradiction:
```text
→ material
```

## Context compiler

AI receives bounded task-specific context:
- facts;
- material changes;
- relevant evidence references;
- relevant memory references;
- unknowns;
- source status.

Do not dump:
- whole memory journal;
- full filing;
- full database;
- every prior agent output.

Use progressive disclosure.

## Structured outputs

Agent-to-agent machine communication should use schemas, not giant prose reports.

Include:
- conclusion;
- confidence;
- claim refs;
- evidence refs;
- risks;
- unknowns;
- context hash.

## Acceptance test

A routine refresh with AI allowed but no material change must produce:

```text
AI API calls = 0
```
