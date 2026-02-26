# AI-generated: Sample FHIR R4 Bundle responses for unit tests

SAMPLE_PRACTITIONER_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [
        {
            "resource": {
                "resourceType": "Practitioner",
                "id": "prac-001",
                "name": [
                    {
                        "prefix": ["Dr."],
                        "given": ["Jane"],
                        "family": "Doe",
                    }
                ],
                "identifier": [
                    {"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}
                ],
                "qualification": [
                    {"code": {"text": "Family Medicine"}}
                ],
                "telecom": [
                    {"system": "phone", "value": "(555) 111-2222"},
                    {"system": "email", "value": "jane.doe@clinic.example.com"},
                ],
            }
        }
    ],
}

SAMPLE_PATIENT = {
    "resourceType": "Patient",
    "id": "pat-001",
    "name": [{"given": ["John"], "family": "Smith"}],
    "birthDate": "1985-03-15",
    "telecom": [
        {"system": "phone", "value": "(555) 101-2001"},
        {"system": "email", "value": "john.smith@email.com"},
    ],
    "address": [{"line": ["123 Oak Street"], "city": "Springfield", "state": "IL"}],
}

SAMPLE_APPOINTMENT = {
    "resourceType": "Appointment",
    "id": "apt-001",
    "status": "booked",
    "start": "2025-02-24T09:00:00",
    "minutesDuration": 30,
    "participant": [
        {"actor": {"reference": "Patient/pat-001"}, "required": "required"},
        {"actor": {"reference": "Practitioner/prov-001"}, "required": "required"},
    ],
}

SAMPLE_SLOT = {
    "resourceType": "Slot",
    "id": "slot-001",
    "status": "free",
    "start": "2025-02-25T08:00:00",
    "end": "2025-02-25T08:30:00",
}

SAMPLE_COVERAGE = {
    "resourceType": "Coverage",
    "id": "cov-001",
    "payor": [{"display": "Blue Cross Blue Shield"}],
    "type": {"text": "PPO Gold"},
    "beneficiary": {"reference": "Patient/pat-001"},
}

SAMPLE_CONDITION = {
    "resourceType": "Condition",
    "id": "cond-001",
    "code": {"text": "Common Cold", "coding": [{"display": "Common Cold"}]},
}

SAMPLE_ORGANIZATION = {
    "resourceType": "Organization",
    "id": "org-001",
    "name": "Main Street Clinic",
    "telecom": [
        {"system": "phone", "value": "(555) 123-4567", "use": "work"},
        {"system": "email", "value": "contact@clinic.example.com", "use": "work"},
    ],
    "address": [
        {
            "line": ["456 Healthcare Ave", "Suite 200"],
            "city": "Springfield",
            "state": "IL",
            "postalCode": "62701",
        }
    ],
}
