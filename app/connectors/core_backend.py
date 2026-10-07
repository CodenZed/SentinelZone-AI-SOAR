"""Deprecated imports for v0.29 extensions; optional SentinelZone adapter only."""
from app.repositories.base import EvidenceRepository as CoreBackendClient, canonical  # noqa: F401
from app.connectors.sentinelzone.client import MockCoreBackendClient, RealCoreBackendClient  # noqa: F401
