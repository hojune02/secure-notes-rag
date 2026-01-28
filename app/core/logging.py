import logging
import sys

LOG_FORMAT = (
    "ts=%(asctime)s level=%(levelname)s logger=%(name)s "
    "msg=%(message)s"
)

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
        format=LOG_FORMAT,
    )
