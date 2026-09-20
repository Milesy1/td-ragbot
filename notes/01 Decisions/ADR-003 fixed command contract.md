# ADR-003: Fixed command contract

Five actions, allowlisted on both sides (Pydantic schema in middleware, hand-written dispatcher in TD): `create_op`, `set_par`, `connect`, `list_ops`, `delete_op`. No `exec`, no `save`, no `quit`. Every reply carries structured debug (`op_errors`, `cook_ms`).

The contract is versioned. A change to it must propagate to every layer — schema, middleware validation, TD executor — simultaneously, or the layers drift apart silently.

**Forced by:** [[../03 Failures/connect command rejected — schema field name drift|connect command rejected]] — the schema used `from_path`/`to_path`, the hand-written TD executor expected `from`/`to`. Same contract, two independent implementations, no shared source of truth. Prevention noted there: generate the TD dispatcher from the Pydantic models instead of hand-writing both sides.

**Related:** [[ADR-001 middleware chokepoint]]
