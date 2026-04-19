from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models import AppConfig, ProductInput
from app.utils.text_normalizer import normalize_brand_name

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ImageDiscoveryError(RuntimeError):
    """Raised when product images cannot be resolved."""


@dataclass
class ProductImages:
    directory: Path
    files: list[Path]


class ImageService:
    def __init__(self, config: AppConfig):
        self.config = config

    def collect_product_images(self, product: ProductInput) -> ProductImages:
        brand_dir = normalize_brand_name(product.brand_name, self.config.brand_aliases)
        image_dir = self.config.paths.register_pic_root / brand_dir / product.product_code

        if not image_dir.exists():
            raise ImageDiscoveryError(f"Image directory does not exist: {image_dir}")
        if not image_dir.is_dir():
            raise ImageDiscoveryError(f"Image path is not a directory: {image_dir}")

        image_files = sorted(
            path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        if not image_files:
            raise ImageDiscoveryError(f"No image files found in: {image_dir}")

        return ProductImages(directory=image_dir, files=image_files)
