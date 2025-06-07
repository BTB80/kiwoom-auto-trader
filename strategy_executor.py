from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QTableWidgetItem

from modules.google_writer import append_trade_log

from utils import (
    log_debug,
    log_info,
    log_trade,
    SHOW_DEBUG,
    SHOW_VERBOSE_BUY_EVAL,
    SHOW_VERBOSE_SELL_EVAL
)

class AutoTradeExecutor:
    def __init__(self, api):
        self.api = api
        self.accounts = []
        self.account_settings = {}
        self.buy_settings = {}
        self.sell_settings = {}
        self.holdings = {}
        self.executed_orders = {}
        self.buy_history = {}
        self.sell_history = {}
        self.pending_buys = set()
        self.enabled = False
        self.basic_info_map = {} 

    def set_accounts(self, accounts):
        self.accounts = accounts

    def set_basic_info_map(self, info_map):
        self.basic_info_map = info_map

    def update_settings(self, strategy):
        self.account_settings = strategy
        self.buy_settings = strategy.get("buy", {})
        self.sell_settings = strategy.get("sell", {})

    def record_holding(self, code, account, price):
        self.holdings.setdefault(code, {})[account] = {"buy_price": price, "qty": 1}

    def clear_holding(self, code, account):
        if code in self.holdings and account in self.holdings[code]:
            del self.holdings[code][account]

    def get_previous_close(self, code):
        return self.basic_info_map.get(code, {}).get("prev_price", 10000)

    def get_account_by_step(self, step):
        if 1 <= step <= len(self.accounts):
            return self.accounts[step - 1]
        return ""

    def evaluate_buy(self, code, current_price):
        if not self.enabled:
            return

        if code.startswith("A"):
            code = code[1:]

        accounts = self.buy_settings.get("accounts", {})

        for i, acc in enumerate(["계좌1", "계좌2", "계좌3", "계좌4"]):
            step = i + 1
            account_no = self.get_account_by_step(step)
            acc_conf = accounts.get(acc)

            if not acc_conf or not acc_conf.get("enabled"):
                continue

            # ✅ 이미 보유 중이면 매수 금지
            if self.holdings.get(code, {}).get(account_no, {}).get("qty", 0) > 0:
                log_debug(None, f"[⛔ 중복보유] {code}는 계좌 {account_no}에서 이미 보유 중 → 매수 생략")
                continue

            # ✅ 체결 대기 중이면 생략
            if (code, account_no) in self.pending_buys:
                log_debug(None, f"[⛔ 체결대기] {code} / 계좌={account_no} → 매수 생략")
                continue

            # ✅ 계좌1은 전일종가 기준 + 매도이력 있는 경우 재매수 제한
            if step == 1:
                if code in self.sell_history:
                    log_debug(None, f"[⏸ 계좌1 재매수 제한] {code} / 매도 기록 있음 → 대기")
                    continue
                base_price = self.get_previous_close(code)

            # ✅ 계좌2~4는 전단계 보유 or 재진입 여부 판단
            else:
                prev_account = self.get_account_by_step(step - 1)
                prev_holding = self.holdings.get(code, {}).get(prev_account)
                prev_sell_price = self.sell_history.get(code, {}).get(prev_account, 0)

                if prev_holding and prev_holding.get("qty", 0) > 0:
                    base_price = prev_holding.get("buy_price", current_price)
                elif prev_sell_price > 0:
                    reentry_drop = acc_conf.get("reentry_drop", -2.0)
                    reentry_price = prev_sell_price * (1 + reentry_drop / 100)
                    if current_price > reentry_price:
                        log_debug(None, f"[⛔ 재진입 조건 미충족] {code} / 현재가={current_price} > 목표={reentry_price:.2f}")
                        continue
                    else:
                        base_price = prev_sell_price
                        log_debug(None, f"[🔁 재진입 조건 충족] {code} / 현재가={current_price} <= 목표={reentry_price:.2f}")
                else:
                    log_debug(None, f"[⛔ 전단계 미보유 + 매도기록 없음] {code} / {prev_account} → 계좌 {account_no} 평가 생략")
                    continue

            # ✅ 목표가 계산 및 매수 조건 평가
            drop_rate = acc_conf.get("drop_rate", 0)
            target_price = base_price * (1 + drop_rate / 100)

            if SHOW_VERBOSE_BUY_EVAL:
                log_debug(None, f"[⚙️ 평가] {code} | step={step} | 계좌={account_no} | 현재가={current_price} | 기준가={base_price} | 목표가={target_price:.2f}")

            if current_price <= target_price:
                amount = acc_conf.get("amount", 0)
                log_info(None, f"[✅ 매수 조건 만족] {code} / 계좌={account_no} / amount={amount}")
                self.send_buy_order(code, amount, step, current_price)
                self.pending_buys.add((code, account_no))
            else:
                if SHOW_VERBOSE_BUY_EVAL:
                    log_debug(None, f"[❌ 조건 미충족] {code} / 현재가={current_price} > 목표가={target_price:.2f}")




    def send_buy_order(self, code, amount, step, current_price):
        account = self.get_account_by_step(step)
        is_test = self.buy_settings.get("test_mode", False)

        # ✅ 항상 지정가로 고정
        order_type = 1  # 1: 지정가
        hoga_type = "00"  # 지정가 호가코드
        qty = 1 if is_test else max(int(float(amount) // float(current_price)), 1)
        price = int(current_price)

        res = self.api.send_order(
            rqname="매수",
            screen_no="0101",
            acc_no=account,
            order_type=order_type,
            code=code,
            qty=qty,
            price=price,
            hoga=hoga_type,
            org_order_no=""
        )

        if SHOW_DEBUG:
            log_debug(None, f"📤 매수주문 전송 → 계좌:{account} | 종목:{code} | 수량:{qty} | 유형:지정가 | "
                            f"{'테스트모드' if is_test else '실매매'} | 가격:{price} | 결과:{res}")

        # ✅ 매수 후 잔고 갱신 요청
        if hasattr(self, "account_manager"):
            if SHOW_DEBUG:
                log_debug(None, f"🔄 매수 후 잔고 갱신 요청 → 계좌: {account}")
            self.account_manager.request_holdings(account)



    def evaluate_sell(self, code, current_price):
        if not self.enabled:
            log_debug(None, f"[⏸ 매도 평가 중단] 자동매매 비활성화 상태")
            return

        if code.startswith("A"):
            code = code[1:]

        if SHOW_VERBOSE_SELL_EVAL:
            log_debug(None, f"[👁 매도평가 진입] {code} / 현재가: {current_price}")

        if code not in self.holdings:
            log_debug(None, f"[❌ 보유정보 없음] {code}")
            return

        for i, account in enumerate(self.accounts):
            holding = self.holdings[code].get(account)
            if not holding:
                log_debug(None, f"[⛔ 해당 계좌 보유 없음] {code} / 계좌: {account}")
                continue

            step = i + 1
            acc = f"계좌{step}"
            acc_conf = self.sell_settings.get("accounts", {}).get(acc)

            if not acc_conf:
                log_debug(None, f"[⚠️ 매도 설정 없음] {code} / {acc}")
                continue
            if not acc_conf.get("enabled"):
                log_debug(None, f"[🚫 매도 설정 비활성화] {code} / {acc}")
                continue

            buy_price = holding.get("buy_price", 0)
            qty = holding.get("qty", 0)

            if qty <= 0:
                log_debug(None, f"[📦 매도 불가: 수량 없음] {code} / 계좌: {account}")
                continue

            target_rate = acc_conf.get("profit_rate", 0)
            target_price = buy_price * (1 + target_rate / 100)

            if SHOW_VERBOSE_SELL_EVAL:
                log_debug(None, f"[⚖️ 매도 평가] {code} | 계좌:{account} | 매수가:{buy_price} | 현재가:{current_price} | 목표가:{target_price:.2f}")

            if current_price >= target_price:
                ratio = acc_conf.get("ratio", 100)
                log_info(None, f"[✅ 매도 조건 만족] {code} / 계좌:{account} / 비율:{ratio}%")
                self.send_sell_order(code, ratio, account, current_price)
                self.sell_history[code] = {"step": step}
            else:
                if SHOW_VERBOSE_SELL_EVAL:
                    log_debug(None, f"[❌ 미충족] {code} / 현재가 < 목표가 ({current_price} < {target_price:.2f})")

    

    def send_sell_order(self, code, ratio, account, current_price):
        if SHOW_DEBUG:
            log_debug(None, f"📍 send_sell_order 호출됨: {code}, 계좌={account}, 현재가={current_price}")

        # ✅ 무조건 지정가 + 무조건 신규매도
        order_type_ui = "지정가"
        order_type = 2
        hoga_type = "00"

        holding_info = self.holdings.get(code, {}).get(account, {})
        total_qty = holding_info.get("qty", 0)

        qty = max(int(float(total_qty) * float(ratio) / 100), 1)
        price = int(current_price)

        if SHOW_DEBUG:
            log_debug(None, f"🧾 매도 준비: 계좌={account}, 총보유={total_qty}, 매도비율={ratio}%, 수량={qty}, 가격={price}")

        res = self.api.send_order(
            rqname="매도",
            screen_no="0101",
            acc_no=account,
            order_type=order_type,
            code=code,
            qty=qty,
            price=price,
            hoga=hoga_type,
            org_order_no=""
        )

        if SHOW_DEBUG:
            log_debug(None, f"📤 매도주문 전송됨 → 계좌:{account} | 종목:{code} | 수량:{qty} | 유형:{order_type_ui} | 가격:{price} | 결과:{res}")

        # ✅ 매도 후 잔고 갱신 요청
        if hasattr(self, "account_manager"):
            if SHOW_DEBUG:
                log_debug(None, f"🔄 매도 후 잔고 갱신 요청 → 계좌: {account}")
            self.account_manager.request_holdings(account)


    def handle_chejan_data(self, gubun, item_cnt, fid_list):
        if SHOW_DEBUG:
            log_debug(None, f"[\U0001F4E5 Chejan 수신] gubun={gubun}")

        if gubun != "0":
            if SHOW_DEBUG:
                log_debug(None, f"[⛔️ 무시됨] gubun={gubun} (체결 아닌 경우)")
            return

        raw_code = self.api.ocx.dynamicCall("GetChejanData(int)", 9001).strip()
        code = raw_code[1:] if raw_code.startswith("A") else raw_code
        order_status = self.api.ocx.dynamicCall("GetChejanData(int)", 913).strip()
        filled_qty = self.api.ocx.dynamicCall("GetChejanData(int)", 911).strip()
        price_str = self.api.ocx.dynamicCall("GetChejanData(int)", 910).strip().replace(",", "")
        account_no = self.api.ocx.dynamicCall("GetChejanData(int)", 9201).strip()
        order_type_str = self.api.ocx.dynamicCall("GetChejanData(int)", 920).strip()

        if SHOW_DEBUG:
            log_debug(None, f"[🧪 체결 판별] status={order_status}, qty={filled_qty}, "
                            f"order_type={order_type_str}, price={price_str}, code={code}, acc={account_no}")

        if order_status != "체결" or not filled_qty.isdigit():
            return

        qty = int(filled_qty)
        price = int(price_str or 0)

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        name = self.basic_info_map.get(code, {}).get("name", code)
        amount = qty * price
        fee, tax = 0, 0
        settled = amount - fee - tax
        strategy_name = getattr(self, "current_strategy_name", "전략미지정")

        row = [date, time, account_no, code, name, order_type_str, qty, price, amount, fee, tax, settled, strategy_name, ""]

        if "매수" in order_type_str:
            log_info(None, f"[🟢 매수 체결] {code} | 계좌: {account_no} | 수량: {qty} | 가격: {price}")
            self.pending_buys.discard(code)

            holding = self.holdings.setdefault(code, {}).get(account_no)
            if holding:
                total_qty = holding.get("qty", 0) + qty
                prev_amt = holding.get("buy_price", 0) * holding.get("qty", 0)
                new_avg_price = (prev_amt + qty * price) // total_qty
                self.holdings[code][account_no] = {"buy_price": new_avg_price, "qty": total_qty}
            else:
                self.holdings.setdefault(code, {})[account_no] = {"buy_price": price, "qty": qty}

            # ✅ executor.holdings 동기화 보장
            if hasattr(self, "manager"):
                self.manager.holdings = self.holdings
                if hasattr(self, "reconstruct_buy_history_from_holdings"):
                    self.reconstruct_buy_history_from_holdings()

            # if strategy_name != "복원":
            #     append_trade_log("1ebHJV_SOg50092IH88yNK5ecPgx_0UBWu5EybpBWuuU", row, "자동매매내역")

            if hasattr(self.manager, 'request_holdings'):
                self.manager.request_holdings(account_no)

            if code in self.sell_history:
                if SHOW_DEBUG:
                    log_debug(None, f"[🧹 재매수 감지 → sell_history 정리] {code}")
                self.sell_history.pop(code)

        elif "매도" in order_type_str:
            log_info(None, f"[🔴 매도 체결] {code} | 계좌: {account_no} | 수량: {qty} | 가격: {price}")

            # ✅ self.holdings, manager.holdings 동시 처리
            holdings_targets = [self.holdings]
            if hasattr(self.manager, 'holdings'):
                holdings_targets.append(self.manager.holdings)

            for h in holdings_targets:
                if code in h and account_no in h[code]:
                    prev_qty = h[code][account_no].get("qty", 0)
                    new_qty = max(0, prev_qty - qty)
                    h[code][account_no]["qty"] = new_qty
                    if new_qty == 0:
                        del h[code][account_no]
                        if not h[code]:
                            del h[code]

            # if strategy_name != "복원":
            #     append_trade_log("1ebHJV_SOg50092IH88yNK5ecPgx_0UBWu5EybpBWuuU", row, "자동매매내역")

            if hasattr(self.manager, 'request_today_profit'):
                self.manager.request_today_profit(account_no)

            # ✅ 2단계 요청으로 잔고 완전 정리 보장
            if hasattr(self.manager, 'request_holdings'):
                self.manager.request_holdings(account_no)
                QTimer.singleShot(2000, lambda: self.manager.request_holdings(account_no))

        if hasattr(self.manager, 'trade_log_table'):
            row_pos = self.manager.trade_log_table.rowCount()
            self.manager.trade_log_table.insertRow(row_pos)
            for col, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter if col in [0, 1, 2, 3, 5, 12] else Qt.AlignRight)
                self.manager.trade_log_table.setItem(row_pos, col, item)

        # ✅ holdings UI 리렌더링 보강
        if hasattr(self.manager, 'refresh_holdings_ui'):
            QTimer.singleShot(1500, self.manager.refresh_holdings_ui)
            QTimer.singleShot(3000, self.manager.refresh_holdings_ui)

        if hasattr(self.manager, 'update_ui'):
            QTimer.singleShot(1600, self.manager.update_ui)


    def reconstruct_buy_history_from_holdings(self):
        new_buy_history = {}
        new_holdings = {}

        for raw_code, account_data in self.holdings.items():
            code = raw_code[1:] if raw_code.startswith("A") else raw_code

            for i, account in enumerate(self.accounts):
                if account in account_data:
                    holding = account_data[account]
                    qty = holding.get("qty", 0)
                    price = holding.get("buy_price", 0)
                    step = i + 1

                    # ❗ buy_price가 없는 경우 건너뜀
                    if qty <= 0 or price <= 0:
                        continue

                    # ✅ buy_history는 최초 보유 계좌 기준
                    if code not in new_buy_history:
                        new_buy_history[code] = {"price": price, "step": step}

                    # ✅ holdings 딕셔너리 업데이트
                    new_holdings.setdefault(code, {})[account] = {
                        "buy_price": price,
                        "qty": qty
                    }

                    if SHOW_DEBUG:
                        log_debug(None, f"🔁 {code} 매수 복원: 계좌{step} / 수량={qty} / 단가={price}")

        self.buy_history = new_buy_history
        self.holdings = new_holdings


    def reconstruct_sell_history_from_holdings(self):
        for code in list(self.buy_history.keys()):
            no_holding = all(
                acc not in self.holdings.get(code, {}) for acc in self.accounts
            )
            if no_holding:
                step = self.buy_history[code]["step"]
                self.sell_history[code] = {"step": step}
                if SHOW_DEBUG:
                    log_debug(None, f"🔁 {code} 매도기록 복원 (step={step})")

    def set_manager(self, manager):
        self.manager = manager