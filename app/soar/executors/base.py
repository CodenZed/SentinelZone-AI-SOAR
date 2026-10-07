from abc import ABC, abstractmethod

from app.errors import DependencyUnavailable


class ActionExecutor(ABC):
    """Four operations: execute, query effect, rollback, query restored state.

    Real adapters return an ExecutionReceipt mapping from execute/rollback and a
    VerificationReport mapping from verify. proposal_id + operation is the stable
    remote idempotency key. Never retry mutating dispatch; timeout means UNKNOWN.
    They must honor cancellation, bound network I/O, keep TLS verification on,
    reject redirects, and query only administrator-configured vendor endpoints.
    """

    name = "abstract"
    dry_run = False

    @abstractmethod
    async def execute(self, proposal): ...

    @abstractmethod
    async def verify(self, proposal, *, restored=False): ...

    @abstractmethod
    async def rollback(self, proposal): ...

    async def health(self):
        return "healthy"


class UnavailableExecutor(ActionExecutor):
    """Explicit integration seam. Selecting an unimplemented executor fails closed."""

    def __init__(self, name):
        self.name = name

    async def execute(self, proposal):
        raise DependencyUnavailable("real_executor_not_implemented")

    async def verify(self, proposal, *, restored=False):
        raise DependencyUnavailable("real_executor_not_implemented")

    async def rollback(self, proposal):
        raise DependencyUnavailable("real_executor_not_implemented")

    async def health(self):
        return "unavailable"
