# Future Shuffle / pfSense adapter gate

Current classes: `ShuffleExecutor`, `PfSenseExecutor` in `app/soar/executors/factory.py`. Both inherit an unavailable implementation: health=unavailable, execute/verify/rollback fail closed. Configuring credentials or URLs does not enable them. Exact vendor API/version/auth/workflow contracts were not supplied and no endpoints are invented.

## Administrator-only configuration

| Adapter | Fields |
| --- | --- |
| shuffle | SHUFFLE_URL, SHUFFLE_API_KEY, SHUFFLE_WORKFLOW_ID, SHUFFLE_CA_FILE |
| pfsense | PFSENSE_URL, PFSENSE_API_TOKEN, PFSENSE_API_CONTRACT, PFSENSE_CA_FILE |
| common | EXECUTOR_TIMEOUT_SECONDS, SOAR_EXECUTOR |

Use `ExternalExecutorConfig` as the typed config seam. Credentials are excluded from serialization. No config is taken from proposal parameters. HTTPS, internal CA and no redirects are required for a future real adapter. Fixed administrator endpoints/workflow IDs must be validated before activation.

## Required implementation

1. `execute(proposal)`: implement an allowlisted action, create an owned vendor effect, and return `ExecutionReceipt` (`proposal_id`, `operation=execute`, remote operation ID, `dry_run=false`, aware `accepted_at`). Receipt acceptance is not containment verification.
2. `verify(proposal, restored=False)`: query authoritative target state independently, proving the **owned effect** on the correct target. Return `VerificationReport`: proposal/target/action, restored flag, verified flag, dry-run flag, aware `queried_at`, bounded sanitized observation and query reference. Do not use only a workflow completion or command exit code.
3. `rollback(proposal)`: remove/restore only this proposal's owned effect and return an operation=rollback receipt. Preserve rules/process changes that existed before this action and those owned by other proposals/operators. Prevent duplicate overlapping proposals from undoing each other's containment.
4. `verify(proposal, restored=True)`: independently query that the owned effect is removed and the original target state is restored. Absence of an API error is insufficient.
5. Read-only reconciliation: locate remote operation/effect by stable proposal ID after crashes/timeouts, compare state and append audit without a new mutation. Stop workers for manual recovery. Never clear a durable claim to retry.

Use `proposal_id + operation` as the remote idempotency key where the platform supports it. The orchestrator commits its claim first and never retries mutating dispatch. This is not exactly-once semantics. The adapter must not introduce internal HTTP mutation retries. Observe cancellation/timeouts without assuming the vendor canceled its side effect.

Supply the exact installed pfSense API package/version or Shuffle workflow definition, request/response examples with credentials removed, auth mechanism, effect ownership query, rollback semantics and restored-state query before implementation. A process suspend adapter additionally needs stable process identity/start time (not only a reusable PID), process ownership and a safe resume query.

## Acceptance before enabling live dispatch

Test in an isolated authorized lab: independent approval, protected target at all three gates, forged/expired scope denial, execute timeout before/after effect, duplicate network delivery, restart, independent verification mismatch, rollback failure/timeout, restoration, concurrent same-target proposals, pre-existing effect preservation and credential/error redaction. No such live tests passed in this release because no live adapter is implemented.
