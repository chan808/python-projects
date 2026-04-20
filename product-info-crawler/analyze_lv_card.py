import json
from bs4 import BeautifulSoup
import sys
import glob

def examine_lv_card(file_path):
    print(f"Analyzing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    cards = soup.select("li[class*='productCard'], div[class*='product-card'], li.lv-product-card")
    print(f"Found {len(cards)} product cards.")
    
    if cards:
        card = cards[0]
        print("\n--- Card Structure Analysis ---")
        
        # 1. 텍스트 전체
        print(f"Full Text: {card.get_text(strip=True)}")
        
        # 2. 모든 자식 요소의 클래스 분석
        def print_children(element, depth=0):
            for child in element.find_all(recursive=False):
                print(f"{'  ' * depth}[{child.name}] class: {child.get('class')}, text: {child.get_text(strip=True)[:50]}")
                print_children(child, depth + 1)
        
        print_children(card)
        
        # 3. 주요 속성 확인
        print("\n--- Card Attributes ---")
        for attr in card.attrs:
            print(f"{attr}: {card.attrs[attr]}")

if __name__ == "__main__":
    files = glob.glob("tmp_debug/lv/Wallet_Man___captcha_challenge__*.html")
    if files:
        examine_lv_card(files[-1])
    else:
        print("No LV debug files found.")
