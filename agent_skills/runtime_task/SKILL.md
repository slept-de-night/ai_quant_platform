# Runtime task skill

1. Work only on the leased task and its supplied dependency outputs.
2. Do not create workers directly. Request delegation through the orchestrator.
3. Treat a task retry as the same logical task. Preserve idempotency.
4. Never perform a broker write from a research/runtime task.
5. Return structured output. Do not silently mutate another task's state.
6. If required evidence is absent, report the missing dependency instead of inventing it.
