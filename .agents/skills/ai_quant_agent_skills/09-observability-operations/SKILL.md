---
name: trading-observability-operations
description: Build operational readiness, health/readiness endpoints, metrics, alerting, runbooks, and state visibility for a real-money trading service.
---

# Trading Observability & Operations

## Principle

Process alive is not trading ready.

Separate:

```text
LIVENESS
READINESS
EXECUTION SAFETY
```

## Readiness inputs

Track independently:
- journal ready;
- broker configured;
- broker connected;
- broker authenticated;
- event stream connected;
- market data fresh;
- reconciliation fresh;
- critical discrepancies;
- engine frozen;
- clock health if available;
- active environment;
- active broker.

## Health endpoints

Prefer:

```text
/health/live
/health/ready
```

Optional summary:
```text
/health
```

Readiness response should include blocking reasons.

## Metrics

Useful metrics:
- orders submitted;
- order rejects;
- ambiguous submits;
- cancel requests;
- fills;
- duplicate broker events;
- reconciliation runs;
- reconciliation mismatches;
- journal failures;
- stale-data rejects;
- broker disconnects;
- event-stream reconnects;
- market-data reconnects;
- engine freeze count;
- reserve exposure totals;
- daily PnL;
- AI calls/avoided calls/cost.

## Alerts

High-priority alerts:
- journal not ready;
- reconciliation critical;
- broker snapshot unavailable;
- event stream stale;
- market data stale;
- emergency kill incomplete;
- submission unknown unresolved;
- daily loss limit hit;
- auth/security startup failure.

## Operator runbook

Document:
- startup;
- shutdown;
- broker switch;
- reconciliation;
- emergency kill;
- journal failure;
- broker disconnect;
- stale market data;
- unresolved ambiguous submit;
- restart with open orders;
- credential rotation.

## UI status strip

Global operator state should be compact and authoritative:

```text
MODE | BROKER | OMS | RECON | DATA | EVENTS
```

Examples:

```text
SANDBOX | WEBULL | READY | 5s | LIVE 120ms | CONNECTED
```

or:

```text
LIVE READ-ONLY | WEBULL | FROZEN | POSITION MISMATCH | STALE | DISCONNECTED
```

Never use optimistic defaults.
