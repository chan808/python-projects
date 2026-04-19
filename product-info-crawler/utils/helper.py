import random
import re
import time

from bs4 import BeautifulSoup


def human_scroll(driver, distance: int = None):
    """실제 사람이 스크롤하는 것처럼 작은 단위로 나누어 스크롤합니다."""
    if distance is None:
        distance = driver.execute_script("return window.innerHeight") * random.uniform(0.7, 0.9)
    
    current_pos = driver.execute_script("return window.pageYOffset")
    target_pos = current_pos + distance
    
    steps = random.randint(3, 7)
    step_distance = distance / steps
    
    for _ in range(steps):
        move = step_distance * random.uniform(0.8, 1.2)
        driver.execute_script(f"window.scrollBy(0, {move});")
        time.sleep(random.uniform(0.1, 0.3))


def scroll_until_lazy_content_loaded(
    driver,
    pause_time: float,
    product_card_selector: str,
    placeholder_selector: str,
    max_loops: int = 8,
    max_placeholder_retries: int = 2,
    stable_rounds_to_finish: int = 2,
) -> dict:
    last_count = 0
    stable_rounds = 0
    placeholder_retries = 0

    for _ in range(max_loops):
        # [수정] 인간다운 스크롤 적용
        human_scroll(driver)
        time.sleep(pause_time * random.uniform(0.8, 1.2))

        html = driver.page_source
        soup = BeautifulSoup(html, "parser.parser" if "html.parser" not in str(BeautifulSoup) else "html.parser")
        # 실제로는 BeautifulSoup 호출 시 parser 이름을 직접 넣는 게 안전함
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
