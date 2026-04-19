from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import ProductInput, UploadResult
from app.services.image_service import ProductImages


class BaseUploader(ABC):
    @abstractmethod
    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        raise NotImplementedError
