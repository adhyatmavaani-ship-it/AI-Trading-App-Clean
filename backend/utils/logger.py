import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logging.getLogger().handlers:
        return logger

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logger
