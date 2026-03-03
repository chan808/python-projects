"""Abstract base class for brand-specific crawlers."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import REQUEST_TIMEOUT, SELENIUM_PAGE_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """Template-method base for every brand crawler.

    Subclasses must implement:
        brand_name      – human-readable brand identifier (lowercase)
        build_search_url – construct a search/product URL from product code
        extract_image_urls – pull image URLs from the loaded page
    """

    # ── abstract interface ────────────────────────────────────────────

    @property
    @abstractmethod
    def brand_name(self) -> str:
        """Lowercase brand identifier used for folder names, etc."""

    @abstractmethod
    def build_product_url(self, product_code: str) -> str:
        """Return the URL to load for a given product code.

        This can be a direct product page URL or a search URL.
        """

    @abstractmethod
    def extract_image_urls(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Return a de-duplicated, ordered list of full-res image URLs.

        Called after the page has loaded. Implementations should try, in order:
        1) JSON-LD / embedded state data
        2) CDN URL pattern scanning in page source
        3) Any brand-specific fallback
        """

    # ── template method ───────────────────────────────────────────────

    def crawl(self, driver: webdriver.Chrome, product_code: str) -> List[str]:
        """Navigate to the product page and return image URLs.

        Returns an empty list (never raises) so the caller can continue
        with the next product code on failure.
        """
        url = self.build_product_url(product_code)
        logger.info("[%s] Loading %s for product %s", self.brand_name, url, product_code)

        try:
            driver.get(url)
            self._wait_for_page(driver)
            urls = self.extract_image_urls(driver, product_code)
            urls = self._deduplicate(urls)
            logger.info("[%s] Found %d image(s) for %s", self.brand_name, len(urls), product_code)
            return urls
        except Exception:
            logger.exception("[%s] Failed to crawl product %s", self.brand_name, product_code)
            return []

    # ── helpers available to subclasses ────────────────────────────────

    def _wait_for_page(self, driver: webdriver.Chrome, extra_seconds: float = 2.0, scroll: bool = False) -> None:
        """Wait for document.readyState == 'complete', then optionally scroll."""
        WebDriverWait(driver, SELENIUM_PAGE_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        self._handle_popups(driver)
        if scroll:
            self._scroll_page(driver)
        else:
            time.sleep(extra_seconds)

    def _handle_popups(self, driver: webdriver.Chrome) -> None:
        """Dismiss common cookie banners, region selectors, etc."""
        popup_selectors = [
            "#onetrust-accept-btn-handler",
            ".cookie-banner-accept",
            "button.accept-cookies",
            "#accept-cookies",
            ".js-accept-all",
            "button[id*='accept']",
            "button[class*='accept']",
            "button[title*='Accept']",
            "button[aria-label*='Accept']",
        ]
        for selector in popup_selectors:
            try:
                btn = driver.find_elements(By.CSS_SELECTOR, selector)
                if btn and btn[0].is_displayed():
                    btn[0].click()
                    logger.info("[%s] Dismissed popup using: %s", self.brand_name, selector)
                    time.sleep(1)
                    break
            except Exception:
                continue

    def _scroll_page(self, driver: webdriver.Chrome, pause: float = 1.0) -> None:
        """Scroll down the page to trigger lazy-loaded images."""
        try:
            total_height = driver.execute_script("return document.body.scrollHeight")
            # Scroll in steps
            steps = 4
            for i in range(1, steps + 1):
                driver.execute_script(f"window.scrollTo(0, {total_height * i / steps});")
                time.sleep(pause)
            # Scroll back to top
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        except Exception:
            logger.warning("[%s] Failed to scroll page", self.brand_name)

    @staticmethod
    def _extract_json_ld(page_source: str) -> List[dict]:
        """Extract all JSON-LD blocks from the page source."""
        results: List[dict] = []
        pattern = re.compile(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(page_source):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    results.extend(data)
                else:
                    results.append(data)
            except json.JSONDecodeError:
                continue
        return results

    @staticmethod
    def _extract_urls_by_pattern(page_source: str, pattern: str) -> List[str]:
        """Find all URLs in *page_source* matching *pattern* (regex)."""
        return list(dict.fromkeys(re.findall(pattern, page_source)))

    @staticmethod
    def _pick_highest_resolution(urls: List[str]) -> List[str]:
        """Given a list of CDN URLs with size tokens, prefer the largest variant.

        This is a generic helper; brand crawlers can override with more
        specific logic.
        """
        return urls  # default: return as-is

    @staticmethod
    def _deduplicate(urls: List[str]) -> List[str]:
        """Remove duplicate URLs while preserving order."""
        return list(dict.fromkeys(urls))

    @staticmethod
    def download_image(url: str) -> Optional[bytes]:
        """Download an image and return raw bytes, or None on failure."""
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.content
        except Exception:
            logger.exception("Failed to download %s", url)
            return None
