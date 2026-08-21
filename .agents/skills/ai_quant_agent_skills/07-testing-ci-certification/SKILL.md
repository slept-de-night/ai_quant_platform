---
name: testing-ci-certification
description: Define and enforce test strategy, CI gates, contract tests, sandbox integration tests, race tests, restart tests, and real-money certification.
---

# Testing, CI & Certification

## Baseline commands

Go:

```bash
cd services/aq-engine-go
go vet ./...
go test -race -count=1 ./...
```

Python:

```bash
python -m pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

CI should fail on dependency-lock inconsistency.
Do not use `npm ci || npm install`.

## Test layers

Separate:

### Unit tests
Pure local behavior.

### Contract tests
Validate exact external protocol assumptions:
- headers;
- signatures;
- paths;
- schema fields;
- parsing.

### Sandbox integration tests
Use real Webull sandbox when credentials are available.

Credential-requiring tests should be opt-in and skipped in public CI if secrets are absent.

### Fault injection
Test failure semantics.

## Broker tests

Required:
- official Webull signature vector;
- route/schema contract;
- auth failure;
- strict numeric parsing;
- strict timestamps;
- account;
- positions;
- orders;
- order detail;
- place;
- cancel;
- partial/final fills;
- ambiguous submit;
- duplicate event;
- out-of-order event;
- reconnect;
- rate limits;
- 500;
- malformed response.

## OMS fault tests

Required:
- journal write failure;
- fsync failure;
- concurrent reservation races;
- stale quote;
- broker accepted + client timeout;
- cancel/fill race;
- restart during SUBMITTING;
- restart during SUBMISSION_UNKNOWN;
- restart during CANCEL_PENDING;
- reconciliation timeout;
- emergency kill partial failure.

## PIT tests

Required:
- filing publication date;
- restatement;
- macro vintage;
- future market bars;
- unsupported PIT source;
- source failure;
- state hash reproducibility.

## Release certification

No `Ready=true` because unit tests are green.

For broker live-readiness, require:
- protocol correctness;
- sandbox integration;
- event transport;
- market data;
- reconciliation;
- restart recovery;
- fault injection;
- operator runbook.

## Test reporting

After work, report exact commands and actual outcomes.

Do not claim:
```text
all tests pass
```
without running the relevant commands.
