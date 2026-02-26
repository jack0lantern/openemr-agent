"""
Test-specific mock data for golden path evaluation.

DO NOT import from app.data.mock_data. This module provides isolated test data
with distinct IDs and fictional names to detect test data leaks.
"""

# Reference date for date-sensitive logic. list_upcoming_appointments uses
# hardcoded today="2025-02-24" in agent; test data aligns with that.
TEST_TODAY = "2026-03-01"

TEST_PROVIDERS = [
    {
        "id": "test-prov-001",
        "name": "Dr. Test Provider",
        "specialty": "Family Medicine",
        "npi": "1111111111",
        "credentials": "MD, FAAFP",
        "phone": "(555) 911-1111",
        "email": "testprov@clinic.test",
        "schedule": {
            "monday": "8:00 AM - 5:00 PM",
            "tuesday": "8:00 AM - 5:00 PM",
            "wednesday": "8:00 AM - 12:00 PM",
            "thursday": "8:00 AM - 5:00 PM",
            "friday": "8:00 AM - 4:00 PM",
        },
    },
    {
        "id": "test-prov-002",
        "name": "Dr. Test Internist",
        "specialty": "Internal Medicine",
        "npi": "2222222222",
        "credentials": "MD, FACP",
        "phone": "(555) 922-2222",
        "email": "internist@clinic.test",
        "schedule": {
            "monday": "9:00 AM - 6:00 PM",
            "tuesday": "9:00 AM - 6:00 PM",
            "wednesday": "9:00 AM - 6:00 PM",
            "thursday": "9:00 AM - 6:00 PM",
            "friday": "9:00 AM - 2:00 PM",
        },
    },
    {
        "id": "test-prov-003",
        "name": "Dr. Test Pediatrician",
        "specialty": "Pediatrics",
        "npi": "3333333333",
        "credentials": "MD, FAAP",
        "phone": "(555) 933-3333",
        "email": "pediatrician@clinic.test",
        "schedule": {
            "monday": "7:30 AM - 4:30 PM",
            "tuesday": "7:30 AM - 4:30 PM",
            "wednesday": "7:30 AM - 4:30 PM",
            "thursday": "7:30 AM - 4:30 PM",
            "friday": "7:30 AM - 3:00 PM",
        },
    },
]

# Edge cases: expired insurance (test-ins-002), patient with no insurance (test-pat-003)
TEST_INSURANCE_PLANS = [
    {
        "id": "test-ins-001",
        "payerName": "Test Health PPO",
        "planName": "Test Gold PPO",
        "planType": "PPO",
        "groupNumber": "TEST-GRP-001",
        "memberId": "TEST-MEM-001",
        "effectiveDate": "2024-01-01",
        "terminationDate": None,
        "status": "active",
        "copay": {
            "pcp": "$25",
            "specialist": "$50",
            "urgentCare": "$75",
            "er": "$250",
        },
    },
    {
        "id": "test-ins-002",
        "payerName": "Expired Test Insurance",
        "planName": "Expired Plan",
        "planType": "HMO",
        "groupNumber": "EXP-GRP-001",
        "memberId": "EXP-MEM-001",
        "effectiveDate": "2023-01-01",
        "terminationDate": "2024-12-31",
        "status": "expired",
        "copay": {},
    },
]

# test-pat-001: has appointments, has insurance
# test-pat-002: has appointments
# test-pat-003: no insurance (insurancePlanId None)
# test-pat-004: no appointments
TEST_PATIENTS = [
    {
        "id": "test-pat-001",
        "name": "Test Patient Alpha",
        "dateOfBirth": "1985-03-15",
        "phone": "(555) 101-1001",
        "email": "alpha@test.patient",
        "address": "100 Test Street, Test City",
        "insurancePlanId": "test-ins-001",
        "primaryCareProviderId": "test-prov-001",
        "emergencyContact": "Test Contact Alpha",
        "emergencyContactPhone": "(555) 101-1002",
    },
    {
        "id": "test-pat-002",
        "name": "Test Patient Beta",
        "dateOfBirth": "1992-07-22",
        "phone": "(555) 102-1002",
        "email": "beta@test.patient",
        "address": "200 Test Avenue, Test Town",
        "insurancePlanId": "test-ins-001",
        "primaryCareProviderId": "test-prov-002",
        "emergencyContact": "Test Contact Beta",
        "emergencyContactPhone": "(555) 102-1003",
    },
    {
        "id": "test-pat-003",
        "name": "Test Patient No Insurance",
        "dateOfBirth": "1990-01-01",
        "phone": "(555) 103-1003",
        "email": "noins@test.patient",
        "address": "300 Test Lane, Test Village",
        "insurancePlanId": None,
        "primaryCareProviderId": "test-prov-001",
        "emergencyContact": "Test Contact Gamma",
        "emergencyContactPhone": "(555) 103-1004",
    },
    {
        "id": "test-pat-004",
        "name": "Test Patient No Appointments",
        "dateOfBirth": "1988-05-20",
        "phone": "(555) 104-1004",
        "email": "noapt@test.patient",
        "address": "400 Test Road, Test Borough",
        "insurancePlanId": "test-ins-001",
        "primaryCareProviderId": "test-prov-002",
        "emergencyContact": "Test Contact Delta",
        "emergencyContactPhone": "(555) 104-1005",
    },
]

# Mix: future, past, cancelled, completed. Tool uses today="2025-02-24".
# Past: 2025-02-23; Future: 2025-02-24, 2025-02-25; Cancelled/completed excluded.
TEST_APPOINTMENTS = [
    {
        "id": "test-apt-001",
        "patientName": "Test Patient Alpha",
        "patientId": "test-pat-001",
        "providerId": "test-prov-001",
        "providerName": "Dr. Test Provider",
        "date": "2025-02-24",
        "time": "9:00 AM",
        "duration": 30,
        "type": "follow-up",
        "status": "scheduled",
        "location": "Main Clinic - Room 101",
        "notes": "Blood pressure follow-up",
    },
    {
        "id": "test-apt-002",
        "patientName": "Test Patient Beta",
        "patientId": "test-pat-002",
        "providerId": "test-prov-002",
        "providerName": "Dr. Test Internist",
        "date": "2025-02-24",
        "time": "10:30 AM",
        "duration": 45,
        "type": "new-patient",
        "status": "confirmed",
        "location": "Main Clinic - Room 205",
    },
    {
        "id": "test-apt-003",
        "patientName": "Test Patient Alpha",
        "patientId": "test-pat-001",
        "providerId": "test-prov-003",
        "providerName": "Dr. Test Pediatrician",
        "date": "2025-02-23",
        "time": "2:00 PM",
        "duration": 20,
        "type": "checkup",
        "status": "scheduled",
        "location": "Pediatrics Wing - Room 301",
    },
    {
        "id": "test-apt-004",
        "patientName": "Test Patient Beta",
        "patientId": "test-pat-002",
        "providerId": "test-prov-001",
        "providerName": "Dr. Test Provider",
        "date": "2025-02-25",
        "time": "11:00 AM",
        "duration": 30,
        "type": "telehealth",
        "status": "cancelled",
        "location": "Video Visit",
    },
    {
        "id": "test-apt-005",
        "patientName": "Test Patient Alpha",
        "patientId": "test-pat-001",
        "providerId": "test-prov-002",
        "providerName": "Dr. Test Internist",
        "date": "2025-02-23",
        "time": "3:00 PM",
        "duration": 60,
        "type": "procedure",
        "status": "completed",
        "location": "Main Clinic - Procedure Room",
    },
]

# Staff with assigned facilities (for get_staff_assigned_clinic)
TEST_STAFF = [
    {"id": "test-staff-001", "name": "Test Receptionist", "facility_id": "test-fac-001"},
    {"id": "test-staff-002", "name": "Test Nurse", "facility_id": "test-fac-001"},
]

TEST_FACILITIES = [
    {
        "id": "test-fac-001",
        "name": "Test Main Clinic",
        "address": "123 Healthcare Ave, Suite 100",
        "city": "Test City",
        "state": "IL",
        "postal_code": "62701",
        "phone": "555-0199",
        "hours": "Mon–Fri 8am–5pm",
    },
]

# Slots on 2026-03-02 and 2026-03-03. 2026-03-01 has no slots (edge case).
TEST_AVAILABLE_SLOTS = [
    {
        "id": "test-slot-001",
        "date": "2026-03-02",
        "time": "8:00 AM",
        "providerId": "test-prov-001",
        "providerName": "Dr. Test Provider",
        "duration": 30,
        "location": "Main Clinic - Room 101",
        "type": "checkup",
    },
    {
        "id": "test-slot-002",
        "date": "2026-03-02",
        "time": "9:30 AM",
        "providerId": "test-prov-002",
        "providerName": "Dr. Test Internist",
        "duration": 45,
        "location": "Main Clinic - Room 205",
        "type": "new-patient",
    },
    {
        "id": "test-slot-003",
        "date": "2026-03-02",
        "time": "11:00 AM",
        "providerId": "test-prov-003",
        "providerName": "Dr. Test Pediatrician",
        "duration": 20,
        "location": "Pediatrics Wing - Room 301",
        "type": "checkup",
    },
    {
        "id": "test-slot-004",
        "date": "2026-03-03",
        "time": "8:30 AM",
        "providerId": "test-prov-001",
        "providerName": "Dr. Test Provider",
        "duration": 30,
        "location": "Main Clinic - Room 101",
        "type": "follow-up",
    },
]
