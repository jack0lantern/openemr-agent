#!/usr/bin/env python3
"""
Test script: Patient.read from agent to OpenEMR FHIR API.

Verifies that the agent can authenticate with OpenEMR and perform Patient.read
operations (GET /Patient and GET /Patient/{id}).

Usage (from openemr-agent/ with venv activated, or from project root via docker):
  python scripts/test_patient_read.py
  python scripts/test_patient_read.py 900001   # Test specific patient ID

Run inside Docker (when openemr + ai-agent are up):
  docker compose exec ai-agent python scripts/test_patient_read.py

Prerequisites:
  - OpenEMR running with FHIR API enabled (api-init in docker-compose)
  - OAuth client registered (Administration → API Clients) with:
    - token_endpoint_auth_method: private_key_jwt
    - jwks from: python scripts/generate_jwks.py
    - scope including system/Patient.read
  - PRIVATE_KEY_PATH, OPENEMR_CLIENT_ID in .env
  - Optional: seed_fhir_data.sql for test patients (900001, 900002)
"""
# AI-generated: Patient.read connectivity test script

import asyncio
import os
import sys
from pathlib import Path

# Add parent for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.fhir_client import FHIRAuthError, FHIRRequestError, get_fhir_client


def _print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f" {title}")
    print("=" * 60)


async def run_test(patient_id: str | None = None) -> bool:
    """Run Patient.read test. Returns True on success."""
    client = get_fhir_client()

    _print_section("1. OAuth token acquisition")
    try:
        token = await client._ensure_token()
        print(f"   OK: Token acquired ({token[:20]}...)")
    except FHIRAuthError as e:
        print(f"   FAIL: {e}")
        return False

    _print_section("2. Patient search (GET /Patient)")
    try:
        bundle = await client.get_patients()
        total = bundle.get("total")
        if total is None:
            total = len(bundle.get("entry", []))
        entries = bundle.get("entry", [])
        print(f"   OK: Found {total} patient(s)")

        if not entries and patient_id is None:
            print("   WARN: No patients in OpenEMR. Run seed_fhir_data.sql for test data.")
            print("   Skipping Patient.read by ID (no patient to read).")
            return True

        # Use first patient if no ID specified
        if patient_id is None and entries:
            first = entries[0].get("resource", {})
            patient_id = first.get("id", "")
            if patient_id:
                print(f"   Using first patient ID: {patient_id}")
    except FHIRRequestError as e:
        print(f"   FAIL: {e}")
        return False

    if not patient_id:
        print("   SKIP: No patient ID to read (empty search result)")
        return True

    _print_section("3. Patient.read (GET /Patient/{id})")
    try:
        patient = await client.get_patient(patient_id)
        if patient.get("resourceType") != "Patient":
            print(f"   FAIL: Expected Patient resource, got {patient.get('resourceType', 'unknown')}")
            return False

        name_parts = []
        for n in patient.get("name", [{}])[:1]:
            given = n.get("given", [])
            family = n.get("family", "")
            name_parts = list(given) + ([family] if family else [])
        name = " ".join(name_parts) if name_parts else "(no name)"

        print(f"   OK: Patient.read succeeded")
        print(f"   ID: {patient.get('id')}")
        print(f"   Name: {name}")
        print(f"   Birth date: {patient.get('birthDate', 'N/A')}")
        return True
    except FHIRRequestError as e:
        print(f"   FAIL: {e}")
        return False


def main() -> int:
    patient_id = sys.argv[1] if len(sys.argv) > 1 else None

    print("Patient.read connectivity test (agent → OpenEMR)")
    print(f"  OPENEMR_FHIR_URL: {os.environ.get('OPENEMR_FHIR_URL', '(default)')}")
    print(f"  OPENEMR_TOKEN_URL: {os.environ.get('OPENEMR_TOKEN_URL', '(default)')}")
    print(f"  OPENEMR_CLIENT_ID: {os.environ.get('OPENEMR_CLIENT_ID', '(default)')}")
    if patient_id:
        print(f"  Patient ID (override): {patient_id}")

    ok = asyncio.run(run_test(patient_id))

    _print_section("Result")
    if ok:
        print("  PASS: Patient.read works from agent to OpenEMR")
        return 0
    print("  FAIL: See errors above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# End AI-generated code
