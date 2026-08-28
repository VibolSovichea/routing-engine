import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

from app.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id:
            record.request_id = request_id
        return True


def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = False
        lg = logging.getLogger(name)
        lg.addHandler(handler)
        lg.setLevel(settings.log_level.upper())
