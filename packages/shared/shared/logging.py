import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class JsonFormatter(logging.Formatter):
    """
    Custom logging formatter that outputs JSON structured logs.
    """
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        if hasattr(record, "extra") and isinstance(record.extra, dict): # type: ignore
            log_data.update(record.extra) # type: ignore
            
        return json.dumps(log_data)

def setup_logging(service_name: str, level: str = "INFO") -> None:
    """
    Sets up structured logging for the given service.
    """
    logger = logging.getLogger()
    logger.setLevel(level.upper())
    
    # Remove existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))
    logger.addHandler(handler)
