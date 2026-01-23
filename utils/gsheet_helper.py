import gspread
from google.oauth2.service_account import Credentials
import re

def get_spreadsheet(json_key_file: str, spreadsheet_name: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(json_key_file, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open(spreadsheet_name)

def sanitize_sheet_name(name):
    return re.sub(r"[\\/?*\[\]]", "_", name)[:100]

def get_or_create_worksheet(spreadsheet, sheet_name):
    sheet_name = sanitize_sheet_name(sheet_name)
    try:
        ws = spreadsheet.worksheet(sheet_name)
        return None
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="10")
        ws.append_row(["번호", "제품명", "레퍼런스", "색상", "카테고리", "가격"])
        return ws

def append_products_to_sheet(ws, products):
    if not products:
        return
    rows = [[ "", p["name"], p["reference"], p["colors"], p["category"], p["price"]] for p in products]
    ws.append_rows(rows)