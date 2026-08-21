# AI Quant Platform v1.3 — Enterprise User Manual

Welcome to the **AI Quant Platform v1.3 Enterprise Workstation**. This platform is a polymorphic cross-asset quantitative trading, research, and execution workstation powered by a **Go OMS/EMS Execution Core**, a **Python Multi-Agent Research & PIT Quant Engine**, and a **React/TypeScript Institutional Terminal**.

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Quickstart & Service Management](#2-quickstart--service-management)
3. [Global Trading Safety Status & Gated Unfreeze Protocol](#3-global-trading-safety-status--gated-unfreeze-protocol)
4. [Polymorphic Cross-Asset Workspaces](#4-polymorphic-cross-asset-workspaces)
   - [Equity Workspace](#equity-workspace)
   - [ETF Workspace](#etf-workspace)
   - [Commodity Workspace](#commodity-workspace)
   - [Crypto Workspace](#crypto-workspace)
   - [Forex Workspace](#forex-workspace)
5. [Point-in-Time (PIT) Quant Runtime & Anti-Lookahead Fabric](#5-point-in-time-pit-quant-runtime--anti-lookahead-fabric)
6. [Go Execution Core, Pre-Trade Risk & Kill Switch](#6-go-execution-core-pre-trade-risk--kill-switch)
7. [Pluggable Multi-Broker Architecture & Strict Contracts](#7-pluggable-multi-broker-architecture--strict-contracts)
8. [Automated Broker Reconciliation Engine](#8-automated-broker-reconciliation-engine)
9. [Multi-Agent Research DAG & Evidence Falsification](#9-multi-agent-research-dag--evidence-falsification)
10. [Workstation UI Navigation](#10-workstation-ui-navigation)
11. [API, Health Probes & Verification Reference](#11-api-health-probes--verification-reference)

---

## 1. System Overview & Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    INSTITUTIONAL REACT WORKSTATION (PORT 5173)                         │
│  - Global Trading Safety Status Bar & Gated Unfreeze Compliance Modal                  │
│  - Polymorphic Cross-Asset Layouts (EQUITY, ETF, COMMODITY, CRYPTO, FOREX)             │
│  - Lightweight Charts Candlestick Engine (1D, 5D, 1M, 6M, 1Y, 5Y)                      │
│  - Truthful Zero-Mock Display (" — " and "unavailable" for missing data)               │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                FASTAPI ORCHESTRATION & CONTROL PLANE (PORT 8000)                       │
│  - Unified Quant Runtime & Bitemporal PIT Observation Store                            │
│  - Multi-Agent Research DAG with Primary-Source XBRL Verification                      │
│  - Alpha Factory (CPCV, DSR, PBO, Ledoit-Wolf Covariance, Neutralization)              │
│  - Fail-Closed Readiness & Safety Proxy Endpoints                                      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  GO 1.22 HIGH-PERFORMANCE OMS / EMS (PORT 8080)                        │
│  - Sub-Millisecond Pre-Trade Pure Risk Checks & Hard Limit Gateways                    │
│  - Deterministic Emergency Kill Switch (Freeze / Gated Unfreeze)                       │
│  - Automated Broker Reconciliation Engine with Freshness Gate (<= 300s)                │
│  - Event-Sourced Order Lifecycle with End-to-End trace_id Lineage & Replay Recovery    │
│  - Probes: /health/live (Liveness) & /health/ready (Deterministic Trading Readiness)   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Quickstart & Service Management

### Prerequisites
- **Python**: 3.11+
- **Go**: 1.22+
- **Node.js**: 20+ / `npm`

---

### Running the Services

#### 1. Full Platform One-Click Launch (Windows)
```cmd
run_full_platform.bat
```

#### 2. Individual Service Launch
- **Go Execution Core** (Port 8080):
  ```cmd
  cd services/aq-engine-go
  go run main.go
  ```
- **FastAPI Backend** (Port 8000):
  ```cmd
  python -m uvicorn src.ai_quant.api.server:app --host 0.0.0.0 --port 8000
  ```
- **Vite Frontend Terminal** (Port 5173):
  ```cmd
  cd frontend
  npm run dev -- --host 0.0.0.0 --port 5173
  ```

Open [`http://localhost:5173`](http://localhost:5173) in your browser.

#### 3. Environment Diagnostics
To check environment readiness (Python virtual environment, Go compiler, Node.js, SQLite, port availability):
```cmd
run_doctor.bat
```

---

## 3. Global Trading Safety Status & Gated Unfreeze Protocol

The v1.3 workstation features a persistent **Safety Status Bar** rendered across all views:

### Safety Indicators
1. **Readiness Badge**:
   - `EXECUTION READY` (Emerald): Engine is live, journal is valid, active broker is connected, and reconciliation is fresh ($\le 300\text{s}$) with 0 critical discrepancies.
   - `ENGINE FROZEN` (Red with pulsing alert): Execution halted via manual kill switch, journal replay fault, or critical reconciliation discrepancy.
   - `NOT READY` (Amber): Prerequisite subsystems uninitialized or unconfigured.
   - `OFFLINE / UNKNOWN` (Slate): Go execution core disconnected.
2. **Active Broker Badge**: Displays current execution target (`paper-simulation`, `alpaca-paper`, `webull-main`), environment (`[SIMULATION]`, `[PAPER]`, `[LIVE]`), and connectivity indicator.
3. **Reconciliation Evidence**: Shows status (`CLEAN`, `MISMATCH`, `STALE`, `UNKNOWN`) and freshness.
4. **Market Feed Status**: Shows `LIVE FEED`, `DEMO / SIMULATED`, or `UNAVAILABLE`.

### Gated Unfreeze Protocol (Modal)
When the engine is frozen, resuming execution requires passing the **Gated Unfreeze Protocol**:
- Verifies that the event-sourced journal is intact.
- Verifies that the active broker is connected.
- Verifies fresh reconciliation evidence (or offers 1-click **"Run Recon"** before clearing).
- Requires a mandatory **Operational Justification / Reason** text input (logged in the audit journal).
- Operator identity sign-off.

---

## 4. Polymorphic Cross-Asset Workspaces

The platform automatically classifies assets into orthogonal **Asset Types** and **Instrument Types**:

| Asset Type | Instrument Type | Example Tickers | Dedicated Analytics |
| :--- | :--- | :--- | :--- |
| **EQUITY** | `STOCK` | `NVDA`, `AAPL`, `MSFT` | 5-Year SEC XBRL statements, Altman Z, Piotroski F, Beneish M8, Sloan Accruals |
| **ETF** | `ETF` | `SPY`, `QQQ`, `DRAM` | AUM, Expense Ratio, Top Basket Holdings & Weights, Sector Allocations |
| **COMMODITY** | `TRUST`, `FUTURE` | `GLD`, `SLV`, `GC=F`, `CL=F` | Physical Vaulting & Custodians, Term Structure, Macro Sensitivity Beta |
| **CRYPTO** | `CRYPTO` | `BTC-USD`, `ETH-USD`, `SOL-USD` | Circulating/Max Supply, ATH Drawdown %, 24/7 30-Day Realized Volatility |
| **FOREX** | `FX_SPOT` | `EURUSD=X`, `USDJPY=X`, `GBPUSD=X` | Central Bank Policy Rates, Interest Rate Differential, Carry Yield |

Corporate forensic fields (Altman Z, Piotroski F, SEC filings, employees) never appear on Crypto, Commodity, ETF, or Forex payloads.

---

## 5. Point-in-Time (PIT) Quant Runtime & Anti-Lookahead Fabric

Located in `src/ai_quant/runtime/pit_store.py`, the PIT engine guarantees that quant models never peek into the future:
- **Bitemporal Time Stamping**: Tracks both `as_of_date` (event date) and `knowledge_time` (when data became publicly available).
- **Revision History**: Handles restated quarterly filings without corrupting past backtest time slices.
- **Strict Query Windows**: Research agents query observations strictly bounded by $T_{\text{knowledge}} \le T_{\text{simulation}}$.

---

## 6. Go Execution Core, Pre-Trade Risk & Kill Switch

The Go OMS core (`services/aq-engine-go/`) provides deterministic, sub-millisecond execution safety:
- **Pure Risk Gateway** (`services/aq-engine-go/oms/engine.go`): Checks max position size, max single-order USD, daily order count limits, and price deviation limits before state mutation.
- **Idempotent Order Submission**: Orders with duplicate `client_order_id` return the existing order without re-hitting the broker.
- **Event-Sourced Journal** (`services/aq-engine-go/oms/journal.go`): All orders, fills, cancelations, freezes, and unfreezes are appended to a durable JSONL log with `trace_id`, operator ID, and timestamp.
- **Instant Kill Switch**: Disables all state-changing endpoints while keeping read-only portfolio queries and reconciliation tools available.

---

## 7. Pluggable Multi-Broker Architecture & Strict Contracts

Pluggable broker adapters implement the standardized `broker.Broker` interface (`services/aq-engine-go/broker/types.go`):
- **`paper-simulation`**: High-speed, local zero-latency fill simulator with simulated order lifecycle.
- **`alpaca-paper`**: Strict REST integration with Alpaca paper trading. Non-numeric or malformed payload fields trigger explicit errors rather than silent zeros.
- **`webull-main`**: Dedicated adapter scaffolding for Webull execution.
- **Dynamic Broker Switching**: Switching active brokers via `POST /api/v1/brokers/select` automatically invalidates reconciliation state and halts order submission until re-verified.

---

## 8. Automated Broker Reconciliation Engine

Located in `services/aq-engine-go/reconciliation/reconciler.go`, this subsystem continuously verifies that the local OMS state matches broker reality:

### Discrepancy Matrix

| Discrepancy Code | Severity | Description | Automated Action |
| :--- | :--- | :--- | :--- |
| `UNKNOWN_BROKER_ORDER` | HIGH | External order or unknown broker fill detected | Flags audit warning |
| `MISSING_BROKER_ORDER` | CRITICAL | Local submitted order not found on broker | Re-queries broker or alerts OMS |
| `FILL_QTY_MISMATCH` | CRITICAL | Cumulative fill quantity difference | Blocks execution resume |
| `POSITION_MISMATCH` | CRITICAL | Position delta exceeds tolerance | Blocks execution resume |
| `CASH_MISMATCH` | HIGH | Cash balance delta exceeds tolerance | Flags cash ledger discrepancy |
| `STALE_LOCAL_ORDER` | MEDIUM | Local status has not updated | Synchronizes status with broker truth |

---

## 9. Multi-Agent Research DAG & Evidence Falsification

The multi-agent research mesh coordinates specialized roles:
1. **Fundamental XBRL Agent**: Direct SEC 10-K/10-Q fact extraction.
2. **Technical Agent**: Multi-period momentum, mean reversion, and volatility.
3. **Macro/Cross-Asset Agent**: Yield curves, commodities, and currency correlations.
4. **Prompt-Injection Scanner & Citation Extractor**: Sanitizes web inputs and validates source domains.
5. **Evidence Falsifier**: Challenges bull/bear hypotheses against hard data before proposing trades.
6. **Context Gate**: Blends verified AI intelligence with quantitative factor models.

---

## 10. Workstation UI Navigation

- **Top Navigation & Health Bar**: Active symbol indicator, system uptime, and live status refresh.
- **Global Safety Status Ribbon**: Readiness badge, broker environment, reconciliation freshness, and emergency kill switch.
- **Watchlist Sidebar**: Cross-asset watchlist with live quotes, 24h change %, and volume (renders `" — "` when unpriced).
- **Navigation Tabs**:
  - **Dashboard**: High-level fund equity, 1-Day parametric VaR (95%), active alpha models, and execution core status.
  - **Intelligence Hub**: Polymorphic cross-asset analytics, SEC financial statements, and multi-agent dossier.
  - **Runtime DAG**: Live task execution queue, node latency, token usage, and audit logs.
  - **Alpha Studio**: Strategy backtests, Walk-Forward CPCV, Deflated Sharpe Ratio (DSR), and PBO overfitting analysis.
  - **Model Control**: Model deployment registry, health probes, and spend governance.
  - **Paper Trading Desk**: Live portfolio state, active orders, broker selection, and reconciliation trigger.
  - **Memory Audit**: Event-sourced agent knowledge graph, notes, and claims.
  - **Institutional Architecture**: 7-layer institutional architectural reference and invariants.

---

## 11. API, Health Probes & Verification Reference

### Health & Readiness Probes
- `GET /health/live`: 200 OK process liveness.
- `GET /health/ready`: 200 OK only when `TradingReady`; 503 Service Unavailable when `NOT_READY`, `FROZEN`, or `UNKNOWN`.
- `GET /api/v1/readiness` (Go) & `GET /api/readiness` (Python): Full operational readiness report with blocking reasons.
- `GET /api/status`: FastAPI control plane health and model status.

### Execution & Safety Endpoints
- `POST /api/risk/kill`: Engage emergency kill switch (accepts `reason`, `requested_by`).
- `POST /api/risk/unfreeze`: Gated execution resume (accepts `reason`, `requested_by`, `reconciliation_run_id`; strictly requires clean, fresh reconciliation without override bypass).
- `POST /api/reconciliation/run`: Execute automated broker reconciliation.
- `GET /api/brokers` & `POST /api/brokers/select`: List and select active broker.
- `GET /api/orders/history`: Event-sourced order history with `trace_id` lineage.

### Running Automated Test Suites

```bash
# 1. Run Go Engine Tests
cd services/aq-engine-go
go vet ./...
go test -race -count=1 ./...

# 2. Run Python Pytest Suite
python -m pytest

# 3. Run Frontend Production Build
cd frontend
npm ci
npm run build
```
