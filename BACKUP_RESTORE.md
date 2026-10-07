# Backup and restore

Back up the dedicated PostgreSQL database and the private `.env`, policy, and playbooks through your approved secret/backup system. Preserve `action_executions`, `simulated_effects`, and `action_audit`; deleting them invalidates restart and reconciliation safety.

Stop workers before restoring. Restore to a disposable database first, run `python -m alembic upgrade head`, `python -m alembic check`, and inspect uncertain proposals. Never automatically re-execute an `EXECUTING`, `UNKNOWN`, `ROLLING_BACK`, or `ROLLBACK_UNKNOWN` operation after restore. Use the dry-run reconciliation command only after workers are stopped. PostgreSQL physical backup tooling and retention policy remain deployment responsibilities.
