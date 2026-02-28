"""
Appointment type to duration mapping based on OpenEMR defaults.

Durations are sourced from openemr_postcalendar_categories.pc_duration (seconds)
in openemr/sql/database.sql. Values converted to minutes for agent use.
"""

# OpenEMR default durations (pc_duration in seconds -> minutes)
# From openemr_postcalendar_categories: office_visit=900, established_patient=900,
# new_patient=1800, reserved=900, health_and_behavioral_assessment=900,
# preventive_care_services=900, ophthalmological_services=900, group_therapy=3600
APPOINTMENT_TYPE_DURATIONS: dict[str, int] = {
    # OpenEMR pc_constant_id -> duration_minutes
    "office_visit": 15,
    "established_patient": 15,
    "new_patient": 30,
    "reserved": 15,
    "health_and_behavioral_assessment": 15,
    "preventive_care_services": 15,
    "ophthalmological_services": 15,
    "group_therapy": 60,
    # Common aliases (user-friendly / mock data types)
    "checkup": 15,
    "follow-up": 15,
    "follow_up": 15,
    "telehealth": 15,
    "procedure": 60,
}

# Display names for each type (for list_appointment_types tool)
APPOINTMENT_TYPE_LABELS: dict[str, str] = {
    "office_visit": "Office Visit",
    "established_patient": "Established Patient",
    "new_patient": "New Patient",
    "reserved": "Reserved",
    "health_and_behavioral_assessment": "Health and Behavioral Assessment",
    "preventive_care_services": "Preventive Care Services",
    "ophthalmological_services": "Ophthalmological Services",
    "group_therapy": "Group Therapy",
    "checkup": "Checkup",
    "follow-up": "Follow-up",
    "follow_up": "Follow-up",
    "telehealth": "Telehealth",
    "procedure": "Procedure",
}

DEFAULT_DURATION_MINUTES = 15


def get_duration_minutes(appointment_type: str | None) -> int:
    """
    Return duration in minutes for an appointment type.
    Uses OpenEMR defaults. Returns DEFAULT_DURATION_MINUTES for unknown types.
    """
    if not appointment_type:
        return DEFAULT_DURATION_MINUTES
    key = appointment_type.strip().lower().replace(" ", "_").replace("-", "_")
    return APPOINTMENT_TYPE_DURATIONS.get(key, DEFAULT_DURATION_MINUTES)


def get_all_appointment_types() -> list[dict[str, str | int]]:
    """
    Return list of appointment types with durations for the list_appointment_types tool.
    Deduplicates by duration+label to avoid redundant entries from aliases.
    """
    seen: set[tuple[str, int]] = set()
    result: list[dict[str, str | int]] = []
    # Prefer canonical OpenEMR types first
    canonical = [
        "office_visit",
        "established_patient",
        "new_patient",
        "reserved",
        "health_and_behavioral_assessment",
        "preventive_care_services",
        "ophthalmological_services",
        "group_therapy",
    ]
    for key in canonical:
        dur = APPOINTMENT_TYPE_DURATIONS[key]
        label = APPOINTMENT_TYPE_LABELS.get(key, key.replace("_", " ").title())
        if (label, dur) not in seen:
            seen.add((label, dur))
            result.append({"type": key, "label": label, "duration_minutes": dur})
    # Add common aliases that differ
    for key in ["checkup", "follow-up", "telehealth", "procedure"]:
        dur = APPOINTMENT_TYPE_DURATIONS[key]
        label = APPOINTMENT_TYPE_LABELS.get(key, key.replace("_", " ").title())
        if (label, dur) not in seen:
            seen.add((label, dur))
            result.append({"type": key, "label": label, "duration_minutes": dur})
    return result
