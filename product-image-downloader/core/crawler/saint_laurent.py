"""Saint Laurent (YSL) product image crawler (Kering Group / SFCC)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import List
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.crawler.base import BaseCrawler
from core.crawler.registry import CrawlerRegistry

logger = logging.getLogger(__name__)

_CDN_PATTERNS = [
    # Kering DAM
    r"(https?://ysl\.dam\.kering\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    r"(https?://saint-laurent\.dam\.kering\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    # media.ysl.com (product CDN)
    r"(https?://media\.ysl\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    # SFCC DIS fallback
    r"(https?://(?:www\.)?ysl\.com/dw/image/v2/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
]

_DAM_SIZES = ["Large", "Medium", "Small", "Thumbnail", "Small_thumbnail"]


@CrawlerRegistry.register
class SaintLaurentCrawler(BaseCrawler):

    @property
    def brand_name(self) -> str:
        return "saint_laurent"

    def build_product_url(self, product_code: str) -> str:
        return f"https://www.ysl.com/ko-kr/search?q={quote_plus(product_code)}"

    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        if "/search" in driver.current_url:
            if not self._navigate_to_product(driver, product_code):
                logger.warning("[saint_laurent] Could not navigate to product page for %s", product_code)

        self._scroll_page(driver)
        source = driver.page_source
        all_urls: List[str] = []

        json_ld_urls = self._from_json_ld(source)
        all_urls.extend(json_ld_urls)

        state_urls = self._from_embedded_state(source)
        all_urls.extend(state_urls)

        cdn_urls = self._from_cdn_patterns(source)
        all_urls.extend(cdn_urls)

        img_urls = self._from_img_tags(driver)
        all_urls.extend(img_urls)

        final_urls = self._select_best_quality(all_urls)

        code_clean = product_code.lower().replace("-", "").replace("_", "").replace(" ", "")
        json_ld_clean = set(self._select_best_quality(json_ld_urls))
        state_clean = set(self._select_best_quality(state_urls))

        filtered = []
        for u in final_urls:
            u_norm = u.lower().replace("-", "").replace("_", "").replace(" ", "")
            if code_clean in u_norm:
                filtered.append(u)
            elif u in json_ld_clean or u in state_clean:
                filtered.append(u)

        if not filtered and final_urls:
            return self._deduplicate(final_urls)

        return self._deduplicate(filtered)

    # ── navigation ────────────────────────────────────────────────

    def _navigate_to_product(self, driver: webdriver.Chrome, product_code: str) -> bool:
        try:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.html'], a[href*='/p/']"))
                )
            except Exception:
                time.sleep(4)

            self._dismiss_popups(driver)
            current_url = driver.current_url
            code_clean = product_code.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
            links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
            candidate = None

            for link in links:
                href = link.get_attribute("href") or ""
                if not href or href == current_url or "/search" in href:
                    continue
                if "ysl.com/ko-kr/" not in href:
                    continue
                href_clean = href.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
                if code_clean in href_clean:
                    candidate = href
                    break

            if not candidate:
                for link in links:
                    href = link.get_attribute("href") or ""
                    if (href and "ysl.com/ko-kr/" in href
                            and href != current_url
                            and "/search" not in href
                            and href.count("/") >= 5):
                        candidate = href
                        break

            if not candidate:
                return False

            logger.info("[saint_laurent] Navigating to: %s", candidate)
            driver.get(candidate)
            self._wait_for_page(driver, extra_seconds=3, scroll=True)
            return True
        except Exception:
            logger.exception("[saint_laurent] Navigation failed")
            return False

    def _dismiss_popups(self, driver: webdriver.Chrome) -> None:
        selectors = [
            "#onetrust-accept-btn-handler",
            ".cookie-banner-accept",
            "button[id*='accept']",
            "button[class*='accept']",
        ]
        for sel in selectors:
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, sel)
                if btns and btns[0].is_displayed():
                    btns[0].click()
                    time.sleep(1)
                    break
            except Exception:
                continue

    # ── extraction strategies ─────────────────────────────────────

    def _from_json_ld(self, source: str) -> List[str]:
        blocks = self._extract_json_ld(source)
        urls = []
        for block in blocks:
            if block.get("@type") not in ("Product", "IndividualProduct", "ProductGroup"):
                continue
            images = block.get("image", [])
            if isinstance(images, str):
                images = [images]
            elif isinstance(images, dict):
                images = [images.get("url", images.get("contentUrl", ""))]
            for img in images:
                if isinstance(img, dict):
                    img = img.get("url", img.get("contentUrl", ""))
                if isinstance(img, str) and img.startswith("http"):
                    urls.append(img)
        return urls

    def _from_embedded_state(self, source: str) -> List[str]:
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});?\s*</script>',
            r'window\.__NEXT_DATA__\s*=\s*({.*?});?\s*</script>',
        ]
        urls: List[str] = []
        for pat in patterns:
            match = re.search(pat, source, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    urls.extend(self._deep_find_image_urls(data))
                except json.JSONDecodeError:
                    continue
        return urls

    def _from_cdn_patterns(self, source: str) -> List[str]:
        urls = []
        for pat in _CDN_PATTERNS:
            urls.extend(re.findall(pat, source, re.IGNORECASE))
        return [u for u in urls if not any(
            skip in u.lower() for skip in ("logo", "icon", "sprite", "favicon", "banner", "pixel", "1x1")
        )]

    def _from_img_tags(self, driver: webdriver.Chrome) -> List[str]:
        urls = []
        try:
            images = driver.find_elements(By.TAG_NAME, "img")
            for img in images:
                for attr in ("src", "data-src", "data-zoom-image", "data-large"):
                    val = img.get_attribute(attr)
                    if val and val.startswith("http"):
                        if any(skip in val.lower() for skip in ("logo", "icon", "sprite", "favicon", "pixel", "svg", "1x1")):
                            continue
                        if any(ext in val.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(val)
                for attr in ("srcset", "data-srcset"):
                    srcset = img.get_attribute(attr)
                    if srcset:
                        for part in srcset.split(","):
                            url = part.strip().split()[0]
                            if url.startswith("http") and any(ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                                urls.append(url)
        except Exception:
            logger.exception("[saint_laurent] Error extracting img tags")
        return urls

    def _deep_find_image_urls(self, obj, depth: int = 0) -> List[str]:
        if depth > 15:
            return []
        urls: List[str] = []
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str) and v.startswith("http") and any(
                    ext in v.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")
                ):
                    if any(domain in v.lower() for domain in ("ysl", "kering", "saint-laurent")):
                        urls.append(v)
                else:
                    urls.extend(self._deep_find_image_urls(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self._deep_find_image_urls(item, depth + 1))
        return urls

    def _select_best_quality(self, urls: List[str]) -> List[str]:
        dam_by_letter: dict = {}
        other_urls: list = []

        for u in urls:
            if "dam.kering.com" in u:
                m = re.search(
                    r"/(Small_thumbnail|Thumbnail|Small|Medium|Large)-[^/]+_([A-Z])\."
                    r"(?:jpg|jpeg|png|webp)",
                    u, re.IGNORECASE,
                )
                if m:
                    size = m.group(1)
                    letter = m.group(2).upper()
                    priority = _DAM_SIZES.index(size) if size in _DAM_SIZES else 99
                    if letter not in dam_by_letter or priority < dam_by_letter[letter][0]:
                        dam_by_letter[letter] = (priority, u)
                else:
                    other_urls.append(u)
            else:
                u_clean = re.sub(r"[?&](sw|sh|sm|q|format|width|height|w|h|size|quality|resize|imwidth|imheight)=[^&]*", "", u)
                u_clean = re.sub(r"[?&]$", "", u_clean)
                if "/dw/image/v2/" in u_clean:
                    sep = "&" if "?" in u_clean else "?"
                    u_clean += f"{sep}q=90"
                other_urls.append(u_clean)

        result = [dam_by_letter[letter][1] for letter in sorted(dam_by_letter.keys())]
        result.extend(list(dict.fromkeys(other_urls)))
        return result
