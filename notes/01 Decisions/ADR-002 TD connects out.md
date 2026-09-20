# ADR-002: TD connects out

TouchDesigner's WebSocket DAT dials OUT to the middleware, rather than the middleware dialing in to TD. This inverts the naive direction.

**Reasoning:** with TD as the client, the session registry becomes simply "who connected" — any TD instance, on any machine, behind any NAT, can join without inbound ports, port-forwarding, or firewall exceptions on the TD side. The middleware just needs to be reachable *from* TD, never the other way round.

**Forced by:** [[../03 Failures/DAT never dials — Active off|DAT never dials]] and [[../03 Failures/TD connects at root path — ws route mismatch|TD connects at root path]] both surfaced connection-direction assumptions that this ADR resolved upfront — but the *symptom* of "nothing is listening" always looks the same regardless of which side is supposed to dial.

**Related:** [[ADR-001 middleware chokepoint]], [[ADR-005 component-first formalization]]
