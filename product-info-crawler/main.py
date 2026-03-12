from pathlib import Path

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from scrapers.registry import get_scraper_class
from utils.config_loader import ConfigError, discover_brand_configs, load_brand_config
from utils.gsheet_helper import (
    append_products_to_sheet,
    get_or_create_worksheet,
    get_spreadsheet,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"


def build_driver(config: dict) -> webdriver.Chrome:
    chrome_options = Options()
    scraping_settings = config.get("scraping_settings", {})

    if scraping_settings.get("headless", False):
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    user_agent = scraping_settings.get("user_agent")
    if user_agent:
        chrome_options.add_argument(f"user-agent={user_agent}")

    return webdriver.Chrome(options=chrome_options)


def run_scraping(brand_name: str, scraper_key: str, config: dict) -> None:
    driver = None

    try:
        scraper_cls = get_scraper_class(scraper_key)
        driver = build_driver(config)
        scraper = scraper_cls(driver, config)

        google_sheets_config = config["google_sheets"]
        spreadsheet = get_spreadsheet(
            google_sheets_config["service_account_file"],
            google_sheets_config["spreadsheet_name"],
        )

        for category_name, url in config["categories"].items():
            sheet_name = f"{brand_name} : {category_name}"
            worksheet = get_or_create_worksheet(spreadsheet, sheet_name)

            if worksheet is None:
                st.warning(f"{sheet_name} 시트가 이미 있어 이번 실행에서는 건너뜁니다.")
                continue

            st.info(f"{category_name} 수집 중")
            products = scraper.parse_category(category_name, url)
            append_products_to_sheet(worksheet, products)
            st.success(f"{category_name} 완료: {len(products)}건")

        st.success(f"{brand_name} 전체 카테고리 수집이 끝났습니다.")

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

    try:
        config = load_brand_config(selected_brand.config_path, project_root=PROJECT_ROOT)
    except ConfigError as exc:
        st.error(f"설정 파일을 불러오지 못했습니다: {exc}")
        st.stop()

    if st.button("크롤링 시작", type="primary"):
        st.info(f"{selected_brand.display_name} 수집을 시작합니다.")

        try:
            run_scraping(selected_brand.display_name, selected_brand.scraper_key, config)
        except Exception as exc:
            st.exception(exc)


if __name__ == "__main__":
    main()
