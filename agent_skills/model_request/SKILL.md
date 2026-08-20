# Skill: Model request and escalation

## Purpose
Use the least expensive model/reasoning effort that reliably handles a task, escalating only when measured complexity or risk justifies it.

## Profiles

- **Fast:** extraction, formatting, deduplication, lightweight classification, journal summaries.
- **Balanced:** ordinary web research, fundamental/trend review, contradiction checks, research digests.
- **Frontier:** alpha generation, difficult hypothesis work, falsification, scenario synthesis, critical promotion review.

## Rules

1. Agents request capabilities, not model names. `ModelRouter` selects the deployment.
2. Complexity, criticality, ambiguity, financial impact, tool needs, and remaining budget drive routing.
3. Routine tasks may be downgraded when budget is tight.
4. High financial-impact reviews are protected from aggressive budget downgrades.
5. `max` reasoning is reserved for explicit quality-first work with very high difficulty and criticality.
6. Every route decision is written to `model_routes` for audit.
7. Model output never overrides deterministic validation, risk, or execution gates.
