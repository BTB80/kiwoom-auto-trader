from PyQt5.QAxContainer import QAxWidget
from utils import log_debug, SHOW_DEBUG

class KiwoomAPI:
    def __init__(self):
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")

    def connect(self):
        self.ocx.dynamicCall("CommConnect()")

    def set_input_value(self, key, value):
        self.ocx.dynamicCall("SetInputValue(QString, QString)", key, value)

    def send_request(self, rq_name, tr_code, next_, screen_no):
        self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", rq_name, tr_code, next_, screen_no)

    def get_comm_data(self, tr_code, rq_name, index, field):
        return self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, rq_name, index, field).strip()

    def send_order(self, rqname, screen_no, acc_no, order_type, code, qty, price, hoga, org_order_no):
        if SHOW_DEBUG:
            log_debug(None, "📡 SendOrder 호출됨:")
            log_debug(None, f"  📄 rqname      = {rqname}")
            log_debug(None, f"  🖥 screen_no   = {screen_no}")
            log_debug(None, f"  💳 acc_no      = {acc_no}")
            log_debug(None, f"  🔁 order_type  = {order_type} (1: 신규매수, 2: 신규매도, 3: 매수정정, ...)")
            log_debug(None, f"  🧾 code        = {code}")
            log_debug(None, f"  🔢 qty         = {qty}")
            log_debug(None, f"  💰 price       = {price}")
            log_debug(None, f"  🎯 hoga        = {hoga} (03: 시장가, 00: 지정가, ...)")
            log_debug(None, f"  🔗 org_order_no= {org_order_no}")

        result = self.ocx.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            [rqname, screen_no, acc_no, order_type, code, qty, price, hoga, org_order_no]
        )

        if SHOW_DEBUG:
            log_debug(None, f"📨 주문 전송 결과: {result}")

        return result
    def get_master_code_name(self, code):
        return self.ocx.dynamicCall("GetMasterCodeName(QString)", code)

    def get_master_last_price(self, code):
        price_str = self.ocx.dynamicCall("GetMasterLastPrice(QString)", code)
        try:
            return int(price_str)
        except (ValueError, TypeError):
            return 0  # 또는 -1 로 기본값 설정