---
name: broker-reconciliation-truth
description: Implement and review broker/local state reconciliation, readiness gates, periodic reconciliation, broker switching, and recovery from discrepancies.
---

# Broker Reconciliation & Truth

## Principle

Broker is external execution truth.
Local OMS is local provenance/state-machine truth.

Disagreement is not resolved by guessing.

Critical disagreement:
```text
→ freeze
→ reconcile
→ require verified recovery
```

## Reconciliation inputs

Compare:
- orders;
- client order IDs;
- broker order IDs;
- order statuses;
- fill quantities;
- average fill prices;
- positions;
- cash;
- equity;
- buying power if relevant;
- pending exposure reservations;
- timestamps/freshness.

## Required discrepancy classes

At minimum:

```text
UNKNOWN_BROKER_ORDER
MISSING_BROKER_ORDER
FILL_QTY_MISMATCH
POSITION_MISMATCH
CASH_MISMATCH
STALE_LOCAL_ORDER
ORDER_STATUS_MISMATCH
AVERAGE_FILL_PRICE_MISMATCH
RESERVATION_MISMATCH
```

## Periodic reconciliation

Do not rely only on startup/manual reconciliation.

Use deterministic scheduling:

```text
RECONCILIATION_INTERVAL_SECONDS
```

Flow:

```text
timer
→ fetch broker snapshot
→ construct local snapshot
→ diff
→ persist reconciliation run
→ update readiness
```

Critical mismatch:
```text
→ freeze immediately
```

Broker snapshot repeatedly unavailable:
```text
→ NOT_READY / FROZEN according to policy
```

## Broker switching

Switching active broker must:
1. freeze;
2. invalidate previous reconciliation;
3. select requested adapter only if configured appropriately;
4. fetch new broker truth;
5. reconcile;
6. remain frozen until safe resume conditions pass.

## Resume gate

Resume requires:
- journal ready;
- broker valid;
- completed reconciliation;
- reconciliation fresh;
- zero critical discrepancies;
- correct broker identity;
- operator reason.

No normal safety override checkbox.

## Crash/restart test

Required scenario:

```text
submit
→ broker ACK
→ process crashes
→ broker partially fills
→ restart
→ journal replay
→ broker snapshot
→ discrepancy detected
→ controlled recovery/import
→ remain frozen until consistent
```

## Reporting

Every reconciliation run should have:
- run ID;
- broker;
- environment;
- started/finished timestamps;
- source snapshot timestamps;
- discrepancy counts;
- critical count;
- outcome;
- reason for freeze if any.
