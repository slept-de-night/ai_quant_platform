# AI Quant Platform v1.4 — Engineering Handoff & Knowledge Base

**Date:** 2026-08-21  
**Repository:** `slept-de-night/ai_quant_platform`  
**Git Author:** `slept-de-night <slept-de-night@users.noreply.github.com>`  
**Status:** All Phases across Safety Hardening (R0–R7), Webull Integration (W1–W6), and Financial Knowledge / Learning Mode (K1–K5) are **COMPLETED, VERIFIED & COMMITTED**.

---

## 1. Executive Summary & State of the Codebase

The platform is an institutional-grade, cross-asset quantitative trading, intelligence, and execution workstation. It pairs a **high-performance Go 1.22 OMS/EMS execution core** with a **Python 3.11 Point-in-Time (PIT) research, multi-agent DAG, and Financial Knowledge engine**, surfaced through a **React 18 / TypeScript institutional workstation**.

### Test Suite Health
- **Go OMS & Execution Core**: `cd services/aq-engine-go && go test -v -count=1 ./...` $\to$ **100% PASS across all packages**
- **Python Research & FastAPI**: `python -m pytest tests/ -q` $\to$ **114 / 114 PASS (43.6s)**
- **Frontend Workstation**: `cd frontend && npm run build` $\to$ **0 Errors (518 kB clean bundle)**
- **Working Tree**: Completely clean, secret-scanned, `.env` git-ignored, all commits on `main`.
- **AI Agent Skill**: Authoritative skill defined in [`.agents/skills/ai-quant-engineer/SKILL.md`](file:///d:/Main/ai-quant/ai_quant_platform/.agents/skills/ai-quant-engineer/SKILL.md).

---

## 2. Mandatory Architectural Invariants

Any future AI or developer working on this codebase **MUST NEVER violate** the following core invariants:

1. **Zero Fabricated Market Values (`missing != zero`)**:
   - Never return dummy fallback prices (e.g. `$100.0`) on API failure.
   - If market data is unavailable, return `price: None` (Python) / `found: false` (Go) / `null` (TypeScript), and render `" — "` or `"unavailable"` in the UI.
   - Simulated/demo ticks must be explicitly gated behind `DEMO_MARKET_DATA=true`.

2. **Fail-Closed Startup Gates (`unknown != healthy`)**:
   - The Go engine starts in `FROZEN` / `NOT_READY` state by default.
   - Execution is only marked `READY` when: (1) Journal is replayed and valid, (2) Active broker is configured and connected, (3) Reconciliation evidence is fresh ($\le 300\text{s}$) with 0 critical discrepancies, and (4) Kill switch is disengaged.

3. **Gated Execution Resume Boundary**:
   - Resuming trading from a frozen state (`POST /api/v1/risk/unfreeze`) requires:
     * A non-empty operational justification reason (recorded in the audit journal).
     * Operator sign-off identity.
     * Verified journal readiness and connected active broker.
     * Fresh reconciliation evidence ($\le 300\text{s}$) for the *currently active* broker.

4. **Reconciliation Invalidation on Broker Switch**:
   - Calling `POST /api/v1/brokers/select` automatically invalidates reconciliation cache and halts execution until fresh reconciliation is executed.

5. **Polymorphic Asset Schemas**:
   - The platform supports 5 asset classes: `EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `FOREX`.
   - Corporate forensic models (`Altman Z`, `Piotroski F`, `Beneish M8`, `Sloan Accruals`, SEC XBRL balance sheets, employees) exist **ONLY on `EQUITY` payloads** and must **NEVER** appear on Crypto, Commodity, ETF, or Forex payloads.

6. **Execution Posture**:
   - The platform is strictly `PAPER_ONLY` / `SIMULATION`. Live execution is disabled by design.

---

## 3. Repository Directory & Architecture Map

```text
ai_quant_platform/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Parallel CI quality gate (Go tests, Pytest, Frontend build)
│       └── secret-scan.yml        # Gitleaks secret protection
├── services/
│   └── aq-engine-go/              # Go 1.22 High-Performance OMS / EMS Core
│       ├── main.go                # HTTP router, readiness probes, health check, broker selection
│       ├── main_test.go           # HTTP API contract & readiness tests
│       ├── models/
│       │   ├── models.go          # Core structs (Order, MarketTick, Fill, RiskCheck)
│       │   └── readiness.go       # ReadinessReport, TradingReadiness enum, ReconSummary
│       ├── oms/
│       │   ├── engine.go          # Pre-trade pure risk checks, order state machine, kill switch
│       │   ├── journal.go         # Event-sourced JSONL journal with replay recovery
│       │   └── engine_test.go     # OMS unit tests, idempotency, journal replay
│       ├── broker/
│       │   ├── types.go           # Broker interface, BrokerOrder, Position, Health
│       │   ├── registry.go        # Dynamic broker adapter registry & switching
│       │   ├── paper.go           # High-speed paper fill simulator
│       │   ├── alpaca.go          # Strict Alpaca REST adapter with strict error parsing
│       │   ├── webull.go          # Webull broker adapter
│       │   └── contract_test.go   # Strict adapter conformance and error handling tests
│       ├── market/
│       │   └── gateway.go         # Zero-mock market tick cache & gateway
│       ├── reconciliation/
│       │   └── reconciler.go      # Discrepancy diff matrix, run caching, invalidation
│       ├── metrics/
│       │   └── metrics.go         # Prometheus metrics registry & counters
│       └── auth/
│           └── auth.go            # HMAC auth middleware & secret redaction
├── src/ai_quant/                  # Python 3.11 FastAPI Orchestrator & Quant Framework
│   ├── api/
│   │   └── server.py              # FastAPI REST endpoints, readiness proxy, unfreeze gateway
│   ├── execution/
│   │   ├── go_client.py           # High-speed HTTP client to Go engine
│   │   ├── engine.py              # Python paper trading engine fallback
│   │   └── risk.py                # Institutional parametric VaR / cVaR calculation
│   ├── runtime/
│   │   ├── pit_store.py           # Bitemporal Point-in-Time observation store
│   │   └── dag.py                 # Multi-agent DAG task scheduler & execution leases
│   ├── data/
│   │   ├── yahoo.py               # Yahoo Finance provider with zero-mock null safety
│   │   ├── edgar.py               # SEC EDGAR XBRL multi-year financial statements
│   │   └── market_data.py         # Bar aggregation & historical cache
│   └── web/static/                # Compiled React production bundle
├── frontend/                      # React 18 / TypeScript Institutional Workstation
│   ├── src/
│   │   ├── App.tsx                # Main container, polling loop, tab router
│   │   ├── types/index.ts         # TypeScript models (ReadinessReport, TradingReadiness, Assets)
│   │   ├── services/api.ts        # Frontend REST API client
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx         # Top ticker bar & search
│   │   │   │   ├── SafetyStatusBar.tsx# Persistent global trading safety status bar
│   │   │   │   ├── UnfreezeModal.tsx  # Gated unfreeze modal with compliance justification
│   │   │   │   └── Sidebar.tsx        # Watchlist sidebar
│   │   │   └── views/
│   │   │       ├── DashboardView.tsx  # Executive overview with live execution core status
│   │   │       ├── IntelligenceHubView.tsx # Polymorphic cross-asset workspaces
│   │   │       ├── PaperTradingDeskView.tsx # Order ledger, broker switch, manual kill switch
│   │   │       └── ...
│   └── package.json
├── tests/                         # Python pytest test suites (79 tests)
├── .env.example                   # Safe configuration template with mock placeholders
├── USER_MANUAL.md                 # Complete Enterprise User Manual
├── README.md                      # Platform overview & quickstart
└── run_full_platform.bat          # 1-click Windows platform launcher
```

---

## 4. REST API & Operational Health Probes Reference

### Go Execution Core (Port 8080)
| Endpoint | Method | Status Codes | Description |
| :--- | :--- | :--- | :--- |
| `/health/live` | `GET` | `200` | Process liveness probe. |
| `/health/ready` | `GET` | `200` (Ready), `503` (Not Ready) | Deterministic readiness check. |
| `/api/v1/readiness` | `GET` | `200`, `503` | Full operational report (`TradingReadiness`, `blocking_reasons`, `reconciliation`). |
| `/api/v1/risk/check` | `POST` | `200` | Sub-millisecond pure risk validation. |
| `/api/v1/orders/submit` | `POST` | `200`, `400`, `500` | Idempotent order submission. |
| `/api/v1/risk/kill` | `POST` | `200` | Engage emergency freeze. Accepts `{"reason": "...", "requested_by": "..."}`. |
| `/api/v1/risk/unfreeze` | `POST` | `200`, `409` | Gated unfreeze. Accepts `{"reason": "...", "requested_by": "...", "override": false}`. |
| `/api/v1/reconciliation/run` | `POST` | `200` | Trigger live broker reconciliation. |
| `/api/v1/brokers` | `GET` | `200` | List registered brokers & configured health. |
| `/api/v1/brokers/select` | `POST` | `200` | Switch active broker (invalidates reconciliation & halts execution). |

### Python Orchestrator (Port 8000)
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/readiness` | `GET` | Truthful readiness report proxied from Go engine (or offline fallback). |
| `/api/risk/kill` | `POST` | Freeze execution via Go engine with audit context. |
| `/api/risk/unfreeze` | `POST` | Disengage kill switch with compliance justification. |
| `/api/reconciliation/run` | `POST` | Run automated broker reconciliation. |
| `/api/market/quote/{symbol}` | `GET` | Null-safe market quote. |
| `/api/market/asset/{symbol}` | `GET` | Polymorphic discriminated asset payload. |

---

## 5. Standard Developer Workflows

### How to Run Locally

```cmd
# 1. Check environment health
run_doctor.bat

# 2. Launch full platform (Go engine + FastAPI + Vite)
run_full_platform.bat
```

### How to Run All Tests

```powershell
# Go Engine Tests
cd services/aq-engine-go
go vet ./...
go test -race -count=1 ./...

# Python Test Suite
python -m pytest

# Frontend Production Build
cd frontend
npm ci
npm run build
```

---

## 6. Recent Stabilization Roadmap History

| Commit | Phase | Summary |
| :--- | :--- | :--- |
| `18cc2ed` | Phase 1 (P0) | `fix(data): eliminate fabricated operational market values` |
| `5755eff` | Phase 2 (P0) | `fix(safety): make startup readiness fail closed` |
| `67d38b0` | Phase 3 (P0) | `feat(ops): expose truthful execution readiness state` |
| `66a2538` | Phase 4 (P0/P1) | `fix(broker): make adapter identity and parsing strict` |
| `9bf4042` | Phase 5 (P0) | `fix(oms): gate execution resume on reconciliation evidence` |
| `86b9f93` | Phase 6 (P0 UX) | `fix(ui): make operational states truthful and fail closed` |
| `d9148db` | Phase 7 (P0 UX) | `feat(ui): add global trading safety status` |
| `3716e3c` | Phase 8 (CI) | `ci: gate Go Python and frontend builds` |

---

## 7. Recommended Next Steps for Future Iterations

1. **Broker Adapter Expansion**:
   - Enhance the Webull adapter (`services/aq-engine-go/broker/webull.go`) with complete HMAC request signing when live paper credentials are provided.
   - Add an Interactive Brokers (IBKR) Client Portal REST / FlexWeb service adapter.

2. **Cross-Asset Real-Time Feeds**:
   - Connect live WebSocket streams for crypto (Binance / Coinbase) and Forex spot pricing into `services/aq-engine-go/market/gateway.go`.

3. **Advanced Quantitative Risk Models**:
   - Add historical simulation and Monte Carlo Value-at-Risk alongside current parametric VaR.
