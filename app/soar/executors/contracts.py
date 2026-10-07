"""Required receipts for future real adapters. No remote contract is invented here."""

from typing import Literal
from pydantic import AwareDatetime, Field
from app.contracts import Contract, Identifier


class ExecutionReceipt(Contract):
    proposal_id: Identifier
    operation: Literal["execute", "rollback"]
    remote_operation_id: str = Field(min_length=1, max_length=256)
    dry_run: bool
    accepted_at: AwareDatetime


class VerificationReport(Contract):
    proposal_id: Identifier
    target: str
    action_type: Literal["BLOCK_IP", "SUSPEND_TEST_PROCESS"]
    restored: bool
    verified: bool
    dry_run: bool
    queried_at: AwareDatetime
    # Sanitized observation, not raw response, exit code, or execute receipt.
    observation: str = Field(min_length=1, max_length=2000)
    query_reference: str = Field(min_length=1, max_length=256)
