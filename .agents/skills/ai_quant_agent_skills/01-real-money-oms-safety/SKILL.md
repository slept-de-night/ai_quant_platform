---
name: real-money-oms-safety
description: Harden the Go OMS, pre-trade risk, journal, order lifecycle, kill switch, capital limits, and failure semantics for real-money use.
---

# Real-Money OMS Safety

## Use this skill when

Work touches:
- `services/aq-engine-go/oms/`
- risk checks
- order reservation
- fills
- cancel lifecycle
- kill switch
- journal/replay
- portfolio/account state
- order submission errors
- live-capital guardrails

## Core rule

A broker request is an economic action.

Never infer financial truth from convenience.

## Order lifecycle

Model explicit states, including uncertainty.

At minimum:

```text
CREATED
RISK_APPROVED
SUBMITTING
SUBMISSION_UNKNOWN
ACKNOWLEDGED
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELED
REJECTED
SUBMIT_FAILED
EXPIRED
RECONCILIATION_REQUIRED
```

A transport timeout after submit is not a confirmed failure.

Flow:

```text
submit
→ ambiguous transport failure
→ SUBMISSION_UNKNOWN
→ query broker using SAME client_order_id
→ resolve broker truth
```

Never blindly retry with a new client order ID.

## Pre-trade truth

Risk must independently validate:
- executable side;
- positive quantity;
- supported order type;
- supported time-in-force;
- fresh market-data tick;
- finite positive risk price;
- non-simulated price for live execution;
- conservative risk notional;
- symbol exposure;
- gross exposure;
- cash;
- daily loss;
- pending-order reservations;
- sellable quantity when shorting is disabled.

Do not trust:
- browser-calculated notional;
- strategy-supplied notional;
- stale reference price.

## Pending exposure reservations

Risk state must include open orders.

Track:
- reserved cash;
- reserved buy notional;
- reserved sell quantity;
- reserved symbol exposure;
- reserved gross exposure.

Reservation states include:

```text
SUBMITTING
SUBMISSION_UNKNOWN
ACKNOWLEDGED
PARTIALLY_FILLED
CANCEL_PENDING
```

Release/reduce only on confirmed:
- rejection;
- cancellation;
- expiration;
- fill;
- reconciliation repair.

## Shorting

Initial real-money posture:

```text
ALLOW_SHORTING=false
```

SELL must satisfy:

```text
confirmed_position_qty - reserved_sell_qty >= requested_sell_qty
```

## Journal durability

Critical execution transitions must not ignore journal errors.

Forbidden:

```go
_ = journal.RecordEvent(...)
_ = UpdateOrderStatus(...)
```

when the function can return a durable-state error.

On journal failure:
- mark journal not ready;
- freeze execution;
- reject new state-changing operations;
- surface readiness failure.

Avoid recursive "journal failure while journaling journal failure" loops.

## Cancellation

```text
ACKNOWLEDGED / PARTIALLY_FILLED
→ CANCEL_PENDING
→ broker confirmation
→ CANCELED
```

Late fills after cancel request must still apply.

`Cancel requested` is not `Canceled`.

## Emergency kill

Emergency kill:
1. freeze new submissions immediately;
2. query open broker orders;
3. request cancels;
4. track pending cancellations;
5. process late fills;
6. reconcile;
7. remain frozen.

Never report "all canceled" until broker truth confirms it.

## Daily PnL

Daily-loss protection must derive from authoritative state.

Track:
- start-of-day equity;
- current equity;
- realized PnL;
- unrealized PnL;
- daily PnL.

A field initialized to zero but never updated is not a risk control.

## Hard live limits

Before live writes exist, support deployment-level caps:

```text
MAX_LIVE_ORDER_NOTIONAL
MAX_LIVE_DAILY_NOTIONAL
MAX_LIVE_GROSS_EXPOSURE
MAX_LIVE_SYMBOL_EXPOSURE
MAX_LIVE_OPEN_ORDERS
```

Strategies and AI cannot change them at runtime.

## Required tests

Include fault tests for:
- concurrent buy reservations;
- concurrent sell reservations;
- stale quotes;
- missing quotes;
- journal write/fsync failure;
- broker accepts + client timeout;
- duplicate broker events;
- out-of-order events;
- cancel/fill race;
- restart in SUBMITTING;
- restart in SUBMISSION_UNKNOWN;
- restart in CANCEL_PENDING;
- emergency kill partial failure.
