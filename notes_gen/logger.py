import sys

from loguru import logger


def setup_logger(verbose: bool = False):
    """Configure loguru for the application."""
    logger.remove()  # Remove default handler

    # Standard output format
    fmt = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if verbose:
        logger.add(sys.stderr, level="DEBUG", format=fmt)
    else:
        logger.add(sys.stderr, level="INFO", format=fmt)


# Default setup
setup_logger(False)
