from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
from utils.helper import scroll_to_bottom, parse_price
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BottegaScraper(BaseScraper):
    def parse_category(self, category_name: str, url: str):
        self.driver.get(url)

        selectors = self.config["selectors"]

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors["product_card"]))
            )
        except Exception:
            html = self.driver.page_source
            self._check_html_or_raise(category_name, html, [])
            return []

        scroll_to_bottom(
            self.driver,
            self.config["scraping_settings"].get("scroll_pause_time", 2),
            product_card_selector=selectors["product_card"]
        )

        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(selectors["product_card"])
        self._check_html_or_raise(category_name, html, cards)

        products = []
        seen_urls: set[str] = set()

        for card in cards:
            # 3-1) 이름
            name_tag = card.select_one(selectors["name"])
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # 3-2) 가격
            price_tag = card.select_one(selectors["price"])
            price = parse_price(price_tag) if price_tag else None

            # 3-3) 링크
            link_tag = card.select_one(selectors["link"])
            detail_url = ""
            if link_tag and link_tag.has_attr("href"):
                href = link_tag["href"]
                detail_url = href if href.startswith("http") \
                    else "https://www.bottegaveneta.com" + href

            # 3-4) 색상 (메인에서 가져올 수 있으면 먼저 시도)
            colors = ""
            color_span = card.select_one("span.u-sronly")
            if color_span:
                full_text = color_span.get_text(strip=True)
                if name and full_text.endswith(name):
                    colors = full_text[:-len(name)].strip()
                else:
                    colors = full_text

            # 3-5) 레퍼런스 (리스트 상단 data-pid 쓰기)
            reference = card.get("data-pid", "")
            if not reference and link_tag:
                reference = link_tag.get("data-pid", "")

            if detail_url and detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            products.append({
                "category": category_name,
                "name": name,
                "price": price,
                "url": detail_url,
                "reference": reference,
                "colors": colors,
            })

        # 4) 색상이 비어 있는 상품만 상세 페이지에 들어가서 보완
        for p in products:
            if not p["url"] or p["colors"]:
                continue

            ref_detail, colors_detail = self.parse_detail(p["url"])

            if colors_detail:
                p["colors"] = colors_detail
            if not p["reference"] and ref_detail:
                p["reference"] = ref_detail

        return products

    def parse_detail(self, detail_url: str):
        self.driver.get(detail_url)

        detail_selectors = self.config.get("detail_selectors", {})

        color_selector = detail_selectors.get("color")

        # 색상 요소 기준으로 로딩 대기 (있으면)
        if color_selector:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, color_selector))
                )
            except Exception:
                pass

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # 색상
        colors = ""
        if color_selector:
            color_tag = soup.select_one(color_selector)
            if color_tag:
                colors = color_tag.get_text(strip=True)

        # 레퍼런스(선택)
        reference = ""
        ref_selector = detail_selectors.get("reference")
        if ref_selector:
            ref_tag = soup.select_one(ref_selector)
            if ref_tag:
                reference = ref_tag.get_text(strip=True)

        return reference, colors