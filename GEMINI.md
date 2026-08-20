# AI Quant Platform v1.2 — Coding Agent Instructions

You are working on an **EXISTING, WORKING quantitative trading platform**.

Your job is **not to redesign the repository from scratch**.

Your job is to carefully inspect the current project, understand how it already works, and incrementally upgrade it into a polymorphic cross-asset quantitative workstation while preserving all working functionality.

---

# 1. PROJECT CONTEXT

Project name:

**AI Quant Platform v1.2**

Current stack:

## Backend
- Python 3.11
- FastAPI
- Pydantic v2
- NumPy
- Pandas
- AsyncIO
- HTTPX
- Existing Yahoo Finance integration
- Existing SEC EDGAR/XBRL integration
- Existing quantitative/factor engines
- Existing forensic accounting models
- Existing portfolio/risk systems

## Execution
- Go 1.22
- OMS / EMS
- Pre-trade risk checks
- TWAP
- VWAP
- Paper trading
- Broker integration

## Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Lucide Icons

## Existing quantitative functionality
The project already contains working implementations for functionality such as:

- Factor engine
- Walk-forward validation
- CPCV
- DSR
- PBO
- Ledoit-Wolf covariance
- Barra-style factor neutralization
- Half-Kelly sizing
- Volatility targeting
- Portfolio/risk limits
- SEC financial statements
- Altman Z-Score
- Canonical Piotroski 9-Point F-Score
- Beneish M-Score
- Sloan Accruals
- Multi-agent research runtime
- Paper trading
- Go execution/risk engine

**DO NOT duplicate these implementations.**

Reuse the existing project code.

---

# 2. PRIMARY DEVELOPMENT GOAL

Historically the application was designed mainly for US operating corporations such as:

- AAPL
- NVDA
- MSFT

Because of this, the UI currently assumes every asset has:

- company financial statements
- employees
- SEC 10-K filings
- Altman Z-Score
- Piotroski F-Score
- Beneish M-Score
- Sloan Accruals
- Wall Street consensus
- corporate fundamentals

This is incorrect for other asset classes.

We are upgrading the platform to support:

```text
EQUITY
ETF
COMMODITY
CRYPTO
FOREX
```

The entire workspace must dynamically change depending on the selected asset.

---

# 3. CRITICAL PROJECT RULES

These rules are mandatory.

## Rule 1 — Inspect before editing
Before modifying a feature, inspect the relevant existing files.
Never assume filenames, architecture, types, functions, or endpoints.
The repository is the source of truth.

## Rule 2 — Do not rewrite working systems
If functionality already exists, reuse or extend it.
If forensic models already exist, reuse them.

## Rule 3 — Minimal coherent changes
Prefer modifying existing files and adding focused domain adapters over broad restructurings.

## Rule 4 — Preserve backward compatibility
Existing functionality for US equities (`AAPL`, `NVDA`, `MSFT`) must continue to work with full financial statements, forensic models, and corporate analytics.

## Rule 5 — Never replace real functionality with mock data
Missing external data should be returned as `null` / `unavailable` / `"—"` with clean UI handling rather than fabricated mock constants.

## Rule 6 — Never silently hide provider failures
Handle expected provider failures explicitly, log errors, and return unavailable fields where appropriate.

## Rule 7 — Do not touch unrelated systems
Cross-asset UI work should not unnecessarily modify Go OMS/EMS, TWAP, VWAP, backtesting, CPCV, DSR, or PBO.

## Rule 8 — Existing tests must continue passing
Run tests after every phase:
- Python: `pytest -q`
- Go: `cd services/aq-engine-go && go test ./...`
- Frontend: `npm run build`

## Rule 9 — Add tests for new behavior
Every new asset classifier or API behavior must have automated tests.

## Rule 10 — Stop when the requested phase is complete

---

# 4. IMPORTANT ASSET TAXONOMY

Two orthogonal dimensions:
- `AssetType`: Controls the ANALYTICS WORKSPACE (`EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `FOREX`).
- `InstrumentType`: Describes WHAT IS ACTUALLY TRADED (`STOCK`, `ETF`, `TRUST`, `ETP`, `FUTURE`, `CRYPTO`, `FX_SPOT`).

Examples:
- `AAPL`: `AssetType.EQUITY`, `InstrumentType.STOCK`
- `SPY`: `AssetType.ETF`, `InstrumentType.ETF`
- `GLD`: `AssetType.COMMODITY`, `InstrumentType.TRUST`
- `GC=F`: `AssetType.COMMODITY`, `InstrumentType.FUTURE`
- `BTC-USD`: `AssetType.CRYPTO`, `InstrumentType.CRYPTO`
- `EURUSD=X`: `AssetType.FOREX`, `InstrumentType.FX_SPOT`

---

# 5. POLYMORPHIC DISCRIMINATED UNION

The backend returns an asset payload discriminated by `asset_type`:
```text
AssetPayload = EquityAssetPayload | ETFAssetPayload | CommodityAssetPayload | CryptoAssetPayload | ForexAssetPayload
```
Corporate forensic fields (`Altman Z`, `Piotroski F`, `Beneish M`, `Sloan Accruals`, balance sheets, employees) MUST NEVER exist on Crypto, Commodity, ETF, or Forex payloads.

---

# 6. ASSET-SPECIFIC WORKSPACES

- **EQUITY**: 5-Year SEC XBRL financial statements, Altman Z, 9-point Piotroski F, Beneish M8, Sloan Accruals, technical analytics, and consensus.
- **ETF**: Fund summary (AUM, expense ratio, replication method, rebalancing schedule), Top 10-25 basket holdings with visual percentage weight bars, and sector allocation.
- **CRYPTO**: Price, 24h change, tokenomics (circulating supply, max supply, hard cap), ATH price & ATH drawdown % (\((P / \text{ATH} - 1) \times 100\)), 30-day 24/7 hourly realized volatility (\(\text{std} \times \sqrt{24 \times 365}\)), and consensus architecture.
- **COMMODITY**: Exposure architecture (Trust vs Futures), physical vaulting standards & custodians (where applicable), macro matrix (Gold/Silver ratio, Real yield sensitivity, 10Y inflation beta), and futures term structure / roll yield.
- **FOREX**: Base/quote currencies, central-bank policy rates, interest-rate differential, annualized carry yield, and policy cycle.
