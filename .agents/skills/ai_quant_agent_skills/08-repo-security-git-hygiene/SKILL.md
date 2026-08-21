---
name: repo-security-git-hygiene
description: Protect repository privacy, secrets, portable docs, focused commits, local runtime files, and safe configuration.
---

# Repository Security & Git Hygiene

## Before edits

```bash
git status --short
git diff
git diff --cached
git log --oneline -15
```

Never assume the working tree is clean.

## Secrets

Never commit:
- `.env`;
- broker keys;
- app secrets;
- access tokens;
- private keys;
- local credential files.

Keep:
```text
.env.example
```
with placeholders only.

If a real secret was committed:
1. identify provider/variable;
2. do not print value;
3. require rotation;
4. do not assume deletion from Git history makes it safe.

## Local information

Public docs must not contain:
- personal home paths;
- machine usernames;
- employee/student IDs;
- local drive paths;
- `file:///...` links;
- private hostnames;
- LAN/VPN addresses unless intentionally documented.

Prefer:
- relative repo paths;
- environment variables;
- `localhost`;
- portable commands.

## Mutable local files

Prefer:

```text
chatgpt_inbox.example.md tracked
chatgpt_inbox.md ignored
```

Same principle for:
- runtime DBs;
- local logs;
- caches;
- temporary reports;
- AI scratchpads.

## Git staging

Do not blindly:

```bash
git add .
git add -A
```

Stage explicit files.

Then:

```bash
git diff --cached
```

Every commit should have one purpose.

## Commit style

Examples:

```text
fix(oms): propagate journal failures
fix(webull): align Trading API routes
fix(pit): remove current-data historical fallback
feat(knowledge): add financial concept registry
test(oms): certify ambiguous submit recovery
```

## Documentation truth

Docs must match code.

Do not leave:
- stale endpoint schemas;
- removed safety override parameters;
- unsupported "periodic" claims;
- hard-coded test counts;
- old version labels without explanation.

## Security defaults

For execution services:
- loopback bind by default;
- auth required for real broker/live modes;
- refuse unsafe live startup config;
- never log secret-bearing headers.
