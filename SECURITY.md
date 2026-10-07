# Security model

The product is designed for least privilege and human control. It owns a separate database; no Core/SIEM credentials or ORM models are reused. Passwords use salted PBKDF2-SHA256. Browser sessions are opaque, hashed in the database, expiring, HttpOnly, SameSite=Strict, and paired with a CSRF token. Tokens are never returned to the web page or logged.

Requests have bounded bodies and provider/dependency responses. External HTTPS verifies certificates, disallows redirects, and rejects credentials embedded in URLs. Source strings are escaped in the UI. AI input is redacted and has no action authority. Audit records are tenant-scoped and append-only through application paths; a database owner can still alter them.

Report vulnerabilities privately to the repository maintainers. Do not include live tokens, private telemetry, database dumps, or certificates in issues. See `KNOWN_LIMITATIONS.md` for deployment gates.
