from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import AppConfig, FieldSelectorConfig, MustitSelectors, ProductInput, UploadResult
from app.services.image_service import ProductImages
from app.uploaders.base import BaseUploader


class MustitUploader(BaseUploader):
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.selectors = self._load_selectors(config.mustit.selectors_path)

    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        started_at = datetime.now(timezone.utc)
        screenshot_path = None
        context = None
        page = None

        try:
            register_url = self._require_value("mustit.register_url", self.config.mustit.register_url)

            with sync_playwright() as playwright:
                context = self._launch_context(playwright)
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)

                page = context.pages[0] if context.pages else context.new_page()
                page.goto(register_url, wait_until="domcontentloaded")
                self._ensure_login_ready(page)
                self._fill_fields(page, product)
                self._upload_images(page, product_images)

                if product.submit_mode == "submit":
                    submit_selector = self._require_value(
                        "selectors.submit_button.selector",
                        self.selectors.submit_button.selector if self.selectors.submit_button else "",
                    )
                    page.locator(submit_selector).click()
                    message = "Submit button clicked."
                else:
                    message = "Preview mode completed. Review the browser and submit manually."

                return UploadResult(
                    site="mustit",
                    product_code=product.product_code,
                    success=True,
                    submit_mode=product.submit_mode,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    message=message,
                )
        except Exception as exc:
            self.logger.exception("Mustit uploader failed.")
            if page is not None:
                screenshot_path = self._capture_failure_screenshot(page, product.product_code)
            return UploadResult(
                site="mustit",
                product_code=product.product_code,
                success=False,
                submit_mode=product.submit_mode,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                message=str(exc),
                screenshot_path=screenshot_path,
            )
        finally:
            if context is not None:
                context.close()

    def prepare_login_session(self) -> str:
        selector = self._require_value("mustit.login_check_selector", self.config.mustit.login_check_selector)
        register_url = self._require_value("mustit.register_url", self.config.mustit.register_url)

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
                    if not self.config.mustit.allow_manual_login:
                        raise RuntimeError("로그인 세션이 없고 수동 로그인이 비활성화되어 있습니다.")

                    timeout_seconds = int(self.config.mustit.manual_login_timeout_ms / 1000)
                    self.logger.info(
                        "브라우저에서 로그인하세요. 로그인 확인 셀렉터가 나타날 때까지 최대 %s초 기다립니다.",
                        timeout_seconds,
                    )
                    page.wait_for_selector(
                        selector,
                        state="visible",
                        timeout=self.config.mustit.manual_login_timeout_ms,
                    )
                    page.goto(register_url, wait_until="domcontentloaded")
                    return "로그인 세션 저장이 완료되었습니다."
            finally:
                context.close()

    def _fill_fields(self, page: Page, product: ProductInput) -> None:
        for field_name, field_config in self.selectors.fields.items():
            selector = self._require_value("fields.%s.selector" % field_name, field_config.selector)
            value = self._resolve_field_value(product, field_name, field_config)
            locator = page.locator(selector)

            if field_config.action == "fill":
                locator.fill(value)
            elif field_config.action == "type":
                locator.fill("")
                locator.type(value, delay=50)
            elif field_config.action == "select_option":
                locator.select_option(label=value)
            else:
                raise ValueError("Unsupported field action: %s" % field_config.action)

            self.logger.info("Filled field '%s' with value '%s'.", field_name, value)

    def _upload_images(self, page: Page, product_images: ProductImages) -> None:
        upload_selector = self._require_value("image_upload.selector", self.selectors.image_upload.selector)
        page.locator(upload_selector).set_input_files([str(path) for path in product_images.files])
        self.logger.info("Uploaded %s image(s).", len(product_images.files))

    def _ensure_login_ready(self, page: Page) -> None:
        selector = self.config.mustit.login_check_selector.strip()
        if not selector:
            return

        try:
            page.wait_for_selector(selector, state="visible", timeout=5000)
            return
        except PlaywrightTimeoutError:
            if not self.config.mustit.allow_manual_login:
                raise

        timeout_seconds = int(self.config.mustit.manual_login_timeout_ms / 1000)
        self.logger.info("로그인이 필요합니다. 브라우저에서 로그인하세요. 최대 %s초 기다립니다.", timeout_seconds)
        page.wait_for_selector(
            selector,
            state="visible",
            timeout=self.config.mustit.manual_login_timeout_ms,
        )
        page.goto(self.config.mustit.register_url, wait_until="domcontentloaded")

    def _resolve_field_value(
        self,
        product: ProductInput,
        field_name: str,
        field_config: FieldSelectorConfig,
    ) -> str:
        if field_config.value_template:
            return field_config.value_template.format(**product.model_dump())

        if field_name == "price":
            return product.price_text

        value = getattr(product, field_name, None)
        if value is None:
            raise ValueError("Unknown product field requested by selector config: %s" % field_name)
        return str(value)

    def _load_selectors(self, path: Path) -> MustitSelectors:
        if not path.exists():
            raise FileNotFoundError("Selector file does not exist: %s" % path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return MustitSelectors.model_validate(data)

    def _capture_failure_screenshot(self, page: Page, product_code: str) -> Optional[str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        screenshot_path = self.config.paths.screenshots_dir / ("%s-mustit-%s.png" % (timestamp, product_code))
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            self.logger.exception("Failed to capture screenshot.")
            return None
        return str(screenshot_path)

    def _launch_context(self, playwright: Any) -> Any:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.browser.user_data_dir),
            headless=self.config.browser.headless,
            slow_mo=self.config.browser.slow_mo_ms,
        )

    @staticmethod
    def _require_value(name: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or "TODO" in cleaned.upper():
            raise ValueError("Required configuration is missing: %s" % name)
        return cleaned
