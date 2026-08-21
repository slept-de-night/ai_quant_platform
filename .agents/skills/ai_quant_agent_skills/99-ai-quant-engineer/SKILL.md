---
name: ai-quant-engineer
description: Institutional quantitative research and execution engineering skill for the AI Quant Platform. Use when developing, extending, testing, or auditing quantitative factor models, Webull OpenAPI integration, Go OMS/EMS engine, pre-trade risk controls, background reconciliation workers, the Financial Knowledge Registry, or the React workstation UI.
---

# AI Quant Platform — Engineering Skill & Architecture Runbook

This skill provides comprehensive instructions, invariants, architectural schemas, and standard verification workflows for developing and extending the **AI Quant Platform**.

---

## 1. Non-Negotiable System Invariants

1. **Safety Hierarchy**:
   ```text
   DATA
     ↓
   PIT / MARKET TRUTH
     ↓
   RESEARCH (Multi-Agent DAG)
     ↓
   FINANCIAL EXPLANATION (Knowledge Registry)
     ↓
   SIGNAL / ORDER PROPOSAL
     ↓
   DETERMINISTIC RISK (Pre-Trade Gates & Reservations)
     ↓
   DURABLE OMS (Write-Ahead Journal with fsync)
     ↓
   BROKER (Webull OpenAPI / Alpaca / Paper)
     ↓
   BROKER EVENTS (gRPC / Streaming / Webhooks)
     ↓
   CONTINUOUS RECONCILIATION (Periodic 30s State Diff)
   ```

2. **Live Order Submission Prohibited (Fail Closed)**:
   - Real-money live trading remains disabled until all formal release gates are passed.
   - Any order submission attempted with `WEBULL_ENVIRONMENT=LIVE` or `ALPACA_LIVE=true` must return `ErrLiveTradingNotPermitted` or fail closed.
   - Execution is restricted to `SANDBOX` or `PAPER`.

3. **AI Governance**:
   - AI agents may assist with research, factor generation, and pedagogical explanation.
   - AI agents **must NEVER** directly place broker orders, override deterministic risk limits, auto-unfreeze the execution engine, or modify gross capital allocations.

4. **Polymorphic Cross-Asset Integrity**:
   - The platform supports `EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, and `FOREX`.
   - Corporate forensic models (Altman Z, 9-point Piotroski F, Beneish M8, Sloan Accruals) and balance sheets must **never** be rendered or fabricated for non-equity assets (`CRYPTO`, `COMMODITY`, `FOREX`). Use `ContextualExplainer` to handle cross-asset queries cleanly.

---

## 2. Codebase Organization & Key Components

### A. Go Low-Latency OMS / EMS Core (`services/aq-engine-go/`)
- `broker/webull/`:
  - `signer.go`: Canonical request formatting and HMAC-SHA256 Base64 OpenAPI signer.
  - `client.go`: Resilient HTTP transport with token-bucket rate limiting (10 req/s, capacity 20) and backoff with jitter.
  - `state.go`: Read-only queries (`FetchAccount`, `FetchPositions`, `FetchOrders`, `FetchBrokerSnapshot`).
  - `order.go`: Sandbox order execution (`SubmitSandboxOrder`, `CancelSandboxOrder`, `QuerySandboxOrder`) and live safety guard.
  - `stream.go`: gRPC streaming event consumer with disconnect watchdog (30s timeout fallback to reconciliation polling).
  - `quote.go`: Level 1 market data quotes, staleness checks (< 60s), and NBBO deviation sanity checks (> 5% rejection).
- `oms/`:
  - `engine.go`: Durable in-memory order management system, pre-trade risk evaluation, and position projection.
  - `journal.go`: Write-ahead event log persistence (`journal.log`) with deterministic recovery replay.
- `reconciliation/`:
  - `worker.go`: Continuous periodic background reconciliation worker (default 30s interval) that diffs local OMS state with broker state and auto-freezes the engine on critical discrepancies.
- `market/`:
  - `gateway.go`: Central market price distribution gateway for authoritative pre-trade checks.
- `auth/`:
  - `auth.go`: Default loopback binding (`127.0.0.1:8080`) and mandatory token entropy verification for protected endpoints.

### B. Python Quantitative Research & Knowledge (`src/ai_quant/`)
- `knowledge/`:
  - `models.py`: `FinancialMetricExplanation` schema (LaTeX formulas, benchmark ranges, pitfalls, quant usage).
  - `registry.py`: `FinancialKnowledgeRegistry` catalog covering Valuation, Forensic, Risk, Portfolio, Execution, and Macro domains.
  - `explainer.py`: `ContextualExplainer` for tailored metric assessment and cross-asset applicability guidance.
- `api/server.py`: FastAPI server exposing `/api/v1/knowledge/metrics`, `/api/v1/knowledge/explain`, `/api/v1/status`, `/api/v1/readiness`.
- `quant/`: Alpha factory, backtest engine, Ledoit-Wolf covariance shrinkage, Barra-style neutralization, Half-Kelly sizing, CPCV, and walk-forward validation.
- `intelligence/`: Multi-agent research DAG, agent memory store, and intelligence scoring.

### C. Frontend Workstation (`frontend/src/`)
- `components/knowledge/`:
  - `KnowledgeBaseModal.tsx`: Institutional quantitative and financial knowledge explorer.
  - `MetricInfoTooltip.tsx`: Interactive tooltip badge for Learning Mode.
- `components/layout/`:
  - `Header.tsx`: Navigation, search autocomplete, Learning Mode toggle, broker venue selector, kill switch status.
  - `SafetyStatusBar.tsx`: Live trading readiness checklist and gated unfreeze controls.
- `components/views/`:
  - `DashboardView.tsx`, `AlphaStudioView.tsx`, `PaperTradingDeskView.tsx`, `RuntimeDAGView.tsx`, `IntelligenceHubView.tsx`.

---

## 3. Standard Verification Runbook

Always verify all three layers before committing:

### 1. Go OMS Test Suite
```powershell
$env:PATH = "C:\Users\2465975\go\bin;" + $env:PATH
cd services/aq-engine-go
go vet ./...
go test -v -count=1 ./...
```
*Expected: 100% PASS across all packages (`broker`, `broker/webull`, `oms`, `reconciliation`, `market`, `execution`, `metrics`).*

### 2. Python Quantitative Engine Test Suite
```bash
python -m pytest -q
```
*Expected: All tests pass with zero regressions.*

### 3. Frontend Workstation Production Build
```powershell
cd frontend
npm run build
```
*Expected: Clean TypeScript compilation (`tsc -b && vite build`) with zero type errors.*

---

## 4. Feature Development Procedure

When implementing new capabilities:

1. **Inspect Before Modifying**: View existing structs, interfaces, and endpoints. Do not make assumptions.
2. **Implement Minimal Coherent Code**: Reuse existing modules, avoid duplicating math or risk models.
3. **Write Comprehensive Automated Tests**: Add test cases for both standard success paths and fail-closed error paths.
4. **Execute Verification Runbook**: Confirm Go, Python, and Frontend builds pass.
5. **Commit and Push**:
   ```bash
   git add <files>
   git commit -m "<type>(<scope>): <descriptive message>"
   git push origin main
   ```
