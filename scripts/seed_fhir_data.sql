-- AI-generated: FHIR seed data for agent endpoints (openemr-connection-prompt.md)
-- Data is DIFFERENT from mock_data.py so USE_MOCK_DATA=false returns distinct live data.
--
-- Endpoint mapping (prompts/openemr-connection-prompt.md):
--   Organization  -> facility
--   Practitioner  -> users (abook_type=spe, calendar=1)
--   Patient       -> patient_data
--   Appointment   -> openemr_postcalendar_events (pc_apptstatus='>')
--   Slot/Schedule -> openemr_postcalendar_events (pc_apptstatus='-')
--   Coverage      -> insurance_companies + insurance_data
--   Condition     -> lists (type=medical_problem)
--
-- Usage: docker compose exec mysql mysql -u openemr -popenemr openemr < openemr-agent/scripts/seed_fhir_data.sql

-- =============================================================================
-- 1. ORGANIZATION (facility) - GET /fhir/Organization
-- =============================================================================
SET @facility_uuid = UNHEX(REPLACE('b2c3d4e5-f6a7-4890-b123-456789abcdef', '-', ''));

UPDATE `facility` SET
  `name` = 'Riverside Medical Center',
  `phone` = '(503) 777-0100',
  `fax` = '(503) 777-0101',
  `street` = '780 Wellness Way, Building A',
  `city` = 'Portland',
  `state` = 'OR',
  `postal_code` = '97201',
  `country_code` = 'US',
  `email` = 'info@riversidemed.org',
  `uuid` = @facility_uuid,
  `info` = 'Hours: Tue–Sat 7am–6pm. Parking: Garage on Level P1, validation at front desk.',
  `primary_business_entity` = 1
WHERE `id` = 3;

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@facility_uuid, 'facility', 'id', '', '', 0, 0, NOW());

-- =============================================================================
-- 2. PRACTITIONER (users) - GET /fhir/Practitioner
-- =============================================================================
SET @prac1_uuid = UNHEX(REPLACE('c3d4e5f6-a7b8-4901-c234-56789abcdef0', '-', ''));
SET @prac2_uuid = UNHEX(REPLACE('d4e5f6a7-b8c9-4012-d345-6789abcdef01', '-', ''));
SET @prac3_uuid = UNHEX(REPLACE('e5f6a7b8-c9d0-4123-e456-789abcdef012', '-', ''));

INSERT INTO `users` (`username`, `authorized`, `fname`, `mname`, `lname`, `facility_id`, `facility`, `npi`, `specialty`, `email`, `phone`, `abook_type`, `calendar`, `active`, `uuid`)
VALUES
  ('fhir-seed-apatel', 1, 'Anita', 'R', 'Patel', 3, 'Riverside Medical Center', '4567890123', 'Cardiology', 'apatel@riversidemed.org', '(503) 777-0201', 'spe', 1, 1, @prac1_uuid),
  ('fhir-seed-jfoster', 1, 'James', 'L', 'Foster', 3, 'Riverside Medical Center', '5678901234', 'Dermatology', 'jfoster@riversidemed.org', '(503) 777-0202', 'spe', 1, 1, @prac2_uuid),
  ('fhir-seed-rkim', 1, 'Rachel', 'S', 'Kim', 3, 'Riverside Medical Center', '6789012345', 'Obstetrics', 'rkim@riversidemed.org', '(503) 777-0203', 'spe', 1, 1, @prac3_uuid)
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@prac1_uuid, 'users', 'id', '', '', 0, 0, NOW()),
       (@prac2_uuid, 'users', 'id', '', '', 0, 0, NOW()),
       (@prac3_uuid, 'users', 'id', '', '', 0, 0, NOW());

-- =============================================================================
-- 3. PATIENT (patient_data) - GET /fhir/Patient
-- =============================================================================
SET @pat1_uuid = UNHEX(REPLACE('f6a7b8c9-d0e1-4234-f567-89abcdef0123', '-', ''));
SET @pat2_uuid = UNHEX(REPLACE('a7b8c9d0-e1f2-4345-a678-9abcdef01234', '-', ''));

INSERT INTO `patient_data` (`pid`, `fname`, `lname`, `DOB`, `street`, `city`, `state`, `postal_code`, `country_code`, `phone_home`, `phone_cell`, `email`, `sex`, `uuid`)
VALUES
  (900001, 'Vikram', 'Sharma', '1988-05-12', '1200 Oak Park Blvd', 'Portland', 'OR', '97202', 'US', '(503) 555-3001', '(503) 555-3002', 'vikram.sharma@email.com', 'male', @pat1_uuid),
  (900002, 'Olivia', 'Nguyen', '1995-11-28', '88 Pine Ridge Lane', 'Beaverton', 'OR', '97005', 'US', '(503) 555-4001', '(503) 555-4002', 'olivia.nguyen@email.com', 'female', @pat2_uuid)
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@pat1_uuid, 'patient_data', 'id', '', '', 0, 0, NOW()),
       (@pat2_uuid, 'patient_data', 'id', '', '', 0, 0, NOW());

-- =============================================================================
-- 4. COVERAGE (insurance_companies + insurance_data) - GET /fhir/Coverage
-- =============================================================================
SET @ins_co_uuid = UNHEX(REPLACE('b8c9d0e1-f2a3-4456-b789-abcdef012345', '-', ''));
SET @cov1_uuid = UNHEX(REPLACE('c9d0e1f2-a3b4-4567-c890-bcdef0123456', '-', ''));
SET @cov2_uuid = UNHEX(REPLACE('d0e1f2a3-b4c5-4678-d901-cdef01234567', '-', ''));

INSERT INTO `insurance_companies` (`id`, `name`, `uuid`)
VALUES (9001, 'Pacific Northwest Health Plan', @ins_co_uuid)
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@ins_co_uuid, 'insurance_companies', 'id', '', '', 0, 0, NOW());

INSERT INTO `insurance_data` (`type`, `provider`, `plan_name`, `policy_number`, `group_number`, `pid`, `date`, `uuid`)
VALUES
  ('primary', 'Pacific Northwest Health Plan', 'PNHP Silver PPO', 'PNH-MEM-881234', 'GRP-55001', 900001, '2024-06-01', @cov1_uuid),
  ('primary', 'Pacific Northwest Health Plan', 'PNHP Gold HMO', 'PNH-MEM-992345', 'GRP-55002', 900002, '2024-08-15', @cov2_uuid)
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@cov1_uuid, 'insurance_data', 'id', '', '', 0, 0, NOW()),
       (@cov2_uuid, 'insurance_data', 'id', '', '', 0, 0, NOW());

-- =============================================================================
-- 5. APPOINTMENT + SLOT (openemr_postcalendar_events) - GET /fhir/Appointment, Slot
-- pc_aid = provider user id, pc_pid = patient id, pc_apptstatus: - = available, > = booked
-- =============================================================================
SET @apt1_uuid = UNHEX(REPLACE('e1f2a3b4-c5d6-4789-e012-def012345678', '-', ''));
SET @apt2_uuid = UNHEX(REPLACE('f2a3b4c5-d6e7-4890-f123-ef0123456789', '-', ''));
SET @slot_uuid = UNHEX(REPLACE('a3b4c5d6-e7f8-4901-a234-f01234567890', '-', ''));

-- Get practitioner IDs (run after practitioner inserts)
SET @prac1_id = (SELECT id FROM users WHERE username = 'fhir-seed-apatel' LIMIT 1);
SET @prac2_id = (SELECT id FROM users WHERE username = 'fhir-seed-jfoster' LIMIT 1);

INSERT INTO `openemr_postcalendar_events` (
  `pc_catid`, `pc_aid`, `pc_pid`, `pc_title`, `pc_eventDate`, `pc_endDate`, `pc_startTime`, `pc_endTime`, `pc_duration`, `pc_eventstatus`, `pc_apptstatus`, `pc_facility`, `uuid`
)
SELECT 3, COALESCE(@prac1_id, 0), '900001', 'Follow-up', CURDATE() + INTERVAL 3 DAY, CURDATE() + INTERVAL 3 DAY, '09:00:00', '09:30:00', 1800, 1, '>', 3, @apt1_uuid
WHERE @prac1_id IS NOT NULL
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

INSERT INTO `openemr_postcalendar_events` (
  `pc_catid`, `pc_aid`, `pc_pid`, `pc_title`, `pc_eventDate`, `pc_endDate`, `pc_startTime`, `pc_endTime`, `pc_duration`, `pc_eventstatus`, `pc_apptstatus`, `pc_facility`, `uuid`
)
SELECT 3, COALESCE(@prac2_id, 0), '900002', 'Skin check', CURDATE() + INTERVAL 5 DAY, CURDATE() + INTERVAL 5 DAY, '14:00:00', '14:20:00', 1200, 1, '>', 3, @apt2_uuid
WHERE @prac2_id IS NOT NULL
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

-- Available slot (pc_apptstatus = '-' means free)
INSERT IGNORE INTO `openemr_postcalendar_events` (
  `pc_catid`, `pc_aid`, `pc_pid`, `pc_title`, `pc_eventDate`, `pc_endDate`, `pc_startTime`, `pc_endTime`, `pc_duration`, `pc_eventstatus`, `pc_apptstatus`, `pc_facility`, `uuid`
)
SELECT 3, COALESCE(@prac1_id, 0), NULL, 'Open slot', CURDATE() + INTERVAL 7 DAY, CURDATE() + INTERVAL 7 DAY, '10:00:00', '10:30:00', 1800, 1, '-', 3, @slot_uuid
WHERE @prac1_id IS NOT NULL;

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@apt1_uuid, 'openemr_postcalendar_events', 'pc_eid', '', '', 0, 0, NOW()),
       (@apt2_uuid, 'openemr_postcalendar_events', 'pc_eid', '', '', 0, 0, NOW()),
       (@slot_uuid, 'openemr_postcalendar_events', 'pc_eid', '', '', 0, 0, NOW());

-- =============================================================================
-- 6. CONDITION (lists) - GET /fhir/Condition
-- type = medical_problem for problem list / Condition
-- =============================================================================
SET @cond1_uuid = UNHEX(REPLACE('b4c5d6e7-f8a9-4012-b345-012345678901', '-', ''));
SET @cond2_uuid = UNHEX(REPLACE('c5d6e7f8-a9b0-4123-c456-123456789012', '-', ''));

INSERT INTO `lists` (`pid`, `type`, `title`, `begdate`, `activity`, `uuid`)
VALUES
  (900001, 'medical_problem', 'Hypertension', '2023-01-15 00:00:00', 1, @cond1_uuid),
  (900002, 'medical_problem', 'Seasonal Allergies', '2024-03-01 00:00:00', 1, @cond2_uuid)
ON DUPLICATE KEY UPDATE `uuid` = VALUES(`uuid`);

INSERT IGNORE INTO `uuid_registry` (`uuid`, `table_name`, `table_id`, `table_vertical`, `couchdb`, `document_drive`, `mapped`, `created`)
VALUES (@cond1_uuid, 'lists', 'id', '', '', 0, 0, NOW()),
       (@cond2_uuid, 'lists', 'id', '', '', 0, 0, NOW());
