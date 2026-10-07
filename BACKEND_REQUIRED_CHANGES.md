# Optional upstream contract changes

The standalone product does not require a change to another application's
backend. Its product-owned ingestion API and database are the supported path.
This document applies only when an administrator elects to enable the optional
SentinelZone adapter against a separately operated deployment.

Run the read-only preflight with a real incident before enabling that adapter.
If an upstream response differs from the verified contract, adapt
`app/connectors/sentinelzone/mapping.py` at the connector boundary. Do not add
an upstream database grant, shared ORM import, dashboard dependency, write-back
route, or vendor behavior based on guesswork.

## Minimum read-only contract

| Contract gap | Required upstream capability |
| --- | --- |
| Incident detail | Authenticated `GET /v1/incidents/{id}` with stable ID, status, priority, and summary/title |
| Event membership | Authenticated paginated timeline with event IDs and selected summaries |
| Citation lookup | Authenticated alert lookup proving event existence and tenant/incident scope |
| Asset inventory | Authenticated paginated inventory with stable IDs, aliases, addresses, role, and criticality |
| Scope | An explicit tenant identifier on returned objects, or an administrator acknowledgement bound to the configured tenant |
| Optional enrichment | Bounded telemetry, identity context, and missing-telemetry fields; no unrestricted logs or credentials |

Every returned object must be checked against the requested tenant. A foreign
tenant is treated as not found. Missing, partial, conflicting, or ambiguous
data fails closed; it never becomes fixture data and never authorizes a live
action. Data mode remains `REAL`, `TEST`, `REPLAY`, or `UNKNOWN` as supplied;
absence of telemetry remains UNKNOWN.

The adapter issues read-only GET requests, uses bounded responses and timeouts,
verifies TLS, rejects redirects, and never accepts tenant scope from event text.
The configured upstream URL, token, and tenant are administrator settings and
have no product defaults.

No live vendor or upstream contract was verified in this release. See
[CONNECTORS.md](CONNECTORS.md) and [docs/integrations/sentinelzone.md](docs/integrations/sentinelzone.md).
