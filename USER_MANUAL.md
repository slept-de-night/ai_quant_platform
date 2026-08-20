# AI Quant Platform v1.3 — Enterprise User Manual

Welcome to the **AI Quant Platform v1.3 Enterprise Workstation**. This platform is a polymorphic cross-asset quantitative trading, research, and execution workstation powered by a **Go OMS/EMS Execution Core**, a **Python Multi-Agent Research & PIT Quant Engine**, and a **React/TypeScript Institutional Terminal**.

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Quickstart & Service Management](#2-quickstart--service-management)
3. [Polymorphic Cross-Asset Workspaces](#3-polymorphic-cross-asset-workspaces)
   - [Equity Workspace](#equity-workspace)
   - [ETF Workspace](#etf-workspace)
   - [Commodity Workspace](#commodity-workspace)
   - [Crypto Workspace](#crypto-workspace)
   - [Forex Workspace](#forex-workspace)
4. [Point-in-Time (PIT) Quant Runtime & Anti-Lookahead Fabric](#4-point-in-time-pit-quant-runtime--anti-lookahead-fabric)
5. [Go Execution Core, Pre-Trade Risk & Kill Switch](#5-go-execution-core-pre-trade-risk--kill-switch)
6. [Automated Broker Reconciliation Engine](#6-automated-broker-reconciliation-engine)
7. [Multi-Agent Research DAG & Evidence Falsification](#7-multi-agent-research-dag--evidence-falsification)
8. [Workstation UI Navigation](#8-workstation-ui-navigation)
9. [API & Verification Reference](#9-api--verification-reference)

---

## 1. System Overview & Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    INSTITUTIONAL REACT WORKSTATION                   │
│  - Polymorphic Cross-Asset Layouts (EQUITY, ETF, COMMODITY, CRYPTO, FX)│
│  - Lightweight Charts Candlestick Engine (1D, 5D, 1M, 6M, 1Y, 5Y)     │
│  - Real-Time Emergency Kill Switch Toggle in Navigation Header       │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                FASTAPI ORCHESTRATION & CONTROL PLANE                 │
│  - Unified Quant Runtime & Bitemporal PIT Observation Store         │
│  - Multi-Agent Research DAG with Primary-Source XBRL Verification    │
│  - Alpha Factory (CPCV, DSR, PBO, Ledoit-Wolf Portfolio Optimizer)   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  GO 1.22 HIGH-PERFORMANCE OMS / EMS                  │
│  - Sub-Millisecond Pre-Trade Risk Checks & Hard Limit Gateways       │
│  - Deterministic Emergency Kill Switch (Freeze / Unfreeze)           │
│  - Automated Broker Reconciliation Engine (Discrepancy Diff Matrix)  │
│  - Event-Sourced Order Lifecycle with End-to-End trace_id Lineage    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Quickstart & Service Management

### Prerequisites
- **Python**: 3.11+ (`.venv` virtual environment)
- **Go**: 1.22+
- **Node.js**: 20+ / `npm`

### Starting the Workstation Services

1. **Start the Go OMS Execution Engine** (Port 8080):
   ```bash
   cd services/aq-engine-go
   go run main.go
   ```

2. **Start the FastAPI Backend** (Port 8000):
   ```bash
   source .venv/bin/activate
   python -m uvicorn src.ai_quant.api.server:app --host 0.0.0.0 --port 8000
   ```

3. **Start the Vite Frontend Terminal** (Port 5173):
   ```bash
   cd frontend
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

Open [`http://localhost:5173`](http://localhost:5173) in your browser to access the workstation.

---

## 3. Polymorphic Cross-Asset Workspaces

The platform automatically classifies selected assets into orthogonal **Asset Types** and **Instrument Types**:

| Asset Type | Instrument Type | Example Tickers | Dedicated Analytics |
| :--- | :--- | :--- | :--- |
| **EQUITY** | `STOCK` | `NVDA`, `AAPL`, `MSFT` | 5-Year SEC XBRL statements, Altman Z, Piotroski F, Beneish M8, Sloan Accruals |
| **ETF** | `ETF` | `SPY`, `QQQ`, `DRAM` | AUM, Expense Ratio, Top Basket Holdings & Weights, Sector Allocations |
| **COMMODITY** | `TRUST`, `FUTURE` | `GLD`, `SLV`, `GC=F`, `CL=F` | Physical Vaulting & Custodians, Term Structure, Macro Sensitivity Beta |
| **CRYPTO** | `CRYPTO` | `BTC-USD`, `ETH-USD`, `SOL-USD` | Circulating/Max Supply, ATH Drawdown %, 24/7 30-Day Realized Volatility |
| **FOREX** | `FX_SPOT` | `EURUSD=X`, `USDJPY=X`, `GBPUSD=X` | Central Bank Policy Rates, Interest Rate Differential, Carry Yield |

### Equity Workspace
- **Forensic Accounting Diagnostics**:
  - **Altman Z-Score**: Evaluates balance-sheet distress and bankruptcy probability.
  - **Canonical 9-Point Piotroski F-Score**: Evaluates profitability, leverage, liquidity, and operating efficiency.
  - **Beneish M8-Score**: Detects earnings manipulation risks.
  - **Sloan Accruals**: Measures operating cash flow vs net income divergence.
- **SEC XBRL Statement Explorer**: Visual 5-year statement matrix for Income Statements, Balance Sheets, and Cash Flows.

### ETF Workspace
- Visual fund composition bar charts.
- Top 10 to 25 basket constituents with percentage allocations.
- Sector weight breakdown.

### Crypto Workspace
- **24/7 Realized Volatility Formula**:
  $$\sigma_{24/7} = \text{std}(\text{hourly returns}) \times \sqrt{24 \times 365}$$
- **All-Time High (ATH) Drawdown %**:
  $$\text{Drawdown} = \left(\frac{P}{\text{ATH}} - 1\right) \times 100$$
- Circulating and maximum token supply tracking.

### Commodity Workspace
- Physical exposure structure (Physical Vault Trust vs Futures roll yield).
- Vaulting custodians, bar audit standards, and real interest-rate macro sensitivities.

### Forex Workspace
- Base and quote central-bank rate differentials.
- Annualized carry yield calculation and central bank policy stance.

---

## 4. Point-in-Time (PIT) Quant Runtime & Anti-Lookahead Fabric

The platform strictly eliminates lookahead bias through the **Point-in-Time (PIT) Bitemporal Data Fabric**:

```
PIT Observation
├── effective_at: Event timestamp (e.g. quarter end Dec 31)
└── known_at: Publication timestamp (e.g. SEC 10-K filed Feb 15)
```

- **Anti-Lookahead Rule**: Any query as of Jan 15 will not see the Feb 15 filing.
- **Immutable Restatements**: If earnings are restated later, historical backtests observe the original value at historical dates and the restated value only after the restatement publication date.
- **Cryptographic Provenance**: Every `QuantSnapshot` produces a deterministic SHA256 ID:
  $$\text{snapshot\_id} = \text{SHA256}(\text{decision\_time} + \text{observation\_hashes})$$
- **Dependency Inversion**: Alpha strategies implement `StrategyProtocol.evaluate(context: DecisionContext) -> StrategyDecision` and receive only frozen snapshots (no direct DB, API, or wall-clock calls).

---

## 5. Go Execution Core, Pre-Trade Risk & Kill Switch

The Go OMS/EMS (`aq-engine-go`) provides sub-millisecond pre-trade risk validation:

### Emergency Global Kill Switch
- **One-Click Freeze**: Click the **KILL SWITCH** badge in the workstation header to immediately freeze all trading firm-wide.
- **API Gateways**:
  - `POST /api/v1/risk/kill`: Freezes execution engine.
  - `POST /api/v1/risk/unfreeze`: Resumes normal execution.
- **Deterministic Hard Risk Rules**:
  - Maximum daily loss circuit breaker (\(> 2\%\) equity drop).
  - Maximum drawdown circuit breaker (\(> 5\%\)).
  - Maximum gross and single-position exposure limits.
  - Minimum cash reserve requirement (\(> 10\%\)).
  - Idempotency check on `client_order_id`.

### Distributed Tracing
Every order intent and execution event carries a persistent `trace_id`, `run_id`, `decision_id`, and `snapshot_id`.

---

## 6. Automated Broker Reconciliation Engine

Located in `services/aq-engine-go/reconciliation/reconciler.go`, this subsystem continuously verifies that the local OMS state matches broker reality:

### Discrepancy Matrix

| Discrepancy Code | Description | Automated Action |
| :--- | :--- | :--- |
| `UNKNOWN_BROKER_ORDER` | External order or unknown broker fill detected | Flags audit warning |
| `MISSING_BROKER_ORDER` | Local submitted order not found on broker | Re-queries broker or alerts OMS |
| `FILL_QTY_MISMATCH` | Cumulative fill quantity difference | Reconciles position quantity |
| `POSITION_MISMATCH` | Position delta exceeds `QtyTolerance` | Triggers position adjustment |
| `CASH_MISMATCH` | Cash balance delta exceeds `CashTolerance` | Flags cash ledger discrepancy |
| `STALE_LOCAL_ORDER` | Local status has not updated after `StaleAfter` | Synchronizes status with broker truth |

---

## 7. Multi-Agent Research DAG & Evidence Falsification

The platform orchestrates a durable research DAG across specialized AI roles:
1. **Fundamental XBRL Agent**: Direct SEC 10-K/10-Q fact extraction.
2. **Technical Agent**: Momentum, mean reversion, and volatility analysis.
3. **Macro/Cross-Asset Agent**: Yield curves, commodities, and currency correlations.
4. **Evidence Falsifier**: Actively challenges and tests bull/bear theses against hard historical data.
5. **Context Gate**: Blends verified AI intelligence with quantitative factor models.

---

## 8. Workstation UI Navigation

- **Ticker Tape** (Top Bar): Real-time prices across active watchlist assets.
- **Global Search Bar**: Universal autocomplete search for stocks, ETFs, commodities, cryptos, and forex pairs.
- **Kill Switch Badge**: Top-right status button (`ACTIVE (GREEN)` vs `FROZEN (RED)`).
- **Timeframe Selector**: Toggle candlestick chart between `1D`, `5D`, `1M`, `6M`, `1Y`, and `5Y`.
- **Navigation Tabs**:
  - **Terminal**: Primary multi-asset analytics workspace and chart.
  - **Alpha Studio**: Factor backtests, Walk-Forward CPCV, Deflated Sharpe Ratio (DSR), and PBO.
  - **Research DAG**: Live task execution queue and primary-source citations.
  - **Risk Center**: Value-at-Risk (VaR 95%/99%), Conditional VaR (cVaR), and limit monitors.
  - **Paper Trading**: Simulated order lifecycle and portfolio tracking.

---

## 9. API & Verification Reference

### Running Automated Test Suites

```bash
# 1. Run Go Unit Tests (OMS, Execution, Reconciliation)
cd services/aq-engine-go
go test -v ./...

# 2. Run Python Pytest Suite (58 Unit Tests)
pytest -v

# 3. Run Live 31-Point End-to-End Test Harness
python scratch/live_test_harness.py

# 4. Run Frontend Production Build
cd frontend
npm run build
```

### Key API Endpoints

- **Health**: `GET /api/status` (FastAPI) | `GET /health` (Go OMS)
- **Market Data**: `GET /api/market/quote/{symbol}` | `GET /api/market/asset/{symbol}`
- **Kill Switch**: `POST /api/risk/kill` | `POST /api/risk/unfreeze`
- **Reconciliation**: `POST /api/reconciliation/run`
- **Order History**: `GET /api/orders/history`
- **Risk Metrics**: `GET /api/risk/metrics?symbol={symbol}`
- **Alpha Backtest**: `POST /api/backtest/run`
- **CPCV Validation**: `POST /api/backtest/validate`
