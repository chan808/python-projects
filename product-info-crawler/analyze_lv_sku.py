import json
from bs4 import BeautifulSoup
import re
import glob

def examine_lv_sku(file_path):
    print(f"Analyzing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select("li.lv-product-card, div.lv-product-card")
    print(f"Found {len(cards)} product cards.")
    
    sku_pattern = re.compile(r"[A-Z][0-9]{5}")
    
    for i, card in enumerate(cards[:20]):
        print(f"\n--- Card {i+1} ---")
        
        # 1. 텍스트에서 찾기
        text = card.get_text(strip=True)
        skus_in_text = sku_pattern.findall(text)
        if skus_in_text:
            print(f"Found SKUs in text: {skus_in_text}")
        
        # 2. 모든 속성(attributes) 확인
        for attr, val in card.attrs.items():
            if isinstance(val, list):
                val = " ".join(val)
            skus_in_attr = sku_pattern.findall(val)
            if skus_in_attr:
                print(f"Found SKUs in attribute '{attr}': {skus_in_attr}")
        
        # 3. 자식 요소 속성 확인
        for child in card.find_all(True):
            for attr, val in child.attrs.items():
                if isinstance(val, list):
                    val = " ".join(val)
                skus_in_child_attr = sku_pattern.findall(val)
                if skus_in_child_attr:
                    print(f"Found SKUs in <{child.name}> attribute '{attr}': {skus_in_child_attr}")

if __name__ == "__main__":
    files = glob.glob("tmp_debug/lv/Wallet_Man___captcha_challenge__*.html")
    if files:
        examine_lv_sku(files[-1])
    else:
        print("No LV debug files found.")
