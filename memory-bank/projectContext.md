# openemr-agent — Project Context

> Memory bank file for persistent AI context. Update as the service evolves.

## Overview

**openemr-agent** is a Python/FastAPI microservice providing Patient and Staff chat APIs for the OpenEMR AI Assistant. It uses LangGraph + LangChain with Claude (Anthropic) and connects to OpenEMR's FHIR R4 API for live healthcare data.

- **Part of:** `openemr-system/` monorepo (alongside `openemr/` PHP EHR and `openemr-ui/` Next.js chat UI)
- **Runs at:** `http://localhost:8000` (local) / Docker service `ai-agent`

## Directory Structure

```
openemr-agent/
├── main.py                        # FastAPI app, CORS, lifespan, routers, telemetry
├── app/
│   ├── api/
│   │   ├── patient.py             # POST /api/chat/patient
│   │   └── staff.py               # POST /api/chat/staff
│   ├── config.py                  # Auth flags from env (PATIENT_AUTH_REQUIRED, etc.)
│   ├── data/
│   │   └── mock_data.py           # Mock providers, patients, appointments (dev/demo)
│   ├── db/
│   │   ├── models.py              # SQLAlchemy ORM: Conversation, ConversationMessage
│   │   ├── crud.py                # DB read/write helpers
│   │   └── session.py             # Async engine + session factory
│   ├── llm/
│   │   ├── agent.py               # LangGraph graphs, prompts, invoke_patient_agent / invoke_staff_agent
│   │   ├── cost.py                # Token cost computation
│   │   ├── retry.py               # LLM retry logic
│   │   └── tools/
│   │       ├── __init__.py        # Re-exports all tools
│   │       ├── _utils.py          # _tool_result() JSON helper
│   │       ├── datetime_tools.py  # get_current_datetime
│   │       ├── scheduling_tools.py # get_appointment_availability, get_patient_appointments, list_upcoming_appointments, book_appointment, list_appointment_types
│   │       ├── clinic_tools.py    # get_clinic_info, list_providers, get_my_appointment_locations, get_staff_assigned_clinic
│   │       ├── medical_info_tools.py # search_medical_info
│   │       ├── clinical_tools.py  # lookup_patient_{summary,allergies,medications,vitals,encounters,immunizations,procedures,lab_reports,care_plans,care_team}
│   │       └── insurance_tools.py # verify_insurance
│   ├── schemas.py                 # ChatMessage, ChatRequest, ChatResponse, ToolCallDebug, Citation, ResponseMetadata
│   ├── services/
│   │   ├── data_service.py        # Dispatches to mock or FHIR based on USE_MOCK_DATA
│   │   └── fhir_client.py         # FHIRClient: OAuth2 JWT, token caching, async FHIR R4
│   ├── langsmith_client.py        # Flush LangSmith traces on shutdown
│   └── telemetry.py               # OpenTelemetry setup (OTLP/Datadog-compatible)
├── tests/
│   ├── conftest.py                # Pytest fixtures, monkeypatching
│   ├── fixtures/
│   │   ├── mock_data.py           # Test-specific mock data (distinct IDs, TEST_TODAY)
│   │   └── fhir_bundles.py        # FHIR bundle fixtures
│   ├── test_tools.py              # Unit tests for @tool functions (no LLM)
│   ├── test_agent_golden_path.py  # Integration tests with natural language
│   ├── test_agent_eval.py         # Extended eval tests
│   ├── test_api.py                # API endpoint tests
│   ├── test_data_service.py       # Data service unit tests
│   ├── test_fhir_client.py        # FHIR client tests
│   └── test_safety.py             # Safety rail tests
├── scripts/
│   └── seed_fhir_data.sql         # SQL for seeding FHIR-compatible test data
├── requirements.txt               # Runtime deps
├── requirements-dev.txt           # Dev/test deps
├── Dockerfile
└── railpack.json
```

## Tool Inventory

**Patient tools (9):**
`get_current_datetime`, `get_clinic_info`, `get_appointment_availability`, `get_my_appointment_locations`, `list_providers`, `list_appointment_types`, `get_patient_appointments`, `book_appointment`, `search_medical_info`

**Staff tools (22):**
All patient tools (replacing `get_my_appointment_locations` → `get_staff_assigned_clinic`) plus:
`lookup_patient_summary`, `lookup_patient_allergies`, `lookup_patient_medications`, `lookup_patient_vitals`, `lookup_patient_encounters`, `lookup_patient_immunizations`, `lookup_patient_procedures`, `lookup_patient_lab_reports`, `lookup_patient_care_plans`, `lookup_patient_care_team`, `verify_insurance`

## Key Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | LLM API key | required |
| `USE_MOCK_DATA` | `true` = mock data, `false` = FHIR | `false` |
| `PATIENT_AUTH_REQUIRED` | Enforce OAuth on patient endpoint | `false` |
| `STAFF_AUTH_REQUIRED` | Enforce OAuth on staff endpoint | `false` |
| `DATABASE_URL` | PostgreSQL (asyncpg) for conversation persistence | postgresql+asyncpg://... |
| `OPENEMR_FHIR_URL` | FHIR R4 base URL | http://localhost:8300/apis/default/fhir |
| `OPENEMR_TOKEN_URL` | OAuth2 token endpoint | http://localhost:8300/oauth2/default/token |
| `OPENEMR_CLIENT_ID` | OAuth2 client ID | — |
| `OPENEMR_CLIENT_SECRET` | OAuth2 client secret | — |
| `PRIVATE_KEY_PATH` | RSA private key for JWT signing | ./certs/private_key.pem |
| `LANGSMITH_TRACING` | Enable LangSmith trace logging | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry OTLP endpoint | — |
| `DEBUG_TOOL_CALLS` | Include tool call debug info in responses | `false` |

## Local Development

```bash
cd openemr-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Or run the full stack:

```bash
# from openemr-system/
docker compose up -d
```

## Testing

```bash
# Unit + integration tests (no LLM)
pytest tests/ -v --timeout=60 -k "not golden_path and not eval"

# All tests including LLM golden path (needs ANTHROPIC_API_KEY)
pytest tests/ -v --timeout=60
```

**Important:** Tests use `tests/fixtures/mock_data.py`, not `app/data/mock_data.py`. Monkeypatch tools at the module level (e.g. `app.llm.tools.scheduling_tools`) for tool unit tests, and at `app.llm.agent` level for agent integration tests.

## Adding a New Tool

1. Add `@tool` function to the appropriate module in `app/llm/tools/`
2. Re-export it from `app/llm/tools/__init__.py`
3. Add it to the relevant tool list in `app/llm/agent.py`
4. Implement backend logic in `app/services/data_service.py` (and `fhir_client.py` for FHIR)

## Related Skills (Cursor)

- `openemr-agent-navigation` — Full directory reference, common navigation patterns
- `openemr-agent-mock-fhir-tools` — Adding tools with mock + FHIR support
- `openemr-project` — Top-level system context
- `openemr-testing` — Test commands for all services
- `openemr-commits` — Conventional Commits format
