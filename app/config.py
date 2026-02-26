from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openemr_fhir_url: str = "http://openemr/apis/default/fhir"
    openemr_token_url: str = "http://openemr/oauth2/default/token"
    openemr_client_id: str = ""
    private_key_path: str = "/app/certs/private_key.pem"
    anthropic_api_key: str = ""
    escalation_phone: str = "555-0199"

    # When False, patient chat allows unauthenticated access (for dev until auth is ready).
    # Set to True when OAuth/patient auth is configured.
    patient_auth_required: bool = True

    # When False, staff chat allows unauthenticated access (for dev until auth is ready).
    # Set to True when OAuth/staff auth is configured.
    staff_auth_required: bool = True

    # Telemetry (PRD §6.2) - OTLP endpoint for Datadog/CloudWatch. Empty = console exporter.
    otel_exporter_otlp_endpoint: str = ""

    # Demo: include tool calls in chat response for UI debug box. Set to True to enable.
    debug_tool_calls: bool = False

    # When True, agent tools use mock data from app/data/mock_data.py.
    # When False, tools use live OpenEMR FHIR API. Set USE_MOCK_DATA=false to switch.
    use_mock_data: bool = False

    # Demo: default patient_id/staff_id when request omits them (e.g. unauthenticated dev).
    # In production, resolve from OAuth token claims.
    default_patient_id: str | None = None
    default_staff_id: str | None = None


settings = Settings()
