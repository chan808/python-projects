"""Background removal + 1000×1000 resize pipeline for downloaded product images."""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image
from rembg import remove

logger = logging.getLogger(__name__)

TARGET_SIZE = 1000
_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _process_bytes(image_bytes: bytes, target_size: int) -> bytes | None:
    try:
        result = remove(image_bytes)
        img = Image.open(io.BytesIO(result)).convert("RGBA")
        img.thumbnail((target_size, target_size), Image.LANCZOS)
        canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 255))
        canvas.paste(img, ((target_size - img.width) // 2, (target_size - img.height) // 2), img)
        buf = io.BytesIO()
        canvas.convert("RGB").save(buf, "PNG", quality=95)
        return buf.getvalue()
    except Exception:
        logger.exception("Image processing failed")
        return None


def process_downloaded_images(local_paths: list[str], target_size: int = TARGET_SIZE) -> list[str]:
    """배경 제거 + 리사이즈 처리. 원본 옆 processed/ 폴더에 PNG로 저장.
    Returns list of processed file paths."""
    if not local_paths:
        return []

    processed: list[str] = []
    for path_str in local_paths:
        src = Path(path_str)
        if not src.exists() or src.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue

        dest_dir = src.parent / "processed"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.with_suffix(".png").name

        if dest.exists():
            processed.append(str(dest))
            continue

        result_bytes = _process_bytes(src.read_bytes(), target_size)
        if result_bytes:
            dest.write_bytes(result_bytes)
            processed.append(str(dest))
            logger.info("Processed → %s", dest)

    return processed
