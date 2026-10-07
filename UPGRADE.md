# Upgrade

Read the release notes, back up the dedicated database, stop all workers, extract the new release beside the old one, copy only reviewed private configuration, install the locked dependencies, then run `python -m alembic upgrade head` and `python -m alembic check`.

Migration `0003_standalone` is additive. It preserves the v0.29.x AI/SOAR tables and historical claims while adding product-owned tenants, evidence, incidents, assets, browser sessions, and bootstrap state. Downgrading to `base` drops tables and is for disposable development databases only. Old non-dry-run claims remain historical and cannot be executed by the disabled live plugins.
