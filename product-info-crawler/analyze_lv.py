import json
from bs4 import BeautifulSoup
import sys

def examine_lv(file_path):
    print(f"Analyzing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. __NEXT_DATA__ 확인
    script = soup.find('script', id='__NEXT_DATA__')
    if script:
        try:
            data = json.loads(script.string)
            print("Found __NEXT_DATA__")
            
            def find_products(obj, path=""):
                if isinstance(obj, dict):
                    if "products" in obj and isinstance(obj["products"], list) and len(obj["products"]) > 0:
                        print(f"Found 'products' at: {path}.products (Count: {len(obj['products'])})")
                        print("Sample product keys:", obj["products"][0].keys())
                        print("Sample product content:", json.dumps(obj["products"][0], indent=2, ensure_ascii=False)[:500])
                    for k, v in obj.items():
                        find_products(v, f"{path}.{k}" if path else k)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_products(item, f"{path}[{i}]")

            find_products(data)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
    else:
        print("__NEXT_DATA__ not found.")

    # 2. HTML 클래스 확인
    print("\nChecking HTML classes...")
    # lv-product-card 가 있는지 확인
    cards = soup.select("li.lv-product-card, li[class*='productCard'], div[class*='product-card']")
    print(f"Found {len(cards)} product cards with current selectors.")
    if cards:
        print("Sample card classes:", cards[0].get('class'))
        print("Sample card content (first 300 chars):", cards[0].get_text(strip=True)[:300])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        examine_lv(sys.argv[1])
    else:
        # 최근 루이비통 파일 자동 선택
        import glob
        files = glob.glob("tmp_debug/lv/Wallet_Man___captcha_challenge__*.html")
        if files:
            examine_lv(files[-1])
        else:
            print("No LV debug files found.")
