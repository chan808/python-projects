from __future__ import annotations

from datetime import datetime, timezone

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import AppConfig, ProductInput, UploadResult
from app.services.image_service import ProductImages
from app.uploaders.base import PlaywrightUploader

import logging

_LIST_URL = "https://partner.trenbe.com/v2/product/add"
_LOGIN_URL = "https://partner.trenbe.com/login"


class TrenbeUploader(PlaywrightUploader):
    SITE = "trenbe"

    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        started_at = datetime.now(timezone.utc)

        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            form_page = None
            screenshot_path = None
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)

                list_page = context.pages[0] if context.pages else context.new_page()
                list_page.on("dialog", lambda d: d.dismiss())

                list_page.goto(_LIST_URL, wait_until="domcontentloaded")
                self._ensure_logged_in(list_page, context)
                list_page.wait_for_timeout(1000)

                # "신규 상품 생성" 클릭 → 새 탭 오픈
                with context.expect_page() as new_page_info:
                    list_page.locator("button:has-text('신규 상품 생성')").click()
                form_page = new_page_info.value
                form_page.wait_for_load_state("domcontentloaded")
                form_page.wait_for_timeout(1500)
                form_page.on("dialog", lambda d: d.dismiss())

                self._fill_product_name(form_page, product)
                self._fill_english_name(form_page)
                self._fill_brand(form_page, product)
                self._select_category(form_page, product)
                self._select_new_product(form_page)
                self._fill_prices(form_page, product)
                self._fill_description(form_page, product)

                if product.submit_mode == "submit":
                    form_page.locator("button:has-text('저장')").click()
                    form_page.wait_for_timeout(2000)
                    message = "업로드 완료"
                else:
                    self.logger.info("작성 완료. 브라우저에서 확인 후 닫아주세요.")
                    while True:
                        try:
                            form_page.wait_for_timeout(1000)
                        except Exception:
                            break
                    message = "미리보기 완료"

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
                target = form_page or (context.pages[0] if context.pages else None)
                if target is not None:
                    screenshot_path = self._capture_screenshot(target, product.product_code)
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
                try:
                    context.close()
                except Exception:
                    pass

    def prepare_login_session(self) -> str:
        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)
                page = context.pages[0] if context.pages else context.new_page()
                page.on("dialog", lambda d: d.dismiss())
                page.goto(_LIST_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(800)

                if self._is_logged_in(page):
                    return "이미 로그인 세션이 준비되어 있습니다."

                self._ensure_logged_in(page, context)
                return "로그인 세팅이 완료되었습니다."
            finally:
                context.close()

    def _is_logged_in(self, page: Page) -> bool:
        try:
            return page.locator("button:has-text('신규 상품 생성')").count() > 0
        except Exception:
            return False

    def _ensure_logged_in(self, page: Page, context: BrowserContext) -> None:
        page.wait_for_timeout(800)
        if self._is_logged_in(page):
            return

        creds = self.config.credentials.get(self.SITE)
        if creds and creds.id:
            self.logger.info("자동 로그인 시도: %s", creds.id)
            try:
                page.goto(_LOGIN_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(500)
                page.locator("input[name='username']").fill(creds.id)
                page.locator("input[name='password']").fill(creds.pw)
                page.locator("input[name='password']").press("Enter")
                page.wait_for_function("() => !window.location.href.includes('/login')", timeout=10000)
                page.goto(_LIST_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                self.logger.info("자동 로그인 성공")
                return
            except PlaywrightTimeoutError:
                self.logger.warning("자동 로그인 실패, 수동 로그인 대기")

        if not self.site_config.allow_manual_login:
            raise RuntimeError("로그인 세션 없음 - 수동 로그인 비활성화 상태")
        timeout_ms = self.site_config.manual_login_timeout_ms
        self.logger.info("브라우저에서 로그인해 주세요. 최대 %ds.", timeout_ms // 1000)
        page.wait_for_function("() => !window.location.href.includes('/login')", timeout=timeout_ms)
        page.goto(_LIST_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

    def _fill_product_name(self, page: Page, product: ProductInput) -> None:
        composed = self._compose_product_name(product)
        self._fill_input(page, 'input[name="name"]', composed, "상품명")

    def _fill_english_name(self, page: Page) -> None:
        self._fill_input(page, 'input[name="shortDesc"]', "english", "영문상품명")

    def _fill_brand(self, page: Page, product: ProductInput) -> None:
        self._fill_input(page, 'input[name="brandNameView"]', product.brand_name.strip(), "브랜드")

    def _select_category(self, page: Page, product: ProductInput) -> None:
        # 카테고리 구현 예정
        pass

    def _select_new_product(self, page: Page) -> None:
        try:
            page.locator('input[name="isProductUsed"][value="0"]').check(force=True)
            self.logger.info("중고 여부: 새상품 선택")
        except Exception as exc:
            self.logger.warning("새상품 선택 실패: %s", exc)

    def _fill_prices(self, page: Page, product: ProductInput) -> None:
        selling_price = product.price or 0
        cost_price = product.original_price if product.original_price is not None else selling_price
        self._fill_input(page, 'input[name="priceSupply"]', str(cost_price), "매입(공급)가격")
        self._fill_input(page, 'input[name="priceLocal"]', str(cost_price), "매입(공급)가격(현지)")
        self._fill_input(page, 'input[name="price"]', str(selling_price), "판매가격")

    def _fill_description(self, page: Page, product: ProductInput) -> None:
        text = self._build_description_text(product)
        if not text:
            return

        # CKEditor가 초기화될 때까지 최대 5초 대기
        try:
            page.wait_for_function(
                "() => typeof CKEDITOR !== 'undefined' && Object.keys(CKEDITOR.instances).length > 0",
                timeout=5000,
            )
        except Exception:
            pass

        try:
            set_ok = page.evaluate(
                """(text) => {
                    if (typeof CKEDITOR === 'undefined') return false;
                    const inst = CKEDITOR.instances['txtLongDesc']
                        || CKEDITOR.instances[Object.keys(CKEDITOR.instances)[0]];
                    if (inst) { inst.setData(text); return true; }
                    return false;
                }""",
                text,
            )
            if set_ok:
                self.logger.info("상품상세 입력 완료 (CKEditor)")
                return
        except Exception as exc:
            self.logger.warning("CKEditor 접근 실패: %s", exc)

        # iframe 내 contenteditable body 직접 접근
        for frame in page.frames:
            try:
                if frame == page.main_frame:
                    continue
                body = frame.locator("body")
                if body.count() == 0:
                    continue
                if body.get_attribute("contenteditable") == "true":
                    body.fill(text)
                    self.logger.info("상품상세 입력 완료 (iframe contenteditable)")
                    return
            except Exception:
                continue

        self.logger.warning("상품상세 입력 실패: CKEditor 및 iframe 모두 접근 불가")

    def _compose_product_name(self, product: ProductInput) -> str:
        parts = [product.brand_name, product.product_name]
        if product.color:
            parts.append(product.color)
        parts.append(product.product_code)
        return " ".join(p.strip() for p in parts if p and p.strip())

    def _fill_input(self, page: Page, selector: str, value: str, label: str) -> None:
        try:
            page.locator(selector).fill(value)
            self.logger.info("%s 입력: %s", label, value)
        except Exception as exc:
            self.logger.warning("%s 입력 실패 (%s): %s", label, selector, exc)
