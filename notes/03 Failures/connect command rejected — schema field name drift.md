---
tags: [failure, td-bridge]
---

# connect command rejected — schema field name drift

**Symptom:** `connect` commands are rejected by the TD-side executor even though the middleware validated and forwarded them successfully.

**Environment:** Middleware Pydantic schema and TD's hand-written command executor, developed somewhat independently.

**Evidence:** Middleware logs show a valid, schema-passing `connect` command sent to TD. TD-side dispatcher fails to find the fields it expects.

**Root cause:** The middleware's Pydantic schema uses `from_path`/`to_path` as field names. The hand-written TD executor was written expecting `from`/`to`. Same logical contract ([[../01 Decisions/ADR-003 fixed command contract|ADR-003]]), two independent hand-written implementations, and they drifted apart on naming without either side raising an error until runtime.

**Fix:** Align field names between schema and executor.

**Prevention:** Generate the TD-side dispatcher directly from the Pydantic models rather than hand-writing both sides of the same contract. Any future field rename then fails at generation/build time, not at a live command's runtime.

**Related:** [[../01 Decisions/ADR-003 fixed command contract]]
