"""Dior product image crawler."""

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

# Known Dior image CDN patterns
_CDN_PATTERNS = [
    r'(https?://(?:eci-media|media)\.dior\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
    r'(https?://[a-z0-9.-]*dior[a-z0-9.-]*/couture/[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
    r'(https?://[a-z0-9.-]*dior[a-z0-9.-]*/(?:product|catalog|dam)[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
]


@CrawlerRegistry.register
class DiorCrawler(BaseCrawler):

    @property
    def brand_name(self) -> str:
        return "dior"

    def build_product_url(self, product_code: str) -> str:
        """Use the Dior search page to find the product."""
        return f"https://www.dior.com/ko_kr/search?query={quote_plus(product_code)}"

    # ── main extraction logic ─────────────────────────────────────

    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Try multiple strategies to find product images and combine them."""

        # Strategy 0: Navigate from search results to product page
        if "/search" in driver.current_url:
            if not self._navigate_to_product(driver, product_code):
                logger.warning("[dior] Could not find product page for %s via search", product_code)

        # Trigger lazy loading
        self._scroll_page(driver)
        source = driver.page_source
        all_urls: List[str] = []

        # Strategy 1: JSON-LD structured data (High precision)
        json_ld_urls = self._from_json_ld(source, product_code)
        if json_ld_urls:
            logger.info("[dior] Found %d images via JSON-LD", len(json_ld_urls))
            all_urls.extend(json_ld_urls)

        # Strategy 2: Embedded JavaScript state
        state_urls = self._from_embedded_state(source, product_code)
        if state_urls:
            logger.info("[dior] Found %d images via embedded state", len(state_urls))
            all_urls.extend(state_urls)

        # Strategy 3: CDN URL pattern scanning (Lower precision, filter strictly)
        cdn_urls = self._from_cdn_patterns(source, product_code)
        if cdn_urls:
            logger.info("[dior] Found %d images via CDN patterns", len(cdn_urls))
            all_urls.extend(cdn_urls)

        # Strategy 4: All <img> tags (Fallback, filter strictly)
        img_urls = self._from_img_tags(driver, product_code)
        if img_urls:
            logger.info("[dior] Found %d images via img tags", len(img_urls))
            all_urls.extend(img_urls)

        # Process and filter final list
        final_urls = self._select_best_quality(all_urls)
        
        # Final filter: ensure they likely belong to the product
        # Product images often contain the product code or are from specific CDN paths
        code_part = product_code.lower().replace("_", "").replace("-", "")
        # Build cleaned sets so membership checks work after URL normalisation
        json_ld_clean = set(self._select_best_quality(json_ld_urls))
        state_clean = set(self._select_best_quality(state_urls))
        filtered = []
        for u in final_urls:
            u_lower = u.lower()
            # If we have JSON-LD or State data, they are very reliable.
            # If not, we check if the URL contains a variant of the product code.
            if any(p in u_lower for p in ("product", "couture", "beauty", "jewelry", "fashion")):
                if code_part in u_lower.replace("_", "").replace("-", ""):
                    filtered.append(u)
                elif len(json_ld_urls) == 0 and len(state_urls) == 0:
                    # Fallback if no structured data found
                    filtered.append(u)
            elif len(json_ld_urls) > 0 and u in json_ld_clean:
                filtered.append(u)
            elif len(state_urls) > 0 and u in state_clean:
                filtered.append(u)

        # If filtering was too aggressive and we have nothing, return unfiltered deduplicated
        if not filtered and final_urls:
            return final_urls

        return self._deduplicate(filtered)

    # ── navigation helpers ────────────────────────────────────────

    def _navigate_to_product(self, driver: webdriver.Chrome, product_code: str) -> bool:
        """From search results, navigate to the actual product page."""
        try:
            time.sleep(4) # Wait a bit more for search results
            self._handle_popups(driver)

            source = driver.page_source
            current_url = driver.current_url

            # Dior product codes in URLs often have hyphen instead of underscore
            code_url_variant = product_code.upper().replace("_", "-")
            
            # 1. Try to find a link containing the product code
            link_pattern = re.compile(
                r'href=["\'](https?://(?:www\.)?dior\.com/ko_kr/[^\s"\'<>?]+' + re.escape(code_url_variant) + r'[^\s"\'<>?]+)["\']',
                re.IGNORECASE,
            )
            matches = link_pattern.findall(source)
            link_match_url = next((m for m in matches if m != current_url), None)

            if not link_match_url:
                # 2. Try to find links via CSS selectors with variants
                selectors = [f"a[href*='{code_url_variant}']", f"a[href*='{product_code}']", "a[href*='/products/']", "a[href*='/product/']"]
                for s in selectors:
                    links = driver.find_elements(By.CSS_SELECTOR, s)
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href != current_url and ("/products/" in href or "/product/" in href):
                            # Prefer links that contain the code, but if we have nothing, take the first product link
                            if code_url_variant.lower() in href.lower() or product_code.lower() in href.lower():
                                link_match_url = href
                                break
                            elif not link_match_url:
                                link_match_url = href
                    if link_match_url and (code_url_variant.lower() in link_match_url.lower() or product_code.lower() in link_match_url.lower()):
                         break

            if not link_match_url:
                return False

            logger.info("[dior] Navigating to product page: %s", link_match_url)
            driver.get(link_match_url)
            self._wait_for_page(driver, extra_seconds=4, scroll=True)
            return True
        except Exception:
            logger.exception("[dior] Failed to navigate to product page")
            return False

    # ── extraction strategies ─────────────────────────────────────

    def _from_json_ld(self, source: str, product_code: str) -> List[str]:
        """Extract image URLs from JSON-LD Product schema."""
        blocks = self._extract_json_ld(source)
        urls: List[str] = []
        for block in blocks:
            btype = block.get("@type", "")
            if btype not in ("Product", "IndividualProduct", "ProductGroup"):
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

            # Also check offers → image
            offers = block.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            for offer in offers:
                if isinstance(offer, dict):
                    offer_img = offer.get("image", "")
                    if isinstance(offer_img, str) and offer_img.startswith("http"):
                        urls.append(offer_img)
        return urls

    def _from_embedded_state(self, source: str, product_code: str) -> List[str]:
        """Extract from embedded JSON state objects."""
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});?\s*</script>',
            r'window\.__NEXT_DATA__\s*=\s*({.*?});?\s*</script>',
            r'window\.initialData\s*=\s*({.*?});?\s*</script>',
        ]
        urls: List[str] = []
        for pat in patterns:
            match = re.search(pat, source, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    urls.extend(self._deep_find_image_urls(data, product_code))
                except json.JSONDecodeError:
                    continue
        return urls

    def _from_cdn_patterns(self, source: str, product_code: str) -> List[str]:
        """Scan page source for known Dior CDN image URLs."""
        urls: List[str] = []
        for pat in _CDN_PATTERNS:
            found = re.findall(pat, source, re.IGNORECASE)
            urls.extend(found)

        # Also try a generic approach: any high-res image URL containing the product code
        code_pattern = re.escape(product_code.replace("_", "[-_]"))
        generic_pat = re.compile(
            r'(https?://[^\s"\'<>]+?' + code_pattern + r'[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
            re.IGNORECASE,
        )
        urls.extend(generic_pat.findall(source))

        # Filter out non-product images
        filtered = []
        for u in urls:
            u_lower = u.lower()
            if any(skip in u_lower for skip in ("logo", "icon", "sprite", "favicon", "banner", "pixel", "tracking", "1x1")):
                continue
            filtered.append(u)
        return filtered

    def _from_img_tags(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Extract from <img> elements."""
        urls: List[str] = []
        try:
            images = driver.find_elements(By.TAG_NAME, "img")
            for img in images:
                for attr in ("src", "data-src", "data-zoom-image", "data-large-image"):
                    val = img.get_attribute(attr)
                    if val and val.startswith("http"):
                        val_lower = val.lower()
                        if any(skip in val_lower for skip in ("logo", "icon", "sprite", "favicon", "pixel", "svg", "1x1")):
                            continue
                        if any(ext in val_lower for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(val)

                srcset = img.get_attribute("srcset")
                if srcset:
                    for part in srcset.split(","):
                        part = part.strip().split()[0]
                        if part.startswith("http") and any(ext in part.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(part)
        except Exception:
            logger.exception("[dior] Error extracting img tags")
        return urls

    # ── utility ───────────────────────────────────────────────────

    def _deep_find_image_urls(self, obj, product_code: str, depth: int = 0) -> List[str]:
        """Recursively find image URLs in nested data."""
        if depth > 15:
            return []
        urls: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith("http") and any(ext in v.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    urls.append(v)
                else:
                    urls.extend(self._deep_find_image_urls(v, product_code, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self._deep_find_image_urls(item, product_code, depth + 1))
        return urls

    def _select_best_quality(self, urls: List[str]) -> List[str]:
        """Prefer highest resolution variants, deduplicate."""
        cleaned: List[str] = []
        for u in urls:
            # Strip size-limiting query params to get full resolution
            u_clean = re.sub(r'[?&](w|width|h|height|resize|size|quality|q|imwidth|imheight)=[^&]*', '', u)
            u_clean = re.sub(r'[?&]$', '', u_clean)
            cleaned.append(u_clean)
        return list(dict.fromkeys(cleaned))
