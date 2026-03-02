"""
OpenEMR AI Agent microservice - Patient and Staff APIs per PRD.
"""

import json
import logging
import os
from pathlib import Path

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

logger = logging.getLogger(__name__)

AGENT_REGISTRATION_FILE = Path(__file__).parent / ".agent-registration"


def _try_load_client_id_from_registration() -> str | None:
    """Load client_id from .agent-registration if it exists."""
    if AGENT_REGISTRATION_FILE.exists():
        logger.info("Auto-registration: .agent-registration exists, loading client_id")
        try:
            data = json.loads(AGENT_REGISTRATION_FILE.read_text())
            client_id = data.get("client_id")
            if client_id:
                logger.info("Auto-registration: loaded client_id from .agent-registration")
            return client_id
        except Exception as e:
            logger.warning("Could not read .agent-registration: %s", e)
    else:
        logger.info("Auto-registration: .agent-registration not found")
    return None


async def _run_auto_registration() -> bool:
    """Run key generation + registration, persist client_id. Returns True on success."""
    from app.config import openemr_registration_url
    from app.services.key_manager import ensure_keys, private_key_to_jwks
    from app.services.oauth_registration import (
        _default_redirect_uri,
        get_all_supported_scopes,
        register_agent,
    )

    logger.info("Auto-registration: starting (OPENEMR_CLIENT_ID empty, OPENEMR_AUTO_REGISTER=true)")

    key_path_str = os.getenv("PRIVATE_KEY_PATH", "./certs/private_key.pem")
    key_path = Path(key_path_str).resolve()
    key_dir = key_path.parent
    logger.info("Auto-registration: key path=%s, key_dir=%s", key_path, key_dir)

    try:
        ensure_keys(key_dir, key_path)
        logger.info("Auto-registration: keys ready at %s", key_path)
    except Exception as e:
        logger.error("Auto-registration: key generation failed: %s", e)
        return False

    logger.info("Auto-registration: deriving JWKS from private key")
    jwks = private_key_to_jwks(key_path)

    logger.info("Auto-registration: fetching scopes from OIDC discovery")
    scope = await get_all_supported_scopes()
    logger.info("Auto-registration: got %d scopes", len(scope.split()))

    registration_url = openemr_registration_url()
    redirect_uri = _default_redirect_uri()
    logger.info("Auto-registration: POSTing to %s (redirect_uri=%s)", registration_url, redirect_uri)

    try:
        result = register_agent(registration_url, jwks, redirect_uri, scope)
    except Exception as e:
        logger.error("Auto-registration: registration failed: %s", e)
        return False

    client_id = result.get("client_id")
    if not client_id:
        logger.error("Auto-registration: registration response missing client_id")
        return False

    reg_uri = result.get("registration_client_uri", "")
    logger.info("Auto-registration: registered successfully, client_id=%s", client_id)

    try:
        AGENT_REGISTRATION_FILE.write_text(
            json.dumps({"client_id": client_id, "registration_client_uri": reg_uri}, indent=2)
        )
        logger.info("Auto-registration: persisted to %s", AGENT_REGISTRATION_FILE)
    except Exception as e:
        logger.warning("Auto-registration: could not persist .agent-registration: %s", e)

    os.environ["OPENEMR_CLIENT_ID"] = client_id
    logger.info(
        "Auto-registration: complete. client_id=%s. "
        "Enable the client in Administration → System → API Clients.",
        client_id,
    )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve OPENEMR_CLIENT_ID: env > .agent-registration > auto-register if enabled
    client_id = os.getenv("OPENEMR_CLIENT_ID", "")
    if client_id:
        logger.info("Skipping auto-registration: OPENEMR_CLIENT_ID already set (from env)")
    else:
        client_id = _try_load_client_id_from_registration()
        if client_id:
            os.environ["OPENEMR_CLIENT_ID"] = client_id
            logger.info("Skipping auto-registration: client_id loaded from .agent-registration")
        elif os.getenv("OPENEMR_AUTO_REGISTER", "").lower() in ("true", "1", "yes"):
            await _run_auto_registration()
        else:
            logger.info(
                "Skipping auto-registration: OPENEMR_AUTO_REGISTER not enabled "
                "(set OPENEMR_AUTO_REGISTER=true to auto-register when OPENEMR_CLIENT_ID is unset)"
            )

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
