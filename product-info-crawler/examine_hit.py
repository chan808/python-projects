import json
from bs4 import BeautifulSoup

def examine_hit(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='__NEXT_DATA__')
    data = json.loads(script.string)
    
    dictionnary = data['props']['pageProps']['queriesProductsDictionnary']
    for key in dictionnary:
        hits = dictionnary[key]['hits']
        if hits:
            print(f"--- Sample hit from {key} ---")
            sample = hits[0]
            print(json.dumps(sample, indent=2, ensure_ascii=False))
            break

examine_hit('tmp_debug/dior/Ring_Woman___no_products__20260419_103135.html')
