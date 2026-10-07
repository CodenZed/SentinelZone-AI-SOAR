from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field("sqlite:///./sentinelzone_ai_soar.db", repr=False)
    core_mode: Literal["standalone", "mock", "real"] = "standalone"
    core_api_url: str = ""
    core_api_token: str = Field("", repr=False)
    core_api_ca_file: str = ""
    core_tenant_id: str = Field("", min_length=0, max_length=128, pattern=r"^[A-Za-z0-9_.:-]*$")
    core_single_tenant_ack: bool = False
    core_max_pages: int = Field(100, ge=1, le=1000)
    core_max_items: int = Field(20000, ge=500, le=100000)
    ai_provider: Literal["mock", "openai", "local", "openai_compatible", "ollama"] = "mock"
    public_origin: str = "http://localhost:8080"
    cookie_secure: bool = True
    session_hours: int = Field(8, ge=1, le=24)
    bootstrap_token: str = Field("", repr=False)
    enable_demo: bool = False
    ollama_url: str = ""
    ollama_model: str = ""
    openai_api_key: str = Field("", repr=False)
    openai_model: str = ""
    openai_api_url: str = "https://api.openai.com/v1"
    local_ai_url: str = ""
    local_ai_model: str = ""
    local_ai_token: str = Field("", repr=False)
    local_ai_ca_file: str = ""
    allow_insecure_http: bool = False
    # Exact hosts, never wildcard/CIDR. Non-loopback HTTP only in development/test.
    trusted_http_hosts: str = ""
    http_timeout_seconds: float = Field(15, gt=0, le=120)
    provider_timeout_seconds: float = Field(60, gt=0, le=300)
    executor_timeout_seconds: float = Field(60, gt=0, le=300)
    max_response_bytes: int = Field(2_000_000, ge=1000, le=10_000_000)
    max_evidence: int = Field(20, ge=1, le=100)
    max_context_chars: int = Field(32000, ge=4000, le=100000)
    max_request_bytes: int = Field(64000, ge=1024, le=1000000)
    soar_executor: Literal["dry_run", "shuffle", "pfsense", "windows_firewall", "generic_webhook"] = "dry_run"
    shuffle_url: str = ""
    shuffle_api_key: str = Field("", repr=False)
    shuffle_workflow_id: str = ""
    shuffle_ca_file: str = ""
    pfsense_url: str = ""
    pfsense_api_token: str = Field("", repr=False)
    pfsense_ca_file: str = ""
    pfsense_api_contract: str = ""
    fixture_dir: Path = ROOT / "fixtures"
    playbook_dir: Path = ROOT / "playbooks"
    protected_assets: str = "splunk,wazuh-manager,pfsense,domain-controller,backup,admin-host"
    protected_networks: str = ""
    # Required for process suspension in addition to the registered asset and test- prefix.
    lab_asset_ids: str = ""
    policy_file: Path = ROOT / "config" / "policy.yml"

    @model_validator(mode="after")
    def validate_deployment(self):
        from urllib.parse import urlsplit
        origin = urlsplit(self.public_origin)
        if origin.scheme not in {'http', 'https'} or not origin.hostname or origin.username or origin.password:
            raise ValueError('public origin must be an HTTP(S) origin without credentials')
        if origin.path not in {'', '/'} or origin.query or origin.fragment:
            raise ValueError('public origin must not include a path, query, or fragment')
        if not self.cookie_secure and origin.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('insecure cookies are permitted only on a loopback origin')
        url = make_url(self.database_url)
        if self.app_env == "production":
            if url.get_backend_name() != "postgresql":
                raise ValueError("production requires separate PostgreSQL")
            if not url.database or not url.username or url.username in {"postgres", "root"}:
                raise ValueError("production requires a dedicated non-superuser database role")
            if self.core_mode == "mock":
                raise ValueError("fixture context is development/test only")
        if self.bootstrap_token and len(self.bootstrap_token) < 32:
            raise ValueError("bootstrap token must contain at least 32 characters")
        if self.core_mode == "real" and not self.core_tenant_id:
            raise ValueError("optional legacy adapter requires an explicit tenant")
        if self.core_single_tenant_ack and not self.core_tenant_id:
            raise ValueError("tenant-less core acknowledgement requires an explicit tenant")
        return self
