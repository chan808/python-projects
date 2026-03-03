"""Bottega Veneta product image crawler."""

from __future__ import annotations

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

# Bottega Veneta (Salesforce Commerce Cloud) image patterns
# NOTE: outer quotes are double-quotes so the inner single-quote in the
#       character class [^\s"'<>] is a plain ASCII apostrophe, not a curly quote.
_CDN_PATTERNS = [
    # Kering DAM – actual product images (e.g. eCom-796966V4LQ24028_A.jpg)
    r"(https?://(?:bottega-veneta|bottegaveneta)\.dam\.kering\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
    # SFCC DIS – fallback
    r"(https?://(?:www\.)?bottegaveneta\.com/dw/image/v2/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?)",
]


@CrawlerRegistry.register
class BottegaVenetaCrawler(BaseCrawler):

    @property
    def brand_name(self) -> str:
        return "bottega_veneta"

    def build_product_url(self, product_code: str) -> str:
        return f"https://www.bottegaveneta.com/ko-kr/search?q={quote_plus(product_code)}"

    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Navigate to product page and extract high-res images."""

        if "/search" in driver.current_url:
            if not self._navigate_to_product(driver, product_code):
                logger.warning("[bottega_veneta] Could not find product page for %s", product_code)

        self._scroll_page(driver)

        # Primary: read directly from the product carousel slides (exact count, no noise)
        carousel_urls = self._from_carousel(driver)
        if carousel_urls:
            logger.info("[bottega_veneta] Found %d images via carousel", len(carousel_urls))
            return self._deduplicate(carousel_urls)

        # Fallback: CDN pattern scan + JSON-LD (used only when carousel is not found)
        logger.warning("[bottega_veneta] Carousel not found, falling back to CDN scan")
        source = driver.page_source
        all_urls: List[str] = []

        json_ld_urls = self._from_json_ld(source, product_code)
        all_urls.extend(json_ld_urls)

        cdn_urls = self._from_cdn_patterns(source, product_code)
        all_urls.extend(cdn_urls)

        final_urls = self._select_best_quality(all_urls)
        json_ld_clean = set(self._select_best_quality(json_ld_urls))

        code_upper = product_code.upper()
        code_clean = product_code.lower().replace("-", "").replace("_", "")
        filtered = []
        for u in final_urls:
            if code_upper in u.upper() or code_clean in u.lower().replace("-", "").replace("_", ""):
                filtered.append(u)
            elif u in json_ld_clean:
                filtered.append(u)

        if not filtered and final_urls:
            return self._deduplicate(final_urls)

        return self._deduplicate(filtered)

    def _navigate_to_product(self, driver: webdriver.Chrome, product_code: str) -> bool:
        """From search results, navigate to the actual product page using live DOM."""
        try:
            self._handle_popups(driver)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.html']"))
                )
            except Exception:
                time.sleep(4)

            current_url = driver.current_url
            code_clean = product_code.lower().replace("-", "").replace("_", "").replace(".", "")
            links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
            candidate = None

            # Pass 1: link whose href contains the product code
            for link in links:
                href = link.get_attribute("href") or ""
                if not href or href == current_url or "/search" in href:
                    continue
                if "bottegaveneta.com/ko-kr/" not in href or not href.endswith(".html"):
                    continue
                href_clean = href.lower().replace("-", "").replace("_", "").replace(".", "")
                if code_clean in href_clean:
                    candidate = href
                    break

            # Pass 2: first product .html link that is not a category/search page
            if not candidate:
                for link in links:
                    href = link.get_attribute("href") or ""
                    if (href
                            and "bottegaveneta.com/ko-kr/" in href
                            and href.endswith(".html")
                            and href != current_url
                            and "/search" not in href
                            and href.count("/") >= 5):   # category pages have fewer slashes
                        candidate = href
                        break

            if not candidate:
                return False

            logger.info("[bottega_veneta] Navigating to: %s", candidate)
            driver.get(candidate)
            self._wait_for_page(driver, extra_seconds=3, scroll=True)
            return True

        except Exception:
            logger.exception("[bottega_veneta] Navigation failed")
            return False

    def _from_json_ld(self, source: str, product_code: str) -> List[str]:
        blocks = self._extract_json_ld(source)
        urls = []
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

    def _from_cdn_patterns(self, source: str, product_code: str) -> List[str]:
        urls = []
        for pat in _CDN_PATTERNS:
            urls.extend(re.findall(pat, source, re.IGNORECASE))
        # Filter obvious non-product images
        return [u for u in urls if not any(
            skip in u.lower() for skip in ("logo", "icon", "sprite", "favicon", "banner", "pixel")
        )]

    def _from_carousel(self, driver: webdriver.Chrome) -> List[str]:
        """Read Large images directly from product carousel slides.

        Each <li.c-productcarousel__slide> contains one product image.
        data-srcset lists sizes (Small_thumbnail → Large); we pick Large.
        """
        urls = []
        try:
            slides = driver.find_elements(
                By.CSS_SELECTOR, "li.c-productcarousel__slide"
            )
            for slide in slides:
                try:
                    img = slide.find_element(By.CSS_SELECTOR, "img[data-srcset]")
                    srcset = img.get_attribute("data-srcset") or ""
                    best_url = None
                    for part in srcset.split(","):
                        candidate = part.strip().split()[0] if part.strip() else ""
                        if "Large-" in candidate and candidate.startswith("http"):
                            best_url = candidate
                            break
                    # Fallback to data-src (Medium) if no Large found in srcset
                    if not best_url:
                        best_url = img.get_attribute("data-src") or ""
                    if best_url and best_url.startswith("http"):
                        urls.append(best_url)
                except Exception:
                    continue
        except Exception:
            logger.exception("[bottega_veneta] Error reading carousel")
        return urls

    def _from_img_tags(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        urls = []
        try:
            images = driver.find_elements(
                By.CSS_SELECTOR,
                "img.c-product__image, .c-productgallery img, .pdp-images img"
            )
            if not images:
                images = driver.find_elements(By.TAG_NAME, "img")

            for img in images:
                for attr in ("src", "data-src", "data-zoom-image"):
                    val = img.get_attribute(attr)
                    if val and val.startswith("http"):
                        if any(ext in val.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                            urls.append(val)

                srcset = img.get_attribute("srcset")
                if srcset:
                    for part in srcset.split(","):
                        url = part.strip().split()[0]
                        if url.startswith("http") and any(
                            ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")
                        ):
                            urls.append(url)
        except Exception:
            logger.exception("[bottega_veneta] Error extracting img tags")
        return urls

    def _select_best_quality(self, urls: List[str]) -> List[str]:
        """
        Kering DAM URLs: keep only the largest size per image variant (A, B, C...).
          Sizes in descending quality: Large > Medium > Small > Thumbnail > Small_thumbnail
        SFCC DIS URLs: strip size params and append q=90.
        """
        _DAM_SIZES = ["Large", "Medium", "Small", "Thumbnail", "Small_thumbnail"]

        dam_by_letter: dict = {}   # letter -> (priority, url)
        other_urls: list = []

        for u in urls:
            if "dam.kering.com" in u:
                m = re.search(
                    r"/(Small_thumbnail|Thumbnail|Small|Medium|Large)-[^/]+_([A-Z])\."
                    r"(?:jpg|jpeg|png|webp)",
                    u, re.IGNORECASE,
                )
                if m:
                    size   = m.group(1)
                    letter = m.group(2).upper()
                    priority = _DAM_SIZES.index(size) if size in _DAM_SIZES else 99
                    if letter not in dam_by_letter or priority < dam_by_letter[letter][0]:
                        dam_by_letter[letter] = (priority, u)
                else:
                    other_urls.append(u)
            else:
                # SFCC DIS or other CDN
                u_clean = re.sub(r"[?&](sw|sh|sm|q|format)=[^&]*", "", u)
                u_clean = re.sub(r"[?&]$", "", u_clean)
                if "/dw/image/v2/" in u_clean:
                    sep = "&" if "?" in u_clean else "?"
                    u_clean += f"{sep}q=90"
                other_urls.append(u_clean)

        # Return: A → B → C → ... (sorted by letter), then other URLs deduplicated
        # dam_by_letter[letter] = (priority, url_string) — extract index 1 for the URL
        result = [dam_by_letter[letter][1] for letter in sorted(dam_by_letter.keys())]
        result.extend(list(dict.fromkeys(other_urls)))
        return result
