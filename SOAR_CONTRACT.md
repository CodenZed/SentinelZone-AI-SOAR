# Phase 29 human-approved SOAR contract

Flow: advisory AI output → human analyst proposal → different operator decision → fresh policy checks → durable claim → execution → independent target-state verification → audit → optional rollback → restoration verification.

AI cannot create, approve or execute a proposal. Roles are `analyst`, `operator`, `admin`; admin is not implicitly either other role. Requester and approver IDs must differ even after a role change. Inactive/non-operator approvers invalidate execution. The dashboard must preserve each human's service identity; the service cannot determine whether two separately provisioned identities are secretly controlled by the same person.

## Actions and protection

| Action | Target | Allowed parameters |
| --- | --- | --- |
| BLOCK_IP | exact canonical literal IPv4/IPv6; no DNS, URL, CIDR, scope ID, mapped IPv4 or whitespace | `{}` or `{"lab_only":true}` |
| SUSPEND_TEST_PROCESS | registered asset, explicit inventory `lab_asset=true` or admin LAB_ASSET_IDS | exactly `lab_only=true` and `process_name` matching `test-[A-Za-z0-9_.-]{1,80}` |

No shell input, command line, arbitrary URL, executor override or provider-issued operation is accepted. Protected names, aliases, IPs, CIDRs, normalized roles and critical assets are rechecked at proposal, approval and execution. Missing/incomplete inventory fails closed; registered unclassified assets are denied. Built-in protected roles include splunk, wazuh-manager, pfsense, domain-controller, backup and admin-host. Populate real addresses and aliases in inventory/policy before use; the package does not guess lab IPs.

A proposal snapshots the playbook and pins its executor and dry-run flag. Configuration changes cannot turn an approved dry-run proposal into a live action or change its executor. Future live execution requires explicit incident `data_mode=REAL`; unknown/test/replay cannot dispatch live actions. Playbooks are bounded safe YAML graphs with mandatory ordered validation/approval/action/verification/rollback gates. No executable expressions or dynamic shell steps exist. The inherited `windows_firewall_block` playbook step name is a symbolic BLOCK_IP step, **not a live Windows firewall implementation**.

## States and durability

PROPOSED → APPROVED or REJECTED. Only a valid unexpired APPROVED proposal can acquire EXECUTING. Dispatch then becomes SUCCESS (state query true), FAILED (state query false), or UNKNOWN (uncertain result). SUCCESS/FAILED/UNKNOWN can acquire ROLLING_BACK, followed by RESTORED, ROLLBACK_FAILED or ROLLBACK_UNKNOWN. Claims left at EXECUTING/ROLLING_BACK after a crash require reconciliation.

A database compare-and-set plus unique `(proposal_id, operation)` records a claim before dispatch. Replays, concurrent calls and restarts cannot redispatch that operation. There is no auto-retry after an uncertain dispatch. This is **at-most-once dispatch per proposal/operation**, not exactly-once vendor behavior; it does not deduplicate distinct human-created proposals targeting the same IP. Restore backups without losing claim history and never delete claims to retry.

Rollback uses the pinned executor/proposal with no caller-supplied replacement target. Proposal expiry does not prohibit undoing an existing effect. A newly protected target does not block rollback of that exact existing effect, so protection can be restored; it cannot authorize a fresh containment operation. Active in-flight workers must stop before administrative reconciliation. Rollback itself has a durable claim and is not blindly retried.

## Executors

`dry_run` implements execution, separate simulator-state verification, rollback and separate restoration verification in the dedicated database. `SUCCESS`/`RESTORED` with `dry_run=true`, `effect_scope=simulated` means **no firewall or endpoint changed**.

`shuffle` and `pfsense` have explicit config and adapter classes but remain unavailable, including when credential fields are populated. `windows_firewall` is retained as a deprecated unavailable legacy selector. No real execution occurs until a vendor-specific adapter is implemented, reviewed and validated. See [docs/EXECUTOR_INTEGRATION.md](docs/EXECUTOR_INTEGRATION.md).

Real adapters must return validated `ExecutionReceipt` mappings for execute/rollback and `VerificationReport` mappings for query/verify-restored. Bare booleans/exit codes are accepted only by the legacy simulator interface. Reports must match proposal, target, action, operation, dry-run mode and query freshness. Any uncertain response remains UNKNOWN and retains the claim. Network timeouts are bounded; remote side effects can outlive a timeout, so never infer failure from a lost response.

The audit trail is append-only through service APIs, not cryptographically tamper-proof against a DB administrator. The API exposes recent audit entries and persists all rows. Approval/claim/result/reconciliation entries survive normal restart. Back up this database independently of Core.
