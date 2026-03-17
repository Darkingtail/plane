"""
Logging configuration
"""

import logging
import logging.handlers
from pathlib import Path

from app.core.config import settings


class HealthCheckFilter(logging.Filter):
    """Filter out health check endpoint logs to reduce noise"""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "args") and len(record.args) >= 1:
            message = record.getMessage()
            if "GET /health" in message and "200 OK" in message:
                return False
        return True


def setup_logging():
    """Configure application logging"""

    log_file_path = Path(settings.log_file)
    log_file_path.parent.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.handlers.RotatingFileHandler(settings.log_file, maxBytes=10 * 1024 * 1024, backupCount=5),
        ],
    )

    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.setLevel(logging.INFO)

    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")
