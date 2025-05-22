import evo.logging
from evo.data_converters.duf.common import DufWrapper, ObjectCollector

logger = evo.logging.getLogger("data_converters")


class DufCollectorContext:
    def __init__(self, filepath: str):
        self._collector = ObjectCollector()

        with DufWrapper(filepath, self._collector) as instance:
            instance.LoadEverything()

    @property
    def collector(self) -> ObjectCollector:
        return self._collector

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Error during DUF collection: {exc_val}")
        return False
