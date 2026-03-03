"""Celine product image crawler."""

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

# Known Celine image CDN patterns
_CDN_PATTERNS = [
    r'(https?://(?:twicpics\.celine\.com|media\.celine\.com|image\.celine\.com|celine\.dam\.kering\.com)[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
    r'(https?://[a-z0-9.-]*celine[a-z0-9.-]*/[^\s"\'<>]*?/(?:product|catalog|image|original)[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)',
]


@CrawlerRegistry.register
class CelineCrawler(BaseCrawler):

    @property
    def brand_name(self) -> str:
        return "celine"

    def build_product_url(self, product_code: str) -> str:
        """Use the Celine search page to find the product."""
        return f"https://www.celine.com/ko-kr/search?q={quote_plus(product_code)}"

    # ── main extraction logic ─────────────────────────────────────

    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Try multiple strategies to find product images and combine them."""

        # Strategy 0: Navigate from search results to product page
        if "/search" in driver.current_url:
            if not self._navigate_to_product(driver, product_code):
                logger.warning("[celine] Could not find product page for %s via search", product_code)

        # Trigger lazy loading
        self._scroll_page(driver)
        source = driver.page_source
        all_urls: List[str] = []

        # Strategy 1: JSON-LD structured data
        json_ld_urls = self._from_json_ld(source, product_code)
        if json_ld_urls:
            logger.info("[celine] Found %d images via JSON-LD", len(json_ld_urls))
            all_urls.extend(json_ld_urls)

        # Strategy 2: Embedded JavaScript state / data
        state_urls = self._from_embedded_state(source, product_code)
        if state_urls:
            logger.info("[celine] Found %d images via embedded state", len(state_urls))
            all_urls.extend(state_urls)

        # Strategy 3: CDN URL pattern scanning
        cdn_urls = self._from_cdn_patterns(source, product_code)
        if cdn_urls:
            logger.info("[celine] Found %d images via CDN patterns", len(cdn_urls))
            all_urls.extend(cdn_urls)

        # Strategy 4: All <img> src/srcset
        img_urls = self._from_img_tags(driver, product_code)
        if img_urls:
            logger.info("[celine] Found %d images via img tags", len(img_urls))
            all_urls.extend(img_urls)

        # Process and filter final list
        final_urls = self._select_best_quality(all_urls)
        
        # Final filter: ensure they likely belong to the product
        code_part = product_code.lower().replace(" ", "").replace("-", "")
        # Build cleaned sets so membership checks work after URL normalisation
        json_ld_clean = set(self._select_best_quality(json_ld_urls))
        state_clean = set(self._select_best_quality(state_urls))
        filtered = []
        for u in final_urls:
            u_lower = u.lower()
            # Celine product images usually have the product code in the name or are from specific CDN paths
            if "celine.com" in u_lower or "twicpics" in u_lower:
                if code_part in u_lower.replace("-", "").replace("_", ""):
                    filtered.append(u)
                elif any(p in u_lower for p in ("product", "catalog", "image")):
                    filtered.append(u)
                elif len(json_ld_urls) == 0 and len(state_urls) == 0:
                    filtered.append(u)
            elif len(json_ld_urls) > 0 and u in json_ld_clean:
                filtered.append(u)
            elif len(state_urls) > 0 and u in state_clean:
                filtered.append(u)

        if not filtered and final_urls:
            return final_urls

        return self._deduplicate(filtered)

    # ── navigation helpers ────────────────────────────────────────

    def _navigate_to_product(self, driver: webdriver.Chrome, product_code: str) -> bool:
        """From search results, navigate to the actual product page using live DOM."""
        try:
            self._handle_popups(driver)

            # Search results load via AJAX — wait for at least one .html link to appear
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.html']"))
                )
            except Exception:
                time.sleep(4)  # fallback static wait

            current_url = driver.current_url
            code_clean = product_code.lower().replace("-", "").replace("_", "").replace(".", "")

            # Query live DOM for all anchor elements
            links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
            candidate = None

            # Pass 1: prefer a link whose href contains the product code
            for link in links:
                href = link.get_attribute("href") or ""
                if not href or href == current_url or "/search" in href:
                    continue
                if "celine.com/ko-kr/" not in href or not href.endswith(".html"):
                    continue
                href_clean = href.lower().replace("-", "").replace("_", "").replace(".", "")
                if code_clean in href_clean:
                    candidate = href
                    break

            # Pass 2: fall back to the first product .html link on the page
            if not candidate:
                for link in links:
                    href = link.get_attribute("href") or ""
                    if (href and "celine.com/ko-kr/" in href
                            and href.endswith(".html")
                            and href != current_url
                            and "/search" not in href):
                        candidate = href
                        break

            if not candidate:
                return False

            logger.info("[celine] Navigating to product page: %s", candidate)
            driver.get(candidate)
            self._wait_for_page(driver, extra_seconds=3, scroll=True)
            return True
        except Exception:
            logger.exception("[celine] Failed to navigate to product page")
            return False

    # ── extraction strategies ─────────────────────────────────────

    def _from_json_ld(self, source: str, product_code: str) -> List[str]:
        """Extract image URLs from JSON-LD Product schema."""
        blocks = self._extract_json_ld(source)
        urls: List[str] = []
        for block in blocks:
            if block.get("@type") not in ("Product", "IndividualProduct"):
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

    def _from_embedded_state(self, source: str, product_code: str) -> List[str]:
        """Extract from window.__INITIAL_STATE__ or similar embedded JSON."""
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
                    urls.extend(self._deep_find_image_urls(data, product_code))
                except json.JSONDecodeError:
                    continue
        return urls

    def _from_cdn_patterns(self, source: str, product_code: str) -> List[str]:
        """Scan page source for known Celine CDN image URLs."""
        urls: List[str] = []
        for pat in _CDN_PATTERNS:
            found = re.findall(pat, source, re.IGNORECASE)
            urls.extend(found)

        # Filter: keep only those that look like product images (not icons/logos)
        filtered = []
        for u in urls:
            u_lower = u.lower()
            if any(skip in u_lower for skip in ("logo", "icon", "sprite", "favicon", "banner", "pixel")):
                continue
            filtered.append(u)
        return filtered

    def _from_img_tags(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Extract image URLs from <img> elements via Selenium."""
        urls: List[str] = []
        try:
            # Try to focus on main product image containers
            selectors = [".pdp-main-images", ".product-images", ".product-carousel", ".pdp-images"]
            elements = []
            for s in selectors:
                elements.extend(driver.find_elements(By.CSS_SELECTOR, s))
            
            # If no containers found, use the whole body
            if not elements:
                elements = [driver.find_element(By.TAG_NAME, "body")]

            for container in elements:
                images = container.find_elements(By.TAG_NAME, "img")
                for img in images:
                    for attr in ("src", "data-src", "data-zoom-image", "data-high-res"):
                        val = img.get_attribute(attr)
                        if val and val.startswith("http"):
                            val_lower = val.lower()
                            if any(skip in val_lower for skip in ("logo", "icon", "sprite", "favicon", "pixel", "svg", "ui", "header", "footer")):
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
            logger.exception("[celine] Error extracting img tags")
        return urls

    # ── utility ───────────────────────────────────────────────────

    def _deep_find_image_urls(self, obj, product_code: str, depth: int = 0) -> List[str]:
        """Recursively search a nested dict/list for image URLs."""
        if depth > 20:
            return []
        urls: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith("http") and any(ext in v.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    # Keep if it looks like a Celine image
                    if "celine" in v.lower() or "twicpics" in v.lower():
                        urls.append(v)
                else:
                    urls.extend(self._deep_find_image_urls(v, product_code, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                urls.extend(self._deep_find_image_urls(item, product_code, depth + 1))
        return urls

    def _select_best_quality(self, urls: List[str]) -> List[str]:
        """Prefer higher-resolution variants and remove duplicates."""
        cleaned: List[str] = []
        for u in urls:
            # Strip only resize/size-related parameters.
            # Do NOT strip all query params — some (e.g. from=N, view=N) identify
            # distinct product angles and must be preserved.
            u_clean = re.sub(r'[?&]im=Resize=[^&]*', '', u)
            u_clean = re.sub(r'[?&](w|width|h|height|resize|size|quality|q|imwidth|imheight)=[^&]*', '', u_clean, flags=re.IGNORECASE)
            u_clean = re.sub(r'[?&]$', '', u_clean)
            cleaned.append(u_clean)

        return list(dict.fromkeys(cleaned))

