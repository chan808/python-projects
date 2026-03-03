import streamlit as st
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from scrapers.celine_scraper import CelineScraper
from scrapers.bottega_scraper import BottegaScraper
from utils.gsheet_helper import get_spreadsheet, get_or_create_worksheet, append_products_to_sheet

# --------------------
# 1. 브랜드 선택
# --------------------
st.title("Multi-Brand 상품 크롤러")
brand = st.radio("브랜드 선택", ["Celine", "Bottega"])

# --------------------
# 2. 선택한 브랜드 config 로드
# --------------------
config_file = f"config/{brand.lower()}.json"
with open(config_file, "r", encoding="utf-8") as f:
    config = json.load(f)

spreadsheet_name = config["google_sheets"]["spreadsheet_name"]
service_account_file = config["google_sheets"]["service_account_file"]

# --------------------
# 3. 크롤링 시작
# --------------------
if st.button("크롤링 시작"):
    st.info(f"{brand} 크롤링 시작")

    # Chrome 설정
    chrome_options = Options()
    if config["scraping_settings"].get("headless", False):
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={config['scraping_settings']['user_agent']}")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    try:
        # 브랜드별 scraper 선택
        if brand == "Celine":
            scraper = CelineScraper(driver, config)
        elif brand == "Bottega":
            scraper = BottegaScraper(driver, config)
        else:
            st.error("지원하지 않는 브랜드입니다.")
            driver.quit()

        # 구글 시트 연결
        spreadsheet = get_spreadsheet(service_account_file, spreadsheet_name)

        # 모든 카테고리 순회
        for category_name, url in config["categories"].items():
            sheet_name = f"{brand} : {category_name}"
            ws = get_or_create_worksheet(spreadsheet, sheet_name)
            if ws is None:
                st.warning(f"⚠️ {sheet_name} 이미 존재, 크롤링 건너뜀")
                continue

            st.info(f"{category_name} 크롤링 중...")
            products = scraper.parse_category(category_name, url)
            append_products_to_sheet(ws, products)
            st.success(f"✅ {category_name} 완료: {len(products)}건")

        st.success(f"🎉 {brand} 모든 카테고리 크롤링 완료!")

    finally:
        driver.quit()