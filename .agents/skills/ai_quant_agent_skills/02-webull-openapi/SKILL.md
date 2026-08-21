---
name: webull-openapi-integration
description: Implement and certify the official Webull OpenAPI integration. Use for Webull auth/signing, routes, account state, orders, market data, event streams, sandbox certification, or adapter health.
---

# Webull OpenAPI Integration

## Safety posture

Webull must remain quarantined with `Ready=false` until certification passes.

Do not use unofficial/reverse-engineered mobile endpoints.

Use current official Webull OpenAPI documentation.

## Environments

Use explicit environment:

```text
SANDBOX
LIVE
```

Current official base hosts:

```text
Sandbox: https://api.sandbox.webull.com
Live:    https://api.webull.com
```

Never infer environment from URL substrings.

## Signing

Use the current official Webull signing contract.

Expected signing headers include:

```text
x-app-key
x-timestamp
x-signature
x-signature-algorithm
x-signature-version
x-signature-nonce
x-version
```

Use:
```text
HMAC-SHA1
signature version 1.0
x-version v2
```

Support access-token auth separately where required.

Never transmit or log the app secret.

Keep a deterministic unit test based on Webull's published signature example.

## Endpoint discipline

Do not assume old `/api/v1/trade/...` paths are valid.

For each operation maintain a contract table:

```text
Operation | Method | Official Path | Request Schema | Response Schema | Retry Class
```

Verify current official routes for:
- account list;
- balances;
- positions;
- open orders;
- historical orders;
- order detail;
- preview;
- place order;
- replace;
- cancel;
- stock snapshots;
- bars/depth/ticks where used.

## Strict parsing

Authoritative broker state must never do:

```text
bad decimal -> 0
bad timestamp -> now
fractional qty -> int truncation
```

Parsing failure is an error.

Preserve exact broker quantities even if local order entry is temporarily whole-share-only.

## Retry semantics

Reads may use bounded retries when safe.

Economic writes must not be blindly retried after ambiguous failure.

For `PlaceOrder`:

```text
ambiguous transport failure
→ OMS SUBMISSION_UNKNOWN
→ query Order Detail using SAME client_order_id
```

Cancel/replace also need explicit retry/idempotency policy.

## Read-only first

Certification order:

```text
auth/signing
→ account list
→ balances
→ positions
→ open orders
→ history
→ order detail
→ broker snapshot
→ reconciliation
```

Keep:

```text
SubmitOrder=false
CancelOrder=false
Ready=false
```

until sandbox write certification.

## Trading events

Implement actual official server-streaming gRPC transport.

Requirements:
- authenticated connection;
- event IDs;
- partial fill;
- final fill;
- place failure;
- cancel success/failure;
- reconnect;
- deduplication;
- out-of-order handling;
- fallback reconciliation.

Do not mark `ExecutionEvents=true` for a mere abstraction without an actual transport.

## Market data

Use official market-data endpoints.

Start with validated HTTP stock snapshot.

Then add official streaming transport.

On reconnect:
1. mark data not ready;
2. reconnect/authenticate;
3. resubscribe;
4. wait for a fresh quote;
5. only then restore readiness.

Feed validated quotes into the central Go market Gateway.

## Webull certification gate

`Ready=true` only after:

```text
PASS official signature vector
PASS official routes/schemas
PASS strict parsing
PASS account state
PASS positions
PASS orders
PASS order detail
PASS broker snapshot
PASS reconciliation
PASS sandbox place
PASS sandbox cancel
PASS ambiguity recovery
PASS partial/final fills
PASS event stream
PASS reconnect
PASS market data
PASS restart recovery
PASS fault injection
```
