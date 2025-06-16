import requests

# TELEGRAM_TOKEN = "7914412501:AAHbEeOW1sRfSYnXydCo7S8NlAxAkciB2N0"
# CHAT_ID = "8196906766"

# def send_telegram_message(message):
#     print(f"텔레그램 전송 시도: {message}")  # ← 수정됨
#     url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
#     data = {
#         "chat_id": CHAT_ID,
#         "text": message
#     }
#     try:
#         response = requests.post(url, data=data)
#         if not response.ok:
#             print("❌ 텔레그램 전송 실패:", response.text)
#     except Exception as e:
#         print("❌ 텔레그램 예외 발생:", e)
TELEGRAM_TOKEN = None
CHAT_ID = None

def configure_telegram(token, chat_id):
    global TELEGRAM_TOKEN, CHAT_ID
    TELEGRAM_TOKEN = token
    CHAT_ID = chat_id

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ 텔레그램 설정이 비어 있어 메시지를 보낼 수 없습니다.")
        return

    print(f"텔레그램 전송 시도: {message}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        if not response.ok:
            print("❌ 텔레그램 전송 실패:", response.text)
    except Exception as e:
        print("❌ 텔레그램 예외 발생:", e)
