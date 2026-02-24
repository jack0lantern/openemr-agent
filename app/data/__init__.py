"""Data layer - mock data for development; FHIR/OpenEMR in production."""

from app.data.mock_data import (
    MOCK_APPOINTMENTS,
    MOCK_AVAILABLE_SLOTS,
    MOCK_INSURANCE_PLANS,
    MOCK_PATIENTS,
    MOCK_PROVIDERS,
)

__all__ = [
    "MOCK_APPOINTMENTS",
    "MOCK_AVAILABLE_SLOTS",
    "MOCK_INSURANCE_PLANS",
    "MOCK_PATIENTS",
    "MOCK_PROVIDERS",
]
