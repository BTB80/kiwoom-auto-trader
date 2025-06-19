from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem
from datetime import datetime
from modules.telegram_utils import send_telegram_message
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from modules.account_tr_handler import handle_account_tr_data
from modules.tr_codes import (
    TR_DEPOSIT_INFO,
    SCR_DEPOSIT_INFO,
    TR_HOLDINGS_INFO,
    SCR_HOLDINGS_INFO,
    TR_ESTIMATED_ASSET,
    TR_TODAY_PROFIT,
    SCR_TODAY_PROFIT,
    TR_ORDER_HISTORY, 
    SCR_ORDER_HISTORY,
    SCR_ESTIMATED_ASSET 
)
from modules.tr_codes import SCR_REALTIME_HOLDINGS
# from strategy_executor import AutoTradeExecutor
from utils import log, log_debug, to_int, SHOW_DEBUG
# from modules.tr_handler import handle_watchlist_tr_data

class AccountManager:
    def __init__(self, api, config=None):
        self.api = api
        self.config = config or {}
        self.executor = None
        self.account_combo = None
        self.account_info_label = None
        self.holdings_table = None
        self.log_box = None
        self.deposit = 0
        self.estimated_asset = 0
        self.available_cash = 0
        self.today_profit = 0
        self.current_account = ""
        self.total_buy = 0
        self.total_eval = 0
        self.holdings = {}  # 종목코드 → {'name', 'qty', 'buy', 'current'}
        self.scr_account_map = {}
        self.existing_trade_keys = set() 
        self.missing_codes_logged = set()
        self.retry_watchlist_queue = []
        self.api.manager = self
        self.ui = None
        # ✅ 계좌 관련 필드 초기화
        self.accounts = []
        self.expected_accounts = set()
        self.received_accounts = set()
        self.holdings_loaded = False

        
    def set_ui_elements(self, combo, label, table, log_box, unsettled_table):
        self.account_combo = combo
        self.account_info_label = label
        self.holdings_table = table
        self.log_box = log_box
        self.unsettled_table = unsettled_table
        
    def set_executor(self, executor):
        self.executor = executor
    
    def handle_login_event(self, err_code):
        if err_code == 0:
            # log(self.log_box, "✅ 로그인 성공")

            acc_list = self.api.ocx.dynamicCall("GetLoginInfo(QString)", "ACCNO")
            accounts = acc_list.strip().split(";")[:-1]

            # ✅ 설정된 계좌 번호로 필터링
            allowed = {
                self.config.get("account1", ""),
                self.config.get("account2", ""),
                self.config.get("account3", ""),
                self.config.get("account4", ""),
            }
            allowed = {acc for acc in allowed if acc}  # 빈 문자열 제거

            filtered = [acc for acc in accounts if acc in allowed]

            if SHOW_DEBUG:
                log_debug(self.log_box, f"[로그인 처리] 전체 계좌 목록: {accounts}")
                log_debug(self.log_box, f"[로그인 처리] 허용된 계좌 필터링 결과: {filtered}")

            self.account_combo.blockSignals(True)
            self.account_combo.clear()
            self.account_combo.addItems(filtered)
            self.account_combo.blockSignals(False)

            self.accounts = filtered

            if filtered and hasattr(self, 'executor') and self.executor:
                self.executor.set_accounts(filtered)
                if SHOW_DEBUG:
                    log_debug(self.log_box, "[로그인 처리] executor에 계좌 리스트 전달 완료")

        else:
            log(self.log_box, f"❌ 로그인 실패: 코드 {err_code}")

    def get_allowed_accounts(self):
        acc_list = self.api.ocx.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        accounts = acc_list.strip().split(";")[:-1]

        # ✅ 설정된 계좌번호로 필터링
        allowed = {
            self.config.get("account1", ""),
            self.config.get("account2", ""),
            self.config.get("account3", ""),
            self.config.get("account4", ""),
        }
        allowed = {acc for acc in allowed if acc}  # 빈 문자열 제거

        return [acc for acc in accounts if acc in allowed]
    
    def get_alias_by_account(self, account):
        if hasattr(self, "accounts") and account in self.accounts:
            return f"계좌{self.accounts.index(account) + 1}"
        return account  # fallback

    def request_deposit_info(self, account):
        self.current_account = account
        log(self.log_box, f"📨 예수금 조회 요청: {account}")
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", "")
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "2")
        self.api.send_request(TR_DEPOSIT_INFO, "opw00001", 0, SCR_DEPOSIT_INFO)

    def request_holdings(self, account):
        # ✅ 계좌 끝 4자리 기준 screen_no 생성 (800000 ~ 899999 내에서 고유하게)
        screen_no = str(800000 + int(account[-4:]))
        log(self.log_box, f"🔧 매핑: screen_no={screen_no}, account={account}")

        self.scr_account_map[screen_no] = account

        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", "")
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "1")
        self.api.set_input_value("거래소구분", "")
        self.api.send_request(TR_HOLDINGS_INFO, "opw00018", 0, screen_no)

    def request_all_holdings(self, accounts, on_complete=None):
        self.pending_accounts = set(accounts)
        self.on_holdings_complete = on_complete
        self._holding_index = 0  # ✅ 내부 인덱스 사용

        def request_next():
            if self._holding_index < len(accounts):
                account = accounts[self._holding_index]
                self._holding_index += 1
                self.request_holdings(account)
                QTimer.singleShot(300, request_next)  # 일정 간격 유지
            else:
                log(self.log_box, "✅ 모든 잔고 요청 전송 완료")
                self.holdings_loaded = True

                # ✅ 안전한 콜백 호출
                callback = getattr(self, "on_holdings_complete", None)
                if callable(callback):
                    callback()

                # ✅ 속성 안전 삭제
                for attr in ("_holding_index", "on_holdings_complete", "pending_accounts"):
                    if hasattr(self, attr):
                        delattr(self, attr)

        request_next()

    def handle_holdings_response_complete(self, account):
        if hasattr(self, "pending_accounts"):
            self.pending_accounts.discard(account)

            if not self.pending_accounts:
                callback = getattr(self, "on_holdings_complete", None)
                if callable(callback):
                    callback()
                if hasattr(self, "on_holdings_complete"):
                    del self.on_holdings_complete
                if hasattr(self, "pending_accounts"):
                    del self.pending_accounts

    def start_realtime_updates(self):
        if not self.holdings:
            log(self.log_box, "⚠️ 실시간 등록 실패: holdings 비어 있음")
            return

        code_list = ";".join(self.holdings.keys())
        self.api.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                SCR_REALTIME_HOLDINGS, code_list, "10", "0")

        log(self.log_box, f"📡 보유종목 실시간 시세 등록 완료 ({len(self.holdings)} 종목)")

    def update_real_time_price(self, code, new_price):
        code = code[1:] if code.startswith("A") else code

        if code in self.holdings and new_price > 0:
            for account in self.holdings[code]:
                self.holdings[code][account]["current"] = new_price
            self.refresh_holdings_ui()
        elif SHOW_DEBUG and code not in self.missing_codes_logged:
            print(f"[❌ holdings에 없음] {code} / 현재가: {new_price}")
            self.missing_codes_logged.add(code)

    def request_today_profit(self, account):
        self.today_profit = 0
        self.current_account = account
        today = datetime.now().strftime("%Y%m%d")

        self.api.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account)
        self.api.ocx.dynamicCall("SetInputValue(QString, QString)", "시작일자", today)
        self.api.ocx.dynamicCall("SetInputValue(QString, QString)", "종료일자", today)
        self.api.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                TR_TODAY_PROFIT, "opt10074", 0, SCR_TODAY_PROFIT)

        if SHOW_DEBUG:
            log_debug(self.log_box, f"[🔄 실현손익 요청] 계좌: {account}, 날짜: {today}")
                
    def request_estimated_asset(self, account):
        self.current_account = account
        log(self.log_box, f"📨 추정자산 조회 요청: {account}")
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", "")
        self.api.set_input_value("상장폐지조회구분", "0")
        self.api.send_request(TR_ESTIMATED_ASSET, "opw00003", 0, SCR_ESTIMATED_ASSET)

    def refresh_holdings_ui(self):
        self.total_buy = 0
        self.total_eval = 0

        if self.holdings_table:
            self.holdings_table.setRowCount(0)

        current_account = self.current_account  # 현재 선택된 계좌

        for code in list(self.holdings.keys()):  # 키 목록 복사하여 반복
            account_data = self.holdings[code]

            if current_account not in account_data:
                continue  # 선택된 계좌가 이 종목을 보유하지 않음

            h = account_data[current_account]
            name = h.get("name", "")
            qty = h.get("qty", 0)
            buy = h.get("buy_price", 0)
            current = h.get("current", 0)

            # ✅ 수량이 0인 경우 holdings에서 제거
            if qty <= 0:
                del self.holdings[code][current_account]
                if not self.holdings[code]:  # 종목 전체 계좌가 비었으면 제거
                    del self.holdings[code]
                continue  # UI에도 출력 생략

            buy_amt = buy * qty
            eval_amt = qty * current
            profit = eval_amt - buy_amt
            rate = ((current - buy) / buy * 100) if buy else 0.0

            self.total_buy += buy_amt
            self.total_eval += eval_amt

            row = self.holdings_table.rowCount()
            self.holdings_table.insertRow(row)

            def create_item(text, align=Qt.AlignRight, color=None):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align | Qt.AlignVCenter)
                if color:
                    item.setForeground(color)
                return item

            # 종목명
            self.holdings_table.setItem(row, 0, create_item(name, Qt.AlignCenter))

            # 수량, 매입가, 현재가
            self.holdings_table.setItem(row, 1, create_item(f"{qty:,}"))
            self.holdings_table.setItem(row, 2, create_item(f"{buy:,}"))
            self.holdings_table.setItem(row, 3, create_item(f"{current:,}"))
            # ✅ 목표단가 계산 및 표시
            alias = self.get_alias_by_account(current_account)
            sell_conf = self.executor.sell_settings.get("accounts", {}).get(alias, {})
            target_price = 0
            if sell_conf.get("enabled"):
                profit_rate = sell_conf.get("profit_rate", 0.0)
                target_price = int(buy * (1 + profit_rate / 100))

            self.holdings_table.setItem(row, 4, create_item(f"{target_price:,}" if target_price else "-"))
            # 수익률
            color = Qt.red if rate > 0 else Qt.blue if rate < 0 else Qt.black
            self.holdings_table.setItem(row, 5, create_item(f"{rate:.2f}%", color=color))

            # 매입금액, 평가금액, 평가손익
            self.holdings_table.setItem(row, 6, create_item(f"{buy_amt:,}"))
            self.holdings_table.setItem(row, 7, create_item(f"{eval_amt:,}"))
            self.holdings_table.setItem(row, 8, create_item(f"{profit:+,}", color=color))



        self.update_ui()
        self.holdings_table.viewport().update()  # ✅ 강제 리렌더링

    def handle_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next):
        if SHOW_DEBUG:
            log_debug(self.log_box, f"[DEBUG] AccountManager.handle_tr_data() 진입 → rq_name: {rq_name}")

        # ✅ 기본 계좌 관련 TR 처리
        if rq_name in (TR_DEPOSIT_INFO, TR_HOLDINGS_INFO, TR_TODAY_PROFIT, TR_ORDER_HISTORY, TR_ESTIMATED_ASSET):
            result = handle_account_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next)

            if rq_name == TR_HOLDINGS_INFO and prev_next == "0":
                if hasattr(self, "pending_accounts"):
                    self.pending_accounts.discard(self.current_account)
                    print(f"✅ 잔고 수신 완료: {self.current_account} → 남은 대기 계좌: {len(self.pending_accounts)}")
                    if not self.pending_accounts:
                        log(self.log_box, "✅ 모든 계좌의 잔고 수신 완료")
                        if hasattr(self, "on_holdings_complete") and callable(self.on_holdings_complete):
                            self.on_holdings_complete()
                        self.holdings_loaded = True

            return result

        # ✅ 관심종목 보완 TR
        elif rq_name.startswith("보완TR_") or rq_name.startswith("재요청TR_"):
            from modules.tr_handler import handle_watchlist_tr_data
            handle_watchlist_tr_data(self.api, self.stock_search_table, self.basic_info_map, rq_name, tr_code)
            return

        # ✅ 조건검색 종목 처리
        elif rq_name.startswith("조건식_TR_") or rq_name.startswith("조건재요청_TR_"):
            code = rq_name.split("_")[-1]
            name = self.api.get_master_code_name(code)
            curr = abs(to_int(self.api.get_comm_data(tr_code, rq_name, 0, "현재가").strip().replace(",", "")))
            prev = to_int(self.api.get_comm_data(tr_code, rq_name, 0, "기준가").strip().replace(",", ""))

            if prev == 0:
                log(self.log_box, f"⚠️ {code} 기준가 없음 → prev = curr ({curr})로 대체")
                prev = curr

            rate = ((curr - prev) / prev * 100) if prev else 0.0

            # ✅ basic_info_map은 executor 쪽으로 저장
            if hasattr(self.executor, "basic_info_map"):
                self.executor.basic_info_map[code] = {
                    "name": name,
                    "price": curr,
                    "current_price": curr,
                    "prev_price": prev
                }

            # ✅ 조건검색 결과 UI에 전달 (append 및 다음 TR 호출은 controller가 담당)
            if hasattr(self, "ui") and hasattr(self.ui, "condition_controller"):
                self.ui.condition_controller.handle_condition_tr_result(code, name, prev, curr, rate)

            return


        # ✅ 매수/매도 요청 후 응답 처리 (현재는 단순 로그만)
        elif rq_name in ("매수", "매도"):
            log(self.log_box, f"✅ 주문 요청 응답 수신 → rq_name: {rq_name} (체결은 chejan_data에서 처리)")
            return

        # ⚠️ 그 외 rq_name 무시
        if SHOW_DEBUG:
            log_debug(self.log_box, f"[⚠️ 무시됨] AccountManager.handle_tr_data(): rq_name={rq_name} 은 처리 대상 아님")

    def update_ui(self):
        if self.account_info_label:
            profit = self.total_eval - self.total_buy
            try:
                profit_rate = (profit / self.total_buy) * 100 if self.total_buy else 0.0
            except:
                profit_rate = 0.0

            # 색상 결정
            profit_color = "red" if profit > 0 else "blue" if profit < 0 else "black"
            rate_color = "red" if profit_rate > 0 else "blue" if profit_rate < 0 else "black"
            day_profit_color = "red" if self.today_profit > 0 else "blue" if self.today_profit < 0 else "black"


            # HTML로 색상 적용된 문자열 구성
            self.account_info_label.setText(
                f"추정예탁자산: {self.estimated_asset:,} 원<br>"
                f"예수금: {self.deposit:,} 원<br>"
                f"주문가능금액: {self.available_cash:,} 원<br>"  # ✅ 추가
                f"총매입금액: {self.total_buy:,} 원<br>"
                f"총평가금액: {self.total_eval:,} 원<br>"
                f"총평가손익금액: <span style='color:{profit_color}'>{profit:,} 원</span><br>"
                f"총수익률(%): <span style='color:{rate_color}'>{profit_rate:.2f}%</span><br>"
                f"당일 실현손익: <span style='color:{day_profit_color}'>{self.today_profit:,} 원</span>"
            )

    def request_order_history(self, account):
        self.last_requested_order_account = account  # ✅ 요청 직전 계좌 기억

        screen_no = str(900000 + int(account[-4:]))
        self.api.set_input_value("주문일자", datetime.now().strftime("%Y%m%d"))
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", "")
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "4")
        self.api.set_input_value("주식채권구분", "1")
        self.api.set_input_value("매도수구분", "0")
        self.api.set_input_value("종목코드", "")
        self.api.set_input_value("시작주문번호", "")
        self.api.set_input_value("거래소구분", "%")
        self.api.send_request(TR_ORDER_HISTORY, "opw00007", 0, screen_no)

    def request_all_order_history(self):
        if hasattr(self, "trade_log_table") and self.trade_log_table:
            self.trade_log_table.setRowCount(0)  # 전체 요청 전에 한 번만 지움
        if not hasattr(self, "accounts"):
            log(self.log_box, "❌ 계좌 목록이 설정되어 있지 않습니다.")
            return

        accounts = self.accounts

        log(self.log_box, f"🔄 전체 계좌 체결내역 요청 시작 ({len(accounts)}개)")

        def request_next_orders(index=0):
            if index >= len(accounts):
                log(self.log_box, "✅ 전체 계좌 체결내역 요청 완료")
                return

            account = accounts[index]
            log(self.log_box, f"📨 체결내역 요청: 계좌 {account}")
            self.request_order_history(account)
            QTimer.singleShot(500, lambda: request_next_orders(index + 1))  # 0.5초 간격으로 순차 요청

        request_next_orders()

    def get_screen_no_by_account(self, account):
        for screen_no, acc in self.scr_account_map.items():
            if acc == account:
                return screen_no
        return ""
