"""Reserved, disabled plugin. Live workflow contract NOT VERIFIED."""
from app.soar.executors.base import UnavailableExecutor


class ShuffleExecutor(UnavailableExecutor):
    def __init__(self, config):
        super().__init__('shuffle')
        self.config = config
