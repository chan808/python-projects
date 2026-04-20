import random
import time
from pathlib import Path
from typing import Optional

import streamlit as st
import undetected_chromedriver as uc
from selenium_stealth import stealth
from selenium.webdriver.chrome.options import Options

from scrapers.registry import get_scraper_class
from utils.config_loader import ConfigError, discover_brand_configs, load_brand_config
from utils.excel_helper import (
    EXCEL_OUTPUT_FOLDER_NAME,
    append_products_to_excel_sheet,
    get_excel_output_path,
    get_or_create_excel_workbook,
    get_or_create_excel_worksheet,
    save_excel_workbook,
)
from utils.gsheet_helper import (
    WRITE_MODE_APPEND,
    WRITE_MODE_OVERWRITE,
    append_products_to_sheet,
    get_or_create_worksheet,
    get_spreadsheet,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
STORAGE_TARGET_GOOGLE_SHEETS = "google_sheets"
STORAGE_TARGET_EXCEL = "excel"


def build_driver(config: dict) -> uc.Chrome:
    chrome_options = uc.ChromeOptions()
    scraping_settings = config.get("scraping_settings", {})

    # [중요] headless 모드는 아카마이 감지 확률을 크게 높이므로 가급적 끕니다.
    if scraping_settings.get("headless", False):
        chrome_options.add_argument("--headless")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")
    chrome_options.add_argument("--start-maximized")

    # [수정] stealth 라이브러리를 사용하지 않고 uc 본연의 우회 기능만 사용
    # 최신 Akamai는 stealth의 중복 설정을 감지할 수 있음
    driver = uc.Chrome(options=chrome_options, use_subprocess=True)

    # 창 크기 고정
    driver.set_window_size(1920, 1080)
    
    # [추가] 초기 접속 전 쿠키 및 캐시 삭제 효과를 위해 약간 대기
    time.sleep(random.uniform(1, 2))

    return driver


def save_products(
    storage_target: str,
    brand_name: str,
    category_name: str,
    write_mode: str,
    spreadsheet,
    workbook,
    excel_path: Optional[Path],
    products: list[dict],
) -> tuple[int, str]:
    if storage_target == STORAGE_TARGET_GOOGLE_SHEETS:
        sheet_name = f"{brand_name} : {category_name}"
        worksheet, created = get_or_create_worksheet(spreadsheet, sheet_name)
        saved_count = append_products_to_sheet(worksheet, products, write_mode=write_mode)

        if created:
            detail_message = "새 구글 시트 생성"
        elif write_mode == WRITE_MODE_OVERWRITE:
            detail_message = "기존 구글 시트 덮어쓰기"
        else:
            detail_message = "기존 구글 시트 이어쓰기"

        return saved_count, detail_message

    worksheet, created = get_or_create_excel_worksheet(workbook, category_name)
    saved_count = append_products_to_excel_sheet(worksheet, products, write_mode=write_mode)
    save_excel_workbook(workbook, excel_path)

    if created:
        detail_message = "새 엑셀 시트 생성"
    elif write_mode == WRITE_MODE_OVERWRITE:
        detail_message = "기존 엑셀 시트 덮어쓰기"
    else:
        detail_message = "기존 엑셀 시트 이어쓰기"

    return saved_count, detail_message


def run_scraping(
    brand_name: str,
    scraper_key: str,
    config: dict,
    write_mode: str,
    selected_categories: list[str],
    storage_target: str,
) -> None:
    driver = None
    spreadsheet = None
    workbook = None
    excel_path = None

    try:
        config["project_root"] = str(PROJECT_ROOT)
        scraper_cls = get_scraper_class(scraper_key)
        if getattr(scraper_cls, "requires_driver", True):
            driver = build_driver(config)

        scraper = scraper_cls(driver, config)

        if storage_target == STORAGE_TARGET_GOOGLE_SHEETS:
            google_sheets_config = config["google_sheets"]
            spreadsheet = get_spreadsheet(
                google_sheets_config["service_account_file"],
                google_sheets_config["spreadsheet_name"],
            )
        else:
            excel_path = get_excel_output_path(brand_name)
            workbook = get_or_create_excel_workbook(excel_path)

        categories_to_process = [
            (category_name, url)
            for category_name, url in config["categories"].items()
            if category_name in selected_categories
        ]

        progress_bar = st.progress(0.0, text="크롤링 준비 중")
        status_container = st.container()
        result_container = st.container()
        category_results = []
        inter_category_delay_sec = float(config.get("scraping_settings", {}).get("inter_category_delay_sec", 0))

        for index, (category_name, url) in enumerate(categories_to_process, start=1):
            progress_ratio = index / len(categories_to_process)
            progress_bar.progress(
                progress_ratio,
                text=f"{index}/{len(categories_to_process)} {category_name} 처리 중",
            )

            try:
                with status_container:
                    st.info(f"{category_name} 수집 중")

                products = scraper.parse_category(category_name, url)
                saved_count, detail_message = save_products(
                    storage_target=storage_target,
                    brand_name=brand_name,
                    category_name=category_name,
                    write_mode=write_mode,
                    spreadsheet=spreadsheet,
                    workbook=workbook,
                    excel_path=excel_path,
                    products=products,
                )

                category_results.append(
                    {
                        "category": category_name,
                        "status": "success",
                        "saved_count": saved_count,
                        "detail": detail_message,
                    }
                )
            except Exception as exc:
                category_results.append(
                    {
                        "category": category_name,
                        "status": "error",
                        "saved_count": 0,
                        "detail": str(exc),
                    }
                )

            if inter_category_delay_sec > 0 and index < len(categories_to_process):
                # [수정] 고정된 대기 시간 대신 무작위성을 부여하여 봇 탐지 회피 (8~15초 권장)
                actual_delay = inter_category_delay_sec * random.uniform(0.8, 1.5)
                with status_container:
                    st.caption(f"다음 카테고리를 위해 {actual_delay:.1f}초간 대기 중...")
                time.sleep(actual_delay)

        progress_bar.progress(1.0, text="크롤링 완료")

        success_count = sum(1 for result in category_results if result["status"] == "success")
        error_count = len(category_results) - success_count

        with result_container:
            if error_count == 0:
                st.success(f"{brand_name} 전체 카테고리 수집이 끝났습니다. 성공 {success_count}건")
            else:
                st.warning(
                    f"{brand_name} 수집이 완료되었습니다. 성공 {success_count}건, 실패 {error_count}건"
                )

            for result in category_results:
                if result["status"] == "success":
                    st.success(
                        f"{result['category']} 완료: {result['saved_count']}건 저장 ({result['detail']})"
                    )
                else:
                    st.error(f"{result['category']} 실패: {result['detail']}")

            if storage_target == STORAGE_TARGET_EXCEL and excel_path is not None:
                st.info(f"엑셀 저장 위치: {excel_path} ({EXCEL_OUTPUT_FOLDER_NAME} 폴더)")


    finally:
        if driver is not None:
            driver.quit()


def main() -> None:
    st.title("멀티 브랜드 상품 크롤러")

    try:
        brand_summaries = discover_brand_configs(CONFIG_DIR, PROJECT_ROOT)
    except ConfigError as exc:
        st.error(f"브랜드 설정을 불러오지 못했습니다: {exc}")
        st.stop()

    brand_by_id = {brand.brand_id: brand for brand in brand_summaries}
    selected_brand_id = st.radio(
        "브랜드 선택",
        [brand.brand_id for brand in brand_summaries],
        format_func=lambda brand_id: brand_by_id[brand_id].display_name,
        horizontal=True,
    )
    selected_brand = brand_by_id[selected_brand_id]

    storage_target = st.radio(
        "저장 대상",
        [STORAGE_TARGET_GOOGLE_SHEETS, STORAGE_TARGET_EXCEL],
        format_func=lambda target: "Google Sheets" if target == STORAGE_TARGET_GOOGLE_SHEETS else "Excel",
        horizontal=True,
    )
    write_mode = st.radio(
        "저장 방식",
        [WRITE_MODE_OVERWRITE, WRITE_MODE_APPEND],
        format_func=lambda mode: "덮어쓰기" if mode == WRITE_MODE_OVERWRITE else "이어쓰기",
        horizontal=True,
    )

    try:
        config = load_brand_config(
            selected_brand.config_path,
            project_root=PROJECT_ROOT,
            validate_credentials=(storage_target == STORAGE_TARGET_GOOGLE_SHEETS),
        )
    except ConfigError as exc:
        st.error(f"설정 파일을 불러오지 못했습니다: {exc}")
        st.stop()

    category_names = list(config["categories"].keys())
    selected_categories = st.multiselect(
        "수집할 카테고리",
        category_names,
        default=category_names,
        help="선택한 카테고리만 실행합니다.",
    )

    if storage_target == STORAGE_TARGET_EXCEL:
        excel_path = get_excel_output_path(selected_brand.display_name)
        st.caption(f"엑셀 파일: {excel_path}")

    if not selected_categories:
        st.warning("최소 1개 이상의 카테고리를 선택해야 합니다.")

    if st.button("크롤링 시작", type="primary"):
        if not selected_categories:
            st.stop()

        st.info(f"{selected_brand.display_name} 수집을 시작합니다.")

        try:
            run_scraping(
                brand_name=selected_brand.display_name,
                scraper_key=selected_brand.scraper_key,
                config=config,
                write_mode=write_mode,
                selected_categories=selected_categories,
                storage_target=storage_target,
            )
        except Exception as exc:
            st.exception(exc)


if __name__ == "__main__":
    main()
