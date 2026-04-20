import random
import re
import time

from bs4 import BeautifulSoup


def human_scroll(driver, distance: int = None):
    """실제 사람이 스크롤하는 것처럼 작은 단위로 나누어 스크롤합니다."""
    # [수정] 스크롤 단위를 키워서 더 시원시원하게 내려가도록 함
    if distance is None:
        distance = driver.execute_script("return window.innerHeight") * random.uniform(1.2, 1.8)
    
    current_pos = driver.execute_script("return window.pageYOffset")
    target_pos = current_pos + distance
    
    # [수정] 단계를 줄여서 더 빠르게 스크롤
    steps = random.randint(2, 4)
    step_distance = distance / steps
    
    for _ in range(steps):
        move = step_distance * random.uniform(0.9, 1.1)
        driver.execute_script(f"window.scrollBy(0, {move});")
        time.sleep(random.uniform(0.05, 0.15))


def scroll_until_lazy_content_loaded(
    driver,
    pause_time: float,
    product_card_selector: str,
    placeholder_selector: str,
    max_loops: int = 8,
    max_placeholder_retries: int = 2,
    stable_rounds_to_finish: int = 2,
) -> dict:
    from selenium.webdriver.common.by import By
    last_count = 0
    stable_rounds = 0
    placeholder_retries = 0

    for _ in range(max_loops):
        # [수정] 인간다운 스크롤 적용
        human_scroll(driver)
        
        # [추가] "더보기" 또는 "View More" 버튼이 보일 경우 클릭 시도
        try:
            # 루이비통의 다양한 더보기 버튼 텍스트 대응 (띄어쓰기 유무 모두 포함)
            # [수정] 화면에 보이는 '모든' 더보기 버튼을 찾아서 클릭
            load_more_buttons = driver.find_elements(By.XPATH, "//button[contains(., '더 보기') or contains(., '더보기') or contains(., 'View more') or contains(., 'Load more') or contains(., 'View More') or contains(., 'Load More')]")
            clicked_any = False
            for btn in load_more_buttons:
                if btn.is_displayed():
                    # 버튼의 위치로 이동 후 클릭 (더 안정적)
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked_any = True
                    # 버튼 클릭 후 데이터가 로드될 시간을 줌
                    time.sleep(1.5)
            
            if clicked_any:
                # 무언가 클릭했다면 추가 데이터 로드를 위해 한 번 더 대기
                time.sleep(1.0)
        except Exception:
            pass

        time.sleep(pause_time * random.uniform(0.8, 1.2))

        html = driver.page_source
        # [수정] 잘못된 파서 이름 'parser.parser'를 'html.parser'로 통일
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(product_card_selector)
        placeholders = soup.select(placeholder_selector) if placeholder_selector else []
        product_count = len(cards)
        placeholder_count = len(placeholders)

        if placeholder_count > 0 and placeholder_retries < max_placeholder_retries:
            placeholder_retries += 1
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(pause_time)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)
            continue

        if product_count == last_count:
            stable_rounds += 1
            if stable_rounds >= stable_rounds_to_finish:
                break
        else:
            last_count = product_count
            stable_rounds = 0

    final_html = driver.page_source
    final_soup = BeautifulSoup(final_html, "html.parser")
    final_products = len(final_soup.select(product_card_selector))
    final_placeholders = len(final_soup.select(placeholder_selector)) if placeholder_selector else 0

    return {
        "product_count": final_products,
        "placeholder_count": final_placeholders,
        "placeholder_retries": placeholder_retries,
    }


def scroll_to_bottom(driver, pause_time: float, product_card_selector: str = None):
    """페이지 끝까지 스크롤하여 모든 데이터를 로드합니다."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        human_scroll(driver)
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def parse_price(tag):
    content_price = tag.get("content")
    if content_price:
        return int(content_price)

    price_text = tag.get_text(strip=True)
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None
