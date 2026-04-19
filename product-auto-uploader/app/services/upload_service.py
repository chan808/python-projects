from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.models import AppConfig, ProductInput, UploadResult
from app.services.image_service import ImageService
from app.uploaders.mustit import MustitUploader


class UploadService:
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.image_service = ImageService(config)

    def run(self, product: ProductInput) -> tuple[UploadResult, Path]:
        started_at = datetime.now(timezone.utc)

        try:
            product_images = self.image_service.collect_product_images(product)
            self.logger.info("Resolved %s image(s) from %s", len(product_images.files), product_images.directory)

            uploader = MustitUploader(self.config, self.logger)
            result = uploader.run(product, product_images)
            result.details.update(
                {
                    "image_dir": str(product_images.directory),
                    "image_count": len(product_images.files),
                }
            )
        except Exception as exc:
            self.logger.exception("Upload failed before completion.")
            result = UploadResult(
                site="mustit",
                product_code=product.product_code,
                success=False,
                submit_mode=product.submit_mode,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                message=str(exc),
            )

        result_path = self._write_result(result)
        return result, result_path

    def _write_result(self, result: UploadResult) -> Path:
        timestamp = result.finished_at.strftime("%Y%m%d-%H%M%S")
        file_name = f"{timestamp}-{result.site}-{result.product_code}.json"
        output_path = self.config.paths.output_dir / file_name
        output_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path
