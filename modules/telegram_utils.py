import requests

TELEGRAM_TOKEN = "7914412501:AAHbEeOW1sRfSYnXydCo7S8NlAxAkciB2N0"
CHAT_ID = "8196906766"

def send_telegram_message(message):
    print(f"텔레그램 전송 시도: {message}")  # ← 수정됨
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
