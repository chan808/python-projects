import json
import random
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.debug_helper import save_html_snapshot
from utils.helper import scroll_until_lazy_content_loaded


class BaseScraper:
    BASE_URL = ""
    requires_driver = True

    def __init__(self, driver: Optional[webdriver.Chrome], config: dict):
        self.driver = driver
        self.config = config

    # ── 템플릿 메서드 (Dior / LV 공통 플로우) ──────────────────────────────────
    # Bottega / Celine 등 다른 플로우가 필요한 스크레이퍼는 이 메서드를 통째로 오버라이드합니다.

    def parse_category(self, category_name: str, url: str) -> list[dict]:
        scraping_settings = self.config.get("scraping_settings", {})
        selectors = self.config["selectors"]

        self._before_navigate(scraping_settings)
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, scraping_settings.get("initial_wait_sec", 20)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(random.uniform(2.0, 5.0))
        except Exception:
            html = self.driver.page_source
            self._check_html_or_raise(category_name, html, [])
            return []

        self._dismiss_known_popups(scraping_settings)
        time.sleep(random.uniform(1.0, 2.0))

        scroll_result = scroll_until_lazy_content_loaded(
            self.driver,
            pause_time=float(scraping_settings.get("scroll_pause_time", 3.0)),
            product_card_selector=selectors["product_card"],
            placeholder_selector=selectors.get("lazy_placeholder", ""),
            max_loops=int(scraping_settings.get("max_scroll_loops", 20)),
            max_placeholder_retries=int(scraping_settings.get("max_placeholder_retries", 3)),
        )
        time.sleep(2)

        html = self.driver.page_source
        block_reason = self._detect_block_reason(html)
        if block_reason:
            snapshot_path = self._save_snapshot(category_name, html, block_reason)
            raise RuntimeError(f"차단 페이지가 감지되었습니다 ({block_reason}): {snapshot_path}")

        products = self.extract_products_from_html(html, category_name, url)

        max_products = int(scraping_settings.get("max_products_per_category", 0))
        if max_products > 0:
            products = products[:max_products]

        if not products:
            reason = "no_products_with_placeholders" if scroll_result["placeholder_count"] > 0 else "no_products"
            snapshot_path = self._save_snapshot(category_name, html, reason)
            raise RuntimeError(f"상품을 찾지 못했습니다. HTML 저장: {snapshot_path}")

        return products

    def _before_navigate(self, scraping_settings: dict) -> None:
        """Hook: 페이지 이동 직전 처리. 필요한 스크레이퍼에서 오버라이드."""
        pass

    def extract_products_from_html(self, html: str, category_name: str, category_url: str) -> list[dict]:
        raise NotImplementedError

    # ── 공통 추출 유틸리티 ────────────────────────────────────────────────────

    def _extract_products_from_json_ld(self, html: str, category_name: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.select('script[type="application/ld+json"]')

        products = []
        for script in scripts:
            raw_text = script.string or script.get_text(strip=True)
            if not raw_text:
                continue
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                continue
            for product_data in self._find_product_entries(payload):
                normalized = self._normalize_product(product_data, category_name)
                if normalized:
                    products.append(normalized)

        return products

    def _find_product_entries(self, payload) -> list[dict]:
        found = []
        if isinstance(payload, dict):
            if payload.get("@type") in {"Product", "IndividualProduct", "ProductGroup"}:
                found.append(payload)
            for value in payload.values():
                found.extend(self._find_product_entries(value))
        elif isinstance(payload, list):
            for item in payload:
                found.extend(self._find_product_entries(item))
        return found

    def _normalize_product(self, product_data: dict, category_name: str) -> Optional[dict]:
        name = str(product_data.get("name", "")).strip()
        if not name:
            return None

        offers = product_data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        raw_price = offers.get("price") if isinstance(offers, dict) else None
        detail_url = product_data.get("url", "") or product_data.get("@id", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = urljoin(self.BASE_URL, detail_url)

        reference = (
            product_data.get("sku")
            or product_data.get("productID")
            or product_data.get("mpn")
            or ""
        )
        colors = product_data.get("color", "")
        if isinstance(colors, list):
            colors = ", ".join(str(c).strip() for c in colors if str(c).strip())

        return {
            "category": category_name,
            "name": name,
            "price": self._parse_price_value(raw_price),
            "url": detail_url,
            "reference": str(reference).strip(),
            "colors": str(colors).strip(),
        }

    def _deduplicate_by_url(self, products: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result = []
        for product in products:
            url = product.get("url", "")
            if url not in seen:
                seen.add(url)
                result.append(product)
        return result

    def _parse_price_value(self, raw_price) -> Optional[int]:
        if raw_price in (None, ""):
            return None
        digits = "".join(ch for ch in str(raw_price) if ch.isdigit())
        return int(digits) if digits else None

    # ── 봇 차단 감지 / 스냅샷 ────────────────────────────────────────────────

    def _detect_block_reason(self, html: str) -> Optional[str]:
        html_lower = html.lower()

        if "403 forbidden" in html_lower or "error 403" in html_lower:
            return "http_403_forbidden"
        if "access denied" in html_lower:
            if "reference #" in html_lower or "akamai" in html_lower:
                return "akamai_access_denied"
            return "general_access_denied"
        if "g-recaptcha" in html_lower or "cf-turnstile" in html_lower or "hcaptcha" in html_lower:
            return "captcha_challenge"
        if 'id="challenge-form"' in html_lower or 'id="challenge-running"' in html_lower:
            return "cloudflare_challenge"
        if "just a moment" in html_lower and "cloudflare" in html_lower:
            return "cloudflare_wait"
        if "page unavailable" in html_lower and "reference id" in html_lower:
            return "akamai_unavailable"
        if "id=" in html_lower and "ip=" in html_lower and "date/time=" in html_lower:
            return "waf_incident_report"
        if "distil" in html_lower or "imperva" in html_lower or "datadome" in html_lower:
            return "advanced_bot_shield"

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

    # ── 팝업 처리 ─────────────────────────────────────────────────────────────

    def _dismiss_known_popups(self, scraping_settings: dict) -> None:
        popup_selectors = scraping_settings.get("popup_selectors", [
            "#onetrust-accept-btn-handler",
            "button[aria-label='Close']",
            "button[aria-label='close']",
            "button[class*='close']",
            "button[class*='modal-close']",
        ])
        popup_xpaths = scraping_settings.get("popup_xpaths", [
            "//button[contains(., '동의')]",
            "//button[contains(., 'Accept All')]",
            "//button[contains(., 'Accept')]",
            "//button[contains(., '닫기')]",
        ])

        for selector in popup_selectors:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if element.is_displayed():
                        element.click()
                        return
            except Exception:
                continue

        for xpath in popup_xpaths:
            try:
                for element in self.driver.find_elements(By.XPATH, xpath):
                    if element.is_displayed():
                        element.click()
                        return
            except Exception:
                continue
