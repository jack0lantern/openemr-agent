"""
OpenEMR AI Agent microservice - Patient and Staff APIs per PRD.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.patient import router as patient_router
from app.api.staff import router as staff_router

app = FastAPI(
    title="OpenEMR AI Agent",
    description="Generative AI Agent for patient and staff support per PRD",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patient_router)
app.include_router(staff_router)


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
        },
    }
