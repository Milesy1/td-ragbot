---
tags: [failure, td-bridge]
---

# Callbacks never fire — build 2023 naming

**Symptom:** DAT connects (visible on the middleware side), but no callback logic ever executes — no register handshake, nothing.

**Environment:** TD build 2023.12480 specifically.

**Evidence:** Connection established at the socket level; callbacks DAT present and populated; nothing happens inside it.

**Root cause:** TD 2023.12480's WebSocket DAT callback API uses `onConnect`/`onReceiveText`. Current TD documentation and most examples assume `onOpen`/`onMessage` (the newer naming). On this build, `onOpen`/`onMessage` are silently ignored — not an error, just never called.

**Fix:** Write callbacks under the `onConnect`/`onReceiveText` names for this build.

**Prevention:** The `TDAgent.tox` component must ship **both** naming conventions (`onConnect` + `onOpen`, `onReceiveText` + `onMessage`) so it works across TD build versions without per-install detection. Logged directly in [[../05 Roadmap|Roadmap]] item 4.

**Related:** [[Connection arrives but no register — missing custom parameters]]
