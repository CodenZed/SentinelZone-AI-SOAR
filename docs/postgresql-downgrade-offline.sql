BEGIN;

-- Running downgrade 0002 -> 0001

ALTER TABLE action_proposals DROP COLUMN executor;

UPDATE alembic_version SET version_num='0001' WHERE alembic_version.version_num = '0002';

-- Running downgrade 0001 ->

DROP TABLE simulated_effects;

DROP INDEX ix_ai_steps_run_id;

DROP TABLE ai_steps;

DROP TABLE ai_analyses;

DROP INDEX ix_action_executions_proposal_id;

DROP TABLE action_executions;

DROP INDEX ix_action_audit_tenant_id;

DROP INDEX ix_action_audit_proposal_id;

DROP TABLE action_audit;

DROP TABLE action_approvals;

DROP INDEX ix_service_users_tenant_id;

DROP TABLE service_users;

DROP INDEX ix_ai_runs_tenant_id;

DROP INDEX ix_ai_runs_incident_id;

DROP TABLE ai_runs;

DROP INDEX ix_action_proposals_tenant_id;

DROP INDEX ix_action_proposals_incident_id;

DROP TABLE action_proposals;

DELETE FROM alembic_version WHERE alembic_version.version_num = '0001';

COMMIT;
