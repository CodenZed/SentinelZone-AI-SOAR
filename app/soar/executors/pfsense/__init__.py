"""Reserved, disabled plugin. Live vendor contract NOT VERIFIED."""
from app.soar.executors.base import UnavailableExecutor


class PfSenseExecutor(UnavailableExecutor):
    def __init__(self, config):
        super().__init__('pfsense')
        self.config = config
