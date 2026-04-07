"""
Centralized logging configuration for the risk evaluation assistant.
Import this module in any file to get a consistent logger.

Usage:
    from logger_config import get_logger
    logger = get_logger(__name__)
    logger.info("Your message here")
"""

import logging
import sys

# Global logging configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Track if logging has been configured to avoid duplicate handlers
_logging_configured = False


def setup_logging(level: int = LOG_LEVEL) -> None:
    """
    Configure logging for the entire application.
    This should be called once at application startup.
    
    Args:
        level: Logging level (default: logging.INFO)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

    _logging_configured = True


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        level: Optional logging level override
        
    Returns:
        Configured logger instance
    """
    # Ensure logging is configured
    setup_logging()

    logger = logging.getLogger(name)

    if level is not None:
        logger.setLevel(level)

    return logger
