from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type

from app.models import AppConfig, ProductInput, UploadResult
from app.services.image_service import ImageDiscoveryError, ImageService, ProductImages
from app.services.pricing_service import PricingService
from app.uploaders.base import PlaywrightUploader
from app.uploaders.fillway import FilwayUploader
from app.uploaders.mustit import MustitUploader
from app.uploaders.trenbe import TrenbeUploader

UPLOADER_CLASSES: Dict[str, Type[PlaywrightUploader]] = {
    "mustit": MustitUploader,
    "trenbe": TrenbeUploader,
    "fillway": FilwayUploader,
}


class UploadService:
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.image_service = ImageService(config)
        self.pricing_service = PricingService(config.pricing_path)

    def run_batch(
        self,
        products: List[ProductInput],
        sites: List[str],
        submit_mode: str,
        on_progress: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> List[UploadResult]:
        uploaders = {site: UPLOADER_CLASSES[site](self.config, self.logger) for site in sites}
        results: List[UploadResult] = []
        total = len(products) * len(sites)
        done = 0

        for product in products:
            product = product.model_copy(update={"submit_mode": submit_mode})
            try:
                product_images = self.image_service.collect_product_images(product)
            except ImageDiscoveryError as exc:
                self.logger.warning("이미지 폴더 없음, 이미지 없이 진행 (%s): %s", product.product_code, exc)
                product_images = ProductImages(directory=Path(), files=[])

            for site in sites:
                if on_progress:
                    on_progress(done, total, product.product_code, site)
                site_price = self.pricing_service.calculate(site, product.price)
                product_for_site = product.model_copy(update={"price": site_price})
                result = uploaders[site].run(product_for_site, product_images)
                self._write_result(result)
                results.append(result)
                done += 1

        return results

    def _make_error_result(self, site: str, product: ProductInput, message: str) -> UploadResult:
        now = datetime.now(timezone.utc)
        return UploadResult(
            site=site,
            product_code=product.product_code,
            success=False,
            submit_mode=product.submit_mode,
            started_at=now,
            finished_at=now,
            message=message,
        )

    def _write_result(self, result: UploadResult) -> Path:
        timestamp = result.finished_at.strftime("%Y%m%d-%H%M%S")
        file_name = f"{timestamp}-{result.site}-{result.product_code}.json"
        output_path = self.config.paths.output_dir / file_name
        output_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path
