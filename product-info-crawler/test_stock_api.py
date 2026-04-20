import requests
import json
import re

def test_lv_stock_api(sku):
    # 루이비통 한국 재고 확인 API (공용 패턴)
    # 2026년 기준 실제 경로를 추론하기 위한 테스트
    url = f"https://kr.louisvuitton.com/ajax/productAvailability.jsp?productIds={sku}&country=KR"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Referer": "https://kr.louisvuitton.com/"
    }
    
    print(f"Testing Stock API for SKU: {sku}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            print("Successfully connected to Stock API!")
            print("Response:", response.text[:500])
            return True
        else:
            print(f"Failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    # 아까 찾은 SKU 중 하나 (Wallet 예시)
    test_lv_stock_api("M61695")
