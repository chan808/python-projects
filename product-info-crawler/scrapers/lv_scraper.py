import json
import random
import re
import time
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
            # [수정] LV는 로딩이 매우 무거울 수 있어 body 대기를 더 여유 있게 잡고, 
            # 만약 로딩이 안 된다면 '접근 차단' 페이지일 가능성이 큼
            WebDriverWait(self.driver, scraping_settings.get("initial_wait_sec", 25)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # 페이지 로드 후 실제 사람처럼 약간의 무작위 대기 추가
            import random
            time.sleep(random.uniform(2.0, 5.0))
        except Exception:
            # 로딩 실패 시 현재 소스 확인하여 차단 여부 체크
            html = self.driver.page_source
            self._check_html_or_raise(category_name, html, [])
            return []

        self._dismiss_known_popups(scraping_settings)

        scroll_result = scroll_until_lazy_content_loaded(
            self.driver,
            pause_time=float(scraping_settings.get("scroll_pause_time", 3.0)),
            product_card_selector=selectors["product_card"],
            placeholder_selector=selectors.get("lazy_placeholder", ""),
            max_loops=int(scraping_settings.get("max_scroll_loops", 30)),
            max_placeholder_retries=int(scraping_settings.get("max_placeholder_retries", 3)),
        )

        # 스크롤 후 데이터가 DOM/JSON에 반영될 시간을 추가로 줌
        time.sleep(2)

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
        # [수정] 방금 확인한 셀렉터(HTML 태그) 기반 추출을 최우선으로 시도
        products = self._extract_products_from_selectors(html, category_name, category_url)
        
        if not products:
            products = self._extract_products_from_next_data(html, category_name)
        if not products:
            products = self._extract_products_from_json_ld(html, category_name)

        deduplicated = []
        seen_urls = set()
        for product in products:
            product_url = product.get("url", "")
            if product_url in seen_urls:
                continue
            seen_urls.add(product_url)
            deduplicated.append(product)

        return deduplicated

    def _extract_products_from_next_data(self, html: str, category_name: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            return []

        try:
            data = json.loads(script.string)
            page_props = data.get("props", {}).get("pageProps", {})
            
            # LV의 다양한 데이터 경로 확인 (2026년 기준 더 깊은 경로 포함)
            items = []
            # 1. 일반 카테고리 페이지
            if "category" in page_props:
                items = page_props["category"].get("products", [])
            # 2. 제품 리스트 필드
            elif "products" in page_props:
                items = page_props["products"]
            # 3. 검색 결과 또는 다른 변형
            elif "searchResult" in page_props:
                items = page_props["searchResult"].get("products", [])
            # 4. PLP(Product List Page) 데이터
            elif "plpData" in page_props:
                items = page_props["plpData"].get("products", [])
            
            # 만약 items가 여전히 비어있다면, Apollo/Relay 같은 GraphQL 결과 확인
            if not items and "apolloState" in data.get("props", {}):
                apollo = data["props"]["apolloState"]
                for key, val in apollo.items():
                    if key.startswith("Product:") and isinstance(val, dict):
                        items.append(val)

            # 만약 items가 여전히 비어있다면, 더 깊은 곳을 찾음 (Dior와 유사한 구조일 경우 대비)
            if not items and "queries" in page_props:
                for query in page_props.get("queries", []):
                    if "hits" in query:
                        items.extend(query["hits"])
                    elif "products" in query:
                        items.extend(query["products"])

        except Exception:
            return []

        products = []
        for item in items:
            # [수정] 2026년 LV의 더 복잡해진 데이터 구조 대응
            # 1) 이름 추출
            name = item.get("name") or item.get("title") or item.get("titleInt")
            if not name and "attributes" in item:
                name = item["attributes"].get("name")
            
            # 2) SKU/Reference 추출
            sku = item.get("sku") or item.get("identifier") or item.get("style_color_ref") or item.get("styleColorRef")
            if not sku and "attributes" in item:
                sku = item["attributes"].get("sku") or item["attributes"].get("identifier")

            # 3) 가격 추출
            price_val = None
            price_data = item.get("price")
            if not price_data and "attributes" in item:
                price_data = item["attributes"].get("price")
                
            if isinstance(price_data, list) and price_data:
                price_data = price_data[0]
            
            if isinstance(price_data, dict):
                price_val = price_data.get("value") or price_data.get("amount") or price_data.get("price")
            else:
                price_val = price_data

            # 4) URL 추출
            url_path = item.get("url") or item.get("slug")
            if not url_path and "attributes" in item:
                url_path = item["attributes"].get("url") or item["attributes"].get("productLink", {}).get("uri")
            full_url = urljoin(LV_BASE_URL, url_path) if url_path else ""
            
            # 5) 색상 추출
            colors = ""
            color_info = item.get("color") or item.get("subtitle") or item.get("variantName")
            if not color_info and "attributes" in item:
                color_info = item["attributes"].get("color") or item["attributes"].get("subtitle")
                
            if isinstance(color_info, list):
                colors = ", ".join(str(c) for c in color_info)
            elif isinstance(color_info, dict):
                colors = color_info.get("label", "") or color_info.get("name", "")
            else:
                colors = str(color_info) if color_info else ""

            if name: # 이름이 있는 경우만 유효한 상품으로 간주
                products.append({
                    "category": category_name,
                    "name": str(name).strip(),
                    "price": self._parse_price_value(price_val),
                    "url": full_url,
                    "reference": str(sku).strip() if sku else "",
                    "colors": str(colors).strip(),
                })
        return products

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
        sku_pattern = re.compile(r"[A-Z][0-9]{5}")

        for card in cards:
            name_tag = card.select_one(selectors.get("name", ""))
            price_tag = card.select_one(selectors.get("price", ""))
            link_tag = card.select_one(selectors.get("link", ""))

            # [수정] 모델 번호(예: M26744) 추출 로직 강화
            sku = ""
            # 1. 카드 자체의 ID나 속성에서 검색
            for attr in ["id", "data-sku", "data-id"]:
                val = card.get(attr, "")
                match = sku_pattern.search(val)
                if match:
                    sku = match.group()
                    break
            
            # 2. 제목 태그(h2 등)의 ID에서 검색
            if not sku and name_tag:
                # name_tag 자체가 h2일 수도 있고, h2의 자식일 수도 있음
                title_tag = name_tag if name_tag.name == "h2" else name_tag.find_parent("h2")
                if title_tag and title_tag.has_attr("id"):
                    match = sku_pattern.search(title_tag["id"])
                    if match:
                        sku = match.group()

            # 3. 링크 URL이나 ID에서 검색
            if not sku and link_tag:
                href = link_tag.get("href", "")
                link_id = link_tag.get("id", "")
                match = sku_pattern.search(link_id) or sku_pattern.search(href)
                if match:
                    sku = match.group()
            
            # 4. 이미지 경로에서 검색 (최후의 보단)
            if not sku:
                img_tag = card.select_one("img")
                if img_tag:
                    src = img_tag.get("src", "") or img_tag.get("data-src", "")
                    match = sku_pattern.search(src)
                    if match:
                        sku = match.group()

            href = ""
            if link_tag and link_tag.has_attr("href"):
                href = urljoin(category_url, link_tag["href"])
                if href and not href.startswith("http"):
                    href = urljoin(LV_BASE_URL, href)

            name = name_tag.get_text(strip=True) if name_tag else ""
            
            # [수정] 텍스트가 섞여있는 경우 (예: '750,000원') 가격만 추출
            price = None
            if price_tag:
                price = parse_price(price_tag)

            if name:
                products.append(
                    {
                        "category": category_name,
                        "name": name,
                        "price": price,
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

