from pathlib import Path
from typing import Optional

from selenium import webdriver

from utils.debug_helper import save_html_snapshot


class BaseScraper:
    requires_driver = True

    def __init__(self, driver: Optional[webdriver.Chrome], config: dict):
        self.driver = driver
        self.config = config

    def parse_category(self, category_name: str, url: str):
        raise NotImplementedError

    def _detect_block_reason(self, html: str) -> Optional[str]:
        html_lower = html.lower()

        if "403 forbidden" in html_lower or "error 403" in html_lower:
            return "http_403"
        if "access denied" in html_lower:
            return "access_denied"
        if "captcha" in html_lower or "cf-chl" in html_lower:
            return "captcha_or_challenge"
        if "just a moment" in html_lower and "cloudflare" in html_lower:
            return "cloudflare_challenge"
        if "page unavailable" in html_lower and "reference id" in html_lower:
            return "akamai_block"
        if "id=" in html_lower and "ip=" in html_lower and "date/time=" in html_lower:
            return "generic_waf_block"

        return None

    def _save_snapshot(self, category_name: str, html: str, reason: str) -> Path:
        project_root = Path(self.config.get("project_root", "."))
        brand_id = self.config.get("brand", {}).get("id", "unknown")
        return save_html_snapshot(project_root, brand_id, category_name, html, reason)

    def _check_html_or_raise(self, category_name: str, html: str, products: list) -> None:
        block_reason = self._detect_block_reason(html)
        if block_reason:
            snapshot_path = self._save_snapshot(category_name, html, block_reason)
            raise RuntimeError(f"차단 페이지가 감지되었습니다 ({block_reason}): {snapshot_path}")

        if not products:
            snapshot_path = self._save_snapshot(category_name, html, "no_products")
            raise RuntimeError(f"상품을 찾지 못했습니다. HTML 저장: {snapshot_path}")
