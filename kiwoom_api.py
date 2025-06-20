from PyQt5.QAxContainer import QAxWidget
from log_manager import LogManager

class KiwoomAPI:
    def __init__(self, logger=None):
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")

        self.chejan_handlers = []
        self.logger = logger or LogManager()

        self.ocx.OnReceiveChejanData.connect(self.on_chejan_data)

    # ✅ 외부 핸들러 등록
    def register_chejan_handler(self, handler):
        self.chejan_handlers.append(handler)
        if self.logger.debug_enabled:
            self.logger.debug("✅ 외부 체결 핸들러 등록됨")

    # ✅ 체결 이벤트 수신 → 외부 핸들러에 전달
    def on_chejan_data(self, gubun, item_cnt, fid_list):
        if self.logger.debug_enabled:
            self.logger.debug(f"[📨 Chejan 이벤트 수신] gubun={gubun}, item_cnt={item_cnt}")
        for handler in self.chejan_handlers:
            handler(gubun, item_cnt, fid_list)

    # ✅ 로그인 요청
    def connect(self):
        self.ocx.dynamicCall("CommConnect()")

    # ✅ TR 요청 입력값 설정
    def set_input_value(self, key, value):
        self.ocx.dynamicCall("SetInputValue(QString, QString)", key, value)

    # ✅ TR 요청 실행
    def send_request(self, rq_name, tr_code, next_, screen_no):
        self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", rq_name, tr_code, next_, screen_no)

    # ✅ 데이터 수신
    def get_comm_data(self, tr_code, rq_name, index, field):
        return self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, rq_name, index, field).strip()

    # ✅ 주문 전송
    def send_order(self, rqname, screen_no, acc_no, order_type, code, qty, price, hoga, org_order_no):
        if self.logger.debug_enabled:
            self.logger.debug(f"📡 SendOrder 호출됨:\n"
                              f"  📄 rqname      = {rqname}\n"
                              f"  🖥 screen_no   = {screen_no}\n"
                              f"  💳 acc_no      = {acc_no}\n"
                              f"  🔁 order_type  = {order_type}\n"
                              f"  🧾 code        = {code}\n"
                              f"  🔢 qty         = {qty}\n"
                              f"  💰 price       = {price}\n"
                              f"  🎯 hoga        = {hoga}\n"
                              f"  🔗 org_order_no= {org_order_no}")

        result = self.ocx.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            [rqname, screen_no, acc_no, order_type, code, qty, price, hoga, org_order_no]
        )

        if self.logger.debug_enabled:
            self.logger.debug(f"📨 주문 전송 결과: {result}")

        return result

    # ✅ 종목명 조회
    def get_master_code_name(self, code):
        return self.ocx.dynamicCall("GetMasterCodeName(QString)", code)

    # ✅ 전일종가 조회
    def get_master_last_price(self, code):
        price_str = self.ocx.dynamicCall("GetMasterLastPrice(QString)", code)
        try:
            return int(price_str)
        except (ValueError, TypeError):
            return 0
