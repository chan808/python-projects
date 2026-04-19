from __future__ import annotations

import argparse
from typing import Optional

from pydantic import ValidationError

from app.config import load_config, save_last_product
from app.models import ProductInput
from app.services.upload_service import UploadService
from app.uploaders.mustit import MustitUploader
from app.utils.logging_utils import setup_logger


def main() -> int:
    args = _parse_args()
    config = load_config()
    logger = setup_logger(config.paths.logs_dir)

    if args.prepare_login:
        uploader = MustitUploader(config, logger)
        try:
            message = uploader.prepare_login_session()
        except Exception as exc:
            logger.exception("Failed to prepare login session.")
            print("success=False")
            print("message=%s" % exc)
            return 1
        print("success=True")
        print("message=%s" % message)
        return 0

    try:
        product = ProductInput(
            category=_read_value(args.category, "카테고리"),
            brand_name=_read_value(args.brand_name, "브랜드명"),
            product_code=_read_value(args.product_code, "상품번호"),
            product_name=_read_value(args.product_name, "제품명"),
            price=int(_read_value(args.price, "가격")),
            submit_mode=args.submit_mode,
        )
    except (ValidationError, ValueError) as exc:
        logger.error("Invalid input: %s", exc)
        return 1

    save_last_product(
        {
            "category": product.category,
            "brand_name": product.brand_name,
            "product_code": product.product_code,
            "product_name": product.product_name,
            "price": str(product.price),
            "submit_mode": product.submit_mode,
        }
    )

    service = UploadService(config, logger)
    result, result_path = service.run(product)

    print("success=%s" % result.success)
    print("message=%s" % result.message)
    print("result_path=%s" % result_path)
    if result.screenshot_path:
        print("screenshot_path=%s" % result.screenshot_path)

    return 0 if result.success else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mustit product uploader MVP")
    parser.add_argument("--category")
    parser.add_argument("--brand-name")
    parser.add_argument("--product-code")
    parser.add_argument("--product-name")
    parser.add_argument("--price")
    parser.add_argument("--submit-mode", choices=["preview", "submit"], default="preview")
    parser.add_argument("--prepare-login", action="store_true")
    return parser.parse_args()


def _read_value(current_value: Optional[str], label: str) -> str:
    if current_value is not None:
        return current_value
    return input("%s: " % label).strip()
