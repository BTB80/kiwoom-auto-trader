from PyQt5.QtCore import QTimer
from modules.watchlist_view import display_condition_results
from utils import log

class ConditionSearchController:
    def __init__(self, ui, api, log_fn):
        self.ui = ui
        self.api = api
        self.log = log_fn

        # 내부 상태
        self.condition_result_codes = []
        self.condition_result_data = []
        self.condition_result_index = 0
        self.condition_retry_queue = []
        self.current_condition_name = ""

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

    def handle_tr_condition(self, screen_no, codes, condition_name):
        if not codes:
            self.log(f"⚠️ 조건 '{condition_name}' 결과 없음")
            return

        code_list = [code.strip() for code in codes.split(';') if code.strip()]
        self.api.ocx.dynamicCall("DisconnectRealData(QString)", screen_no)
        if code_list:
            codes_str = ";".join(code_list)
            self.api.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_no, codes_str, "10;11", "1")

        self.condition_result_codes = code_list
        self.condition_result_data = []
        self.condition_result_index = 0
        self.current_condition_name = condition_name
        self.condition_retry_queue = []
        self.fetch_next_condition_stock()
        self.log(f"✅ 조건 '{condition_name}' 결과 수신: {len(code_list)}건")

    def fetch_next_condition_stock(self):
        if self.condition_result_index >= len(self.condition_result_codes):
            if self.condition_retry_queue:
                self.log(f"🔁 누락 종목 재시도 시작 ({len(self.condition_retry_queue)}건)")
                QTimer.singleShot(1000, self.fetch_retry_condition_stock)
                return

            if self.condition_result_data:
                self.log(f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료")
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
            if self.condition_result_data:
                self.log(f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료 (재시도 포함)")
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

        # ✅ 기존 실시간 등록 해제
        self.api.ocx.dynamicCall("DisconnectRealData(QString)", screen_no)

        # ✅ 실시간 등록 (현재가, 전일가 등)
        fid_list = "10;11"
        if code_list:
            codes_str = ";".join(code_list)
            self.api.ocx.dynamicCall(
                "SetRealReg(QString, QString, QString, QString)",
                screen_no, codes_str, fid_list, "1"
            )

        # ✅ 내부 상태 초기화 및 순차 TR 조회 시작
        self.condition_result_codes = code_list
        self.condition_result_data = []
        self.condition_result_index = 0
        self.current_condition_name = condition_name  # 조건식명 기억
        self.fetch_next_condition_stock()

        self.log(f"✅ 조건 '{condition_name}' 결과 수신: {len(code_list)}건, 실시간 등록 및 TR 조회 시작")
