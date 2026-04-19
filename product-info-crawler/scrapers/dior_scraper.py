import json
import random
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.helper import parse_price, scroll_until_lazy_content_loaded

from .base_scraper import BaseScraper


class DiorScraper(BaseScraper):
    requires_driver = True

    def parse_category(self, category_name: str, url: str):
        selectors = self.config["selectors"]
        scraping_settings = self.config.get("scraping_settings", {})

        # [수정] 무작위성 추가: 페이지 접속 전 약간 대기
        time.sleep(random.uniform(1.0, 3.0))
        self.driver.get(url)

        try:
            # [수정] 디올은 로딩이 무거울 수 있어 body 대기를 더 여유 있게 잡음
            WebDriverWait(self.driver, scraping_settings.get("initial_wait_sec", 20)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # 페이지 로드 후 추가 무작위 대기
            time.sleep(random.uniform(2.0, 4.0))
        except Exception:
            return []

        self._dismiss_known_popups(scraping_settings)
        # 팝업 제거 후 잠시 대기
        time.sleep(random.uniform(1.0, 2.0))

        scroll_result = scroll_until_lazy_content_loaded(
            self.driver,
            pause_time=float(scraping_settings.get("scroll_pause_time", 3.0)),
            product_card_selector=selectors["product_card"],
            placeholder_selector=selectors.get("lazy_placeholder", ""),
            max_loops=int(scraping_settings.get("max_scroll_loops", 12)),
            max_placeholder_retries=int(scraping_settings.get("max_placeholder_retries", 3)),
        )

        html = self.driver.page_source
        block_reason = self._detect_block_reason(html)
        if block_reason:
            snapshot_path = self._save_snapshot(category_name, html, block_reason)
            raise RuntimeError(f"Dior 차단 페이지가 감지되었습니다 ({block_reason}): {snapshot_path}")

        products = self.extract_products_from_html(html, category_name, url)
        max_products = int(scraping_settings.get("max_products_per_category", 0))
        if max_products > 0:
            products = products[:max_products]

        if not products:
            reason = "no_products_with_placeholders" if scroll_result["placeholder_count"] > 0 else "no_products"
            snapshot_path = self._save_snapshot(category_name, html, reason)
            raise RuntimeError(f"Dior 상품을 찾지 못했습니다. HTML 저장: {snapshot_path}")

        return products

    def extract_products_from_html(self, html: str, category_name: str, category_url: str) -> list[dict]:
        products = self._extract_products_from_json_ld(html, category_name)
        if not products:
            products = self._extract_products_from_selectors(html, category_name, category_url)

        deduplicated = []
        seen_urls = set()
        for product in products:
            product_url = product.get("url", "")
            if product_url in seen_urls:
                continue
            seen_urls.add(product_url)
            deduplicated.append(product)

        return deduplicated

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

    def _normalize_product(self, product_data: dict, category_name: str):
        name = str(product_data.get("name", "")).strip()
        if not name:
            return None

        offers = product_data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        raw_price = offers.get("price") if isinstance(offers, dict) else None
        detail_url = product_data.get("url", "") or product_data.get("@id", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = urljoin("https://www.dior.com", detail_url)

        reference = product_data.get("sku") or product_data.get("productID") or product_data.get("mpn") or ""
        colors = product_data.get("color", "")
        if isinstance(colors, list):
            colors = ", ".join(str(color).strip() for color in colors if str(color).strip())

        return {
            "category": category_name,
            "name": name,
            "price": self._parse_price_value(raw_price),
            "url": detail_url,
            "reference": str(reference).strip(),
            "colors": str(colors).strip(),
        }

    def _extract_products_from_selectors(self, html: str, category_name: str, category_url: str) -> list[dict]:
        selectors = self.config["selectors"]
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(selectors["product_card"])

        products = []
        for card in cards:
            name_tag = card.select_one(selectors.get("name", ""))
            price_tag = card.select_one(selectors.get("price", ""))
            link_tag = card.select_one(selectors.get("link", ""))

            href = ""
            if link_tag and link_tag.has_attr("href"):
                href = urljoin(category_url, link_tag["href"])

            products.append(
                {
                    "category": category_name,
                    "name": name_tag.get_text(strip=True) if name_tag else "N/A",
                    "price": parse_price(price_tag) if price_tag else None,
                    "url": href,
                    "reference": "",
                    "colors": "",
                }
            )

        return products

    def _parse_price_value(self, raw_price):
        if raw_price in (None, ""):
            return None

        digits = "".join(character for character in str(raw_price) if character.isdigit())
        return int(digits) if digits else None

    def _dismiss_known_popups(self, scraping_settings: dict) -> None:
        popup_selectors = scraping_settings.get(
            "popup_selectors",
            [
                "#onetrust-accept-btn-handler",
                "button[aria-label='Close']",
                "button[aria-label='close']",
                "button[class*='close']",
            ],
        )
        popup_xpaths = scraping_settings.get(
            "popup_xpaths",
            [
                "//button[contains(., '동의')]",
                "//button[contains(., 'Accept')]",
                "//button[contains(., '닫기')]",
            ],
        )

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

