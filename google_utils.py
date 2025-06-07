import gspread
from oauth2client.service_account import ServiceAccountCredentials

def load_stocks_from_google(sheet_id, worksheet_name="관심종목"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name)

    rows = worksheet.get_all_values()
    header, *data = rows
    return data  # [["005930", "삼성전자", "장기보유"], ...]

