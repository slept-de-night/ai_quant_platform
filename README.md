# AI Quant Platform v1.2

A research-first, **paper-trading-only** AI/quant platform.

v1.2 keeps the Alpha Factory + Deep Intelligence Layer and adds a **durable local agent runtime, model deployment control plane, and empirical routing evaluation** for technical, fundamental, micro-trend, mega/macro-trend, future-scenario, hypothesis-falsification, and evidence verification.

## What v1.2 adds

v1.2 turns the v1.1 agent plan into an executable, auditable DAG:

- SQLite-backed task queue with dependencies;
- worker leases and lease recovery;
- retries with bounded exponential backoff;
- dead-letter tasks rather than silent disappearance;
- idempotency keys to prevent duplicate logical work;
- bounded local parallel workers;
- versioned model deployments for `fast / balanced / frontier`;
- deployment health and safe tier fallback;
- live model probe command with optional health application;
- task/model evaluation records for quality, reliability, evidence, latency, tokens and cost;
- learned routing **recommendations** based on measured outcomes;
- explicit approval before a routing recommendation can become policy;
- separate `capital_approved` gate before learned overrides may affect high-impact financial review;
- non-destructive memory expiration + checkpoint consolidation;
- per-run routed-AI spend guard using recorded token usage and configurable price inputs.

The scheduler can be smoke-tested completely offline. AI/web tasks are skipped unless `--execute-ai` is supplied. The paper broker remains separate and live trading remains unavailable.

See `RUNTIME_AND_ROUTING.md` and `AGENT_GOVERNANCE.md` for the control-plane rules.

The core design remains intentionally asymmetric:

- quantitative code owns signals and backtests;
- AI may research, compare evidence, propose hypotheses and build scenarios;
- weak or contradictory research can reduce risk easily;
- AI/news can increase position sizing only slightly, and only under high evidence trust;
- hard risk rules and the paper broker remain deterministic.

## Architecture

```text
                         PUBLIC DATA
                             |
        +--------------------+---------------------+
        |                    |                     |
      OHLCV              SEC XBRL                FRED
        |                    |                     |
        v                    v                     v
 Technical Engine     Fundamental Engine      Macro Engine
        |                    |                     |
        +------------+-------+----------+----------+
                     |                  |
                 Micro Trend         Mega Trend
                     |                  |
                     +---------+--------+
                               |
                     OpenAI Web Research
                               |
                     Citation extraction
                               |
                  Unicode / injection scanner
                               |
                       Source classifier
                               |
              +----------------+----------------+
              |                                 |
       Primary-source path             Multi-source corroboration
              |                                 |
              +----------------+----------------+
                               |
                    Evidence Verification
                               |
                    Contradiction Detector
                               |
                         VERIFIED CLAIMS
                               |
                     Future Scenario Agent
                               |
                    Hypothesis Falsifier
                               |
                       Research Dossier
                               |
                         Context Gate
                               |
             +-----------------+-------------------+
             |                                     |
      Quant strategy signal                 Alpha Factory
             |                              hypothesis search
             |                                     |
             +-----------------+-------------------+
                               |
                      HARD RISK ENGINE
                               |
                       Alpaca PAPER only
```

## What the new intelligence layers do

### Technical analysis

Deterministic, not LLM-calculated:

- 5/20/60-day momentum
- price vs SMA200
- SMA20 vs SMA50
- RSI
- realized volatility
- mean-reversion warning
- directional score + confidence

### Fundamental analysis

Optional SEC Company Facts/XBRL adapter for US issuers:

- revenue and revenue growth
- operating income / margin
- net income / margin
- assets and asset growth
- liabilities / equity
- debt-to-equity
- diluted EPS when available

This is deliberately **not** called a complete valuation model. Reliable P/E, EV/EBITDA, FCF yield, dilution, SBC, segment economics and point-in-time share counts still need a richer fundamentals dataset.

### Micro trend

Weeks-to-months context:

- symbol momentum
- relative strength versus a sector/industry proxy
- relative strength versus the broad market
- leadership / lagging / transition classification

Example for NVDA:

```powershell
--sector XLK --market SPY
```

For semiconductor-specific work you may prefer a semiconductor ETF proxy rather than XLK. The proxy is intentionally explicit rather than silently guessed.

### Mega / macro trend

Months-to-years context using market and cross-asset trends, with optional FRED macro data:

- broad equity trend
- growth-vs-market leadership
- long-duration bond trend
- gold trend
- Fed funds
- unemployment
- CPI YoY
- industrial production YoY
- 10y-2y yield curve

### Future trend

The AI does **scenario analysis**, not an exact price prophecy.

It returns several conditional futures with:

- probability
- horizon
- direction
- drivers
- invalidators
- explicit unknowns

A scenario is a hypothesis. It is not promoted to “fact” because a model phrased it confidently.

### Hypothesis / falsification research

Every central thesis must include:

- supporting evidence
- contradicting evidence
- missing evidence
- explicit falsification tests
- confidence
- whether the thesis survives current evidence

The goal is to make the AI spend effort trying to kill its own thesis instead of behaving like a brokerage newsletter.

## Fake-news / adversarial-news defense

No system can guarantee immunity from fake news. v1.2 instead uses several independent defenses.

### 1. Webpages are untrusted data

The research prompt explicitly forbids following instructions found in pages, headlines, metadata, article text, or hidden content.

### 2. Tool-returned citations, not model-invented source URLs

The web research layer extracts URLs and titles from OpenAI web-search citation annotations returned by the Responses API.

### 3. Source tiers

Default primary/official sources include SEC and US government/regulatory domains.

Trusted secondary sources include a conservative allow-list of major wire/news organizations.

Social/UGC sources such as Reddit, X, Stocktwits and Quora are blocked from the web-search layer and are not admissible as material evidence.

You can add official investor-relations domains in `.env`:

```env
EXTRA_PRIMARY_DOMAINS=investor.nvidia.com,investor.apple.com
```

### 4. Independent corroboration

A claim is normally considered verified only when it has either:

- at least one recognized primary/official source, or
- at least two independent trusted secondary sources.

Multiple pages from the same publisher do not count as independent corroboration.

### 5. Adversarial text scanner

The evidence layer flags/rejects content containing signals such as:

- zero-width characters
- bidi-control characters
- hidden/control characters
- prompt-injection-like instructions

This specifically addresses the class of attacks where machine-visible content differs from what a human sees.

### 6. Contradiction pass

After deterministic verification, a separate low-effort AI pass receives only **sanitized claim text**, not raw webpages. It identifies direct contradictions among retrieved claims. Conflicting claims are downgraded to `DISPUTED` and lower the evidence-trust score.

### 7. Asymmetric risk permissions

This is the important one.

Weak news can reduce risk. It cannot easily increase it.

```text
Evidence trust < 0.35
    -> context sizing capped around 55%

Evidence trust < 0.20 + positive thesis
    -> new BUY blocked

Material contradiction
    -> context sizing capped around 50%

High-trust evidence aligned with quant signal
    -> maximum context increase is only 5%
```

So one exciting headline cannot turn a 5% position into a 20% position. Civilization survives another afternoon.

## Alpha Factory remains separate

The Alpha Factory still works as in v0.9:

```text
GPT-5.6
   |
Generate constrained StrategySpec
   |
Safe factor DSL
   |
Walk-forward validation
   |
Cost stress
   |
Threshold perturbation
   |
Robustness gate
   |
CANDIDATE / VALIDATED
   |
Manual approval
```

The model does not generate executable trading code.

## Quick Start & Web Dashboard

### 1. Run with Docker (Recommended)

```powershell
copy .env.example .env
docker compose up --build -d
```
Open **http://localhost:8000** in your browser to access the full Quant Terminal & DAG Control Plane.

To stop the container:
```powershell
docker compose down
```

### 2. Run Locally on Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env
python -m ai_quant.main doctor

# Start the Web Application
python -m ai_quant.main web --port 8000
```
Or double-click `run_web.bat` or `docker_run.bat`.

## Configuration

### OpenAI + model deployment tiers

```env
OPENAI_API_KEY=...
MODEL_FAST=gpt-5.6-luna
MODEL_BALANCED=gpt-5.6-terra
MODEL_FRONTIER=gpt-5.6-sol
ENABLE_PRO_MODE=false
ENABLE_WEB_RESEARCH=true

AGENT_USD_BUDGET_PER_RUN=10
```

The price fields in `.env.example` are used only for local estimated-cost accounting and routing evaluation. Verify current API pricing before relying on them operationally.

### SEC fundamentals

Set a real identifying user agent, including a contact email:

```env
SEC_USER_AGENT=MyResearchApp my-email@example.com
```

### FRED macro data

```env
FRED_API_KEY=...
```

### Alpaca

```env
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
USE_ALPACA_DATA=true
```

## Run deep research

Example for a technology stock:

```powershell
python -m ai_quant.main deep-research `
  --symbol NVDA `
  --market SPY `
  --sector XLK `
  --growth QQQ `
  --bond TLT `
  --gold GLD `
  --days 1000
```

The command persists a `ResearchDossier` in SQLite.

Inspect it later:

```powershell
python -m ai_quant.main research-status --symbol NVDA
```

By default the dossier expires after 24 hours.

## Paper-trading gate

`REQUIRE_FRESH_DOSSIER=true` by default.

That means a new paper BUY requires a fresh research dossier. SELL/position-reduction logic does not need bullish evidence because risk exits should not be trapped behind an AI research outage.

Workflow:

```powershell
# 1. Refresh research
python -m ai_quant.main deep-research --symbol NVDA --market SPY --sector XLK

# 2. Validate/approve a quantitative strategy separately
python -m ai_quant.main validate --symbol NVDA --strategy YOUR_STRATEGY --days 1800
python -m ai_quant.main approve YOUR_STRATEGY

# 3. Inspect paper decision
python -m ai_quant.main paper-cycle --symbol NVDA --strategy YOUR_STRATEGY

# 4. Paper order only
python -m ai_quant.main paper-cycle --symbol NVDA --strategy YOUR_STRATEGY --execute
```

Even with `--execute`, the broker client remains hard-coded to Alpaca paper mode.

## v1.2 runtime

Preview the bounded agent hierarchy:

```powershell
python -m ai_quant.main orchestrator-plan --symbol NVDA
```

Enqueue it without executing:

```powershell
python -m ai_quant.main runtime-plan --symbol NVDA
```

Run the DAG offline using deterministic/fallback handlers:

```powershell
python -m ai_quant.main runtime-run --symbol NVDA --concurrency 4
```

Allow routed OpenAI/web work for eligible runtime tasks:

```powershell
python -m ai_quant.main runtime-run --symbol NVDA --concurrency 4 --execute-ai
```

Inspect queue and event state:

```powershell
python -m ai_quant.main runtime-status
python -m ai_quant.main runtime-events --limit 100
```

Dead-letter/cancelled work can be deliberately requeued:

```powershell
python -m ai_quant.main runtime-requeue TASK_ID
```

## Model deployment manager

```powershell
python -m ai_quant.main model-deployments
python -m ai_quant.main model-register --tier balanced --model MODEL_ID --notes "candidate"
python -m ai_quant.main model-activate DEPLOYMENT_ID
python -m ai_quant.main model-health DEPLOYMENT_ID --status degraded --reason "elevated errors"
python -m ai_quant.main model-probe DEPLOYMENT_ID
```

A probe does not change health unless `--apply-health` is explicitly supplied.

## Empirical routing evaluation

Alpha generation now records a validation-backed evaluation after each generated batch. Other task outcomes can be imported/recorded through the evaluation API or CLI.

```powershell
python -m ai_quant.main model-performance --task-type alpha_generation
python -m ai_quant.main route-recommend --task-type alpha_generation --current-tier frontier
python -m ai_quant.main route-recommendations
python -m ai_quant.main route-approve RECOMMENDATION_ID
```

For high-impact financial tasks, an ordinary approved override is ignored. Deliberate approval requires:

```powershell
python -m ai_quant.main route-approve RECOMMENDATION_ID --capital-approved
```

There is intentionally no auto-approve mode.

## Memory maintenance

```powershell
python -m ai_quant.main memory-maintain --agent alpha_research_agent --symbol NVDA
```

This marks due notes expired and can create a derived checkpoint citing original memory IDs. It does not erase the original notes.

## Other commands

```powershell
python -m ai_quant.main doctor
python -m ai_quant.main backtest --symbol SPY --strategy trend_momentum --days 1600
python -m ai_quant.main validate --symbol SPY --strategy trend_momentum --days 1800
python -m ai_quant.main alpha-search --symbol SPY --count 8 --days 1800
python -m ai_quant.main list-strategies
python -m ai_quant.main portfolio-backtest --symbols SPY,QQQ,IWM,GLD,TLT --strategy trend_momentum --days 1600
```

## Tests

```powershell
pytest -q
```

v1.2 currently passes **28 tests**, covering:

- backtest signal timing
- factor validation
- registry approval gate
- hard risk rules
- walk-forward validation
- primary-source verification
- insufficient single-source evidence
- hidden/adversarial text detection
- low-trust context sizing
- task idempotency and DAG dependency ordering
- retry/dead-letter behavior
- worker-pool DAG execution
- model deployment activation and health fallback
- empirical routing recommendation + approval
- capital-impact override protection
- non-destructive memory expiry/checkpointing

## Remaining production gaps

Read `PRODUCTION_GAPS.md`.

The largest remaining research problems are not “add more agents.” They are:

- point-in-time data and revision-aware macro data
- survivorship-safe equity universes
- complete fundamentals/valuation history
- corporate-action correctness
- execution/reconciliation streaming
- realistic market impact / liquidity
- benchmark and factor attribution
- model/prompt/version evals
- long forward paper-trading evidence

A complicated system can still be wrong. v1.2 is designed to make being wrong **observable, constrained, and less expensive**.
