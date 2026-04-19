import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.helper import parse_price, scroll_until_lazy_content_loaded

from .base_scraper import BaseScraper

LV_BASE_URL = "https://kr.louisvuitton.com"


class LvScraper(BaseScraper):
    requires_driver = True

    def parse_category(self, category_name: str, url: str):
        selectors = self.config["selectors"]
        scraping_settings = self.config.get("scraping_settings", {})

        self.driver.get(url)

        try:
            WebDriverWait(self.driver, scraping_settings.get("initial_wait_sec", 15)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            return []

        self._dismiss_known_popups(scraping_settings)

        scroll_result = scroll_until_lazy_content_loaded(
            self.driver,
            pause_time=float(scraping_settings.get("scroll_pause_time", 2.5)),
            product_card_selector=selectors["product_card"],
            placeholder_selector=selectors.get("lazy_placeholder", ""),
            max_loops=int(scraping_settings.get("max_scroll_loops", 8)),
            max_placeholder_retries=int(scraping_settings.get("max_placeholder_retries", 2)),
        )

        html = self.driver.page_source
        block_reason = self._detect_block_reason(html)
        if block_reason:
            snapshot_path = self._save_snapshot(category_name, html, block_reason)
            raise RuntimeError(f"LV 차단 페이지가 감지되었습니다: {snapshot_path}")

        products = self.extract_products_from_html(html, category_name, url)
        max_products = int(scraping_settings.get("max_products_per_category", 0))
        if max_products > 0:
            products = products[:max_products]

        if not products:
            reason = "no_products_with_placeholders" if scroll_result["placeholder_count"] > 0 else "no_products"
            snapshot_path = self._save_snapshot(category_name, html, reason)
            raise RuntimeError(f"LV 상품을 찾지 못했습니다. HTML 저장: {snapshot_path}")

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
            detail_url = urljoin(LV_BASE_URL, detail_url)

        reference = product_data.get("sku") or product_data.get("productID") or product_data.get("mpn") or ""
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
                if href and not href.startswith("http"):
                    href = urljoin(LV_BASE_URL, href)

            sku = card.get("data-sku", "") or card.get("data-id", "")

            products.append(
                {
                    "category": category_name,
                    "name": name_tag.get_text(strip=True) if name_tag else "N/A",
                    "price": parse_price(price_tag) if price_tag else None,
                    "url": href,
                    "reference": sku,
                    "colors": "",
                }
            )

        return products

    def _parse_price_value(self, raw_price):
        if raw_price in (None, ""):
            return None

        digits = "".join(ch for ch in str(raw_price) if ch.isdigit())
        return int(digits) if digits else None

    def _dismiss_known_popups(self, scraping_settings: dict) -> None:
        popup_selectors = scraping_settings.get(
            "popup_selectors",
            [
                "#onetrust-accept-btn-handler",
                "button[aria-label='Close']",
                "button[aria-label='close']",
                "button[class*='close']",
                "button[class*='modal-close']",
            ],
        )
        popup_xpaths = scraping_settings.get(
            "popup_xpaths",
            [
                "//button[contains(., '동의')]",
                "//button[contains(., 'Accept')]",
                "//button[contains(., '닫기')]",
                "//button[contains(., 'Accept All')]",
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

