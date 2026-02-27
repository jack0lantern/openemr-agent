"""
OpenEMR AI Agent microservice - Patient and Staff APIs per PRD.
"""

from dotenv import load_dotenv

load_dotenv()  # Load .env into os.environ so LangSmith/LangChain see LANGSMITH_* vars

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.oauth import router as oauth_router
from app.api.patient import router as patient_router
from app.api.staff import router as staff_router
from app.db import init_db
from app.langsmith_client import flush_langsmith
from app.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    flush_langsmith()


app = FastAPI(
    title="OpenEMR AI Agent",
    description="Generative AI Agent for patient and staff support per PRD",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oauth_router)
app.include_router(patient_router)
app.include_router(staff_router)
app.include_router(conversations_router)

# Setup OpenTelemetry (PRD §6.2 - Datadog/CloudWatch compatible)
setup_telemetry(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    return {
        "service": "OpenEMR AI Agent",
        "endpoints": {
            "patient": "POST /api/chat/patient (Bearer token required)",
            "staff": "POST /api/chat/staff (Bearer token required)",
            "oauth": "GET /oauth/callback, /oauth/launch, /oauth/logout",
        },
    }
