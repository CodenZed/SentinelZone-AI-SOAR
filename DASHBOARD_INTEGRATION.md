# Web interface integration

This release includes its own frontend and does not require an existing dashboard. If an organization embeds the API in another UI, use a server-side proxy with a fixed upstream URL, per-user identity mapping, same-origin CSRF checks, no browser-forwarded service token, bounded requests, `cache: no-store`, and no automatic mutation retries.

The shipped frontend is a static same-origin client served by the `frontend` Compose service. It calls only `/v1/*` product routes and displays mode, validation, simulation, verification, and audit state explicitly. No service token is stored in localStorage, HTML, source maps, or client configuration.
