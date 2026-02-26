# AI-generated: Data access layer - mock vs FHIR dispatch with transformers
# Returns identical dict shapes for agent tools regardless of data source

import asyncio
import os  # AI-generated
from datetime import date, datetime

from app.data.mock_data import (
    MOCK_APPOINTMENTS,
    MOCK_AVAILABLE_SLOTS,
    MOCK_FACILITIES,
    MOCK_INSURANCE_PLANS,
    MOCK_MEDICAL_CONDITIONS,
    MOCK_PATIENTS,
    MOCK_PROVIDERS,
    MOCK_STAFF,
)
from app.services.fhir_client import FHIRRequestError, get_fhir_client


# --- FHIR-to-mock shape transformers ---


def _fhir_practitioner_to_provider(resource: dict) -> dict:
    """Transform FHIR Practitioner resource to provider dict matching mock shape."""
    name = resource.get("name", [{}])[0] if resource.get("name") else {}
    prefix = name.get("prefix", [""])
    given = name.get("given", [""])
    family = name.get("family", "")
    full_name = " ".join(
        p for p in [prefix[0] if prefix else "", given[0] if given else "", family] if p
    ).strip() or "Unknown"

    npi = ""
    for ident in resource.get("identifier", []) or []:
        if ident.get("system", "").endswith("npi") or "npi" in ident.get("system", "").lower():
            npi = ident.get("value", "")
            break

    specialty = ""
    for qual in resource.get("qualification", []) or []:
        if qual.get("code", {}).get("text"):
            specialty = qual["code"]["text"]
            break

    telecom = resource.get("telecom", []) or []
    phone = ""
    email = ""
    for t in telecom:
        sys = t.get("system", "")
        val = t.get("value", "")
        if sys == "phone":
            phone = val
        elif sys == "email":
            email = val

    return {
        "id": resource.get("id", ""),
        "name": full_name,
        "specialty": specialty or "General Practice",
        "npi": npi,
        "credentials": "",
        "phone": phone,
        "email": email,
        "schedule": {},
    }


def _fhir_slot_to_available_slot(slot: dict, schedule_ref: str = "") -> dict:
    """Transform FHIR Slot to mock slot shape. schedule_ref used to resolve provider."""
    start = slot.get("start", "")
    dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
    date_str = dt.strftime("%Y-%m-%d") if dt else ""
    time_str = (dt.strftime("%I:%M %p").lstrip("0") if dt else "")  # 9:00 AM (portable)

    return {
        "id": slot.get("id", ""),
        "date": date_str,
        "time": time_str,
        "providerId": "",
        "providerName": "",
        "duration": 30,
        "location": "",
        "type": "checkup",
    }


def _fhir_appointment_to_appointment(resource: dict) -> dict:
    """Transform FHIR Appointment to mock appointment shape."""
    start = resource.get("start", "")
    dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
    date_str = dt.strftime("%Y-%m-%d") if dt else ""
    time_str = (dt.strftime("%I:%M %p").lstrip("0") if dt else "")

    participant = resource.get("participant", []) or []
    patient_ref = ""
    actor_ref = ""
    for p in participant:
        ref = p.get("actor", {}).get("reference", "")
        if "Patient/" in ref:
            patient_ref = ref
        elif "Practitioner/" in ref:
            actor_ref = ref

    return {
        "id": resource.get("id", ""),
        "patientName": "",
        "patientId": patient_ref.replace("Patient/", ""),
        "providerId": actor_ref.replace("Practitioner/", ""),
        "providerName": "",
        "date": date_str,
        "time": time_str,
        "duration": resource.get("minutesDuration", 30),
        "type": resource.get("appointmentType", {}).get("text", "visit") or "visit",
        "status": resource.get("status", "booked"),
        "location": "",
        "notes": "",
    }


def _fhir_patient_to_patient(resource: dict) -> dict:
    """Transform FHIR Patient to mock patient shape."""
    name = resource.get("name", [{}])[0] if resource.get("name") else {}
    given = name.get("given", [])
    family = name.get("family", "")
    full_name = " ".join(given + [family]).strip() if given or family else "Unknown"

    telecom = resource.get("telecom", []) or []
    phone = ""
    email = ""
    for t in telecom:
        if t.get("system") == "phone":
            phone = t.get("value", "")
        elif t.get("system") == "email":
            email = t.get("value", "")

    addr = resource.get("address", [{}])[0] if resource.get("address") else {}
    line = addr.get("line", [])
    city = addr.get("city", "")
    state = addr.get("state", "")
    addr_str = ", ".join(p for p in [", ".join(line), city, state] if p)

    return {
        "id": resource.get("id", ""),
        "name": full_name,
        "dateOfBirth": resource.get("birthDate", ""),
        "phone": phone,
        "email": email,
        "address": addr_str,
        "insurancePlanId": None,
        "primaryCareProviderId": None,
        "emergencyContact": "",
        "emergencyContactPhone": "",
    }


def _fhir_coverage_to_insurance(resource: dict) -> dict:
    """Transform FHIR Coverage to mock insurance plan shape."""
    payor = resource.get("payor", [{}])[0] if resource.get("payor") else {}
    return {
        "id": resource.get("id", ""),
        "payerName": payor.get("display", "Unknown"),
        "planName": resource.get("type", {}).get("text", ""),
        "planType": "PPO",
        "groupNumber": "",
        "memberId": "",
        "effectiveDate": "",
        "terminationDate": None,
        "status": "active",
        "copay": {},
    }


def _fhir_condition_to_condition(resource: dict) -> dict:
    """Transform FHIR Condition to mock condition shape (for search_medical_info)."""
    code = resource.get("code", {})
    return {
        "id": resource.get("id", ""),
        "name": code.get("text", code.get("coding", [{}])[0].get("display", "Condition")),
        "description": "",
        "common_symptoms": [],
    }


def _fhir_encounter_to_encounter(resource: dict) -> dict:
    """Transform FHIR Encounter to encounter dict."""
    period = resource.get("period", {})
    start = period.get("start", "")
    dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None

    participant = resource.get("participant", []) or []
    practitioner_ref = ""
    for p in participant:
        ref = p.get("individual", {}).get("reference", "")
        if "Practitioner/" in ref:
            practitioner_ref = ref
            break

    reason_codes = resource.get("reasonCode", []) or []
    reason = reason_codes[0].get("text", "") if reason_codes else ""

    return {
        "id": resource.get("id", ""),
        "status": resource.get("status", ""),
        "class": resource.get("class", {}).get("code", ""),
        "type": (resource.get("type", [{}])[0].get("text", "") if resource.get("type") else ""),
        "date": dt.strftime("%Y-%m-%d") if dt else "",
        "practitionerId": practitioner_ref.replace("Practitioner/", ""),
        "reason": reason,
    }


def _fhir_allergy_to_allergy(resource: dict) -> dict:
    """Transform FHIR AllergyIntolerance to allergy dict."""
    code = resource.get("code", {})
    coding = code.get("coding", [{}])[0] if code.get("coding") else {}
    reactions = resource.get("reaction", []) or []
    manifestations = []
    for r in reactions:
        for m in r.get("manifestation", []) or []:
            manifestations.append(m.get("text", m.get("coding", [{}])[0].get("display", "")))

    return {
        "id": resource.get("id", ""),
        "substance": coding.get("display", code.get("text", "Unknown")),
        "clinicalStatus": resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", ""),
        "criticality": resource.get("criticality", ""),
        "type": resource.get("type", ""),
        "reactions": manifestations,
    }


def _fhir_procedure_to_procedure(resource: dict) -> dict:
    """Transform FHIR Procedure to procedure dict."""
    code = resource.get("code", {})
    coding = code.get("coding", [{}])[0] if code.get("coding") else {}
    performed = resource.get("performedDateTime", resource.get("performedPeriod", {}).get("start", ""))

    return {
        "id": resource.get("id", ""),
        "name": coding.get("display", code.get("text", "Unknown")),
        "status": resource.get("status", ""),
        "date": performed[:10] if performed else "",
    }


def _fhir_observation_to_observation(resource: dict) -> dict:
    """Transform FHIR Observation to observation dict."""
    code = resource.get("code", {})
    coding = code.get("coding", [{}])[0] if code.get("coding") else {}

    value = ""
    unit = ""
    if "valueQuantity" in resource:
        vq = resource["valueQuantity"]
        value = str(vq.get("value", ""))
        unit = vq.get("unit", vq.get("code", ""))
    elif "valueCodeableConcept" in resource:
        vc = resource["valueCodeableConcept"]
        value = vc.get("text", vc.get("coding", [{}])[0].get("display", ""))
    elif "valueString" in resource:
        value = resource["valueString"]

    effective = resource.get("effectiveDateTime", "")

    category_list = resource.get("category", []) or []
    category = category_list[0].get("coding", [{}])[0].get("code", "") if category_list else ""

    return {
        "id": resource.get("id", ""),
        "name": coding.get("display", code.get("text", "Unknown")),
        "value": value,
        "unit": unit,
        "date": effective[:10] if effective else "",
        "category": category,
        "status": resource.get("status", ""),
    }


def _fhir_immunization_to_immunization(resource: dict) -> dict:
    """Transform FHIR Immunization to immunization dict."""
    vaccine = resource.get("vaccineCode", {})
    coding = vaccine.get("coding", [{}])[0] if vaccine.get("coding") else {}
    occurrence = resource.get("occurrenceDateTime", "")

    return {
        "id": resource.get("id", ""),
        "vaccine": coding.get("display", vaccine.get("text", "Unknown")),
        "date": occurrence[:10] if occurrence else "",
        "status": resource.get("status", ""),
    }


def _fhir_medication_request_to_medication(resource: dict) -> dict:
    """Transform FHIR MedicationRequest to medication dict."""
    med = resource.get("medicationCodeableConcept", {})
    coding = med.get("coding", [{}])[0] if med.get("coding") else {}

    dosage = resource.get("dosageInstruction", [{}])
    dosage_text = dosage[0].get("text", "") if dosage else ""

    return {
        "id": resource.get("id", ""),
        "medication": coding.get("display", med.get("text", "Unknown")),
        "status": resource.get("status", ""),
        "dosage": dosage_text,
        "authoredOn": resource.get("authoredOn", "")[:10] if resource.get("authoredOn") else "",
    }


def _fhir_diagnostic_report_to_report(resource: dict) -> dict:
    """Transform FHIR DiagnosticReport to report dict."""
    code = resource.get("code", {})
    coding = code.get("coding", [{}])[0] if code.get("coding") else {}
    effective = resource.get("effectiveDateTime", "")

    return {
        "id": resource.get("id", ""),
        "name": coding.get("display", code.get("text", "Unknown")),
        "status": resource.get("status", ""),
        "date": effective[:10] if effective else "",
        "conclusion": resource.get("conclusion", ""),
    }


def _fhir_care_plan_to_care_plan(resource: dict) -> dict:
    """Transform FHIR CarePlan to care plan dict."""
    categories = resource.get("category", []) or []
    category = categories[0].get("text", "") if categories else ""

    return {
        "id": resource.get("id", ""),
        "status": resource.get("status", ""),
        "intent": resource.get("intent", ""),
        "title": resource.get("title", ""),
        "category": category,
        "description": resource.get("description", ""),
    }


def _fhir_care_team_to_care_team(resource: dict) -> dict:
    """Transform FHIR CareTeam to care team dict."""
    participants = []
    for p in resource.get("participant", []) or []:
        member = p.get("member", {})
        role = p.get("role", [{}])[0].get("text", "") if p.get("role") else ""
        participants.append({
            "name": member.get("display", ""),
            "role": role,
            "reference": member.get("reference", ""),
        })

    return {
        "id": resource.get("id", ""),
        "name": resource.get("name", ""),
        "status": resource.get("status", ""),
        "participants": participants,
    }


def _fhir_organization_to_clinic(resource: dict) -> dict:
    """Transform FHIR Organization to clinic dict shape. Hours/parking not in FHIR; left empty."""
    addr = resource.get("address", [{}])[0] if resource.get("address") else {}
    line = addr.get("line", [])
    city = addr.get("city", "")
    state = addr.get("state", "")
    postal = addr.get("postalCode", "")
    addr_parts = [", ".join(line) if line else "", city, state, postal]
    address = ", ".join(p for p in addr_parts if p).strip()

    phone = ""
    for t in resource.get("telecom", []) or []:
        if t.get("system") == "phone":
            phone = t.get("value", "")
            break

    return {
        "address": address or "",
        "hours": "",  # FHIR Organization does not include hours
        "parking": "",  # FHIR Organization does not include parking
        "phone": phone or "",
    }


# --- Data access functions (sync, dispatch mock vs FHIR) ---


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def get_providers(specialty: str = "") -> list[dict]:
    """Get providers, optionally filtered by specialty."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        providers = MOCK_PROVIDERS
        if specialty:
            providers = [
                p for p in providers if specialty.lower() in p.get("specialty", "").lower()
            ]
        return providers

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_practitioners(specialty=specialty if specialty else None)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_practitioner_to_provider(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Practitioner"
        ]

    return _run_async(_fetch())


def get_available_dates() -> list[str]:
    """Get list of dates that have available slots (for fallback message)."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return sorted({s["date"] for s in MOCK_AVAILABLE_SLOTS})
    return []


def get_available_slots(date_str: str) -> list[dict]:
    """Get available appointment slots for a date. date_str in YYYY-MM-DD."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return [s for s in MOCK_AVAILABLE_SLOTS if s["date"] == date_str]

    async def _fetch():
        try:
            client = get_fhir_client()
            start_ge = f"{date_str}T00:00:00"
            bundle = await client.get_slots(start_ge=start_ge, status="free")
            entries = bundle.get("entry", []) or []
            return [
                _fhir_slot_to_available_slot(e.get("resource", {}))
                for e in entries
                if e.get("resource", {}).get("resourceType") == "Slot"
            ]
        except FHIRRequestError:
            # OpenEMR does not implement FHIR Slot; return empty rather than failing. AI-generated.
            return []

    return _run_async(_fetch())


def get_patient_appointments(patient_id: str) -> list[dict]:
    """Get appointments for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return [a for a in MOCK_APPOINTMENTS if a["patientId"] == patient_id]

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_appointments(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_appointment_to_appointment(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Appointment"
        ]

    return _run_async(_fetch())


def _today() -> date:
    """Injected for tests; override to control date-sensitive logic."""
    return date.today()


def _time_sort_key(time_str: str) -> tuple[int, int]:
    """Convert '9:00 AM' to (hour, minute) for correct chronological sorting."""
    try:
        from datetime import datetime as dt

        parsed = dt.strptime(time_str.strip(), "%I:%M %p")
        return (parsed.hour, parsed.minute)
    except (ValueError, TypeError):
        return (0, 0)


def get_upcoming_appointments(today: str | None = None) -> list[dict]:
    """Get upcoming appointments (date >= today, not cancelled/completed)."""
    today_str = today or _today().isoformat()
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        apts = [
            a
            for a in MOCK_APPOINTMENTS
            if a["date"] >= today_str and a["status"] not in ("cancelled", "completed")
        ]
        apts.sort(key=lambda a: (a["date"], _time_sort_key(a.get("time", ""))))
        return apts

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_appointments(date_ge=today_str, status="booked")
        entries = bundle.get("entry", []) or []
        apts = [
            _fhir_appointment_to_appointment(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Appointment"
        ]
        apts.sort(key=lambda a: (a["date"], _time_sort_key(a.get("time", ""))))
        return apts

    return _run_async(_fetch())


def book_appointment(patient_id: str, slot_id: str) -> dict:
    """
    Book an appointment. Returns {success, appointment?, error?, suggestion?}.
    Mock: returns confirmation. FHIR: POSTs Appointment.
    """
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        slot = next((s for s in MOCK_AVAILABLE_SLOTS if s["id"] == slot_id), None)
        if not slot:
            return {
                "success": False,
                "error": f"Slot {slot_id} not found",
                "suggestion": "Use get_appointment_availability to see available slots",
            }
        patient = next((p for p in MOCK_PATIENTS if p["id"] == patient_id), None)
        if not patient:
            return {"success": False, "error": f"Patient {patient_id} not found"}
        return {
            "success": True,
            "appointment": {
                "patientName": patient["name"],
                "date": slot["date"],
                "time": slot["time"],
                "providerName": slot["providerName"],
                "type": slot["type"],
                "duration": slot["duration"],
                "location": slot["location"],
            },
            "confirmation_note": "Confirmation will be sent via email",
        }

    async def _book():
        client = get_fhir_client()
        try:
            # Build minimal FHIR Appointment
            appointment = {
                "resourceType": "Appointment",
                "status": "booked",
                "participant": [
                    {"actor": {"reference": f"Patient/{patient_id}"}, "required": "required"},
                    {"actor": {"reference": f"Slot/{slot_id}"}, "required": "required"},
                ],
            }
            created = await client.create_appointment(appointment)
            start = created.get("start", "")
            dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
            return {
                "success": True,
                "appointment": {
                    "patientName": "",
                    "date": dt.strftime("%Y-%m-%d") if dt else "",
                    "time": (dt.strftime("%I:%M %p").lstrip("0") if dt else ""),
                    "providerName": "",
                    "type": "visit",
                    "duration": created.get("minutesDuration", 30),
                    "location": "",
                },
                "confirmation_note": "Appointment booked successfully.",
            }
        except FHIRRequestError as e:
            return {"success": False, "error": str(e)}

    return _run_async(_book())


def get_patient_summary(patient_id: str) -> dict:
    """Get patient summary with insurance and recent appointments."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        patient = next((p for p in MOCK_PATIENTS if p["id"] == patient_id), None)
        if not patient:
            return {"error": f"Patient {patient_id} not found"}
        ins = next(
            (i for i in MOCK_INSURANCE_PLANS if i["id"] == patient.get("insurancePlanId")),
            None,
        )
        prov = next(
            (p for p in MOCK_PROVIDERS if p["id"] == patient.get("primaryCareProviderId")),
            None,
        )
        apts = [a for a in MOCK_APPOINTMENTS if a["patientId"] == patient_id]
        return {
            "patient": {
                "id": patient["id"],
                "name": patient["name"],
                "dateOfBirth": patient["dateOfBirth"],
                "phone": patient["phone"],
                "email": patient["email"],
                "address": patient["address"],
                "emergencyContact": patient.get("emergencyContact"),
                "emergencyContactPhone": patient.get("emergencyContactPhone"),
            },
            "insurance": {
                "payerName": ins["payerName"],
                "planName": ins["planName"],
                "memberId": ins["memberId"],
            } if ins else None,
            "primaryCareProvider": prov["name"] if prov else None,
            "recentAppointments": [
                {"date": a["date"], "time": a["time"], "status": a["status"]}
                for a in apts[:5]
            ],
        }

    async def _fetch():
        client = get_fhir_client()
        try:
            patient_res = await client.get_patient(patient_id)
            patient = _fhir_patient_to_patient(patient_res)
            cov_bundle = await client.get_coverages()
            cov_entries = cov_bundle.get("entry", []) or []
            ins = None
            for e in cov_entries:
                r = e.get("resource", {})
                if r.get("resourceType") == "Coverage" and r.get("beneficiary", {}).get("reference") == f"Patient/{patient_id}":
                    ins = _fhir_coverage_to_insurance(r)
                    break
            apts = await client.get_appointments(patient_id=patient_id)
            apt_entries = apts.get("entry", []) or []
            recent = []
            for e in apt_entries[:5]:
                r = e.get("resource", {})
                if r.get("resourceType") == "Appointment":
                    a = _fhir_appointment_to_appointment(r)
                    recent.append({"date": a["date"], "time": a["time"], "status": a["status"]})
            return {
                "patient": {
                    "id": patient["id"],
                    "name": patient["name"],
                    "dateOfBirth": patient["dateOfBirth"],
                    "phone": patient["phone"],
                    "email": patient["email"],
                    "address": patient["address"],
                    "emergencyContact": patient.get("emergencyContact"),
                    "emergencyContactPhone": patient.get("emergencyContactPhone"),
                },
                "insurance": {
                    "payerName": ins["payerName"],
                    "planName": ins["planName"],
                    "memberId": ins.get("memberId", ""),
                } if ins else None,
                "primaryCareProvider": None,
                "recentAppointments": recent,
            }
        except FHIRRequestError as e:
            return {"error": str(e)}

    return _run_async(_fetch())


def verify_insurance(member_id: str) -> dict:
    """Verify insurance by member ID or patient ID."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        if member_id.startswith("pat-") or member_id.startswith("test-pat-"):
            patient = next((p for p in MOCK_PATIENTS if p["id"] == member_id), None)
            if not patient:
                return {"error": f"Patient {member_id} not found"}
            plan = next(
                (i for i in MOCK_INSURANCE_PLANS if i["id"] == patient.get("insurancePlanId")),
                None,
            )
            if not plan:
                return {"error": f"Patient {member_id} has no insurance on file"}
        else:
            plan = next((i for i in MOCK_INSURANCE_PLANS if i["memberId"] == member_id), None)
            if not plan:
                return {"error": f"No active insurance found for member ID {member_id}"}
        return {
            "memberId": plan["memberId"],
            "plan": {
                "payerName": plan["payerName"],
                "planName": plan["planName"],
                "planType": plan["planType"],
                "groupNumber": plan["groupNumber"],
                "status": plan["status"],
                "effectiveDate": plan["effectiveDate"],
            },
            "copay": plan.get("copay") or {},
        }

    async def _fetch():
        client = get_fhir_client()
        try:
            if member_id.startswith("pat-") or member_id.startswith("test-pat-"):
                pid = member_id.replace("test-", "") if member_id.startswith("test-pat-") else member_id
                patient_res = await client.get_patient(pid)
                if not patient_res.get("id"):
                    return {"error": f"Patient {member_id} not found"}
                cov_bundle = await client.get_coverages()
                entries = cov_bundle.get("entry", []) or []
                plan = None
                for e in entries:
                    r = e.get("resource", {})
                    if r.get("resourceType") == "Coverage" and r.get("beneficiary", {}).get("reference") == f"Patient/{pid}":
                        plan = _fhir_coverage_to_insurance(r)
                        break
                if not plan:
                    return {"error": f"Patient {member_id} has no insurance on file"}
            else:
                cov_bundle = await client.get_coverages(identifier=member_id)
                entries = cov_bundle.get("entry", []) or []
                if not entries:
                    return {"error": f"No active insurance found for member ID {member_id}"}
                plan = _fhir_coverage_to_insurance(entries[0].get("resource", {}))
            return {
                "memberId": plan.get("memberId", member_id),
                "plan": {
                    "payerName": plan["payerName"],
                    "planName": plan["planName"],
                    "planType": plan["planType"],
                    "groupNumber": plan["groupNumber"],
                    "status": plan["status"],
                    "effectiveDate": plan["effectiveDate"],
                },
                "copay": plan.get("copay") or {},
            }
        except FHIRRequestError as e:
            return {"error": str(e)}

    return _run_async(_fetch())


def search_conditions(symptoms: str) -> list[dict]:
    """Search conditions by symptoms. Keeps mock for educational content per prompt."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        query = (symptoms or "").lower().strip()
        if not query:
            return []
        query_terms = [t for t in query.split() if len(t) >= 2]
        matches = []
        for cond in MOCK_MEDICAL_CONDITIONS:
            symptom_text = " ".join(cond.get("common_symptoms", [])).lower()
            if any(term in symptom_text or term in cond["name"].lower() for term in query_terms):
                matches.append({
                    "name": cond["name"],
                    "description": cond["description"],
                    "common_symptoms": cond["common_symptoms"],
                })
        return matches

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_conditions(code_text=symptoms if symptoms else None)
        entries = bundle.get("entry", []) or []
        return [
            {
                "name": _fhir_condition_to_condition(e.get("resource", {}))["name"],
                "description": "",
                "common_symptoms": [],
            }
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Condition"
        ]

    return _run_async(_fetch())


def get_clinic_info(query: str = "") -> dict:
    """Get clinic info and optionally filtered providers."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        q = query.lower().strip() if query else ""
        if q:
            providers = [
                p for p in MOCK_PROVIDERS
                if q in p["name"].lower() or q in p["specialty"].lower()
            ]
        else:
            providers = MOCK_PROVIDERS
        return {
            "clinic": {
                "address": "123 Healthcare Ave, Suite 100",
                "hours": "Mon–Fri 8am–5pm",
                "parking": "Free parking in the lot behind the building",
                "phone": "555-0199",
            },
            "providers": [
                {"id": p["id"], "name": p["name"], "specialty": p["specialty"], "phone": p["phone"], "email": p["email"]}
                for p in providers
            ],
            "query_filter": query or None,
        }

    async def _fetch():
        client = get_fhir_client()
        org_task = client.get_organizations()
        prov_task = client.get_practitioners(specialty=query if query else None)
        results = await asyncio.gather(org_task, prov_task, return_exceptions=True)
        org_bundle = results[0] if not isinstance(results[0], Exception) else {"entry": []}
        prov_bundle = results[1] if not isinstance(results[1], Exception) else {"entry": []}
        org_entries = org_bundle.get("entry", []) or []
        orgs = [
            e.get("resource", {})
            for e in org_entries
            if e.get("resource", {}).get("resourceType") == "Organization"
        ]
        clinic = (
            _fhir_organization_to_clinic(orgs[0])
            if orgs
            else {"address": "", "hours": "", "parking": "", "phone": ""}
        )
        prov_entries = prov_bundle.get("entry", []) or []
        providers = [
            _fhir_practitioner_to_provider(e.get("resource", {}))
            for e in prov_entries
            if e.get("resource", {}).get("resourceType") == "Practitioner"
        ]
        return {
            "clinic": clinic,
            "providers": [
                {"id": p["id"], "name": p["name"], "specialty": p["specialty"], "phone": p["phone"], "email": p["email"]}
                for p in providers
            ],
            "query_filter": query or None,
        }

    return _run_async(_fetch())


def get_my_appointment_locations(patient_id: str, today: str | None = None) -> dict:
    """
    Get locations of the patient's upcoming appointments.

    Use when a patient asks "where is my clinic" or "where are my appointments".
    Returns locations from upcoming (date >= today, not cancelled/completed) appointments.
    """
    today_str = today or _today().isoformat()
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        apts = [
            a
            for a in MOCK_APPOINTMENTS
            if a["patientId"] == patient_id
            and a["date"] >= today_str
            and a["status"] not in ("cancelled", "completed")
        ]
        apts.sort(key=lambda a: (a["date"], _time_sort_key(a.get("time", ""))))
        locations = []
        seen = set()
        for a in apts:
            loc = a.get("location") or ""
            if loc and loc not in seen:
                seen.add(loc)
                locations.append(
                    {"location": loc, "date": a["date"], "time": a.get("time", ""), "type": a.get("type", "")}
                )
        return {
            "patient_id": patient_id,
            "locations": locations,
            "message": f"No upcoming appointments for {patient_id}" if not locations else None,
        }

    apts = get_patient_appointments(patient_id)
    apts = [
        a
        for a in apts
        if a["date"] >= today_str and a.get("status") not in ("cancelled", "completed")
    ]
    apts.sort(key=lambda a: (a["date"], _time_sort_key(a.get("time", ""))))
    locations = []
    seen = set()
    for a in apts:
        loc = a.get("location") or ""
        if loc and loc not in seen:
            seen.add(loc)
            locations.append(
                {"location": loc, "date": a["date"], "time": a.get("time", ""), "type": a.get("type", "")}
            )
    return {
        "patient_id": patient_id,
        "locations": locations,
        "message": f"No upcoming appointments for {patient_id}" if not locations else None,
    }


def get_staff_assigned_clinic(staff_id: str) -> dict:
    """
    Get the clinic/facility assigned to a staff member.

    Use when staff asks "where is the clinic" or "where is my clinic".
    Returns assigned facility address, phone, hours.
    """
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        staff = next((s for s in MOCK_STAFF if s["id"] == staff_id), None)
        if not staff:
            return {"staff_id": staff_id, "error": f"Staff {staff_id} not found"}
        fac_id = staff.get("facility_id")
        facility = next((f for f in MOCK_FACILITIES if f["id"] == fac_id), None)
        if not facility:
            return _fallback_clinic_for_staff(staff_id)
        return {
            "staff_id": staff_id,
            "staff_name": staff.get("name", ""),
            "facility": {
                "name": facility["name"],
                "address": facility.get("address", ""),
                "city": facility.get("city", ""),
                "state": facility.get("state", ""),
                "postal_code": facility.get("postal_code", ""),
                "phone": facility.get("phone", ""),
                "hours": facility.get("hours", ""),
            },
        }

    # FHIR: PractitionerRole has location. Fallback to first Organization.
    async def _fetch():
        client = get_fhir_client()
        org_bundle = await client.get_organizations()
        org_entries = org_bundle.get("entry", []) or []
        orgs = [
            e.get("resource", {})
            for e in org_entries
            if e.get("resource", {}).get("resourceType") == "Organization"
        ]
        org = orgs[0] if orgs else {}
        clinic = _fhir_organization_to_clinic(org) if org else {}
        return {
            "staff_id": staff_id,
            "facility": {
                "name": org.get("name", "Main Clinic"),
                "address": clinic.get("address", ""),
                "city": "",
                "state": "",
                "postal_code": "",
                "phone": clinic.get("phone", ""),
                "hours": clinic.get("hours", ""),
            },
        }

    return _run_async(_fetch())


def get_patient_allergies(patient_id: str) -> list[dict]:
    """Get allergies for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_allergy_intolerances(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_allergy_to_allergy(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "AllergyIntolerance"
        ]

    return _run_async(_fetch())


def get_patient_medications(patient_id: str) -> list[dict]:
    """Get active medication requests for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_medication_requests(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_medication_request_to_medication(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "MedicationRequest"
        ]

    return _run_async(_fetch())


def get_patient_observations(patient_id: str, category: str = "") -> list[dict]:
    """Get observations (vitals, labs, etc.) for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_observations(
            patient_id=patient_id,
            category=category if category else None,
        )
        entries = bundle.get("entry", []) or []
        return [
            _fhir_observation_to_observation(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Observation"
        ]

    return _run_async(_fetch())


def get_patient_encounters(patient_id: str) -> list[dict]:
    """Get encounters for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_encounters(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_encounter_to_encounter(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Encounter"
        ]

    return _run_async(_fetch())


def get_patient_immunizations(patient_id: str) -> list[dict]:
    """Get immunizations for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_immunizations(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_immunization_to_immunization(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Immunization"
        ]

    return _run_async(_fetch())


def get_patient_procedures(patient_id: str) -> list[dict]:
    """Get procedures for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_procedures(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_procedure_to_procedure(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Procedure"
        ]

    return _run_async(_fetch())


def get_patient_diagnostic_reports(patient_id: str) -> list[dict]:
    """Get diagnostic reports for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_diagnostic_reports(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_diagnostic_report_to_report(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "DiagnosticReport"
        ]

    return _run_async(_fetch())


def get_patient_care_plans(patient_id: str) -> list[dict]:
    """Get care plans for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_care_plans(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_care_plan_to_care_plan(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "CarePlan"
        ]

    return _run_async(_fetch())


def get_patient_care_teams(patient_id: str) -> list[dict]:
    """Get care teams for a patient."""
    if os.getenv("USE_MOCK_DATA", "false").lower() == "true":  # AI-generated
        return []

    async def _fetch():
        client = get_fhir_client()
        bundle = await client.get_care_teams(patient_id=patient_id)
        entries = bundle.get("entry", []) or []
        return [
            _fhir_care_team_to_care_team(e.get("resource", {}))
            for e in entries
            if e.get("resource", {}).get("resourceType") == "CareTeam"
        ]

    return _run_async(_fetch())


def _fallback_clinic_for_staff(staff_id: str) -> dict:
    """Return generic clinic info when staff has no facility."""
    clinic_info = get_clinic_info("")
    clinic = clinic_info.get("clinic", {})
    return {
        "staff_id": staff_id,
        "facility": {
            "name": "Main Clinic",
            "address": clinic.get("address", ""),
            "city": "",
            "state": "",
            "postal_code": "",
            "phone": clinic.get("phone", ""),
            "hours": clinic.get("hours", ""),
        },
    }


# End AI-generated code
