---
name: pit-data-provenance
description: Protect point-in-time correctness, bitemporal semantics, snapshot provenance, state hashes, historical research reproducibility, and source availability.
---

# PIT Data & Provenance

## Principle

Historical research may only know information that was actually knowable at the historical decision time.

Never make current data wear a historical timestamp.

## Time semantics

Distinguish:
- observed/effective date;
- known/publication date;
- ingestion date;
- research `as_of`;
- revision/vintage date.

Example:

```text
fiscal period end = 2025-12-31
filing accepted   = 2026-02-20
```

A run as of 2026-01-15 must not see that filing.

## SEC

`known_at` must come from actual filing/public availability.

Never use fiscal period end as filing availability.

If historical filing availability cannot be reconstructed:

```text
SourceState.NOT_PIT_CAPABLE
```

Do not fall back to current SEC state.

## FRED / macro

Historical research must respect release/vintage information.

If only current revised series are available:

```text
NOT_PIT_CAPABLE
```

Do not call current snapshot and stamp it with historical `as_of`.

## Market data

Historical provider must explicitly support PIT-safe `as_of`.

Post-filtering a modern adjusted series is not automatically PIT-safe because corporate-action adjustments may encode future knowledge.

## Source status

Use explicit statuses:

```text
AVAILABLE
UNAVAILABLE
ERROR
NOT_CONFIGURED
NOT_PIT_CAPABLE
```

No source failure should silently look like "zero fundamentals."

## Missing values

```text
MISSING != ZERO
```

Do not emit zero facts because parsing/data retrieval failed.

## Hash semantics

Separate:

### Provenance identity
May include:
- run ID;
- as_of;
- retrieval metadata;
- source references.

### State/content fingerprint
Represents economically relevant information.

Same information across runs:
```text
→ same state_hash
```

Changed fact/source/version:
```text
→ different state_hash
```

Do not include arbitrary run timestamps in the state fingerprint.

## Required tests

- filing invisible before public date;
- restatement invisible before restatement date;
- future market bars excluded;
- unsupported historical source -> NOT_PIT_CAPABLE;
- source failure -> ERROR;
- missing field -> no fake zero;
- identical economic state -> same state hash;
- changed state -> changed state hash;
- historical memory retrieval excludes future memory.
