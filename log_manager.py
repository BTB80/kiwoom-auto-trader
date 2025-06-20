import os
from datetime import datetime

def to_int(text):
    """문자열을 정수로 안전하게 변환"""
    try:
        return int(str(text).lstrip("0") or "0")
    except Exception:
        return 0


class LogManager:
    def __init__(self, log_box=None, config=None):
        self.log_box = log_box
        self.logged_messages = set()
        self.config = config or {}
        self.update_flags(self.config)

        # 모든 로그 저장 (튜플: (메시지, 레벨))
        self.all_logs = []

        # 필터 상태 기본값 (True=보임)
        self.filter_debug = True
        self.filter_info = True
        self.filter_trade = True  # 필요 시 추가

    def update_flags(self, config):
        """설정값에 따라 로그 플래그 갱신"""
        self._debug = config.get("show_debug", True)
        self._verbose_buy = config.get("show_verbose_buy", True)
        self._verbose_sell = config.get("show_verbose_sell", True)

    @property
    def debug_enabled(self):
        return self._debug

    @property
    def verbose_buy(self):
        return self._verbose_buy

    @property
    def verbose_sell(self):
        return self._verbose_sell

    def set_log_box(self, log_box):
        """로그창 위젯 연결"""
        self.log_box = log_box

    def log(self, message, level="info"):
        """기본 로그 (info, debug, trade 등 레벨 지정 가능)"""
        # 저장
        self.all_logs.append((message, level))

        # 현재 필터 상태에 따라 출력 여부 결정
        if self.log_box:
            if (level == "debug" and not self.filter_debug) or \
               (level == "info" and not self.filter_info) or \
               (level == "trade" and not self.filter_trade):
                return
            self.log_box.append(message)

        # 터미널 출력은 옵션에 따라 추후 추가 가능 (현재는 항상 출력)
        print(message)

    def debug(self, message):
        """디버그 로그"""
        if self._debug:
            self.log(message, level="debug")

    def info(self, message):
        """정보 로그"""
        self.log(message, level="info")

    def trade(self, message):
        """체결/매매 로그"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.log(full_message, level="trade")
        self.write_trade_log_file(full_message)

    def log_once(self, message):
        """중복 방지 로그"""
        if message not in self.logged_messages:
            self.logged_messages.add(message)
            self.debug(message)

    def apply_filters(self):
        """필터 상태에 따라 로그창 내용 재구성"""
        if not self.log_box:
            return

        self.log_box.clear()
        for msg, level in self.all_logs:
            if level == "debug" and not self.filter_debug:
                continue
            if level == "info" and not self.filter_info:
                continue
            if level == "trade" and not self.filter_trade:
                continue
            self.log_box.append(msg)

    def write_trade_log_file(self, message):
        """체결 내역 파일 저장 (logs/trade_YYYYMMDD.log)"""
        os.makedirs("logs", exist_ok=True)
        today_str = datetime.now().strftime("%Y%m%d")
        filepath = os.path.join("logs", f"trade_{today_str}.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
