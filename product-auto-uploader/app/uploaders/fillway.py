from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.models import ProductInput, UploadResult
from app.services.image_service import ProductImages
from app.uploaders.base import PlaywrightUploader

_REGISTER_URL = "https://www.feelway.com/tobe/page/mypage/productRegistration.php"
_LOGIN_URL = "https://www.feelway.com/login.php"
_DEFAULT_BRAND_KR_MAP = {
    "louis vuitton": "루이비통",
    "louisvuitton": "루이비통",
    "dior": "디올",
}
_ORIGIN_TEXT = "프랑스, 이탈리아, 스페인 등"
_CONDITION_TEXT = "새 상품"
_ACCESSORY_ETC_TEXT = "선물포장 쇼핑백 및 백화점풀셋"
_CONSULT_PHONE = "01025087086"

# 필웨이 카테고리명 -> radio button ID 매핑
_CATEGORY_MAP = {
    "여성의류": "productCategory106",
    "남성의류": "productCategory107",
    "여성신발": "productCategory101",
    "남성신발": "productCategory102",
    "가방": "productCategory103",
    "핸드백": "productCategory103",
    "지갑": "productCategory104",
    "벨트": "productCategory104",
    "시계": "productCategory110",
    "쥬얼리": "productCategory105",
    "머플러": "productCategory109",
    "선글라스": "productCategory109",
    "패션잡화": "productCategory111",
    "뷰티": "productCategory108",
    "키즈": "productCategory112",
    "골프": "productCategory113",
    "라이프": "productCategory150",
    "bag(woman)": "productCategory103",
    "bag": "productCategory103",
    "women bag": "productCategory103",
    "woman bag": "productCategory103",
}


class FilwayUploader(PlaywrightUploader):
    SITE = "fillway"

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

                page.goto(_REGISTER_URL, wait_until="domcontentloaded")
                self._ensure_logged_in(page)

                self._accept_terms(page)
                self._set_new_product_condition(page)
                brand_kr = self._resolve_brand_display_name(product.brand_name)
                self._select_brand(page, brand_kr)
                self._select_category(page, product.category)
                self._fill_fields(page, product, brand_kr)
                self._upload_images(page, product_images)

                if product.submit_mode == "submit":
                    page.locator("button#productRegisterSubmit").click()
                    page.wait_for_timeout(2000)
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
                page.goto(_REGISTER_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(800)

                if "productRegistration" in page.url or "mypage" in page.url:
                    return "이미 로그인 세션이 준비되어 있습니다."

                self._ensure_logged_in(page)
                return "로그인 세팅이 완료되었습니다."
            finally:
                context.close()

    def _ensure_logged_in(self, page: Page) -> None:
        # 알림 후 리다이렉트 대기
        page.wait_for_timeout(800)

        # 등록 페이지에 있으면 로그인된 상태
        if "productRegistration" in page.url or "mypage" in page.url:
            return

        # 자동 로그인 시도
        creds = self.config.credentials.get(self.SITE)
        if creds and creds.id:
            self.logger.info("자동 로그인 시도: %s", creds.id)
            try:
                if "login" not in page.url:
                    page.goto(_LOGIN_URL, wait_until="domcontentloaded")
                page.locator("input[name='login_id']").fill(creds.id)
                page.locator("input[name='login_password']").fill(creds.pw)
                page.locator("input[name='login_password']").press("Enter")
                page.wait_for_function("() => !window.location.href.includes('login')", timeout=10000)
                page.goto(_REGISTER_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                self.logger.info("자동 로그인 성공")
                return
            except PlaywrightTimeoutError:
                self.logger.warning("자동 로그인 실패, 수동 로그인 대기")

        if not self.site_config.allow_manual_login:
            raise RuntimeError("로그인 세션 없음 - 수동 로그인 비활성화 상태")
        timeout_ms = self.site_config.manual_login_timeout_ms
        self.logger.info("브라우저에서 로그인해 주세요. 최대 %ds.", timeout_ms // 1000)
        page.goto(_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_function("() => !window.location.href.includes('login')", timeout=timeout_ms)
        page.goto(_REGISTER_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

    def _accept_terms(self, page: Page) -> None:
        try:
            page.locator("#clauseTotal").check(timeout=3000)
            page.wait_for_timeout(300)
            self.logger.info("약관 전체 동의 완료")
        except Exception as exc:
            self.logger.warning("약관 동의 실패 (이미 체크됐을 수 있음): %s", exc)

    def _resolve_brand_display_name(self, brand_name: str) -> str:
        merged = dict(_DEFAULT_BRAND_KR_MAP)
        for k, v in self.config.brand_aliases.items():
            if isinstance(k, str) and isinstance(v, str):
                merged[k.strip().lower()] = v.strip()
                merged[k.strip().lower().replace(" ", "")] = v.strip()
        key = brand_name.strip().lower()
        return merged.get(key, merged.get(key.replace(" ", ""), brand_name))

    def _select_brand(self, page: Page, brand_name: str) -> None:
        self._fill_first(page, ["#brandAutoCompleteKeyword", "input[name='brand']", "input[name='brand_name']"], brand_name, "브랜드")

    def _select_category(self, page: Page, category: str) -> None:
        cat_id = self._resolve_category_id(category)
        if not cat_id:
            self.logger.warning("카테고리 매핑 없음: %s", category)
            return
        try:
            page.locator(f"#{cat_id}").click()
            self.logger.info("카테고리 선택: %s -> #%s", category, cat_id)
        except Exception as exc:
            self.logger.warning("카테고리 클릭 실패 (#%s): %s", cat_id, exc)

    def _resolve_category_id(self, category: str) -> str | None:
        normalized = category.strip().lower().replace(" ", "")
        if category in _CATEGORY_MAP:
            return _CATEGORY_MAP[category]
        if normalized in _CATEGORY_MAP:
            return _CATEGORY_MAP[normalized]
        for key, val in _CATEGORY_MAP.items():
            key_n = key.lower().replace(" ", "")
            if key_n in normalized or normalized in key_n:
                return val
        return None

    def _fill_fields(self, page: Page, product: ProductInput, brand_kr: str) -> None:
        composed_name = self._compose_product_name(product, brand_kr)

        market_price = self._calc_market_price(product.price)

        self._fill_first(page, ["input#proprietaryName", "input[name='product_name']"], composed_name, "상품명")
        self._fill_first(page, ["input#sellingPrice", "input[name='price']"], str(product.price), "가격")
        self._fill_first(page, ["#gBuyPrice", "input[name='g_buy_price']"], str(market_price), "시중가(정상가)")
        self._fill_first(page, ["input[name='model_name']", "input[name='serialNo']"], product.product_code, "상품번호")
        self._fill_first(page, ["#stock_total_amount", "input[name='stock_total_amount']"], "10", "재고수량")

        self._set_checked_first(
            page,
            ["#deliveryInfo0101", "input[name='delivery_sending_nation'][value='A']"],
            "배송: 국내배송",
        )
        self._set_checked_first(
            page,
            ["#deliveryInfo0301", "input[name='shipping_method'][value='01']"],
            "배송방법: 택배",
        )
        self._fill_first(page, ["#countryOfOrigin", "input[name='origin_place_value']"], _ORIGIN_TEXT, "원산지(제조국)")

        purchase_place = f"{brand_kr} 부티크" if brand_kr and brand_kr.strip() else None
        self._fill_first(page, ["#purchasePlace", "input[name='product_buy_place']"], purchase_place, "구입 장소")
        self._fill_first(page, ["#flawScratch", "input[name='product_scrach']"], _CONDITION_TEXT, "홈(스크래치 정도)")

        self._set_checked_first(
            page,
            ["#warranty01", "input[name='product_guarantee'][value='Y']"],
            "보증서 유무: 보증서 있음",
        )
        self._set_checked_first(page, ["#partCheck01"], "부속품: 택")
        self._set_checked_first(page, ["#partCheck03"], "부속품: 더스트백")
        self._set_checked_first(page, ["#partCheck04"], "부속품: 케이스")
        self._fill_first(page, ["#etcPart", "input[name='product_etc_part']"], _ACCESSORY_ETC_TEXT, "기타 부속품")
        self._fill_first(page, ["#adviceTel", "input[name='seller_phone']"], _CONSULT_PHONE, "상담가능 연락처")

        self._dispatch_input_change(page, "input#proprietaryName", composed_name)
        self._dispatch_input_change(page, "input#sellingPrice", str(product.price))
        self._dispatch_input_change(page, "#gBuyPrice", str(market_price))
        self._dispatch_input_change(page, "#stock_total_amount", "10")
        self._dispatch_input_change(page, "#countryOfOrigin", _ORIGIN_TEXT)
        if purchase_place:
            self._dispatch_input_change(page, "#purchasePlace", purchase_place)
        self._dispatch_input_change(page, "#flawScratch", _CONDITION_TEXT)
        self._dispatch_input_change(page, "#etcPart", _ACCESSORY_ETC_TEXT)
        self._dispatch_input_change(page, "#adviceTel", _CONSULT_PHONE)

        self._fill_description(page, self._build_description_text(product))
        self.logger.info("필웨이 필드 입력 완료")

    def _set_new_product_condition(self, page: Page) -> None:
        self._set_checked_first(
            page,
            ["#newUsed01", "input[name='product_condition'][value='N']"],
            "새상품/중고품: 새상품",
        )

    def _calc_market_price(self, selling_price: int) -> int:
        ten_pct = selling_price * 0.1
        ndigits = -5 if selling_price >= 1_000_000 else -4
        return selling_price + int(round(ten_pct, ndigits))

    def _compose_product_name(self, product: ProductInput, brand_kr: str) -> str:
        parts = [brand_kr, product.product_name]
        if product.color:
            parts.append(product.color)
        parts.append(product.product_code)
        return " ".join(p.strip() for p in parts if p and p.strip())

    def _fill_description(self, page: Page, description: str) -> None:
        locator = page.locator("textarea#g_intro")
        try:
            locator.wait_for(state="attached", timeout=3000)
            if locator.first.is_visible():
                locator.fill(description)
                return
        except Exception:
            pass

        page.evaluate(
            """(value) => {
                const el = document.querySelector("textarea#g_intro");
                if (!el) return false;
                el.value = value;
                el.dispatchEvent(new Event("input", { bubbles: true }));
                el.dispatchEvent(new Event("change", { bubbles: true }));
                return true;
            }""",
            description,
        )

    def _upload_images(self, page: Page, product_images: ProductImages) -> None:
        if not product_images.files:
            self.logger.info("업로드할 이미지 없음, 건너뜀")
            return
        try:
            file_input = page.locator("input.photoFile").first
            file_input.set_input_files([str(p) for p in product_images.files])
            page.wait_for_timeout(2000)
            self.logger.info("이미지 %d개 업로드 요청", len(product_images.files))
        except Exception as exc:
            self.logger.warning("이미지 업로드 실패: %s", exc)

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
                input_type = ""
                try:
                    input_type = (loc.get_attribute("type") or "").lower()
                except Exception:
                    input_type = ""
                if input_type in {"radio", "checkbox"}:
                    loc.check()
                else:
                    loc.click()
                self.logger.info("%s 클릭", label)
                return
            except Exception:
                continue
        self.logger.warning("%s 클릭 셀렉터를 찾지 못함", label)

    def _dispatch_input_change(self, page: Page, selector: str, value: str) -> None:
        try:
            page.evaluate(
                """({ selector, value }) => {
                    const el = document.querySelector(selector);
                    if (!el) return false;
                    el.value = value;
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    return true;
                }""",
                {"selector": selector, "value": value},
            )
        except Exception:
            pass

    def _set_checked_first(self, page: Page, selectors: Sequence[str], label: str) -> None:
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            try:
                loc.check(force=True)
                self.logger.info("%s 체크", label)
                return
            except Exception:
                try:
                    target_id = loc.get_attribute("id")
                    if target_id:
                        label_loc = page.locator(f"label[for='{target_id}']").first
                        if label_loc.count() > 0:
                            label_loc.click()
                            self.logger.info("%s 라벨 클릭", label)
                            return
                except Exception:
                    pass
                try:
                    loc.click(force=True)
                    self.logger.info("%s 강제 클릭", label)
                    return
                except Exception:
                    continue
        self.logger.warning("%s 체크/클릭 셀렉터를 찾지 못함", label)
