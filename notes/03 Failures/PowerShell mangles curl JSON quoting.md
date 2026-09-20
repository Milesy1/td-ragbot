---
tags: [failure, hygiene]
---

# PowerShell mangles curl JSON quoting

**Symptom:** `curl` commands with inline JSON bodies fail or send malformed payloads when run from PowerShell, even though the same command works fine from a POSIX shell.

**Environment:** Windows PowerShell, testing middleware endpoints directly during development (not a TD-bridge issue — a general Windows dev-environment hygiene note).

**Evidence:** JSON quoting gets mangled by PowerShell's own parsing before it reaches `curl`.

**Root cause:** PowerShell's argument parsing and quote-escaping rules differ from bash/POSIX shells, and plain `curl` aliases to `Invoke-WebRequest` in PowerShell by default rather than the real curl binary.

**Fix:** Use `curl.exe` explicitly (not the `curl` alias) with single-quoted JSON, or use `Invoke-RestMethod` with a `-Body` parameter instead of inline JSON string construction.

**Prevention:** Default to `Invoke-RestMethod -Body` for scripted middleware testing on this machine rather than reaching for `curl` syntax that assumes a POSIX shell.
