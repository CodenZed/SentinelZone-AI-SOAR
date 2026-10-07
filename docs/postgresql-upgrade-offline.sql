BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE action_proposals (
    proposal_id VARCHAR(128) NOT NULL,
    tenant_id VARCHAR(128) NOT NULL,
    incident_id VARCHAR(128) NOT NULL,
    action_type VARCHAR(60) NOT NULL,
    target VARCHAR(128) NOT NULL,
    parameters JSON NOT NULL,
    requested_by VARCHAR(128) NOT NULL,
    approved_by VARCHAR(128),
    status VARCHAR(40) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    playbook_id VARCHAR(128) NOT NULL,
    playbook_snapshot JSON NOT NULL,
    rollback_available BOOLEAN NOT NULL,
    dry_run BOOLEAN NOT NULL,
    PRIMARY KEY (proposal_id)
);

CREATE INDEX ix_action_proposals_incident_id ON action_proposals (incident_id);

CREATE INDEX ix_action_proposals_tenant_id ON action_proposals (tenant_id);

CREATE TABLE ai_runs (
    run_id VARCHAR(128) NOT NULL,
    tenant_id VARCHAR(128) NOT NULL,
    incident_id VARCHAR(128) NOT NULL,
    requested_by VARCHAR(128) NOT NULL,
    provider VARCHAR(40) NOT NULL,
    model VARCHAR(128) NOT NULL,
    status VARCHAR(40) NOT NULL,
    validation_status VARCHAR(40) NOT NULL,
    error_code VARCHAR(100),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    context_snapshot JSON NOT NULL,
    PRIMARY KEY (run_id)
);

CREATE INDEX ix_ai_runs_incident_id ON ai_runs (incident_id);

CREATE INDEX ix_ai_runs_tenant_id ON ai_runs (tenant_id);

CREATE TABLE service_users (
    id VARCHAR(128) NOT NULL,
    tenant_id VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    active BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (tenant_id, name),
    UNIQUE (token_hash)
);

CREATE INDEX ix_service_users_tenant_id ON service_users (tenant_id);

CREATE TABLE action_approvals (
    proposal_id VARCHAR(128) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    decision VARCHAR(40) NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (proposal_id),
    FOREIGN KEY(proposal_id) REFERENCES action_proposals (proposal_id)
);

CREATE TABLE action_audit (
    id VARCHAR(128) NOT NULL,
    tenant_id VARCHAR(128) NOT NULL,
    proposal_id VARCHAR(128),
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(80) NOT NULL,
    detail JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(proposal_id) REFERENCES action_proposals (proposal_id)
);

CREATE INDEX ix_action_audit_proposal_id ON action_audit (proposal_id);

CREATE INDEX ix_action_audit_tenant_id ON action_audit (tenant_id);

CREATE TABLE action_executions (
    id VARCHAR(128) NOT NULL,
    proposal_id VARCHAR(128) NOT NULL,
    operation VARCHAR(20) NOT NULL,
    status VARCHAR(40) NOT NULL,
    executor VARCHAR(40) NOT NULL,
    result JSON NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(proposal_id) REFERENCES action_proposals (proposal_id),
    UNIQUE (proposal_id, operation)
);

CREATE INDEX ix_action_executions_proposal_id ON action_executions (proposal_id);

CREATE TABLE ai_analyses (
    run_id VARCHAR(128) NOT NULL,
    output JSON NOT NULL,
    trusted BOOLEAN NOT NULL,
    validation JSON NOT NULL,
    PRIMARY KEY (run_id),
    FOREIGN KEY(run_id) REFERENCES ai_runs (run_id)
);

CREATE TABLE ai_steps (
    id VARCHAR(128) NOT NULL,
    run_id VARCHAR(128) NOT NULL,
    sequence INTEGER NOT NULL,
    stage VARCHAR(80) NOT NULL,
    evidence_ids JSON NOT NULL,
    tool_name VARCHAR(80) NOT NULL,
    output_ref VARCHAR(256) NOT NULL,
    duration_ms INTEGER NOT NULL,
    status VARCHAR(40) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(run_id) REFERENCES ai_runs (run_id),
    UNIQUE (run_id, sequence)
);

CREATE INDEX ix_ai_steps_run_id ON ai_steps (run_id);

CREATE TABLE simulated_effects (
    proposal_id VARCHAR(128) NOT NULL,
    active BOOLEAN NOT NULL,
    target VARCHAR(128) NOT NULL,
    action_type VARCHAR(60) NOT NULL,
    PRIMARY KEY (proposal_id),
    FOREIGN KEY(proposal_id) REFERENCES action_proposals (proposal_id)
);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

ALTER TABLE action_proposals ADD COLUMN executor VARCHAR(40) DEFAULT 'dry_run' NOT NULL;

UPDATE action_proposals SET executor = 'legacy_unbound' WHERE dry_run = false;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;
