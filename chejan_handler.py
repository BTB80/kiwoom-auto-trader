from datetime import datetime
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QTableWidgetItem
from utils import log_debug, log_info, write_trade_log_file
from modules.telegram_utils import send_telegram_message

class ChejanHandlerMixin:
    def handle_chejan_data(self, gubun, item_cnt, fid_list):
        if gubun != "0":
            if getattr(self, "SHOW_DEBUG", False):
                log_debug(None, f"[⛔️ 무시됨] gubun={gubun} (체결 아님)")
            return

        code = self._get_clean_code(self.api.ocx.dynamicCall("GetChejanData(int)", 9001).strip())
        order_status = self.api.ocx.dynamicCall("GetChejanData(int)", 913).strip()
        filled_qty = self.api.ocx.dynamicCall("GetChejanData(int)", 911).strip()
        price_str = self.api.ocx.dynamicCall("GetChejanData(int)", 910).strip().replace(",", "")
        account_no = self.api.ocx.dynamicCall("GetChejanData(int)", 9201).strip()
        order_type_code = self.api.ocx.dynamicCall("GetChejanData(int)", 907).strip()

        order_type_str = {
            "1": "매도",
            "2": "매수",
            "3": "취소",
            "4": "정정",
        }.get(order_type_code, order_type_code)

        if order_status != "체결" or not filled_qty.isdigit():
            return

        qty = int(filled_qty)
        price = int(price_str or "0")

        if "매수" in order_type_str:
            self.handle_chejan_buy(code, account_no, qty, price)
        elif "매도" in order_type_str:
            self.handle_chejan_sell(code, account_no, qty, price)

    def handle_chejan_buy(self, code, account_no, qty, price):
        now = datetime.now()
        name = self.basic_info_map.get(code, {}).get("name", code)
        amount = qty * price
        strategy_name = getattr(self, "current_strategy_name", "전략미지정")

        log_info(None, f"[🟢 매수 체결] {code} | 계좌:{account_no} | 수량:{qty} | 가격:{price}")
        write_trade_log_file(f"[🟢 매수 체결] {code} | 계좌:{account_no} | 수량:{qty} | 가격:{price}")

        self.pending_buys.discard((code, account_no))

        holdings = self.holdings.setdefault(code, {})
        prev = holdings.get(account_no, {"qty": 0, "buy_price": 0})
        new_qty = prev["qty"] + qty
        new_price = (prev["qty"] * prev["buy_price"] + qty * price) // new_qty if new_qty else price
        holdings[account_no] = {"qty": new_qty, "buy_price": new_price}

        if hasattr(self, "executor") and self.executor:
            self.executor.holdings.setdefault(code, {})[account_no] = holdings[account_no]
            log_debug(None, f"[🔄 executor.holdings 반영] {code} / 계좌:{account_no} / qty={new_qty} / price={new_price}")

        if hasattr(self, "reconstruct_buy_history_from_holdings"):
            self.reconstruct_buy_history_from_holdings()
            self.reconstruct_sell_history_from_holdings()

        if hasattr(self, "manager"):
            self.manager.holdings = self.holdings
            self.manager.current_account = account_no
            if hasattr(self.manager, 'request_holdings'):
                QTimer.singleShot(2000, lambda: self.manager.request_holdings(account_no))

        self.sell_history.pop((code, account_no), None)

        send_telegram_message(
            f"[🟢 매수 체결]\n📌 종목: {code} ({name})\n📆 시간: {now.strftime('%H:%M:%S')}\n"
            f"💰 수량: {qty}주 @ {price:,}원\n📊 체결금액: {amount:,}원\n🧾 실현금액: {amount:,}원\n"
            f"🎯 전략: {strategy_name}\n🏦 계좌: {account_no}"
        )

    def handle_chejan_sell(self, code, account_no, qty, price):
        now = datetime.now()
        name = self.basic_info_map.get(code, {}).get("name", code)
        amount = qty * price
        strategy_name = getattr(self, "current_strategy_name", "전략미지정")
        key = self.normalize_key(code, account_no)

        if not (isinstance(key, tuple) and len(key) == 2 and all(isinstance(k, str) for k in key)):
            log_debug(None, f"[⛔️ 잘못된 sell_history 저장 시도 차단] {key}")
            return

        log_info(None, f"[🔴 매도 체결] {code} | 계좌:{account_no} | 수량:{qty} | 가격:{price}")
        write_trade_log_file(f"[🔴 매도 체결] {code} | 계좌:{account_no} | 수량:{qty} | 가격:{price}")

        # ✅ 잔고 차감
        for h in [self.holdings, getattr(self.manager, 'holdings', {})]:
            if code in h and account_no in h[code]:
                prev_qty = h[code][account_no].get("qty", 0)
                new_qty = max(0, prev_qty - qty)
                h[code][account_no]["qty"] = new_qty
                log_debug(None, f"[📉 매도 후 잔고 수정] {code} / 계좌: {account_no} / 잔여:{new_qty}")
                if new_qty == 0:
                    del h[code][account_no]
                    if not h[code]:
                        del h[code]

        step = self.accounts.index(account_no) + 1 if account_no in self.accounts else 1
        self.buy_history = {k: v for k, v in self.buy_history.items() if k != key}
        self.sell_history[key] = {"price": price, "time": now, "step": step}

        send_telegram_message(
            f"[🔴 매도 체결]\n📌 종목: {code} ({name})\n📆 시간: {now.strftime('%H:%M:%S')}\n"
            f"💰 수량: {qty}주 @ {price:,}원\n📊 체결금액: {amount:,}원\n🧾 실현금액: {amount:,}원\n"
            f"🎯 전략: {strategy_name}\n🏦 계좌: {account_no}"
        )

    @staticmethod
    def _get_clean_code(raw_code):
        return raw_code[1:] if raw_code.startswith("A") else raw_code

    @staticmethod
    def normalize_key(code, account):
        if isinstance(code, tuple): code = code[0]
        if isinstance(account, tuple): account = account[0]
        return (str(code).strip(), str(account).strip())
