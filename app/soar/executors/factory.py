"""Administrator-selected adapters. No URL, credentials or executor from request data."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.soar.executors.base import UnavailableExecutor
from app.soar.executors.dry_run import DryRunExecutor
from app.soar.executors.pfsense import PfSenseExecutor
from app.soar.executors.shuffle import ShuffleExecutor
from app.soar.executors.generic_webhook import GenericWebhookExecutor


class ExternalExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    endpoint: str = ""
    credential: SecretStr = Field(default=SecretStr(""), exclude=True)
    ca_file: str = ""
    contract_version: str = ""
    workflow_id: str = ""
    timeout_seconds: float = Field(60, gt=0, le=300)


def build_executor(settings, sessions):
    if settings.soar_executor == "dry_run":
        return DryRunExecutor(sessions)
    if settings.soar_executor == "shuffle":
        return ShuffleExecutor(
            ExternalExecutorConfig(
                endpoint=settings.shuffle_url,
                credential=settings.shuffle_api_key,
                ca_file=settings.shuffle_ca_file,
                workflow_id=settings.shuffle_workflow_id,
                timeout_seconds=settings.executor_timeout_seconds,
            )
        )
    if settings.soar_executor == "pfsense":
        return PfSenseExecutor(
            ExternalExecutorConfig(
                endpoint=settings.pfsense_url,
                credential=settings.pfsense_api_token,
                ca_file=settings.pfsense_ca_file,
                contract_version=settings.pfsense_api_contract,
                timeout_seconds=settings.executor_timeout_seconds,
            )
        )
    if settings.soar_executor == "generic_webhook":
        return GenericWebhookExecutor()
    return UnavailableExecutor(settings.soar_executor)
