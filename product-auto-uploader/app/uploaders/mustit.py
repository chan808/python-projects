from __future__ import annotations

from datetime import datetime, timezone

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import ProductInput, UploadResult
from app.services.image_service import ProductImages
from app.uploaders.base import PlaywrightUploader

_ADD01_URL = "https://mustit.co.kr/product/add01"


class MustitUploader(PlaywrightUploader):
    SITE = "mustit"

    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        started_at = datetime.now(timezone.utc)
        screenshot_path = None
        context = None
        page = None

        try:
            with sync_playwright() as playwright:
                context = self._launch_context(playwright)
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)

                page = context.pages[0] if context.pages else context.new_page()
                page.on("dialog", lambda d: d.dismiss())

                page.goto(_ADD01_URL, wait_until="domcontentloaded")
                self._ensure_logged_in(page)

                if "add01" in page.url:
                    self._proceed_to_add02(page)

                self._dismiss_consent_modal(page)
                self._select_brand(page, product.brand_name)
                self._select_category(page, product.category)
                self._fill_fields(page, product)

                if product.color:
                    self._fill_color(page, product.color)
                if product.size:
                    self._fill_size(page, str(product.size))

                self._upload_images(page, product_images)

                if product.submit_mode == "submit":
                    page.locator("input#add_btn").click()
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
            if context is not None:
                context.close()

    def prepare_login_session(self) -> str:
        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)
                page = context.pages[0] if context.pages else context.new_page()
                page.on("dialog", lambda d: d.dismiss())
                page.goto(_ADD01_URL, wait_until="domcontentloaded")

                if "/member/login" not in page.url:
                    return "이미 로그인 세션이 준비되어 있습니다."

                self._ensure_logged_in(page)
                return "로그인 세션 저장이 완료되었습니다."
            finally:
                context.close()

    def _ensure_logged_in(self, page: Page) -> None:
        if "/member/login" not in page.url:
            return

        creds = self.config.credentials.get(self.SITE)
        if creds and creds.id:
            self.logger.info("자동 로그인 시도: %s", creds.id)
            try:
                page.locator("input[name='id']").fill(creds.id)
                page.locator("input[name='pw']").fill(creds.pw)
                page.locator("input[name='pw']").press("Enter")
                page.wait_for_url("**/product/**", timeout=10000)
                self.logger.info("자동 로그인 성공")
                return
            except PlaywrightTimeoutError:
                self.logger.warning("자동 로그인 실패, 수동 로그인 대기")

        if not self.site_config.allow_manual_login:
            raise RuntimeError("로그인 세션 없음 - 수동 로그인 비활성화 상태")
        timeout_ms = self.site_config.manual_login_timeout_ms
        self.logger.info("브라우저에서 로그인하세요. 최대 %ds.", timeout_ms // 1000)
        page.wait_for_url("**/product/**", timeout=timeout_ms)

    def _proceed_to_add02(self, page: Page) -> None:
        try:
            next_btn = page.locator("input[value='다음단계'], button:has-text('다음단계')")
            next_btn.click(timeout=5000)
            page.wait_for_url("**/add02**", timeout=10000)
        except PlaywrightTimeoutError:
            self.logger.warning("add01 → add02 전환 실패, URL: %s", page.url)

    def _dismiss_consent_modal(self, page: Page) -> None:
        try:
            page.locator("#divLongchampConfirm").wait_for(state="visible", timeout=2000)
            page.locator("#divLongchampConfirm input[value='동의함']").click()
            self.logger.info("동의함 모달 처리 완료")
        except PlaywrightTimeoutError:
            pass

    def _select_brand(self, page: Page, brand_name: str) -> None:
        match = page.evaluate(
            """(name) => {
                const spans = document.querySelectorAll('[id^="brand_list_"] span');
                for (const s of spans) {
                    if (s.textContent.trim() === name) { s.click(); return 'exact'; }
                }
                const lower = name.toLowerCase();
                for (const s of spans) {
                    if (s.textContent.trim().toLowerCase().includes(lower)) { s.click(); return 'partial'; }
                }
                return null;
            }""",
            brand_name,
        )
        if match:
            self.logger.info("브랜드 선택: %s (%s match)", brand_name, match)
        else:
            self.logger.warning("브랜드 없음: %s", brand_name)

    def _select_category(self, page: Page, category: str) -> None:
        try:
            page.locator("#flag_Women").click()
            page.wait_for_timeout(300)
            page.locator("#category_search_input").fill(category)
            page.locator("#category_search_btn").click()
            page.wait_for_timeout(500)
            first_result = page.locator("#category_choice p[onclick]").first
            first_result.click(timeout=3000)
            self.logger.info("카테고리 선택: %s", category)
        except (PlaywrightTimeoutError, Exception) as exc:
            self.logger.warning("카테고리 선택 실패 (%s): %s", category, exc)

    def _fill_color(self, page: Page, color: str) -> None:
        try:
            page.locator("#option_color_use").click()
            page.wait_for_timeout(200)
            page.locator("input[name='tmpOptionColor[]']").fill(color[:10])
            self.logger.info("색상 입력: %s", color[:10])
        except Exception as exc:
            self.logger.warning("색상 입력 실패: %s", exc)

    def _fill_size(self, page: Page, size: str) -> None:
        try:
            page.locator("#option_size_use").click()
            page.wait_for_timeout(200)
            page.locator("input[name='tmpOptionSize[]']").fill(size[:10])
            self.logger.info("사이즈 입력: %s", size[:10])
        except Exception as exc:
            self.logger.warning("사이즈 입력 실패: %s", exc)

    def _upload_images(self, page: Page, product_images: ProductImages) -> None:
        if not product_images.files:
            self.logger.info("업로드할 이미지 없음, 건너뜀")
            return
        try:
            file_input = page.locator("input[type='file']")
            file_input.set_input_files([str(p) for p in product_images.files])
            page.locator("input#uploadfiles").click()
            page.wait_for_timeout(2000)
            self.logger.info("이미지 %d장 업로드 요청", len(product_images.files))
        except Exception as exc:
            self.logger.warning("이미지 업로드 실패: %s", exc)
