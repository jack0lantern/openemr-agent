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

## Testing

```bash
pip install -r requirements-dev.txt

# Unit tests only (no API key needed)
pytest tests/test_tools.py tests/test_api.py -v

# Core golden path (13 critical integration tests; requires ANTHROPIC_API_KEY)
pytest tests/test_agent_golden_path.py -v --timeout=60

# Full suite including extended eval tests
pytest tests/ -v --timeout=60

# Safety tests only
pytest tests/test_safety.py -v --timeout=60
```
