---
name: financial-explainability-ui
description: Build the financial education, explainability, operator UX, and truth-state presentation layer without weakening execution safety.
---

# Financial Explainability & Operator UX

## Product goal

The workstation should answer:

1. What is happening?
2. What does this metric mean?
3. How was it calculated?
4. Why did the system reach this conclusion?
5. What could make it wrong?
6. What will happen if I place this order?
7. What does the broker currently say is true?

## Authority levels

Visually distinguish:

```text
BROKER FACT
DETERMINISTIC CALCULATION
QUANT INTERPRETATION
AI INTERPRETATION
```

Do not render them as equally authoritative.

## Truth-state rules

```text
UNKNOWN != HEALTHY
MISSING != ZERO
NO SIGNAL != HOLD
NO RECONCILIATION != CLEAN
CANCEL REQUESTED != CANCELED
CONFIGURED != CONNECTED
```

## Financial knowledge registry

Prefer deterministic definitions.

Suggested records:

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

Initial categories:
- market microstructure;
- orders;
- portfolio;
- risk;
- performance;
- technical;
- fundamentals;
- forensic/quality;
- quant research;
- OMS/broker concepts.

## Examples

### RSI

Do not teach:
```text
RSI > 70 = SELL
```

Teach:
```text
RSI 72.3 indicates recent gains have been strong relative to recent losses.
Values above 70 are often called "overbought", but this does not imply price must fall.
Strong trends can remain elevated for extended periods.
```

### Maximum drawdown

Explain:
```text
Historical peak-to-trough loss.
Not a guarantee of maximum future loss.
```

### Reconciliation

Explain:
```text
Checks whether local OMS and broker agree on orders, positions, and cash.
A mismatch can freeze trading because the system cannot safely determine portfolio truth.
```

## Explain risk rejections deterministically

Example:

```text
ORDER BLOCKED

Reason:
Single-symbol exposure limit

Current exposure:
$1,520

Pending reserved exposure:
$300

Requested:
$800

Projected:
$2,620

Maximum:
$2,000
```

AI is not needed for this explanation.

## Learning mode

Optional learning mode:
- more definitions;
- formulas;
- examples;
- limitations;
- order consequence explanations.

Normal mode:
- compact institutional workstation.

## Live-mode UX

Future real-money mode must be visually unmistakable.

Show:
- broker;
- environment;
- account sync;
- event stream;
- market-data freshness;
- reconciliation freshness;
- OMS readiness;
- real-money label.

Never hide a critical state behind one generic green "CONNECTED."
