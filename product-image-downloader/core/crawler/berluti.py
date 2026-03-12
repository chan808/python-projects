"""Berluti product image crawler (LVMH Group)."""

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
    # Berluti media/CDN (LVMH group structure, similar to Dior)
    r"(https?://(?:eci-media|media|cdn|assets)\.berluti\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    # On-domain content
    r"(https?://(?:www\.)?berluti\.com/(?:content|media|dam|images|product)[^\s\"'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    # Generic berluti URL patterns
    r"(https?://[a-z0-9.-]*berluti[a-z0-9.-]*/[^\s\"'<>]*?/(?:product|catalog|image|media)[^\s\"'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
]


@CrawlerRegistry.register
class BerlutiCrawler(BaseCrawler):

    @property
    def brand_name(self) -> str:
        return "berluti"

    def build_product_url(self, product_code: str) -> str:
        return f"https://www.berluti.com/ko-kr/search?q={quote_plus(product_code)}"

    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        if "/search" in driver.current_url:
            if not self._navigate_to_product(driver, product_code):
                logger.warning("[berluti] Could not navigate to product page for %s", product_code)

        self._scroll_page(driver)
        source = driver.page_source
        all_urls: List[str] = []

        json_ld_urls = self._from_json_ld(source)
        all_urls.extend(json_ld_urls)

        state_urls = self._from_embedded_state(source)
        all_urls.extend(state_urls)

        cdn_urls = self._from_cdn_patterns(source, product_code)
        all_urls.extend(cdn_urls)

        img_urls = self._from_img_tags(driver)
        all_urls.extend(img_urls)

        final_urls = self._select_best_quality(all_urls)

        code_part = product_code.lower().replace("_", "").replace("-", "").replace(" ", "")
        json_ld_clean = set(self._select_best_quality(json_ld_urls))
        state_clean = set(self._select_best_quality(state_urls))

        filtered = []
        for u in final_urls:
            u_lower = u.lower()
            u_norm = u_lower.replace("_", "").replace("-", "").replace(" ", "")
            if code_part in u_norm:
                filtered.append(u)
            elif u in json_ld_clean or u in state_clean:
                filtered.append(u)
            elif any(p in u_lower for p in ("product", "catalog", "media", "content")) and "berluti" in u_lower:
                if len(json_ld_urls) == 0 and len(state_urls) == 0:
                    filtered.append(u)

        if not filtered and final_urls:
            return self._deduplicate(final_urls)

        return self._deduplicate(filtered)

    # ── navigation ────────────────────────────────────────────────

    def _navigate_to_product(self, driver: webdriver.Chrome, product_code: str) -> bool:
        try:
            time.sleep(3)
            self._dismiss_popups(driver)

            source = driver.page_source
            current_url = driver.current_url
            code_url_variant = product_code.upper().replace("_", "-").replace(" ", "-")

            link_pattern = re.compile(
                r'href=["\'](https?://(?:www\.)?berluti\.com/ko-kr/[^\s"\'<>?]+)["\']',
                re.IGNORECASE,
            )
            matches = link_pattern.findall(source)
            code_clean = product_code.lower().replace("-", "").replace("_", "").replace(" ", "")
            link_match_url = next(
                (m for m in matches if m != current_url and "/search" not in m
                 and code_clean in m.lower().replace("-", "").replace("_", "")), None
            )

            if not link_match_url:
                links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if (href and "berluti.com/ko-kr/" in href
                            and href != current_url
                            and "/search" not in href
                            and href.count("/") >= 5):
                        if code_clean in href.lower().replace("-", "").replace("_", ""):
                            link_match_url = href
                            break
                        elif not link_match_url:
                            link_match_url = href

            if not link_match_url:
                return False

            logger.info("[berluti] Navigating to: %s", link_match_url)
            driver.get(link_match_url)
            self._wait_for_page(driver, extra_seconds=4, scroll=True)
            return True
        except Exception:
            logger.exception("[berluti] Navigation failed")
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

    def _from_cdn_patterns(self, source: str, product_code: str) -> List[str]:
        urls = []
        for pat in _CDN_PATTERNS:
            urls.extend(re.findall(pat, source, re.IGNORECASE))

        code_pat = re.escape(product_code.replace(" ", "[-_ ]?").replace("_", "[-_]"))
        generic = re.compile(
            r'(https?://[^\s"\'<>]+?' + code_pat + r'[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
            re.IGNORECASE,
        )
        urls.extend(generic.findall(source))

        return [u for u in urls if not any(
            skip in u.lower() for skip in ("logo", "icon", "sprite", "favicon", "banner", "pixel", "1x1")
        )]

    def _from_img_tags(self, driver: webdriver.Chrome) -> List[str]:
        urls = []
        try:
            images = driver.find_elements(By.TAG_NAME, "img")
            for img in images:
                for attr in ("src", "data-src", "data-zoom-image", "data-large-image"):
                    val = img.get_attribute(attr)
                    if val and val.startswith("http"):
                        if any(skip in val.lower() for skip in ("logo", "icon", "sprite", "favicon", "pixel", "svg", "1x1")):
                            continue
                        if any(ext in val.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(val)
                srcset = img.get_attribute("srcset")
                if srcset:
                    for part in srcset.split(","):
                        part = part.strip().split()[0]
                        if part.startswith("http") and any(ext in part.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(part)
        except Exception:
            logger.exception("[berluti] Error extracting img tags")
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
                    if "berluti" in v.lower():
                        urls.append(v)
                else:
                    urls.extend(self._deep_find_image_urls(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self._deep_find_image_urls(item, depth + 1))
        return urls

    def _select_best_quality(self, urls: List[str]) -> List[str]:
        cleaned: List[str] = []
        for u in urls:
            u_clean = re.sub(r'[?&](w|width|h|height|resize|size|quality|q|imwidth|imheight)=[^&]*', '', u)
            u_clean = re.sub(r'[?&]$', '', u_clean)
            cleaned.append(u_clean)
        return list(dict.fromkeys(cleaned))
