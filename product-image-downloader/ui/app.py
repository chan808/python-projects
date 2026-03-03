"""Streamlit web UI for the luxury brand image extractor."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path so `core.*` imports work.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import LOG_FORMAT, LOG_DATE_FORMAT, OUTPUT_BASE_DIR
from core.crawler.registry import CrawlerRegistry
from core.driver import create_driver
from core.crawler.base import BaseCrawler
from core.image_processor.processor import process_and_save
from core.spreadsheet_reader.reader import read_excel, read_google_sheet

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Register crawlers ─────────────────────────────────────────────────
CrawlerRegistry._ensure_loaded()

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(page_title="Image Extractor", layout="centered")
st.title("Luxury Brand Image Extractor")
st.caption("상품코드 기반 공식 이미지 자동 수집 / 배경 제거 / 1000x1000 정규화")

# ── Brand selector ────────────────────────────────────────────────────
brands = CrawlerRegistry.available_brands()
if not brands:
    st.error("등록된 브랜드 크롤러가 없습니다.")
    st.stop()

brand = st.selectbox("브랜드 선택", options=brands, format_func=str.title)

st.divider()

# ── Input method ──────────────────────────────────────────────────────
input_method = st.radio(
    "상품코드 입력 방식",
    ["직접 입력", "Excel 업로드", "Google Spreadsheet"],
    horizontal=True,
)

product_codes: list[str] = []

if input_method == "직접 입력":
    raw = st.text_area(
        "상품코드 입력 (줄바꿈 또는 쉼표로 구분)",
        height=120,
        placeholder="예:\nL100J2X9838SI\n1ADPO350YKY, M0446CWGH_M900",
    )
    if raw.strip():
        product_codes = [
            c.strip()
            for c in raw.replace(",", "\n").splitlines()
            if c.strip()
        ]

elif input_method == "Excel 업로드":
    uploaded_file = st.file_uploader("Excel 파일 (.xlsx)", type=["xlsx"])
    c1, c2 = st.columns(2)
    col_excel = c1.text_input("열 (Column)", value="A", max_chars=3)
    row_excel = c2.text_input("행 (Row)", placeholder="예: 2-10 또는 2,3,5")
    if uploaded_file and col_excel.strip() and row_excel.strip():
        try:
            product_codes = read_excel(uploaded_file.getvalue(), col_excel, row_excel)
        except Exception as e:
            st.error(f"Excel 읽기 실패: {e}")

else:  # Google Spreadsheet
    gsheet_url = st.text_input("Google Spreadsheet URL (공개 문서)")
    c1, c2 = st.columns(2)
    col_gs = c1.text_input("열 (Column)", value="A", max_chars=3)
    row_gs = c2.text_input("행 (Row)", placeholder="예: 2-10 또는 2,3,5")
    if gsheet_url.strip() and col_gs.strip() and row_gs.strip():
        try:
            product_codes = read_google_sheet(gsheet_url, col_gs, row_gs)
        except Exception as e:
            st.error(f"Google Sheet 읽기 실패: {e}")

# ── Preview ───────────────────────────────────────────────────────────
if product_codes:
    preview = ", ".join(product_codes[:10])
    suffix = f" ... 외 {len(product_codes) - 10}건" if len(product_codes) > 10 else ""
    st.info(f"**{len(product_codes)}건** 인식: {preview}{suffix}")

st.divider()

# ── Execute ───────────────────────────────────────────────────────────
if st.button("실행", type="primary", disabled=not product_codes, use_container_width=True):
    succeeded: list[str] = []
    failed: list[str] = []
    details: dict[str, str] = {}  # code → failure reason

    progress = st.progress(0.0, text="Chrome 드라이버 초기화 중...")
    status_text = st.empty()
    log_expander = st.expander("실시간 로그", expanded=True)

    driver = None
    try:
        driver = create_driver()
        crawler: BaseCrawler = CrawlerRegistry.get(brand)()
        total = len(product_codes)

        for i, code in enumerate(product_codes):
            pct = i / total
            progress.progress(pct, text=f"[{i + 1}/{total}] {code}")

            with log_expander:
                st.text(f">>> {code} 크롤링 시작")

            # 1. Crawl
            image_urls = crawler.crawl(driver, code)
            if not image_urls:
                failed.append(code)
                details[code] = "이미지를 찾을 수 없음"
                with log_expander:
                    st.text(f"    {code}: 이미지 없음 (실패)")
                continue

            with log_expander:
                st.text(f"    {code}: {len(image_urls)}개 이미지 발견, 처리 중...")

            # 2. Download + process each image
            save_dir = OUTPUT_BASE_DIR / crawler.brand_name / code
            saved_count = 0

            # Only process up to 5 images as requested
            target_images = image_urls[:5]
            with log_expander:
                st.text(f"    {code}: {len(image_urls)}개 이미지 발견, 상위 {len(target_images)}개 처리 중...")

            for idx, img_url in enumerate(target_images):
                img_bytes = crawler.download_image(img_url)
                if img_bytes is None:
                    continue

                # Determine original file extension from the URL
                url_ext = Path(img_url.split("?")[0]).suffix.lower()
                if url_ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    url_ext = ".jpg"

                # Save original image as-is
                origin_path = save_dir / f"{code}_{idx + 1:02d}_origin{url_ext}"
                origin_path.parent.mkdir(parents=True, exist_ok=True)
                origin_path.write_bytes(img_bytes)

                # Save background-removed version
                save_path = save_dir / f"{code}_{idx + 1:02d}.png"
                if process_and_save(img_bytes, save_path):
                    saved_count += 1

            if saved_count > 0:
                succeeded.append(code)
                with log_expander:
                    st.text(f"    {code}: {saved_count}개 저장 완료 (원본 + 누끼 각 {saved_count}장)")
            else:
                failed.append(code)
                details[code] = "이미지 다운로드/처리 실패"
                with log_expander:
                    st.text(f"    {code}: 처리 실패")

        progress.progress(1.0, text="완료!")

    except Exception as e:
        st.error(f"치명적 오류: {e}")
        logger.exception("Fatal error")
    finally:
        if driver:
            driver.quit()

    # ── Results ───────────────────────────────────────────────────
    st.divider()
    st.subheader("결과 요약")
    c1, c2 = st.columns(2)
    c1.metric("성공", f"{len(succeeded)} 건")
    c2.metric("실패", f"{len(failed)} 건")

    if succeeded:
        output_dir = OUTPUT_BASE_DIR / crawler.brand_name
        st.success(f"저장 위치: `{output_dir}`")
        with st.expander("성공 목록"):
            for code in succeeded:
                st.text(code)

    if failed:
        with st.expander("실패 목록", expanded=True):
            for code in failed:
                reason = details.get(code, "알 수 없음")
                st.text(f"{code}  —  {reason}")
