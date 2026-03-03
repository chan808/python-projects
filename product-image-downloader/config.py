"""Global configuration for image-extractor."""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
DESKTOP_PATH = Path(os.path.expanduser("~/Desktop"))
OUTPUT_BASE_DIR = DESKTOP_PATH  # {DESKTOP}/{brand}/{product_code}/

# ── Image processing ──────────────────────────────────────────────────
TARGET_IMAGE_SIZE = 1000  # px, square

# ── Selenium / HTTP ───────────────────────────────────────────────────
SELENIUM_PAGE_TIMEOUT = 20  # seconds
SELENIUM_IMPLICIT_WAIT = 5
REQUEST_TIMEOUT = 30  # seconds for image download
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

# ── Logging ───────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
