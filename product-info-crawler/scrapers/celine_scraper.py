import json
import urllib.parse
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.helper import parse_price, scroll_to_bottom

from .base_scraper import BaseScraper

CELINE_BASE_URL = "https://www.celine.com"


class CelineScraper(BaseScraper):
    def parse_category(self, category_name: str, url: str) -> list[dict]:
        self.driver.get(url)

        selectors = self.config["selectors"]
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors["product_card"]))
            )
        except Exception:
            html = self.driver.page_source
            self._check_html_or_raise(category_name, html, [])
            return []

        scroll_to_bottom(self.driver, self.config["scraping_settings"].get("scroll_pause_time", 2))

        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(selectors["product_card"])

        self._check_html_or_raise(category_name, html, cards)

        products = []
        seen_urls: set[str] = set()

        for card in cards:
            name_tag = card.select_one(selectors["name"])
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            price_tag = card.select_one(selectors["price"])
            price = parse_price(price_tag) if price_tag else None

            link_tag = card.select_one(selectors["link"])
            href = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""
            detail_url = urljoin(CELINE_BASE_URL, href) if href else ""

            if detail_url and detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            reference = colors = ""
            slider = card.select_one("div.m-tile-slider")
            if slider:
                pid = slider.get("data-pid", "")
                if pid:
                    parts = pid.split(".")
                    reference = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else pid

                gtm_raw = slider.get("data-gtm-data")
                if gtm_raw:
                    try:
                        decoded = urllib.parse.unquote(gtm_raw)
                        gtm = json.loads(decoded)
                        colors = gtm.get("productColor", "")
                    except json.JSONDecodeError:
                        pass

            products.append({
                "category": category_name,
                "name": name,
                "price": price,
                "url": detail_url,
                "reference": reference,
                "colors": colors,
            })

        return products