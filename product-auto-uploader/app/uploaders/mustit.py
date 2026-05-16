from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import ProductInput, UploadResult
from app.services.image_service import ProductImages
from app.uploaders.base import PlaywrightUploader

_ADD01_URL = "https://mustit.co.kr/product/add01"
_DEFAULT_BRAND_KR_MAP = {
    "louis vuitton": "루이비통",
    "louisvuitton": "루이비통",
    "dior": "디올",
}
_ORIGIN_TEXT = "프랑스, 이탈리아, 스페인 등"
_ORIGIN_TEXT = "프랑스, 이탈리아, 스페인 등"
_CONDITION_TEXT = "새 상품"
_ACCESSORY_ETC_TEXT = "선물포장 쇼핑백 및 백화점풀셋"
_CONSULT_PHONE = "01025087086"


class MustitUploader(PlaywrightUploader):
    SITE = "mustit"

    def run(self, product: ProductInput, product_images: ProductImages) -> UploadResult:
        started_at = datetime.now(timezone.utc)

        with sync_playwright() as playwright:
            context = self._launch_context(playwright)
            page = None
            screenshot_path = None
            try:
                context.set_default_navigation_timeout(self.config.browser.navigation_timeout_ms)
                context.set_default_timeout(self.config.browser.action_timeout_ms)

                page = context.pages[0] if context.pages else context.new_page()
                page.on("dialog", lambda d: d.dismiss())

                page.goto(_ADD01_URL, wait_until="domcontentloaded")
                self._ensure_logged_in(page)

                if "add01" in page.url:
                    self._proceed_to_add02(page)

                self._dismiss_consent_modal(page)
                brand_kr = self._resolve_brand_display_name(product.brand_name)
                self._fill_brand_only(page, brand_kr)
                self._select_category(page, product.category)
                self._fill_fields(page, product, brand_kr)

                if product.color:
                    self._fill_color(page, product.color)
                if product.size:
                    self._fill_size(page, str(product.size))

                self._upload_images(page, product_images)

                if product.submit_mode == "submit":
                    page.locator("input#add_btn").click()
                    page.wait_for_timeout(1500)
                    message = "업로드 완료"
                else:
                    self.logger.info("작성 완료. 브라우저에서 확인 후 닫아주세요.")
                    while True:
                        try:
                            page.wait_for_timeout(1000)
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
                page.goto(_ADD01_URL, wait_until="domcontentloaded")

                if "/member/login" not in page.url:
                    return "이미 로그인 세션이 준비되어 있습니다."

                self._ensure_logged_in(page)
                return "로그인 세팅이 완료되었습니다."
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
        self.logger.info("브라우저에서 로그인해 주세요. 최대 %ds.", timeout_ms // 1000)
        page.wait_for_url("**/product/**", timeout=timeout_ms)

    def _proceed_to_add02(self, page: Page) -> None:
        try:
            next_btn = page.locator("input[value='다음단계'], button:has-text('다음단계')")
            next_btn.click(timeout=5000)
            page.wait_for_url("**/add02**", timeout=10000)
        except PlaywrightTimeoutError:
            self.logger.warning("add01 -> add02 전환 실패, URL: %s", page.url)

    def _dismiss_consent_modal(self, page: Page) -> None:
        try:
            page.locator("#divLongchampConfirm").wait_for(state="visible", timeout=2000)
            page.locator("#divLongchampConfirm input[value='동의함']").click()
            self.logger.info("동의 모달 처리 완료")
        except PlaywrightTimeoutError:
            pass

    def _resolve_brand_display_name(self, brand_name: str) -> str:
        merged = dict(_DEFAULT_BRAND_KR_MAP)
        for k, v in self.config.brand_aliases.items():
            if isinstance(k, str) and isinstance(v, str):
                merged[k.strip().lower()] = v.strip()
                merged[k.strip().lower().replace(" ", "")] = v.strip()
        key = brand_name.strip().lower()
        return merged.get(key, merged.get(key.replace(" ", ""), brand_name))

    def _fill_brand_only(self, page: Page, brand_name_kr: str) -> None:
        if not brand_name_kr or not brand_name_kr.strip():
            self.logger.info("브랜드 값이 비어 있어 브랜드 입력을 건너뜀")
            return
        self._fill_first(page, ["input#brand_search_input"], brand_name_kr, "브랜드")

    def _select_category(self, page: Page, category: str) -> None:
        try:
            page.locator("#flag_Women").click()
            page.wait_for_timeout(300)
            page.locator("#category_search_input").fill(category)
            page.locator("#category_search_input").press("Enter")
            page.wait_for_timeout(500)
            first_result = page.locator("#category_choice p[onclick]").first
            first_result.click(timeout=3000)
            self.logger.info("카테고리 선택: %s", category)
        except (PlaywrightTimeoutError, Exception) as exc:
            self.logger.warning("카테고리 선택 실패 (%s): %s", category, exc)

    def _fill_fields(self, page: Page, product: ProductInput, brand_kr: str) -> None:
        composed_name = self._compose_product_name(product, brand_kr)
        self.logger.info("조합 상품명: %s", composed_name)

        self._fill_first(page, ["input[name='product_name']"], composed_name, "상품명")
        self._fill_first(page, ["input[name='serialNo']"], product.product_code, "상품번호")
        self._fill_first(page, ["input[name='normal_price']"], str(product.price), "판매가격")
        self._fill_first(page, ["input[name='stock[]']"], "1", "재고 수량")
        self._click_first(page, ["#pkg_brand_shopping_bag"], "포장: 브랜드 쇼핑백")
        self._click_first(page, ["#comp_dust_bag"], "구성품: 더스트백")
        self._click_first(page, ["#comp_guarantee_card"], "구성품: 개런티카드")
        self._click_first(page, ["#comp_authentic_tag"], "구성품: 정품택")
        self._fill_first(page, ["input[name='wonsanji_text']"], _ORIGIN_TEXT, "원산지")
        self._click_first(page, ["#substitution"], "판매형태: 구매대행")
        self._fill_description(page, self._build_description_text(product))

    def _compose_product_name(self, product: ProductInput, brand_kr: str) -> str:
        parts = [brand_kr, product.product_name]
        if product.color:
            parts.append(product.color)
        parts.append(product.product_code)
        return " ".join(p.strip() for p in parts if p and p.strip())

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
            self.logger.info("이미지 %d개 업로드 요청", len(product_images.files))
        except Exception as exc:
            self.logger.warning("이미지 업로드 실패: %s", exc)

    def _fill_description(self, page: Page, text: str) -> None:
        self._fill_first(page, ["textarea#ir1", "textarea[name='ir1']"], text, "상품상세")

    def _fill_first(self, page: Page, selectors: Sequence[str], value: Optional[str], label: str) -> None:
        if value is None or not str(value).strip():
            self.logger.info("%s 값이 없어 입력 건너뜀", label)
            return

        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            try:
                loc.fill(str(value))
                self.logger.info("%s 입력: %s", label, value)
                return
            except Exception:
                continue
        self.logger.warning("%s 입력 셀렉터를 찾지 못함", label)

    def _click_first(self, page: Page, selectors: Sequence[str], label: str) -> None:
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            try:
                loc.click()
                self.logger.info("%s 클릭", label)
                return
            except Exception:
                continue
        self.logger.warning("%s 클릭 셀렉터를 찾지 못함", label)
