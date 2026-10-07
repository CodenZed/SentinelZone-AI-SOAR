"""No generic arbitrary URL dispatch: a verified effect/rollback contract is required."""
from app.soar.executors.base import UnavailableExecutor


class GenericWebhookExecutor(UnavailableExecutor):
    def __init__(self):
        super().__init__('generic_webhook')
