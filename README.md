# AI Quant Platform v1.3 — Institutional Polymorphic Quant Workstation

A production-grade, research-first, **paper-trading-only** cross-asset quantitative trading, multi-agent intelligence, and execution platform.

v1.3 introduces a **Go 1.22 deterministic OMS/EMS Execution Core**, a **Point-in-Time (PIT) Quant Runtime with Bitemporal Observation Store**, **Polymorphic Cross-Asset Workspaces** (`EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `FOREX`), and a **React/TypeScript Institutional Terminal** with a persistent **Global Trading Safety Status Bar & Gated Execution Resume Protocol**.

---

## Key Platform Capabilities

- **Polymorphic Cross-Asset Workspaces**: Tailored analytics per asset class (SEC XBRL financial statements, Altman Z, Piotroski F, Beneish M8, Sloan Accruals for Equities; AUM, Basket Weights & Sector Allocations for ETFs; Custodians, Vaulting & Roll Yield for Commodities; Tokenomics, ATH Drawdown & 24/7 Realized Vol for Crypto; Rate Differentials & Carry Yield for Forex).
- **Sub-Millisecond Go OMS/EMS Core**: Pure pre-trade risk checks, atomic order reservation, order submission state machine, event-sourced JSONL journal with replay recovery, and pluggable broker adapters.
- **Fail-Closed Truth & Safety Architecture**: Strict institutional invariants where `unknown != healthy`, `missing != zero`, `failed != ready`, `simulation != broker connected`, and `reconciliation unavailable != reconciliation clean`.
- **Automated Broker Reconciliation Engine**: Periodic and on-demand discrepancy diff matrix comparing OMS ledger vs broker snapshots. Gated unfreeze requires fresh reconciliation ($\le 300\text{s}$) with 0 critical discrepancies.
- **Global Safety Status Bar & Unfreeze Protocol**: Real-time readiness badges (`READY`, `NOT_READY`, `FROZEN`, `UNKNOWN`), broker connection telemetry, 1-click emergency kill switch, and compliance-attested unfreeze modal with prerequisite gates.
- **Bitemporal Point-in-Time (PIT) Runtime**: Anti-lookahead data fabric enforcing strict separation between `as_of` publication date and `knowledge_time`.
- **Durable Multi-Agent DAG Research Engine**: Multi-node research mesh with primary-source citation extraction, prompt-injection defense, contradiction pass, and hypothesis falsification.
- **Alpha Factory**: Walk-forward validation, Combinatorial Purged Cross-Validation (CPCV), Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), Ledoit-Wolf covariance shrinkage, and Barra-style factor neutralization.
- **Paper Execution Exclusively**: Live capital execution is intentionally disabled by design.

---

## System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        INSTITUTIONAL REACT TERMINAL (PORT 5173)                        │
│  - Global Trading Safety Status Bar & Gated Unfreeze Protocol Modal                    │
│  - Polymorphic Cross-Asset Workspaces (EQUITY, ETF, COMMODITY, CRYPTO, FOREX)          │
│  - Interactive Candlestick Chart Engine (1D, 5D, 1M, 6M, 1Y, 5Y)                       │
│  - Real-Time Broker Health, Order Ledger Lineage, and Reconciliation Matrix View       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       FASTAPI ORCHESTRATION & QUANT CONTROL PLANE (PORT 8000)          │
│  - Polymorphic Asset Metadata & Discriminator Resolvers                                │
│  - Point-in-Time (PIT) Bitemporal Store & Anti-Lookahead Defense Layer                 │
│  - Multi-Agent Research DAG with Primary-Source XBRL Verification                      │
│  - Alpha Factory (CPCV, DSR, PBO, Half-Kelly, Ledoit-Wolf Sizing)                      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       GO 1.22 HIGH-PERFORMANCE OMS / EMS (PORT 8080)                   │
│  - Sub-Millisecond Pre-Trade Pure Risk Gateways & Hard Limit Allocator                 │
│  - Event-Sourced JSONL Order Journal with Replay Recovery & Lineage Audit Context      │
│  - Fail-Closed Readiness Probes (/health/live, /health/ready, /api/v1/readiness)       │
│  - Pluggable Strict Broker Adapters (Paper Simulation, Alpaca Paper, Webull)           │
│  - Automated Broker Reconciliation Engine & Gated Execution Resume Boundary            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Quickstart & Service Management

### Prerequisites
- **Python**: 3.11+
- **Go**: 1.22+
- **Node.js**: 20+ / `npm`
- **Git**

---

### Starting the Workstation

#### Option A: One-Click Full Platform Launcher (Windows)
```cmd
run_full_platform.bat
```
*This launches the Go Engine (Port 8080), Python FastAPI backend (Port 8000), and Vite frontend (Port 5173).*

#### Option B: Individual Services

1. **Start the Go Execution Engine (Port 8080)**:
   ```cmd
   cd services/aq-engine-go
   go run main.go
   ```

2. **Start the Python FastAPI Backend (Port 8000)**:
   ```cmd
   python -m uvicorn src.ai_quant.api.server:app --host 0.0.0.0 --port 8000
   ```

3. **Start the Vite Frontend Terminal (Port 5173)**:
   ```cmd
   cd frontend
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

Open [`http://localhost:5173`](http://localhost:5173) in your browser.

---

### Diagnostic Environment Health Check

To verify that your local environment (Go, Python, Node, `.env` file, SQLite, and network ports) is healthy:
```cmd
run_doctor.bat
```

---

## Test Suites & CI Verification

All platform components are covered by automated unit and contract test suites.

### 1. Go Engine Tests
```powershell
cd services/aq-engine-go
go vet ./...
go test -race -count=1 ./...
```
*Covers pure risk checks, order submission idempotency, kill switch state, readiness probes, broker contracts, journal replay, and reconciliation.*

### 2. Python Quantitative Tests
```powershell
python -m pytest
```
*Covers PIT runtime, agent DAG, alpha strategies, forensics, risk metrics, and API routes.*

### 3. Frontend Terminal Build
```powershell
cd frontend
npm ci
npm run build
```
*Generates a clean, type-checked production bundle in `src/ai_quant/web/static/`.*

### 4. CI Workflow
The platform includes a unified GitHub Actions workflow at `.github/workflows/ci.yml` that runs Go, Python, and Frontend builds in parallel on every push and PR.

---

## Institutional Safety & Truth Invariants

1. **Zero Fabricated Market Values**: If a price or volume is missing or an API call fails, the platform returns `null` and displays `" — "` or `"unavailable"`. It never fabricates fallback `$100.0` prices.
2. **Fail-Closed Startup Gate**: The Go Engine starts frozen by default and only reports `READY` after verifying journal integrity, broker connectivity, and clean reconciliation.
3. **Gated Execution Resume**: An operator cannot unfreeze execution without providing a compliance justification reason and satisfying pre-trade gates (valid journal, connected broker, and fresh reconciliation with 0 mismatches).
4. **Broker Selection Invalidation**: Switching the active broker immediately invalidates reconciliation cache and halts execution until the new broker is reconciled.
5. **Strict Broker Normalization**: Adapters strictly validate API responses; unparseable numbers trigger explicit errors rather than silent zeros.

---

## Documentation Index

- [Enterprise User Manual (`USER_MANUAL.md`)](file:///d:/Main/ai-quant/ai_quant_platform/USER_MANUAL.md): Complete operational guide for the UI workstation and analytical modules.
- [Institutional Architecture Reference (`INSTITUTIONAL_ARCHITECTURE.md`)](file:///d:/Main/ai-quant/ai_quant_platform/INSTITUTIONAL_ARCHITECTURE.md): Deep-dive into OMS/EMS mechanics, reconciliation algorithms, and risk layers.
- [AI Handoff & Knowledge Base (`AI_HANDOFF.md`)](file:///d:/Main/ai-quant/ai_quant_platform/AI_HANDOFF.md): Engineering context, codebase map, invariants, and roadmap for incoming developers/agents.
- [Agent Governance & Spend Rules (`AGENT_GOVERNANCE.md`)](file:///d:/Main/ai-quant/ai_quant_platform/AGENT_GOVERNANCE.md): Rules for autonomous model evaluation and token budgets.
