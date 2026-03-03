import time
import re

from bs4 import BeautifulSoup


def scroll_to_bottom(driver, pause_time: float, product_card_selector: str = None, max_loops: int = 30):
    # last_height = driver.execute_script("return document.body.scrollHeight")
    # for _ in range(max_scrolls):
    #     driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    #     time.sleep(pause_time)
    #     new_height = driver.execute_script("return document.body.scrollHeight")
    #     if new_height == last_height:
    #         break
    #     last_height = new_height
    """
        - window 맨 아래까지 여러 번 스크롤하면서 상품이 더 이상 늘어나지 않을 때까지 반복
        - product_card_selector를 넘기면, 실제 상품 개수를 기준으로 종료 판단
        """

    last_count = 0
    stable_rounds = 0

    for i in range(max_loops):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)

        # product_card_selector 없으면 기존 scrollHeight 방식만 사용
        if not product_card_selector:
            continue

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(product_card_selector)
        count = len(cards)
        print(f"   [스크롤 {i + 1}] 상품 개수: {count}")

        if count == last_count:
            stable_rounds += 1
            # 2~3번 연속으로 개수가 안 늘어나면 끝난 걸로 판단
            if stable_rounds >= 3:
                print("   -> 더 이상 상품이 늘어나지 않아 스크롤 종료")
                break
        else:
            last_count = count
            stable_rounds = 0

def parse_price(tag):
    content_price = tag.get("content")
    if content_price:
        return int(content_price)
    else:
        price_text = tag.get_text(strip=True)
        return int(re.sub(r"[^\d]", "", price_text))