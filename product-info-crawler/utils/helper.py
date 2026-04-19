import re
import time

from bs4 import BeautifulSoup


def scroll_to_bottom(driver, pause_time: float, product_card_selector: str = None, max_loops: int = 30):
    last_count = 0
    stable_rounds = 0

    for _ in range(max_loops):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)

        if not product_card_selector:
            continue

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(product_card_selector)
        count = len(cards)

        if count == last_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            last_count = count
            stable_rounds = 0


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
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)

        html = driver.page_source
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


def parse_price(tag):
    content_price = tag.get("content")
    if content_price:
        return int(content_price)

    price_text = tag.get_text(strip=True)
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None
