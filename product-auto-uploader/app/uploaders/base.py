from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import AppConfig, FieldSelectorConfig, ProductInput, SiteConfig, SiteSelectors, UploadResult
from app.services.image_service import ProductImages


class BaseUploader(ABC):
    @abstractmethod
    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        raise NotImplementedError


class PlaywrightUploader(BaseUploader):
    SITE: str = ""

    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.site_config: SiteConfig = getattr(config, self.SITE)
        self.selectors = self._load_selectors(self.site_config.selectors_path)

    @property
    def _user_data_dir(self) -> Path:
        return self.config.browser.user_data_dir / self.SITE

    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        started_at = datetime.now(timezone.utc)
        register_url = self._require_url(self.site_config.register_url)

        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            page = None
            screenshot_path = None
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)

                page = context.pages[0] if context.pages else context.new_page()
                page.goto(register_url, wait_until="domcontentloaded")
                self._ensure_login_ready(page)
                self._fill_fields(page, product)
                self._upload_images(page, product_images)

                if product.submit_mode == "submit":
                    submit_sel = self._require_selector(
                        self.selectors.submit_button.selector if self.selectors.submit_button else ""
                    )
                    page.locator(submit_sel).click()
                    message = "Submit button clicked."
                else:
                    message = "Preview mode: form filled, not submitted."

                return UploadResult(
                    site=self.SITE,
                    product_code=product.product_code,
                    success=True,
                    submit_mode=product.submit_mode,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    message=message,
                )
            except Exception as exc:
                self.logger.exception("%s uploader failed: %s", self.SITE, exc)
                if page is not None:
                    screenshot_path = self._capture_screenshot(page, product.product_code)
                return UploadResult(
                    site=self.SITE,
                    product_code=product.product_code,
                    success=False,
                    submit_mode=product.submit_mode,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    message=str(exc),
                    screenshot_path=screenshot_path,
                )
            finally:
                context.close()

    def prepare_login_session(self) -> str:
        selector = self._require_selector(self.site_config.login_check_selector)
        register_url = self._require_url(self.site_config.register_url)

        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(register_url, wait_until="domcontentloaded")

                try:
                    page.wait_for_selector(selector, state="visible", timeout=5000)
                    return "이미 로그인 세션이 준비되어 있습니다."
                except PlaywrightTimeoutError:
                    if not self.site_config.allow_manual_login:
                        raise RuntimeError("로그인 세션이 없고 수동 로그인이 비활성화되어 있습니다.")

                timeout_s = int(self.site_config.manual_login_timeout_ms / 1000)
                self.logger.info("브라우저에서 로그인하세요. 최대 %s초 기다립니다.", timeout_s)
                page.wait_for_selector(selector, state="visible", timeout=self.site_config.manual_login_timeout_ms)
                page.goto(register_url, wait_until="domcontentloaded")
                return "로그인 세션 저장이 완료되었습니다."
            finally:
                context.close()

    def _fill_fields(self, page: Page, product: ProductInput) -> None:
        for field_name, field_config in self.selectors.fields.items():
            selector = field_config.selector.strip()
            if not selector or "TODO" in selector.upper():
                self.logger.debug("셀렉터 미설정, 건너뜀: %s", field_name)
                continue

            value = self._resolve_field_value(product, field_name, field_config)
            if value is None:
                continue

            locator = page.locator(selector)
            if field_config.action == "fill":
                locator.fill(value)
            elif field_config.action == "type":
                locator.fill("")
                locator.type(value, delay=50)
            elif field_config.action == "select_option":
                locator.select_option(label=value)

            self.logger.info("입력: %s = %s", field_name, value)

    def _upload_images(self, page: Page, product_images: ProductImages) -> None:
        upload_sel = self._require_selector(self.selectors.image_upload.selector)
        page.locator(upload_sel).set_input_files([str(p) for p in product_images.files])
        self.logger.info("이미지 %s장 업로드 완료.", len(product_images.files))

    def _ensure_login_ready(self, page: Page) -> None:
        selector = self.site_config.login_check_selector.strip()
        if not selector:
            return
        try:
            page.wait_for_selector(selector, state="visible", timeout=5000)
            return
        except PlaywrightTimeoutError:
            if not self.site_config.allow_manual_login:
                raise

        timeout_s = int(self.site_config.manual_login_timeout_ms / 1000)
        self.logger.info("로그인이 필요합니다. 브라우저에서 로그인하세요. 최대 %s초.", timeout_s)
        page.wait_for_selector(selector, state="visible", timeout=self.site_config.manual_login_timeout_ms)
        page.goto(self.site_config.register_url, wait_until="domcontentloaded")

    def _resolve_field_value(
        self,
        product: ProductInput,
        field_name: str,
        field_config: FieldSelectorConfig,
    ) -> Optional[str]:
        if field_config.value_template:
            return field_config.value_template.format(**product.model_dump())
        if field_name == "price":
            return product.price_text
        value = getattr(product, field_name, None)
        return str(value) if value is not None else None

    def _load_selectors(self, path: Path) -> SiteSelectors:
        if not path.exists():
            raise FileNotFoundError(f"셀렉터 파일 없음: {path}")
        return SiteSelectors.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _capture_screenshot(self, page: Page, product_code: str) -> Optional[str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = self.config.paths.screenshots_dir / f"{timestamp}-{self.SITE}-{product_code}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            self.logger.exception("스크린샷 캡처 실패.")
            return None

    def _launch_context(self, playwright: Any) -> Any:
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._user_data_dir),
            headless=self.config.browser.headless,
            slow_mo=self.config.browser.slow_mo_ms,
        )

    def _require_url(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"[{self.SITE}] 등록 URL이 설정되지 않았습니다.")
        return cleaned

    def _build_description_text(self, product: ProductInput) -> str:
        fields = [
            ("상품명", product.product_name),
            ("SKU", product.product_code),
            ("색상", product.color),
            ("소재", product.material),
            ("사이즈", product.size),
        ]
        parts = [f"{label}: {value}" for label, value in fields if value and str(value).strip()]
        return " / ".join(parts)

    def _require_selector(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or "TODO" in cleaned.upper():
            raise ValueError(f"[{self.SITE}] 필수 셀렉터가 설정되지 않았습니다: {cleaned!r}")
        return cleaned
