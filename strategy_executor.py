from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QTableWidgetItem
from modules.telegram_utils import send_telegram_message
from modules.google_writer import append_trade_log
from utils import write_trade_log_file
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
        self.test_mode = False
        self.condition_auto_buy = False

    def set_accounts(self, accounts):
        self.accounts = accounts

    def set_basic_info_map(self, info_map):
        self.basic_info_map = info_map

    def update_settings(self, strategy):
        self.account_settings = strategy
        self.buy_settings = strategy.get("buy", {})
        self.sell_settings = strategy.get("sell", {})
        
            # 🔽 여기에 추가
        if hasattr(strategy, "name"):
            self.current_strategy_name = strategy["name"]
        elif hasattr(self, "manager") and hasattr(self.manager.ui, "strategy_dropdown"):
            self.current_strategy_name = self.manager.ui.strategy_dropdown.currentText()
        else:
            self.current_strategy_name = "전략미지정"

    def record_holding(self, code, account, qty, price):
        self.holdings.setdefault(code, {})[account] = {"buy_price": price, "qty": qty}


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
            log_debug(None, f"[⏸ 매수 평가 중단] 자동매매 비활성화 상태")
            return

        if code.startswith("A"):
            code = code[1:]

        if SHOW_VERBOSE_BUY_EVAL:
            log_debug(None, f"[👁 매수평가 진입] {code} / 현재가: {current_price}")

        # ✅ 계좌 1~4 순서대로 평가
        for step in range(1, 5):
            account_no = self.get_account_by_step(step)
            acc_conf = self.buy_settings["accounts"].get(f"계좌{step}", {})
            if not self.can_buy(code, account_no, acc_conf, step, current_price):
                continue

            amount = acc_conf.get("amount", 0)
            order_type = self.buy_settings.get("order_type", "시장가")
            self.send_buy_order(code, account_no, current_price, amount, order_type, step)
            break  # ✅ 한 계좌만 매수 후 종료 (다중매수 방지)
        
        
    def can_buy(self, code, account_no, acc_conf, step, current_price):
        if (code, account_no) in self.pending_buys:
            self.log_once(f"[⛔ 체결대기] {code} / 계좌={account_no} → 생략")
            return False

        if self.holdings.get(code, {}).get(account_no, {}).get("qty", 0) > 0:
            self.log_once(f"[⛔ 중복보유] {code}는 계좌 {account_no}에서 이미 보유 중 → 생략")
            return False

        if not acc_conf.get("enabled", False):
            self.log_once(f"[⚠️ 비활성] 계좌 {account_no} 매수 비활성화됨 → 생략")
            return False

        drop_rate = acc_conf.get("drop_rate", 0)

        # ✅ 선행 매수 가격 가져오기 (계좌1은 기준가를 prev_price = 전일종가 사용)
        if step == 1:
            prev_price = self.get_previous_close(code)
        else:
            prev_account = self.get_account_by_step(step - 1)
            prev_price = self.buy_history.get((code, prev_account), {}).get("price")

        if prev_price and current_price > 0:
            rate = (prev_price - current_price) / prev_price * 100
            if rate < drop_rate:
                self.log_once(f"[⏬ 하락률 미달] {code} 현재: {current_price}, 기준대비 {rate:.2f}% < {drop_rate}% → 생략")
                return False
        else:
            self.log_once(f"[❌ 기준 가격 없음] {code} → 생략")
            return False

        return True

    
    
    def send_buy_order(self, code, account_no, current_price, amount, order_type, step):
        if amount <= 0 or current_price <= 0:
            self.log_once(f"[❌ 매수불가] 잘못된 금액 또는 가격 ({amount} / {current_price})")
            return

        if self.test_mode:
            qty = 1
            price = 0 if order_type == "시장가" else current_price
            self.api.send_order(f"매수_TEST_{code}", "1000", account_no, 1, code, qty, price, order_type, "")
            self.pending_buys.add((code, account_no))
            self.log_once(f"[🧪 1주 매수 테스트] {code} / 계좌: {account_no}")
            return

        qty = int(amount / current_price)
        if qty <= 0:
            self.log_once(f"[❌ 매수불가] 금액 {amount}으로 매수 수량 부족 → 생략")
            return

        price = 0 if order_type == "시장가" else current_price
        screen_no = self.get_screen_no_by_account(account_no)
        order_id = f"매수_{code}_{account_no}_{step}"

        self.api.send_order(order_id, screen_no, account_no, 1, code, qty, price, order_type, "")
        self.pending_buys.add((code, account_no))

        self.log_once(f"[📤 매수주문 전송] {code} / 계좌: {account_no} / 수량: {qty} / 가격: {price} / 방식: {order_type}")

        # 기록용 정보 저장
        self.buy_history[(code, account_no)] = {
            "step": step,
            "price": current_price,
            "strategy": self.current_strategy_name
        }


    def evaluate_sell(self, code, current_price):
        # print(f"[매도 평가 시도] {code} / 현재가: {current_price}")
        if not self.enabled:
            log_debug(None, f"[⏸ 매도 평가 중단] 자동매매 비활성화 상태")
            return

        if code.startswith("A"):
            code = code[1:]

        if SHOW_VERBOSE_SELL_EVAL:
            log_debug(None, f"[👁 매도평가 진입] {code} / 현재가: {current_price}")

        if code not in self.holdings:
            self.log_once(f"[❌ 보유정보 없음] {code}")
            return

        for i, account in enumerate(self.accounts):
            # print(f" - 계좌 검사: {account} / 보유 여부: {account in self.holdings.get(code, {})}")
            holding = self.holdings[code].get(account)
            if not holding:
                self.log_once(f"[⛔ 해당 계좌 보유 없음] {code} / 계좌: {account}")
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
            # print(f"[📦 보유정보] {code} / 계좌:{account} / qty={qty}, buy_price={buy_price}")
            
            if qty <= 0:
                log_debug(None, f"[📦 매도 불가: 수량 없음] {code} / 계좌: {account}")
                continue
            
            # ✅ buy_price가 0 이하인 경우 매도 평가 생략
            if buy_price <= 0:
                log_debug(None, f"[⛔ 매도 평가 생략] {code} / 계좌:{account} / buy_price=0 이하")
                continue
            # ✅ 여기에 로그 추가
            log_debug(None, f"[검사] 매도 평가 전 buy_price 확인: {code} / 계좌:{account} / qty:{qty} / buy_price:{buy_price} / current_price:{current_price}")

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

        # ✅ 전략에서 주문 방식 가져오기
        order_type_ui = self.sell_settings.get("order_type", "지정가")
        if order_type_ui == "시장가":
            order_type = 2
            hoga_type = "03"
            price = 0  # 시장가 주문은 가격 0
        else:
            order_type = 2
            hoga_type = "00"
            price = int(current_price)

        holding_info = self.holdings.get(code, {}).get(account, {})
        total_qty = holding_info.get("qty", 0)

        qty = max(int(float(total_qty) * float(ratio) / 100), 1)

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

        if hasattr(self, "account_manager"):
            if SHOW_DEBUG:
                log_debug(None, f"🔄 매도 후 잔고 갱신 요청 → 계좌: {account}")
            self.account_manager.request_holdings(account)



    def handle_chejan_data(self, gubun, item_cnt, fid_list):
        print("✅ handle_chejan_data 진입")

        if SHOW_DEBUG:
            log_debug(None, f"[📨 Chejan 수신] gubun={gubun}")

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
        order_type_code = self.api.ocx.dynamicCall("GetChejanData(int)", 907).strip()
        order_type_str = {
            "1": "매도",
            "2": "매수",
            "3": "취소",
            "4": "정정",
            # 필요하면 더 추가
        }.get(order_type_code, order_type_code)


        if SHOW_DEBUG:
            log_debug(None, f"[🧪 체결 판별] status={order_status}, qty={filled_qty}, order_type={order_type_str}, price={price_str}, code={code}, acc={account_no}")

        if not order_type_str or order_status != "체결" or not filled_qty.isdigit():
            return

        qty = int(filled_qty)
        price = int(price_str or "0")

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
            write_trade_log_file(f"[🟢 매수 체결] {code} | 계좌: {account_no} | 수량: {qty} | 가격: {price}")

            if hasattr(self, "pending_buys"):
                self.pending_buys.discard((code, account_no))

            account_holdings = self.holdings.setdefault(code, {})
            if account_no in account_holdings:
                prev_qty = account_holdings[account_no].get("qty", 0)
                prev_price = account_holdings[account_no].get("buy_price", 0)
                new_qty = prev_qty + qty
                new_avg_price = (prev_qty * prev_price + qty * price) // new_qty
                account_holdings[account_no] = {"buy_price": new_avg_price, "qty": new_qty}
            else:
                account_holdings[account_no] = {"buy_price": price, "qty": qty}

            # ✅ executor에도 반영
            # if hasattr(self, "executor"):
            #     self.executor.record_holding(code, account_no, qty, price)

            if hasattr(self, "reconstruct_buy_history_from_holdings"):
                self.reconstruct_buy_history_from_holdings()
                self.reconstruct_sell_history_from_holdings()

            if hasattr(self, "manager"):
                self.manager.holdings = self.holdings
                self.manager.current_account = account_no
                if hasattr(self.manager, 'request_holdings'):
                    QTimer.singleShot(2000, lambda: self.manager.request_holdings(account_no))

            if code in self.sell_history:
                if SHOW_DEBUG:
                    log_debug(None, f"[🧹 재매수 감지 → sell_history 정리] {code}")
                self.sell_history.pop(code)

            msg = (
                f"[🟢 매수 체결]\n"
                f"📌 종목: {code} ({name})\n"
                f"📆 시간: {time}\n"
                f"💰 수량: {qty}주 @ {price:,}원\n"
                f"📊 체결금액: {amount:,}원\n"
                f"🧾 실현금액: {settled:,}원\n"
                f"🎯 전략: {strategy_name}\n"
                f"🏦 계좌: {account_no}"
            )
            print("📨 텔레그램 메시지 전송 시도:", msg[:30])
            send_telegram_message(msg)

        elif any(k in order_type_str for k in ["매도", "현금매도", "신용매도"]):
            log_info(None, f"[🔴 매도 체결] {code} | 계좌: {account_no} | 수량: {qty} | 가격: {price}")
            write_trade_log_file(f"[🔴 매도 체결] {code} | 계좌: {account_no} | 수량: {qty} | 가격: {price}")

            holdings_targets = [self.holdings]
            if hasattr(self.manager, 'holdings'):
                holdings_targets.append(self.manager.holdings)

            for h in holdings_targets:
                if code in h and account_no in h[code]:
                    prev_qty = h[code][account_no].get("qty", 0)
                    new_qty = max(0, prev_qty - qty)
                    h[code][account_no]["qty"] = new_qty
                    log_debug(None, f"[📉 매도 후 잔고 수정] {code} / 계좌: {account_no} / 잔여수량: {new_qty}")
                    if new_qty == 0:
                        log_debug(None, f"[🧹 잔고에서 제거됨] {code} / 계좌: {account_no}")
                        del h[code][account_no]
                        if not h[code]:
                            del h[code]

            self.sell_history[code] = {"price": price, "time": now}
            self.buy_history.pop(code, None)

            if hasattr(self.manager, 'request_today_profit'):
                self.manager.request_today_profit(account_no)
            if hasattr(self.manager, 'request_holdings'):
                QTimer.singleShot(2000, lambda: self.manager.request_holdings(account_no))
            if hasattr(self.manager, "ui") and hasattr(self.manager.ui, "account_combo"):
                combo = self.manager.ui.account_combo
                idx = combo.findText(account_no)
                if idx != -1:
                    combo.setCurrentIndex(idx)
            if hasattr(self.manager, 'refresh_holdings_ui'):
                QTimer.singleShot(500, self.manager.refresh_holdings_ui)
                QTimer.singleShot(1500, self.manager.refresh_holdings_ui)
                QTimer.singleShot(3000, self.manager.refresh_holdings_ui)

            msg = (
                f"[🔴 매도 체결]\n"
                f"📌 종목: {code} ({name})\n"
                f"📆 시간: {time}\n"
                f"💰 수량: {qty}주 @ {price:,}원\n"
                f"📊 체결금액: {amount:,}원\n"
                f"🧾 실현금액: {settled:,}원\n"
                f"🎯 전략: {strategy_name}\n"
                f"🏦 계좌: {account_no}"
            )
            print("📨 텔레그램 메시지 전송 시도:", msg[:30])
            send_telegram_message(msg)

        if hasattr(self.manager, 'trade_log_table'):
            row_pos = self.manager.trade_log_table.rowCount()
            self.manager.trade_log_table.insertRow(row_pos)
            for col, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter if col in [0, 1, 2, 3, 5, 12] else Qt.AlignRight)
                self.manager.trade_log_table.setItem(row_pos, col, item)

        if hasattr(self.manager, 'refresh_holdings_ui'):
            self.manager.refresh_holdings_ui()
            QTimer.singleShot(1500, self.manager.refresh_holdings_ui)
        if hasattr(self.manager, 'update_ui'):
            QTimer.singleShot(1600, self.manager.update_ui)



    def reconstruct_buy_history_from_holdings(self):
        # ✅ 이미 복원된 경우 생략
        if self.buy_history:
            if SHOW_DEBUG:
                log_debug(None, "[⏩ 복원 생략] buy_history가 이미 채워져 있음")
            return

        new_buy_history = {}
        new_holdings = {}

        # 1️⃣ holdings 기반으로 buy_history 및 holdings 재구성
        for raw_code, account_data in self.holdings.items():
            code = raw_code[1:] if raw_code.startswith("A") else raw_code

            for i, account in enumerate(self.accounts):
                if account in account_data:
                    holding = account_data[account]
                    qty = holding.get("qty", 0)
                    price = holding.get("buy_price", 0)
                    step = i + 1

                    # ✅ holdings 재구성은 수량이 있을 때만
                    if qty > 0 and price > 0:
                        new_holdings.setdefault(code, {})[account] = {
                            "buy_price": price,
                            "qty": qty
                        }

                    # ✅ buy_history는 qty/price 없어도 step 기준으로 복원
                    if code not in new_buy_history and step:
                        new_buy_history[code] = {"price": price or 0, "step": step}
                        if SHOW_DEBUG:
                            log_debug(None, f"🔁 {code} → buy_history 복원: step={step}, price={price}")

        # 2️⃣ sell_history 기반 누락 보정 (step 정보 유지)
        for code, sell_info in self.sell_history.items():
            if code not in new_buy_history:
                new_buy_history[code] = {"price": 0, "step": sell_info.get("step", 1)}
                if SHOW_DEBUG:
                    log_debug(None, f"📌 {code} → sell_history 기반 buy_history 추가: step={sell_info.get('step', 1)}")

        self.buy_history = new_buy_history
        self.holdings = new_holdings

        if SHOW_DEBUG:
            log_debug(None, f"✅ buy_history 복원 완료: {len(new_buy_history)} 종목")
            self.print_holdings_summary()  # 🔍 자동 복원 직후 보유 상태 확인




    def reconstruct_sell_history_from_holdings(self):
        # 전체 종목 목록: buy_history + holdings 키 통합
        all_codes = set(self.buy_history.keys()) | set(self.holdings.keys())

        for code in list(all_codes):
            # ✅ 모든 계좌에서 해당 종목을 보유하고 있지 않으면 → 매도 기록 복원
            no_holding = all(
                acc not in self.holdings.get(code, {}) or self.holdings[code][acc].get("qty", 0) <= 0
                for acc in self.accounts
            )

            if no_holding:
                step = self.buy_history.get(code, {}).get("step", 1)
                self.sell_history[code] = {"step": step}

                if SHOW_DEBUG:
                    log_debug(None, f"🔁 {code} 매도기록 복원됨 (step={step})")

    def reconstruct_pending_buys_from_unsettled(self):
        if not hasattr(self.manager, 'unsettled_table'):
            return

        table = self.manager.unsettled_table
        rows = table.rowCount()

        for row in range(rows):
            name_item = table.item(row, 1)
            type_item = table.item(row, 2)
            remain_item = table.item(row, 5)

            if not name_item or not type_item or not remain_item:
                continue

            name = name_item.text().strip()
            order_type = type_item.text().strip()
            remain_qty = int(remain_item.text().replace(",", "") or "0")

            if remain_qty > 0 and "매수" in order_type:
                # 이름으로 코드 찾기
                code = self.get_code_by_name(name)
                account = self.manager.current_account
                if code and account:
                    self.pending_buys.add((code, account))
                    log_debug(None, f"⏳ 미체결 복원: {code} / 계좌={account} → 체결 대기 등록됨")

    def get_code_by_name(self, name):
        for code, info in self.basic_info_map.items():
            if info.get("name") == name:
                return code
        return None

    def set_manager(self, manager):
        self.manager = manager
         

    def print_holdings_summary(self):
        print("📋 [보유 종목 요약]")
        for code, acc_map in self.holdings.items():
            print(f"📦 종목코드: {code}")
            for acc, info in acc_map.items():
                qty = info.get("qty", 0)
                price = info.get("buy_price", 0)
                print(f"  └ 계좌: {acc} | 수량: {qty} | 단가: {price}")
                
    def log_once(self, message: str):
        if not hasattr(self, "_logged_messages"):
            self._logged_messages = set()
        if message not in self._logged_messages:
            self._logged_messages.add(message)
            log_debug(None, message)
