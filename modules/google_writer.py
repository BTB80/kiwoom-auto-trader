# google_writer.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def append_trade_log(sheet_id, row, worksheet_name="자동매매내역"):
    try:
        # ✅ "복원" 전략일 경우 구글 시트 기록 생략
        if len(row) > 12 and row[12] == "복원":
            return

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        print(f"[✅ 구글 시트 기록 완료] {row}")
    except Exception as e:
        print(f"[❌ 구글 시트 기록 실패] {e}")

def get_existing_trade_keys(sheet_id, sheet_name):
    import requests

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{sheet_name}?key=YOUR_API_KEY"
    response = requests.get(url)

    if response.status_code != 200:
        print("❌ 시트 읽기 실패:", response)
        return set()

    values = response.json().get("values", [])
    keys = set()
    for row in values[1:]:  # 첫 줄은 헤더
        if len(row) >= 4:
            key = f"{row[0]}_{row[1]}_{row[2]}_{row[3]}"  # 날짜_시간_계좌_종목코드
            keys.add(key)
    return keys
