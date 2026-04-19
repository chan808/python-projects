from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(logs_dir: Path) -> logging.Logger:
    logger = logging.getLogger("product_auto_uploader")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file = logs_dir / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
