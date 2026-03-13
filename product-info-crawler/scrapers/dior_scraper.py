import json
import time
from typing import Any, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class DiorScraper(BaseScraper):
    requires_driver = False

    def __init__(self, driver: Optional[object], config: dict):
        super().__init__(driver, config)

    def parse_category(self, category_name: str, url: str):
        html = self._fetch_category_html(url)

        products = self._extract_products_from_json_ld(html, category_name)
        if not products:
            products = self._extract_products_from_selectors(html, category_name, url)

        deduplicated = []
        seen_urls = set()
        for product in products:
            product_url = product.get("url", "")
            if product_url in seen_urls:
                continue
            seen_urls.add(product_url)
            deduplicated.append(product)

        return deduplicated

    def _fetch_category_html(self, url: str) -> str:
        scraping_settings = self.config.get("scraping_settings", {})
        request_delay_sec = float(scraping_settings.get("request_delay_sec", 2.5))
        timeout_sec = int(scraping_settings.get("request_timeout_sec", 20))
        user_agent = scraping_settings.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )

        time.sleep(request_delay_sec)
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        with urlopen(request, timeout=timeout_sec) as response:
            return response.read().decode("utf-8", errors="ignore")

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

    def _find_product_entries(self, payload: Any) -> list[dict]:
        found = []

        if isinstance(payload, dict):
            payload_type = payload.get("@type")
            if payload_type in {"Product", "IndividualProduct", "ProductGroup"}:
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

        raw_price = None
        if isinstance(offers, dict):
            raw_price = offers.get("price")

        detail_url = product_data.get("url", "") or product_data.get("@id", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = urljoin("https://www.dior.com", detail_url)

        reference = (
            product_data.get("sku")
            or product_data.get("productID")
            or product_data.get("mpn")
            or ""
        )

        colors = product_data.get("color", "")
        if isinstance(colors, list):
            colors = ", ".join(str(color).strip() for color in colors if str(color).strip())

        return {
            "category": category_name,
            "name": name,
            "price": self._parse_price(raw_price),
            "url": detail_url,
            "reference": str(reference).strip(),
            "colors": str(colors).strip(),
        }

    def _extract_products_from_selectors(self, html: str, category_name: str, category_url: str) -> list[dict]:
        selectors = self.config.get("selectors", {})
        product_card_selector = selectors.get("product_card")
        if not product_card_selector:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(product_card_selector)
        products = []

        for card in cards:
            name_selector = selectors.get("name")
            price_selector = selectors.get("price")
            link_selector = selectors.get("link")

            name_tag = card.select_one(name_selector) if name_selector else None
            price_tag = card.select_one(price_selector) if price_selector else None
            link_tag = card.select_one(link_selector) if link_selector else None

            href = ""
            if link_tag and link_tag.has_attr("href"):
                href = urljoin(category_url, link_tag["href"])

            price = None
            if price_tag:
                price = self._parse_price(price_tag.get("content") or price_tag.get_text(strip=True))

            products.append(
                {
                    "category": category_name,
                    "name": name_tag.get_text(strip=True) if name_tag else "N/A",
                    "price": price,
                    "url": href,
                    "reference": "",
                    "colors": "",
                }
            )

        return products

    def _parse_price(self, raw_price: Any):
        if raw_price in (None, ""):
            return None

        digits = "".join(character for character in str(raw_price) if character.isdigit())
        return int(digits) if digits else None
