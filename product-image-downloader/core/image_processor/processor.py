"""Image processing pipeline: background removal → resize → pad → save."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image
from rembg import remove

from config import TARGET_IMAGE_SIZE

logger = logging.getLogger(__name__)


def process_and_save(
    image_bytes: bytes,
    save_path: Path,
    target_size: int = TARGET_IMAGE_SIZE,
) -> bool:
    """Run the full pipeline on raw image bytes and save the result.

    Pipeline:
        1. Background removal  (rembg)
        2. Resize keeping aspect ratio
        3. Center on white square canvas
        4. Save as PNG

    Returns True on success, False on failure.
    """
    try:
        # 1. Remove background
        result_bytes = remove(image_bytes)
        img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

        # 2. Resize – fit inside target_size × target_size
        img.thumbnail((target_size, target_size), Image.LANCZOS)

        # 3. White background canvas, center-paste
        canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 255))
        offset_x = (target_size - img.width) // 2
        offset_y = (target_size - img.height) // 2
        canvas.paste(img, (offset_x, offset_y), img)

        # 4. Convert to RGB and save
        final = canvas.convert("RGB")
        save_path.parent.mkdir(parents=True, exist_ok=True)
        final.save(str(save_path), "PNG", quality=95)
        logger.info("Saved processed image → %s", save_path)
        return True

    except Exception:
        logger.exception("Image processing failed for %s", save_path.name)
        return False
