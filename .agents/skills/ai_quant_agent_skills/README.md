# AI Quant Platform Agent Skill Library

This folder contains modular `SKILL.md` files for AI coding agents working on the project.

## Recommended loading

Load only the skills relevant to the current task.

| Skill | Use when |
|---|---|
| `00-project-orchestrator` | Cross-cutting work, roadmap, baseline, sequencing |
| `01-real-money-oms-safety` | OMS, risk, journal, cancel, kill switch, capital controls |
| `02-webull-openapi` | Webull auth, routes, orders, market data, event stream |
| `03-reconciliation-broker-truth` | Broker/local truth, periodic reconciliation, recovery |
| `04-pit-data-provenance` | Historical research, bitemporal data, provenance, PIT |
| `05-ai-runtime-efficiency` | Reduce AI calls, routing, context, caching, materiality |
| `06-financial-explainability-ui` | Financial education, operator UX, explanations |
| `07-testing-ci-certification` | Tests, CI, sandbox, fault injection, certification |
| `08-repo-security-git-hygiene` | Secrets, local paths, commits, docs, repo hygiene |
| `09-observability-operations` | Health/readiness, metrics, alerts, runbooks |

## Default skill pairings

### Webull broker task
Load:
- `00-project-orchestrator`
- `02-webull-openapi`
- `03-reconciliation-broker-truth`
- `07-testing-ci-certification`
- `08-repo-security-git-hygiene`

### OMS/risk task
Load:
- `00-project-orchestrator`
- `01-real-money-oms-safety`
- `03-reconciliation-broker-truth`
- `07-testing-ci-certification`

### Research/PIT task
Load:
- `00-project-orchestrator`
- `04-pit-data-provenance`
- `05-ai-runtime-efficiency`
- `07-testing-ci-certification`

### Frontend educational UX task
Load:
- `00-project-orchestrator`
- `06-financial-explainability-ui`
- `09-observability-operations`

## Rule

Do not load every skill into every agent prompt unless the task genuinely spans all areas. The point of the library is to reduce context and keep the coding agent focused.
