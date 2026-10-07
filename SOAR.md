# SOAR safety

The state machine is proposal → independent approval → execution claim → executor result → state verification → optional rollback claim → restoration verification. A proposal pins its playbook and executor. Approval requires an active Operator different from the requester. Expiry and protected-target policy are checked again immediately before execution.

Fresh installations use `dry_run`. Its `WOULD EXECUTE` and `WOULD ROLLBACK` receipts manipulate only the product simulator and are labeled `DRY RUN`; they never change firewall, endpoint, network, account, or production state. A separate verification query checks simulator state. Durable unique `(proposal_id, operation)` claims prevent blind retries after crashes. This is at-most-once application dispatch, not exactly-once remote semantics.

pfSense, Shuffle, and generic webhook plugins are disabled/unverified. A real plugin must provide an exact contract, protected-target checks, ownership-aware rollback, state verification, timeout reconciliation, and tests before it can be enabled.
