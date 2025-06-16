from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem
from config_manager import load_user_config
import os
# ⚙️ 전역 설정값
SHOW_DEBUG = False
SHOW_VERBOSE_BUY_EVAL = False
SHOW_VERBOSE_SELL_EVAL = False

def update_debug_flags(config):
    global SHOW_DEBUG, SHOW_VERBOSE_BUY_EVAL, SHOW_VERBOSE_SELL_EVAL
    SHOW_DEBUG = config.get("show_debug", False)
    SHOW_VERBOSE_BUY_EVAL = config.get("show_verbose_buy", False)
    SHOW_VERBOSE_SELL_EVAL = config.get("show_verbose_sell", False)

# ✅ 디버깅 로그
def log_debug(log_box, message):
    if SHOW_DEBUG:
        print(message)
        if log_box:
            log_box.append(message)

# ✅ 일반 정보 로그
def log_info(log_box, message):
    if SHOW_DEBUG:
        print(message)
    if log_box:
        log_box.append(message)

# ✅ 항상 출력 (기본 로그)
def log(log_box, message):
    print(message)
    if log_box:
        log_box.append(message)

# ✅ 문자열을 정수로 안전하게 변환
def to_int(text):
    try:
        return int(text.lstrip('0') or "0")
    except:
        return 0

# ✅ 거래 로그 (시간 태그 포함, UI 로그 연동 지원)
def log_trade(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    if hasattr(log_trade, "log_widget") and log_trade.log_widget:
        log_trade.log_widget.append(full_message)

# ✅ 테이블 정렬 아이템 생성기
def aligned_item(text, align="right"):
    item = QTableWidgetItem(str(text))
    if align == "center":
        item.setTextAlignment(Qt.AlignCenter)
    elif align == "left":
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    else:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def write_trade_log_file(message):
    os.makedirs("logs", exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = os.path.join("logs", "trade_history.log")
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")