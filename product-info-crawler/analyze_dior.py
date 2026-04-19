import json
import re
from bs4 import BeautifulSoup

def analyze_next_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='__NEXT_DATA__')
    if not script:
        print("No __NEXT_DATA__ found")
        return

    data = json.loads(script.string)
    
    # Helper to find keys
    def find_keys(d, target_keys, path=""):
        if isinstance(d, dict):
            for k, v in d.items():
                if k in target_keys:
                    print(f"Found {k} at {path}.{k}: {str(v)[:100]}...")
                find_keys(v, target_keys, f"{path}.{k}")
        elif isinstance(d, list):
            for i, item in enumerate(d):
                find_keys(item, target_keys, f"{path}[{i}]")

    print("--- Searching for product-related keys ---")
    find_keys(data, ["products", "productGrid", "items", "name", "price", "sku", "mpn"])

analyze_next_data('tmp_debug/dior/Ring_Woman___no_products__20260419_103135.html')
