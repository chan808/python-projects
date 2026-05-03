from __future__ import annotations

import argparse
from pathlib import Path

from app.config import load_config
from app.services.excel_service import load_products_from_excel
from app.services.upload_service import UPLOADER_CLASSES, UploadService
from app.utils.logging_utils import setup_logger


def main() -> int:
    args = _parse_args()
    config = load_config()
    logger = setup_logger(config.paths.logs_dir)

    if args.prepare_login:
        site = args.prepare_login
        if site not in UPLOADER_CLASSES:
            print(f"알 수 없는 사이트: {site}. 선택 가능: {', '.join(UPLOADER_CLASSES)}")
            return 1
        try:
            message = UPLOADER_CLASSES[site](config, logger).prepare_login_session()
            print(f"success=True\nmessage={message}")
            return 0
        except Exception as exc:
            logger.exception("로그인 세션 준비 실패")
            print(f"success=False\nmessage={exc}")
            return 1

    excel_path = Path(args.excel)
    if not excel_path.exists():
        print(f"엑셀 파일 없음: {excel_path}")
        return 1

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    invalid = [s for s in sites if s not in UPLOADER_CLASSES]
    if invalid:
        print(f"알 수 없는 사이트: {invalid}")
        return 1

    products = load_products_from_excel(excel_path)
    if not products:
        print("엑셀에서 유효한 상품을 찾지 못했습니다.")
        return 1

    if args.submit_mode == "preview":
        products = products[:1]

    service = UploadService(config, logger)
    results = service.run_batch(products, sites, args.submit_mode)

    success = sum(1 for r in results if r.success)
    print(f"완료: 성공 {success}건 / 실패 {len(results) - success}건")
    return 0 if all(r.success for r in results) else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Product auto uploader CLI")
    parser.add_argument("--excel", help="엑셀 파일 경로")
    parser.add_argument("--sites", default="mustit,trenbe,fillway", help="업로드 사이트 (쉼표 구분)")
    parser.add_argument("--submit-mode", choices=["preview", "submit"], default="preview")
    parser.add_argument("--prepare-login", metavar="SITE", help="로그인 세션 준비 (mustit/trenbe/fillway)")
    return parser.parse_args()
