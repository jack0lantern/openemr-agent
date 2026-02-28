# Active Context — openemr-agent

> Current focus areas and work-in-progress. Update as priorities change.

## Current Focus

- [ ] *(Add current tasks or focus areas here)*

## Recent Decisions

- Memory bank initialized for openemr-agent
- LLM model: `claude-haiku-4-5` (temperature 0) — fast, deterministic tool-calling
- Tools refactored into `app/llm/tools/` package — one module per domain; `agent.py` imports from the package
- `get_current_datetime` tool added — resolves relative date expressions ("next week", "next month") before date-dependent tool calls
- `list_appointment_types` tool added to scheduling tools
- Conversation persistence added via PostgreSQL (`app/db/`) — `Conversation` + `ConversationMessage` ORM models, async SQLAlchemy + asyncpg
- `app/llm/cost.py` + `app/llm/retry.py` extracted for cost tracking and retry logic
- `Citation` and `ResponseMetadata` added to `app/schemas.py`
- Auth is opt-in per endpoint via `PATIENT_AUTH_REQUIRED` / `STAFF_AUTH_REQUIRED` env flags (default: off for local dev)

## Blockers / Notes

- *(Add blockers or important notes here)*
