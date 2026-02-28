# Architecture Decisions — openemr-agent

> Key architectural choices for the OpenEMR AI Agent microservice.

## Agent Design (PRD §4.1)

- **Framework:** LangGraph — directed state graph, tool-calling loop, auditability
- **Pattern:** Two independent agents share a common graph shape:
  - **Patient Agent** — appointment booking, clinic info, non-diagnostic medical info; scoped to the authenticated patient's data
  - **Staff Agent** — all patient capabilities + full FHIR clinical read (history, labs, meds, vitals) + insurance verification
- **State:** `MessagesState` TypedDict — `messages` (add_messages reducer), `debug_tool_calls`, `patient_id`, `staff_id`
- **Graph nodes:** `agent` (LLM call) → `tools` (ToolNode) → back to `agent` until no tool calls → END
- **Public API:** `invoke_patient_agent(messages, patient_id)` / `invoke_staff_agent(messages, staff_id)` — returns `ChatResponse`

## LLM

- **Model:** `claude-haiku-4-5`, temperature 0 — fast, deterministic tool-calling (PRD §4.2)
- **Provider:** Anthropic via `langchain-anthropic`
- **Cost tracking:** `app/llm/cost.py` computes USD cost from token usage metadata; attached to `ResponseMetadata`
- **Retry:** `app/llm/retry.py` — wraps LLM invocation with backoff for transient API errors

## Data Layer

- **Mock vs FHIR:** `USE_MOCK_DATA` env flag; `app/services/data_service.py` dispatches to either path, returning identical dict shapes to tools
- **Mock data:** `app/data/mock_data.py` — deterministic demo data; tests use `tests/fixtures/mock_data.py` (distinct IDs)
- **FHIR client:** `app/services/fhir_client.py` — async FHIR R4, OAuth2 Private Key JWT (RSA), token caching; base URL from `OPENEMR_FHIR_URL`

## Conversation Persistence

- **Database:** PostgreSQL via SQLAlchemy async (asyncpg driver)
- **Schema:**
  - `conversations` — `id` (UUID), `user_type` (patient/staff), `user_id`, `title`, timestamps
  - `conversation_messages` — `id`, `conversation_id` (FK), `role`, `content` (Text), `tool_calls_json` (JSON), `created_at`
- **Migrations:** Alembic
- **Session:** `app/db/session.py` — async engine + `AsyncSession` factory
- **CRUD:** `app/db/crud.py` — async helpers for creating/reading conversations and messages

## Authentication & Security

- **OpenEMR OAuth2:** Private Key JWT (RS256/RS384) — `OPENEMR_CLIENT_ID` + `PRIVATE_KEY_PATH`
- **Patient endpoint:** Bearer token validated against OpenEMR introspection; token scoped to authenticated patient
- **Staff endpoint:** Bearer token with staff-level scopes
- **Auth is opt-in:** `PATIENT_AUTH_REQUIRED` / `STAFF_AUTH_REQUIRED` env flags default to `false` for local dev
- **No "God Mode":** Each token scoped to one patient — agent cannot cross-access patient records
- **Prompt injection:** System prompts use `<user_input>` boundary markers; strict instruction grounding
- **PHI/PII logging:** Never log patient data — all tool results are ephemeral in agent state only

## API Shape

- `POST /api/chat/patient` — `ChatRequest` → `ChatResponse`
- `POST /api/chat/staff` — `ChatRequest` → `ChatResponse`
- `ChatRequest`: `{ messages: [{ role, content }], patient_id?, conversation_id? }`
- `ChatResponse`: `{ message: string, tool_calls?: ToolCallDebug[], metadata?: ResponseMetadata, citations?: Citation[] }`

## Telemetry

- **OpenTelemetry:** `app/telemetry.py` — OTLP HTTP exporter; compatible with Datadog and CloudWatch
- **LangSmith:** Optional trace logging (`LANGSMITH_TRACING`); flushed on shutdown via `app/langsmith_client.py`
- **Instrumentation:** `openinference-instrumentation-langchain` for LangGraph trace spans

## Human-in-the-Loop (HITL — PRD)

- Clinical recommendations → draft only; clinician approval required before actioning
- "Stop Button" escalation path: connect to human staff
- Red-flag triage (chest pain, emergency symptoms) → immediate 911/ER escalation warning
- Explicit patient consent required before AI triage/diagnosis

## Conventions

- Tools return structured JSON via `_tool_result()` helper (`app/llm/tools/_utils.py`); LLM formats into natural language
- One tool module per domain in `app/llm/tools/` — add tools there, not in `agent.py`
- Use `??` (nullish coalescing) over `||` for defaults — avoids falsy traps on `0` or `""`
- Avoid non-null assertion (`!`) unless value presence is certain
- `app/config.py` reads auth flags at call time (not module import time) so tests can monkeypatch env
- Alembic migrations live alongside models; run before starting the service
