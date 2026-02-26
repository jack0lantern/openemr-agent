# AI-generated: Unit tests for data_service transformers and dispatch logic

import pytest

from app.services.data_service import (
    _fhir_appointment_to_appointment,
    _fhir_coverage_to_insurance,
    _fhir_organization_to_clinic,
    _fhir_patient_to_patient,
    _fhir_practitioner_to_provider,
    _fhir_slot_to_available_slot,
    get_available_dates,
    get_providers,
)
from tests.fixtures.fhir_bundles import (
    SAMPLE_APPOINTMENT,
    SAMPLE_COVERAGE,
    SAMPLE_ORGANIZATION,
    SAMPLE_PATIENT,
    SAMPLE_PRACTITIONER_BUNDLE,
    SAMPLE_SLOT,
)


class TestFHIRTransformers:
    """Unit tests for FHIR-to-mock-shape transformer functions."""

    def test_fhir_practitioner_to_provider(self):
        resource = SAMPLE_PRACTITIONER_BUNDLE["entry"][0]["resource"]
        result = _fhir_practitioner_to_provider(resource)
        assert result["id"] == "prac-001"
        assert "Dr." in result["name"] and "Jane" in result["name"] and "Doe" in result["name"]
        assert result["specialty"] == "Family Medicine"
        assert result["npi"] == "1234567890"
        assert result["phone"] == "(555) 111-2222"
        assert result["email"] == "jane.doe@clinic.example.com"

    def test_fhir_patient_to_patient(self):
        result = _fhir_patient_to_patient(SAMPLE_PATIENT)
        assert result["id"] == "pat-001"
        assert "John" in result["name"] and "Smith" in result["name"]
        assert result["dateOfBirth"] == "1985-03-15"
        assert result["phone"] == "(555) 101-2001"

    def test_fhir_appointment_to_appointment(self):
        result = _fhir_appointment_to_appointment(SAMPLE_APPOINTMENT)
        assert result["id"] == "apt-001"
        assert result["date"] == "2025-02-24"
        assert result["patientId"] == "pat-001"
        assert result["providerId"] == "prov-001"
        assert result["duration"] == 30

    def test_fhir_slot_to_available_slot(self):
        result = _fhir_slot_to_available_slot(SAMPLE_SLOT)
        assert result["id"] == "slot-001"
        assert result["date"] == "2025-02-25"
        assert "8" in result["time"] and "AM" in result["time"]

    def test_fhir_coverage_to_insurance(self):
        result = _fhir_coverage_to_insurance(SAMPLE_COVERAGE)
        assert result["id"] == "cov-001"
        assert result["payerName"] == "Blue Cross Blue Shield"
        assert result["planName"] == "PPO Gold"

    def test_fhir_organization_to_clinic(self):
        result = _fhir_organization_to_clinic(SAMPLE_ORGANIZATION)
        assert result["address"] == "456 Healthcare Ave, Suite 200, Springfield, IL, 62701"
        assert result["phone"] == "(555) 123-4567"
        assert result["hours"] == ""
        assert result["parking"] == ""


class TestDataServiceDispatch:
    """Tests for data_service with use_mock_data=True (default)."""

    def test_get_providers_returns_mock_data(self):
        providers = get_providers("")
        assert len(providers) >= 1
        assert "id" in providers[0]
        assert "name" in providers[0]
        assert "specialty" in providers[0]

    def test_get_providers_filters_by_specialty(self):
        providers = get_providers("Family Medicine")
        assert all("Family Medicine" in p.get("specialty", "") for p in providers)

    def test_get_available_dates_returns_sorted_dates(self):
        dates = get_available_dates()
        assert len(dates) >= 0
        assert dates == sorted(dates)
