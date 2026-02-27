# OpenEMR AI Agent Microservice

FastAPI microservice providing patient and staff chat APIs per the [PRD](../PRD.md).

## APIs

| Endpoint | Audience | Use Cases |
|----------|----------|-----------|
| `POST /api/chat/patient` | Patients | Appointment info, clinic info, booking/modify/cancel, non-diagnostic medical info |
| `POST /api/chat/staff` | Staff | Scheduling, insurance verification, medication drafts, bloodwork review, administrative tools |

Both endpoints require `Authorization: Bearer <oauth_token>`.

## Request/Response

```json
// Request
{
  "messages": [
    { "role": "user", "content": "When is my next appointment?" }
  ]
}

// Response
{
  "message": "Your next appointment is..."
}
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Docker

```bash
docker build -t openemr-agent .
docker run -p 8000:8000 openemr-agent
```

## Project Structure

```
app/
├── api/                     # FastAPI route handlers (patient.py, staff.py)
├── data/                    # Mock data for dev/demo
├── llm/
│   ├── agent.py             # LangGraph graphs, system prompts, invoke_*_agent
│   └── tools/               # LangChain @tool definitions, one module per domain
│       ├── __init__.py      # Re-exports all tools
│       ├── _utils.py        # Shared JSON serialization helper
│       ├── datetime_tools.py        # get_current_datetime
│       ├── scheduling_tools.py      # availability, booking, appointments
│       ├── clinic_tools.py          # clinic info, providers, locations
│       ├── medical_info_tools.py    # educational symptom search
│       ├── clinical_tools.py        # patient records (staff only)
│       └── insurance_tools.py       # coverage verification (staff only)
├── schemas.py               # Pydantic request/response models
└── services/                # Data access layer (mock or FHIR)
```

To add a new tool: implement it in the appropriate `tools/` module, re-export it from `tools/__init__.py`, then add it to the tool list in `agent.py`.

## Testing

```bash
pip install -r requirements-dev.txt

# Unit tests only (no API key needed)
pytest tests/test_tools.py tests/test_api.py -v

# Core golden path (13 critical integration tests; requires ANTHROPIC_API_KEY)
pytest tests/test_agent_golden_path.py -v --timeout=60

# Only eval tests
pytest tests/test_agent_eval.py -v --timeout=60

# Full suite including extended eval tests
pytest tests/ -v --timeout=60

# Safety tests only
pytest tests/test_safety.py -v --timeout=60
```
