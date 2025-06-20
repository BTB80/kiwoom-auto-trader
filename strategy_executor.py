from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QTableWidgetItem
from modules.telegram_utils import send_telegram_message
from modules.google_writer import append_trade_log
from chejan_handler import ChejanHandlerMixin
from log_manager import LogManager

class AutoTradeExecutor(ChejanHandlerMixin):
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
        from config_manager import load_user_config
        self.config = load_user_config()
        self.SHOW_DEBUG = self.config.get("show_debug", False)
        self._buy_history_reconstructed = False

    def set_accounts(self, accounts):
        self.accounts = accounts

    def set_basic_info_map(self, info_map):
        self.basic_info_map = info_map

    def update_settings(self, strategy):
        self.account_settings = strategy
        self.buy_settings = strategy.get("buy", {})
        self.sell_settings = strategy.get("sell", {})

        if "name" in strategy:
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
            self.logger.debug(f"[⏸ 매수 평가 중단] 자동매매 비활성화 상태")
            return

        if code.startswith("A"):
            code = code[1:]

        if self.logger.verbose_buy:
            self.logger.debug(f"[👁 매수평가 진입] {code} / 현재가: {current_price}")

        for step in range(1, 5):
            account_no = self.get_account_by_step(step)
            acc_conf = self.buy_settings["accounts"].get(f"계좌{step}", {})

            if step > 1:
                prev_acc = self.get_account_by_step(step - 1)
                prev_holding_info = self.holdings.get(code, {}).get(prev_acc)
                prev_qty = prev_holding_info.get("qty", 0) if prev_holding_info else 0
                prev_pending = (code, prev_acc) in self.pending_buys
                prev_in_history = (code, prev_acc) in self.buy_history

                if self.logger.verbose_buy:
                    self.logger.debug(

                        f"[👁 선행확인] step={step} / 이전계좌={prev_acc} / "
                        f"보유={prev_qty}, pending={prev_pending}, history={prev_in_history}"
                    
)

                if prev_qty <= 0 and not prev_pending and not prev_in_history:
                    self.logger.debug(

                        f"[⛔ 선행계좌 조건 미충족] step={step} / 이전계좌={prev_acc} → 평가 중단"
                    
)
                    break  # ❌ 이후 step 평가 중단

                # ✅ 선행계좌가 보유는 있는데 price 정보 없음
                if prev_qty > 0 and (code, prev_acc) not in self.buy_history:
                    self.logger.debug(

                        f"[❌ 선행계좌 가격 없음] {code} / 이전계좌: {prev_acc} → 생략"
                    
)
                    break

            # ✅ 실제 매수 조건 검사
            if not self.can_buy(code, account_no, acc_conf, step, current_price):
                if self.logger.verbose_buy:
                    self.logger.debug(f"[⏩ 매수조건 미충족] {code} / step: {step} / 계좌: {account_no}")
                continue

            # ✅ 조건 충족 → 매수 실행
            amount = acc_conf.get("amount", 0)
            order_type = self.buy_settings.get("order_type", "시장가")
            self.send_buy_order(code, account_no, current_price, amount, order_type, step)
            break  # ✅ 한 계좌만 매수 후 종료



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

        # ✅ 기준가 결정
        if step == 1:
            prev_price = self.get_previous_close(code)
            if not prev_price:
                self.log_once(f"[❌ 전일종가 없음] {code} → 생략")
                return False
        else:
            prev_account = self.get_account_by_step(step - 1)
            buy_info = self.buy_history.get((code, prev_account), {})
            prev_price = buy_info.get("price")

            # 🔍 디버깅 로그
            self.log_once(f"[🔍 기준가 검사] step={step}, code={code}, prev_acc={prev_account}, prev_price={prev_price}, current={current_price}")

            if not prev_price or prev_price <= 0:
                self.log_once(f"[❌ 선행계좌 가격 없음] {code} / 이전계좌: {prev_account} → 생략")
                return False

        if current_price <= 0:
            self.log_once(f"[❌ 현재가 0] {code} → 생략")
            return False

        rate = (prev_price - current_price) / prev_price * 100

        # 🔍 하락률 디버그 로그
        self.log_once(
            f"[📉 하락률 평가] {code} / 기준가: {prev_price} / 현재가: {current_price} / "
            f"하락률: {rate:.2f}% / 필요조건: {drop_rate}%"
        )

        if rate < abs(drop_rate):
            self.log_once(f"[⏬ 하락률 미달] {code} 현재: {current_price}, 기준대비 {rate:.2f}% < {abs(drop_rate)}% → 생략")
            return False

        return True




    
    
    def send_buy_order(self, code, account_no, current_price, amount, order_type, step):
        if amount <= 0 or current_price <= 0:
            self.log_once(f"[❌ 매수불가] 잘못된 금액 또는 가격 ({amount} / {current_price})")
            return

        # Kiwoom용 order_type, hoga 변환
        if order_type == "시장가":
            order_type_code = 1
            hoga_code = "03"
        else:  # 지정가
            order_type_code = 1
            hoga_code = "00"

        screen_no = self.manager.get_screen_no_by_account(account_no) or "9999"
        order_id = f"매수_{code}_{account_no}_{step}"

        # 테스트 모드 (1주 매수)
        if self.test_mode:
            qty = 1
            price = 0 if order_type_code == 1 and hoga_code == "03" else current_price
            self.api.send_order(order_id, screen_no, account_no, order_type_code, code, qty, price, hoga_code, "")
            self.pending_buys.add((code, account_no))
            self.log_once(f"[🧪 1주 매수 테스트] {code} / 계좌: {account_no}")
            return

        # 일반 매수
        qty = int(amount / current_price)
        if qty <= 0:
            self.log_once(f"[❌ 매수불가] 금액 {amount}으로 매수 수량 부족 → 생략")
            return

        price = 0 if hoga_code == "03" else current_price

        self.api.send_order(order_id, screen_no, account_no, order_type_code, code, qty, price, hoga_code, "")
        self.pending_buys.add((code, account_no))
        self.log_once(f"[📤 매수주문 전송] {code} / 계좌: {account_no} / 수량: {qty} / 가격: {price} / 방식: {order_type}")

        # 기록용 정보 저장
        self.buy_history[(code, account_no)] = {
            "step": step,
            "price": current_price,
            "strategy": self.current_strategy_name
        }



    def evaluate_sell(self, code, current_price):

        self.logger.debug(f"[🧪 sell 평가 진입] {code} / 현재가: {current_price}")
        if code in self.holdings:
            for acc, h in self.holdings[code].items():
                self.logger.debug(f"[💾 holdings 내용] {code} / 계좌:{acc} / 보유: {h}")
        else:
            self.logger.debug(f"[❌ holdings 없음] {code} → self.holdings.keys: {list(self.holdings.keys())}")

        if not self.enabled:
            self.logger.debug(f"[⏸ 매도 평가 중단] 자동매매 비활성화 상태")
            return

        code = code[1:] if code.startswith("A") else code

        if self.logger.verbose_sell:
            self.logger.debug(f"[👁 매도평가 진입] {code} / 현재가: {current_price}")

        if code not in self.holdings:
            self.log_once(f"[❌ 보유정보 없음] {code}")
            return

        for i, account in enumerate(self.accounts):
            holding = self.holdings[code].get(account)
            if not holding:
                self.log_once(f"[⛔ 해당 계좌 보유 없음] {code} / 계좌: {account}")
                continue

            step = i + 1
            acc = f"계좌{step}"
            acc_conf = self.sell_settings.get("accounts", {}).get(acc)

            if not acc_conf:
                self.logger.debug(f"[⚠️ 매도 설정 없음] {code} / {acc}")
                continue
            if not acc_conf.get("enabled"):
                self.logger.debug(f"[🚫 매도 설정 비활성화] {code} / {acc}")
                continue

            buy_price = holding.get("buy_price", 0)
            qty = holding.get("qty", 0)

            if qty <= 0:
                self.logger.debug(f"[📦 매도 불가: 수량 없음] {code} / 계좌: {account}")
                continue

            if buy_price <= 0:
                self.logger.debug(f"[⛔ 매도 평가 생략] {code} / 계좌:{account} / buy_price=0 이하")
                continue

            target_rate = acc_conf.get("profit_rate", 0)
            target_price = buy_price * (1 + target_rate / 100)

            if self.logger.verbose_sell:
                self.logger.debug(f"[⚖️ 매도 평가] {code} | 계좌:{account} | 매수가:{buy_price} | 현재가:{current_price} | 목표가:{target_price:.2f}")

            if current_price >= target_price:
                ratio = acc_conf.get("ratio", 100)
                self.logger.info(f"[✅ 매도 조건 만족] {code} / 계좌:{account} / 비율:{ratio}%")
                self.send_sell_order(code, ratio, account, current_price)

                # ✅ 튜플 키 정규화 후 기록
                key = self.normalize_key(code, account)
                prev_step = self.sell_history.get(key, {}).get("step")
                self.sell_history[key] = {"step": step}
                if self.logger.debug_enabled and prev_step != step:
                    self.logger.debug(f"[🔁 sell_history 갱신] {code} / 계좌: {account} / step: {prev_step} → {step}")

            else:
                if self.logger.verbose_sell:
                    self.logger.debug(f"[❌ 미충족] {code} / 현재가 < 목표가 ({current_price} < {target_price:.2f})")


    def send_sell_order(self, code, ratio, account, current_price):
        self.logger.debug(f"📍 send_sell_order 호출됨: {code}, 계좌={account}, 현재가={current_price}")

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

        self.logger.debug(f"🧾 매도 준비: 계좌={account}, 총보유={total_qty}, 매도비율={ratio}%, 수량={qty}, 가격={price}")

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

        self.logger.debug(f"📤 매도주문 전송됨 → 계좌:{account} | 종목:{code} | 수량:{qty} | 유형:{order_type_ui} | 가격:{price} | 결과:{res}")

        if hasattr(self, "account_manager"):
            self.logger.debug(f"🔄 매도 후 잔고 갱신 요청 → 계좌: {account}")
            self.account_manager.request_holdings(account)


    def reconstruct_buy_history_from_holdings(self):
        if self._buy_history_reconstructed:
            return
        self._buy_history_reconstructed = True

        self.logger.debug("[🔁 buy_history 복원 시작 - 기존 내용 포함]")

        new_buy_history = {
            self.normalize_key(*k): v
            for k, v in self.buy_history.items()
            if isinstance(k, tuple) and len(k) == 2 and all(isinstance(i, str) for i in k)
        }

        for k in self.buy_history.keys():
            if not isinstance(k, tuple) or len(k) != 2 or not all(isinstance(i, str) for i in k):
                self.logger.debug(f"[⚠️ 이상한 키 제거됨] buy_history 키: {k}")

        new_holdings = {}

        for raw_code, account_data in self.holdings.items():
            code = raw_code[1:] if raw_code.startswith("A") else raw_code

            for account, holding in account_data.items():
                if account not in self.accounts:
                    continue

                qty = holding.get("qty", 0)
                price = holding.get("buy_price", 0)

                if qty > 0 and price > 0:
                    step = self.accounts.index(account) + 1
                    new_holdings.setdefault(code, {})[account] = {"buy_price": price, "qty": qty}

                    key = self.normalize_key(code, account)
                    if key not in new_buy_history:
                        new_buy_history[key] = {"price": price, "step": step}
                        self.logger.debug(f"[🔁 복원] {code} → 계좌: {account}, step: {step}, price: {price}")

                    self.logger.debug(f"[executor.holdings 저장] {code} / 계좌:{account} / qty={qty} / buy_price={price}")

        for key in self.sell_history.keys():
            if not isinstance(key, tuple) or len(key) != 2:
                continue

            code, acc = key
            for i, account in enumerate(self.accounts):
                buy_key = self.normalize_key(code, account)
                if buy_key not in new_buy_history:
                    new_buy_history[buy_key] = {"price": 0, "step": i + 1}
                    self.logger.debug(f"[📌 보완] {buy_key} → 매도기록 기반 계좌: {account}, step: {i + 1}")

        self.buy_history = new_buy_history
        self.holdings = new_holdings

        self.logger.debug(f"✅ buy_history 복원 완료: {len(new_buy_history)}개 (계좌별)")
        self.logger.debug("🧾 [디버그] buy_history 복원 결과 ↓")

        valid_keys = sorted(new_buy_history.keys(), key=lambda x: (x[0], x[1]))
        for (code, acc) in valid_keys:
            val = new_buy_history[(code, acc)]
            self.logger.debug(f" - 종목: {code} | 계좌: {acc} | step: {val.get('step')} | price: {val.get('price')}")

        self.logger.debug("📦 holdings 전체 구조 출력 시작")
        for code, account_data in self.holdings.items():
            for acc, val in account_data.items():
                self.logger.debug(f" - 코드: {code} | 계좌: {acc} | 수량: {val.get('qty')} | 단가: {val.get('buy_price')}")

        self.print_holdings_summary()



    def reconstruct_sell_history_from_holdings(self):

        # ✅ 전체 종목코드 수집 (buy_history, holdings 기반)
        all_codes = {k[0] for k in self.buy_history if isinstance(k, tuple) and len(k) == 2}
        all_codes.update(self.holdings.keys())

        for code in all_codes:
            for account in self.accounts:
                key = self.normalize_key(code, account)

                # ✅ buy_history에 기록이 없는 경우: skip
                if key not in self.buy_history:
                    continue

                # ✅ holdings에 보유한 적이 없었던 경우: skip (실제 매수 기록 없음)
                if code not in self.holdings or account not in self.holdings[code]:
                    continue

                # ✅ 수량이 0 이하인 경우에만 매도된 것으로 판단
                qty = self.holdings[code][account].get("qty", 0)
                if qty <= 0 and key not in self.sell_history:
                    step = self.buy_history[key].get("step", 1)
                    self.sell_history[key] = {"step": step}
                    if self.SHOW_DEBUG:
                        self.logger.debug(f"🔁 {key} 매도기록 복원됨 (step={step})")



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
                    self.logger.debug(f"⏳ 미체결 복원: {code} / 계좌={account} → 체결 대기 등록됨")

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
            self.logger.debug(message)
