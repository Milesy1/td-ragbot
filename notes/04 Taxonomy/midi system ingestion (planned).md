# MIDI system ingestion (planned)

**Planned, not yet built.** [[../05 Roadmap|Roadmap]] item 6.

Convert the existing MIDI-triggering Python system (a working TouchDesigner project) into technique documents — `.md` files with YAML front-matter: `id`, `ops_required`, `key_params`, `verification`.

**Why a different format from the main corpus:** [[corpus design|the main RAG corpus]] is prose meant to answer "what is X" questions. Technique documents are meant to be *read by both a human and the model*, and the model's reading needs to be actionable — `ops_required` and `key_params` map directly onto `create_op`/`set_par` calls, and `verification` gives the agent something concrete to check against after building, rather than just returning a text answer.

This is the first real test of retrieval feeding the [[../01 Decisions/ADR-003 fixed command contract|five-action contract]] rather than just feeding a chat response.
