from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import time
import json
import urllib.parse
from utils.helper import scroll_to_bottom, parse_price
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CelineScraper(BaseScraper):
    def parse_category(self, category_name: str, url: str):
        print(f"[*] Celine - {category_name} 접속 중")
        self.driver.get(url)

        selectors = self.config["selectors"]
        # 상품 카드가 나타날 때까지 대기
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors["product_card"]))
            )
        except:
            print("❌ Celine 상품 카드가 로딩되지 않았습니다.")
            return []

        scroll_to_bottom(self.driver, self.config["scraping_settings"].get("scroll_pause_time", 2))

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        selectors = self.config["selectors"]
        cards = soup.select(selectors["product_card"])
        print(f"   -> 발견된 상품 카드 수: {len(cards)}")

        products = []
        for card in cards:
            name_tag = card.select_one(selectors["name"])
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            price_tag = card.select_one(selectors["price"])
            price = parse_price(price_tag) if price_tag else None

            link_tag = card.select_one(selectors["link"])
            detail_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""

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
                "colors": colors
            })
        return products