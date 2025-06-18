from PyQt5.QtCore import QTimer
from modules.watchlist_view import display_condition_results
from utils import log

class ConditionSearchController:
    def __init__(self, ui, api, log_fn):
        self.ui = ui
        self.api = api
        self.log = log_fn
        self.executor = None

        # 내부 상태
        self.condition_result_codes = []
        self.condition_result_data = []
        self.condition_result_index = 0
        self.condition_retry_queue = []
        self.current_condition_name = ""
        self._retry_logged = False
        self.is_retrying = False

    def on_condition_loaded(self, ret, msg):
        if ret == 1:
            self.log("✅ 조건식 로드 완료")
            self.initialize_condition_dropdown()
        else:
            self.log("❌ 조건식 로드 실패")

    def initialize_condition_dropdown(self):
        cond_list = self.ui.condition_manager.load_condition_list()
        self.ui.condition_dropdown.clear()

        if not cond_list:
            self.log("⚠️ 조건식이 없습니다.")
            return

        for index, name in cond_list:
            self.ui.condition_dropdown.addItem(f"{index}: {name}")

        self.condition_list = cond_list

    def handle_search(self):
        current_text = self.ui.condition_dropdown.currentText()
        if not current_text or ":" not in current_text:
            self.log("⚠️ 조건식을 선택하세요.")
            return

        index_str, name = current_text.split(":", 1)
        try:
            index = int(index_str.strip())
        except ValueError:
            self.log("❌ 조건식 인덱스가 올바르지 않습니다.")
            return

        name = name.strip()
        screen_no = "5000"
        self.log(f"🔍 조건검색 실행: {index} - {name}")
        self.api.ocx.dynamicCall("SendCondition(QString, QString, int, int)", screen_no, name, index, 1)

    def fetch_next_condition_stock(self):
        if self.condition_result_index >= len(self.condition_result_codes):
            if self.condition_retry_queue:
                if not self.is_retrying:
                    self.is_retrying = True
                    self.log(f"🔁 누락 종목 재시도 시작 ({len(self.condition_retry_queue)}건)")
                    QTimer.singleShot(1000, self.fetch_retry_condition_stock)
                return

            if self.condition_result_data:
                if not self._retry_logged:
                    self.log(f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료")
                    self._retry_logged = True
                display_condition_results(self.ui.condition_table, self.condition_result_data, self.ui.manual_buy_clicked)
            else:
                self.log("⚠️ 조건검색 결과가 없습니다. (가격정보 누락 또는 조회 실패 가능)")
                self.ui.condition_table.setRowCount(0)
            return

        code = self.condition_result_codes[self.condition_result_index]
        rq_name = f"조건식_TR_{code}"
        screen_no = f"60{code[-2:]}"
        self.api.set_input_value("종목코드", code)
        self.api.send_request(rq_name, "opt10001", 0, screen_no)

        if code not in self.condition_retry_queue:
            self.condition_retry_queue.append(code)

        self.condition_result_index += 1
        QTimer.singleShot(200, self.fetch_next_condition_stock)

    def fetch_retry_condition_stock(self):
        if not self.condition_retry_queue:
            self.is_retrying = False
            if self.condition_result_data:
                if not self._retry_logged:
                    self.log(f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료 (재시도 포함)")
                    self._retry_logged = True
                display_condition_results(self.ui.condition_table, self.condition_result_data, self.ui.manual_buy_clicked)
            else:
                self.log("⚠️ 재시도 후에도 조건검색 결과 없음")
                self.ui.condition_table.setRowCount(0)
            return

        code = self.condition_retry_queue.pop(0)
        rq_name = f"조건재요청_TR_{code}"
        screen_no = f"61{code[-2:]}"
        self.api.set_input_value("종목코드", code)
        self.api.send_request(rq_name, "opt10001", 0, screen_no)

        QTimer.singleShot(700, self.fetch_retry_condition_stock)

    def on_receive_tr_condition(self, screen_no, codes, condition_name, condition_index, next_):
        if not codes:
            self.log(f"⚠️ 조건 '{condition_name}' 결과 없음")
            return

        code_list = [code.strip() for code in codes.split(';') if code.strip()]

        self.api.ocx.dynamicCall("DisconnectRealData(QString)", screen_no)

        fid_list = "10;11"
        if code_list:
            codes_str = ";".join(code_list)
            self.api.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_no, codes_str, fid_list, "1")

        self.condition_result_codes = code_list
        self.condition_result_data = []
        self.condition_result_index = 0
        self.condition_retry_queue = []
        self._retry_logged = False
        self.is_retrying = False
        self.current_condition_name = condition_name

        self.log(f"✅ 조건 '{condition_name}' 결과 수신: {len(code_list)}건, 실시간 등록 및 TR 조회 시작")
        self.fetch_next_condition_stock()

    def on_receive_condition_result(self, screen_no, condition_name, condition_index, code_list_str, type_flag, condition_type):
        codes = code_list_str.strip().split(';')
        codes = [code for code in codes if code]

        self.log(f"✅ 조건 '{condition_name}' 결과 수신: {len(codes)}건, 실시간 등록 및 TR 조회 시작")

        for code in codes:
            self.api.request_basic_info(code)

            if self.executor and self.executor.condition_auto_buy:
                step = 1
                account = self.executor.get_account_by_step(step)
                buy_conf = self.executor.buy_settings.get("accounts", {}).get("계좌1", {})
                amount = buy_conf.get("amount", 0)
                enabled = buy_conf.get("enabled", False)
                order_type = self.executor.buy_settings.get("order_type", "시장가")

                if not enabled or amount <= 0:
                    continue

                if self.executor.holdings.get(code, {}).get(account, {}).get("qty", 0) > 0:
                    self.log(f"[조건매수 스킵] {code}: 계좌1 보유 중")
                    continue
                if (code, account) in self.executor.pending_buys:
                    self.log(f"[조건매수 스킵] {code}: 체결 대기 중")
                    continue

                price = self.api.get_master_last_price(code)
                name = self.api.get_master_code_name(code)

                self.log(f"[조건검색 실시간 매수] {code} / {name} / 현재가 {price:,} / 금액 {amount:,}")
                self.executor.send_buy_order(code, account, price, amount, order_type, step)

    def on_receive_real_condition(self, screen_no, code, event_type, condition_name):
        if event_type != "I":
            return

        if not self.ui.condition_auto_buy_checkbox.isChecked():
            return

        step = 1
        account = self.executor.get_account_by_step(step)
        buy_conf = self.executor.buy_settings.get("accounts", {}).get("계좌1", {})
        amount = buy_conf.get("amount", 0)
        enabled = buy_conf.get("enabled", False)
        order_type = self.executor.buy_settings.get("order_type", "시장가")

        if not enabled or amount <= 0:
            return

        if self.executor.holdings.get(code, {}).get(account, {}).get("qty", 0) > 0:
            self.log(f"[조건매수 스킵] {code}: 계좌1 보유 중")
            return
        if (code, account) in self.executor.pending_buys:
            self.log(f"[조건매수 스킵] {code}: 체결 대기 중")
            return

        name = self.api.get_master_code_name(code)
        price = self.api.get_master_last_price(code)

        self.log(f"[조건검색 실시간 매수] {code} / {name} / 현재가 {price:,} / 금액 {amount:,}")
        self.executor.send_buy_order(code, account, price, amount, order_type, step)
