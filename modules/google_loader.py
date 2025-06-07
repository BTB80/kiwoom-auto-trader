# google_loader.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials


def fetch_google_sheet_data(sheet_id, worksheet_name="관심종목"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name)
    rows = worksheet.get_all_values()

    header, *data = rows
    stocks = []
    for row in data:
        if len(row) >= 2:
            code = row[0].strip()
            name = row[1].strip()
            tag = row[2].strip() if len(row) >= 3 else ""
            stocks.append((code, name, tag))
    return stocks
