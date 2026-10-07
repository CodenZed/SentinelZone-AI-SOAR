# Architecture

The product is composed as a standalone service. External sources submit normalized events or incidents to the product API; optional adapters translate verified upstream contracts at the boundary. The product never reads another application's database or imports its ORM.

```text
REST / Webhook / Wazuh* / Splunk* / SentinelZone*
                         │
                  Connector boundary
                         │
              normalized evidence repository
                         │
              PostgreSQL + Alembic migrations
                   ┌─────┴─────┐
             AI investigation   SOAR engine
                   └─────┬─────┘
                 standalone web UI
```

`*` denotes an optional adapter. Generic REST and webhook ingestion are implemented. Wazuh and Splunk are skeletons marked NOT IMPLEMENTED. SentinelZone is a read-only, contract-tested adapter marked UNVERIFIED until a real deployment is checked.

The `EvidenceRepository` port in `app/repositories/base.py` isolates AI and SOAR from transport. `SQLEvidenceRepository` reads product-owned incidents, events, memberships, and assets. The adapter at `app/connectors/sentinelzone/` is selected only with explicit configuration.

The additive migration `0003_standalone` introduces tenants, assets, incidents, evidence events, incident-event membership, browser sessions, password hashes, and bootstrap state. Migrations `0001` and `0002` remain intact so historical AI/SOAR claims are not discarded.

AI runs persist a bounded redacted context and structured output. SOAR records a proposal, independent approval, durable execution claim, executor outcome, verification report, rollback claim, restoration verification, and audit events. Claims are at-most-once per proposal and operation.
