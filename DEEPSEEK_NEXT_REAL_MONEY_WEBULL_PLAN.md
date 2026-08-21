# DEEPSEEK_NEXT_REAL_MONEY_WEBULL_PLAN.md

# AI Quant Platform v1.4
## DeepSeek Continuation Plan — Correct Webull OpenAPI, Certify Broker Truth, Then Add Explainability

## Mission

Continue from the CURRENT local repository.

Gemini has already completed a large part of the core real-money hardening. Do not reimplement completed work.

The next priority is:

1. verify the local baseline;
2. correct the new Webull OpenAPI subpackage against CURRENT official Webull documentation;
3. keep the top-level Webull adapter quarantined until contract certification passes;
4. integrate Webull in stages: read-only -> sandbox order lifecycle -> event stream -> execution market data;
5. close remaining PIT/numeric correctness gaps;
6. then add a deterministic Financial Knowledge & Explainability layer.

LIVE MONEY ORDER SUBMISSION MUST REMAIN DISABLED.

AI may assist research and explanation. AI must never directly submit orders, bypass risk/reconciliation, unfreeze execution, or change hard live capital limits.

---

## 0. Local baseline is authoritative

GitHub public indexing has lagged behind raw `main` several times.

Before editing:

```bash
git status --short
git diff
git diff --cached
git log --oneline -20
git branch --show-current
```

Then run:

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

Do not continue on red tests.

Report first:

```text
HEAD:
Working tree:
Go:
Python:
Frontend:
Already completed:
Remaining P0:
```

---

## 1. Completed core work — verify, do not rebuild

Current public `main` already shows equivalents of:

- authoritative fresh Gateway tick validation;
- MaxTickStalenessSeconds enforcement;
- conservative risk-price/notional calculation;
- whole-share order validation;
- short selling disabled by default;
- pending/open-order exposure reservations;
- reserved sell quantity protection;
- journal fail-closed helper;
- journalReady=false + engine freeze on durable write failure;
- `SUBMISSION_UNKNOWN` ambiguous broker-submit state;
- same-client-order-id recovery query;
- cancel state machine with `CANCEL_PENDING`;
- cancel HTTP endpoints;
- emergency freeze + cancel-all + reconciliation;
- periodic reconciliation worker;
- secure loopback default bind;
- live authentication requirement;
- start-of-day equity / DailyPnL / account hydration fields;
- Webull top-level adapter quarantined with Ready=false;
- PIT snapshot SourceStatus/state_hash/provenance_hash;
- AI `execute_ai` separate from explicit `force_refresh`;
- portable README links and `.env` hygiene.

Do not rewrite these unless tests prove a bug.

---

## 2. New P0 — current Webull subpackage is not official-protocol correct

Inspect:

```text
services/aq-engine-go/broker/webull/
    adapter.go
    client.go
    signer.go
    order.go
    state.go
    quote.go
    stream.go
    *_test.go
```

The subpackage exists, but the current public code contains protocol assumptions that conflict with CURRENT official Webull OpenAPI documentation.

The top-level `services/aq-engine-go/broker/webull.go` is still quarantined and must REMAIN quarantined while these issues are fixed.

Do not wire the subpackage into real broker execution until certification passes.

---

## 3. P0 — fix Webull base URLs

Current subpackage contains legacy hosts similar to:

```text
https://quoteapi.webullfintech.com/api
https://quoteapi.webullbroker.com/api
```

Do not use those as OpenAPI trading/account base URLs.

Use CURRENT official hosts:

```text
Sandbox:
https://api.sandbox.webull.com

Production:
https://api.webull.com
```

Environment must be explicit. Do not infer it from URL text.

Tests:

```text
SANDBOX -> api.sandbox.webull.com
LIVE    -> api.webull.com
```

Do not enable LIVE order placement.

---

## 4. P0 — rewrite Webull signer to current official spec

The current signer uses HMAC-SHA256 and custom headers such as:

```text
App-Key
Timestamp
Nonce
Signature
Signature-Method
```

Current Webull OpenAPI instead requires headers equivalent to:

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
x-signature-algorithm = HMAC-SHA1
x-signature-version   = 1.0
x-version             = v2
```

Trading/account calls may also require `x-access-token`.

### Official signing algorithm

Implement exactly:

1. Merge query params + signing headers (`x-app-key`, `x-signature-algorithm`, `x-signature-version`, `x-signature-nonce`, `x-timestamp`, `host`).
2. Sort names ascending.
3. Join as `key=value&key=value...`.
4. If body exists, compute uppercase MD5 hex of the body.
5. Construct `path + "&" + sortedPairs [+ "&" + bodyMD5]`.
6. URL-encode the complete signing string.
7. Signing key = `appSecret + "&"`.
8. Signature = Base64(HMAC-SHA1(signingKey, encodedString)).

Use the CURRENT official Webull worked example as a deterministic test vector.

Acceptance:

```text
official example inputs -> exact official signature output
```

Suggested commit:

```text
fix(webull): implement official OpenAPI HMAC-SHA1 signing
```

---

## 5. P0 — request retry policy must be order-safe

The current generic Webull Client retries requests with exponential backoff. This is dangerous if applied blindly to order placement.

A POST order request can be accepted by Webull while the client loses the response.

Therefore:

```text
transport timeout on PlaceOrder != safe automatic retry
```

Implement operation-aware retry policy.

Safe candidates:

```text
GET account
GET positions
GET order detail
GET market snapshot
-> bounded retry may be allowed
```

Unsafe/ambiguous:

```text
POST place order
-> NEVER blindly auto-retry after ambiguous transport failure
```

Instead return an error classified so OMS performs:

```text
SUBMISSION_UNKNOWN
-> query by SAME client_order_id
-> resolve broker truth
```

Cancel/modify requests also need explicit idempotency semantics.

Suggested commit:

```text
fix(webull): make transport retries order-idempotency aware
```

---

## 6. P0 — verify every Webull endpoint against official docs

Current code contains paths such as:

```text
/api/v1/trade/order/place
/api/v1/trade/order/cancel
/api/v1/trade/account/detail
/api/v1/trade/account/positions
/api/v1/trade/order/list
/api/v1/market/quote
```

Do not assume these are correct.

Audit every route against CURRENT:

```text
https://developer.webull.com/apis/docs/
```

For each operation record:

```text
Operation | Method | Official Path | Request Schema | Response Schema
```

Cover:

- account list/identity;
- account balance;
- positions;
- open orders;
- order history;
- order detail;
- place order;
- cancel order;
- market snapshot.

A mock returning success for an invented path is not a contract test.

---

## 7. P0 — strict broker parsing: never invalid -> zero/now

Current Webull state code still has behavior equivalent to:

```go
parseFloatSafe("bad") -> 0.0
```

and timestamps may fall back to `time.Now()`.

Replace with strict helpers:

```go
func parseRequiredDecimal(name, value string) (float64, error)
func parseRequiredTimestamp(name, value string) (time.Time, error)
```

For authoritative broker fields:

```text
invalid cash -> error
invalid equity -> error
invalid quantity -> error
invalid fill price -> error
invalid created_at -> error
```

Do not fabricate financial zero or current timestamps.

Suggested commit:

```text
fix(webull): reject malformed authoritative broker state
```

---

## 8. P0 — preserve exact broker quantity

Current normalization still uses patterns like:

```go
Qty: int(totalQty)
FilledQty: int(filledQty)
```

For initial order submission the platform may continue enforcing WHOLE SHARES ONLY, but broker truth must preserve exact reported quantity.

Do not truncate `1.75` to `1`.

At minimum:

- reconciliation compares non-truncated quantities;
- fills preserve exact quantity;
- positions preserve exact quantity.

Longer-term use fixed decimal/fixed-point for authoritative money and quantity.

Suggested commit:

```text
fix(models): preserve exact broker quantities in reconciliation
```

---

## 9. P0 — read-only Webull certification before order submission

After signer/client/routes/parsing are corrected, integrate only READ-ONLY Webull functionality first.

Top-level adapter may expose verified read capabilities, but keep:

```text
SubmitOrder=false
CancelOrder=false
Ready=false
```

until sandbox write certification passes.

Required read-only operations:

```text
account identity/list
balance/equity/cash
positions
open orders
order history
order detail by client_order_id
broker snapshot
```

If list endpoints can lag latest state, use individual order detail by `client_order_id` for ambiguity recovery.

Suggested commit:

```text
feat(webull): certify official read-only broker state
```

---

## 10. P0 — integrate top-level adapter without duplicate clients

The top-level `broker.WebullAdapter` currently has its own legacy URL/client fields and does not use the new `broker/webull` implementation.

Target:

```text
broker.WebullAdapter
        ↓
broker/webull.Client
        ↓
official Webull OpenAPI
```

Top-level adapter should mainly provide:

```text
BrokerAdapter interface glue
normalization
capabilities
health
environment
```

Do not duplicate signing/HTTP/route logic.

Keep LIVE writes disabled.

---

## 11. P0 — actual gRPC event transport, not only abstraction

Current `stream.go` contains useful consumer/reconnect abstractions, but public code does not show an actual gRPC transport connection.

Webull trade events use server-streaming gRPC.

Implement actual transport using CURRENT official Webull proto/interface.

Requirements:

```text
connect sandbox event endpoint
authenticate correctly
subscribe
receive events
map official event payload
heartbeat/last-message tracking
reconnect
deduplicate
fallback REST reconciliation
```

Support official scenarios equivalent to:

```text
FILLED
FINAL_FILLED
PLACE_FAILED
MODIFY_SUCCESS
MODIFY_FAILED
CANCEL_SUCCESS
CANCEL_FAILED
```

Do not mark `ExecutionEvents=true` until actual sandbox integration passes.

Suggested commit:

```text
feat(webull): connect official gRPC trading event stream
```

---

## 12. P1 — execution market data

Current `quote.go` must also be verified against CURRENT official market-data endpoints.

Webull OpenAPI uses:

```text
HTTP -> snapshot/historical queries
MQTT over WebSocket/TCP -> real-time streaming market data
```

Implement verified HTTP market snapshot first, then streaming.

Reconnect semantics:

```text
disconnect
-> reconnect
-> authenticate
-> resubscribe symbols
-> wait for fresh quote
-> market-data READY
```

Feed verified quotes into the existing Go market Gateway.

Risk already enforces freshness; preserve it.

---

## 13. P1 — sandbox order lifecycle

Only after Webull read-only truth and signer certification pass.

Enable SANDBOX writes only.

Required:

```text
place
query by client_order_id
partial fill
full fill
cancel request
cancel success
cancel/fill race
ambiguous place response
duplicate event
out-of-order event
```

No LIVE writes.

---

## 14. P1 — Webull certification gate

Do not activate Webull merely because mock tests pass.

Require:

```text
PASS official signature vector
PASS official base URLs
PASS official route/schema contract tests
PASS strict decimal parsing
PASS strict timestamp parsing
PASS read-only account
PASS positions
PASS orders
PASS order detail
PASS reconciliation
PASS sandbox place
PASS sandbox query
PASS sandbox cancel
PASS ambiguous-submit recovery
PASS partial fill
PASS final fill
PASS gRPC event stream
PASS reconnect recovery
PASS execution market data
PASS restart with open order
PASS fault injection
```

Until then:

```text
Ready=false
```

---

## 15. P1 — certify Gemini's new OMS safety work under faults

Required tests:

```text
journal write/fsync failure
-> frozen, not ready

two concurrent BUY orders
-> cannot exceed reserved cash/exposure

two concurrent SELL orders
-> cannot oversell confirmed position

broker accepts + client timeout
-> SUBMISSION_UNKNOWN
-> same client_order_id query
-> no duplicate order

cancel request + late fill
-> fill retained
-> remaining quantity reconciled

emergency kill
-> freeze
-> cancel requests
-> reconcile
-> remains frozen

periodic reconciliation failure
-> readiness fails closed as policy requires

restart during:
SUBMITTING
SUBMISSION_UNKNOWN
PARTIALLY_FILLED
CANCEL_PENDING
```

Suggested commit:

```text
test(oms): certify failure recovery and reservation invariants
```

---

## 16. P1 — remaining PIT look-ahead risks

After Webull protocol correctness is stable, remove historical fallbacks such as:

```text
SEC historical TypeError -> current snapshot
FRED historical TypeError -> current snapshot
market loader lacks as_of -> current loader/post-filter
missing filing timestamp -> fiscal end_date
```

For historical runs use:

```text
SourceState.NOT_PIT_CAPABLE
```

when reconstruction is unsupported.

Fiscal period end is not filing availability.
Current/revised macro data is not historical vintage data.
Current adjusted price history is not automatically PIT-safe.

Suggested commit:

```text
fix(pit): remove current-data fallbacks from historical snapshots
```

---

## 17. P2 — Financial Knowledge & Explainability layer

A dedicated education layer is still not present in the current frontend.

Implement it as READ-ONLY and deterministic first.

Suggested:

```text
frontend/src/features/education/
    concepts.ts
    registry.ts
    MetricHelp.tsx
    KnowledgeDrawer.tsx
    ExplainValue.tsx
```

Concept model:

```text
id
name
category
beginner_definition
advanced_definition
institutional_definition
formula
inputs
interpretation
limitations
common_mistakes
related_concepts
example
source_refs
```

Initial topics:

```text
bid / ask / spread / liquidity / slippage
market / limit / stop order
partial fill / cancel pending
cash / equity / buying power
realized / unrealized PnL
volatility / drawdown / VaR / Expected Shortfall
gross / net exposure / beta / correlation
Sharpe / Sortino / Calmar
RSI / ATR / momentum / z-score
P/E / P/B / FCF / ROE
Piotroski / Beneish / Altman
look-ahead bias / survivorship bias / overfitting
walk-forward / CPCV / DSR / PBO
reconciliation / broker truth / journal / kill switch
```

Visually distinguish:

```text
BROKER FACT
DETERMINISTIC CALCULATION
QUANT INTERPRETATION
AI INTERPRETATION
```

Explain risk rejections deterministically, including current exposure, pending reservations, requested exposure, projected exposure, and configured maximum.

---

## 18. Deployment stages

Do not create a casual PAPER/LIVE switch.

Use:

```text
SIMULATION
WEBULL_SANDBOX
WEBULL_LIVE_READ_ONLY
WEBULL_LIVE_SHADOW
WEBULL_LIVE_MANUAL
WEBULL_LIVE_LIMITED
```

Progress only:

```text
Simulation
-> Sandbox
-> Live Read-Only
-> Shadow
-> Manual tiny orders
-> Limited automation
```

---

## 19. Hard capital guardrails before live writes

Before any real-money write capability exists add deployment-level limits:

```text
MAX_LIVE_ORDER_NOTIONAL
MAX_LIVE_DAILY_NOTIONAL
MAX_LIVE_GROSS_EXPOSURE
MAX_LIVE_SYMBOL_EXPOSURE
MAX_LIVE_OPEN_ORDERS
```

AI and strategy code cannot modify these at runtime.

---

## 20. Implementation order for DeepSeek

```text
D0  baseline + verify completed OMS safety work

D1  correct Webull base URLs + official HMAC-SHA1 signer

D2  make HTTP retries order-idempotency aware

D3  audit/correct every Webull route and schema

D4  strict Webull decimal/timestamp parsing

D5  preserve exact broker quantities

D6  integrate certified read-only Webull client into top-level adapter

D7  read-only reconciliation certification

D8  actual gRPC trade-event transport

D9  official execution market-data snapshot/stream

D10 Webull sandbox place/query/cancel lifecycle

D11 OMS + Webull fault-injection/restart certification

D12 remove remaining PIT current-data fallbacks

K1  FinancialKnowledgeRegistry

K2  metric explanation UI

K3  deterministic order/risk explanation

K4  signal explanation

K5  optional Learning Mode

THEN ONLY:
WEBULL_LIVE_READ_ONLY
-> SHADOW
-> MANUAL
-> LIMITED AUTOMATION
```

---

## 21. Immediate task

Start with D0.

Then implement ONLY D1:

```text
WEBULL OFFICIAL BASE URL + SIGNATURE CORRECTION
```

Do not wire the top-level adapter yet.

Acceptance:

```text
PASS sandbox host = api.sandbox.webull.com
PASS production host = api.webull.com
PASS x-* headers match current official Webull spec
PASS HMAC-SHA1, not SHA256
PASS official signature vector matches exactly
PASS app secret never transmitted
PASS x-access-token supported separately
PASS Go tests pass
PASS race detector passes
```

After D1, stop and report before D2.

---

## 22. Required report after every phase

```text
HEAD before:
HEAD after:

Files changed:
Official Webull docs consulted:

Problem corrected:
Safety invariant:

Tests added:
Commands executed:
Results:

git diff summary:
Commit SHA:
Push result:
CI result:

Remaining P0:
```

---

## 23. Core principle

For broker integration:

```text
lots of code != correct broker integration
```

Trust requires:

```text
official protocol
+ strict parsing
+ idempotency
+ durability
+ event truth
+ reconciliation
+ fault testing
```

Automation should act only on states the system can explain and verify.
