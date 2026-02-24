from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openemr_fhir_url: str = "http://openemr/apis/default/fhir"
    openemr_token_url: str = "http://openemr/oauth2/default/token"
    openemr_client_id: str = ""
    private_key_path: str = "/app/certs/private_key.pem"
    anthropic_api_key: str = ""
    escalation_phone: str = "555-0199"

    # Telemetry (PRD §6.2) - OTLP endpoint for Datadog/CloudWatch. Empty = console exporter.
    otel_exporter_otlp_endpoint: str = ""


settings = Settings()
