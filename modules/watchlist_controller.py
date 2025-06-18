class WatchlistController:
    def __init__(self, ui, api, log_fn):
        self.ui = ui
        self.api = api
        self.log = log_fn
        self.watchlist = []
        self.retry_queue = []
        self.tr_index = 0

    def load_watchlist_from_google(self, sheet_id, sheet_name):
        from modules.google_loader import fetch_google_sheet_data
        from modules.watchlist_view import display_watchlist

        try:
            self.watchlist = fetch_google_sheet_data(sheet_id, sheet_name)
            display_watchlist(self.ui.stock_search_table, self.watchlist, self.ui.manual_buy_clicked)

            for stock in self.watchlist:
                try:
                    code, name, tag = stock
                except ValueError:
                    code, name = stock
                    tag = ""
                self.log(f"🔎 관심종목: {code} | {name} | {tag}")

            self.request_basic_info_tr()
            self.register_realtime()

        except Exception as e:
            self.log(f"❌ 관심종목 불러오기 실패: {e}")

    def request_basic_info_tr(self):
        if not self.watchlist:
            self.log("⚠️ 관심종목 없음: 기본정보 요청 생략")
            return
        self.tr_index = 0
        self.retry_queue.clear()
        self.send_next_tr()

    def register_realtime(self):
        if not self.watchlist:
            self.log("⚠️ 실시간 등록 실패: watchlist 비어 있음")
            return

        code_list = ";".join([s[0] for s in self.watchlist])
        screen_no = "9100"
        self.api.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                  screen_no, code_list, "10;11;12", "0")
        self.log(f"📡 관심종목 실시간 등록 완료 ({len(self.watchlist)} 종목)")

    def send_next_tr(self):
        from modules.tr_codes import TR_WATCHLIST_DETAILS

        if self.tr_index >= len(self.watchlist):
            self.log(f"✅ 관심종목 1차 TR 요청 완료, 누락종목 수: {len(self.retry_queue)}")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(3000, self.send_retry_tr)
            return

        stock = self.watchlist[self.tr_index]
        code = stock[0]
        self.api.set_input_value("종목코드", code)
        rq_name = f"보완TR_{code}"
        screen_no = f"91{code[-2:]}"
        self.api.send_request(rq_name, TR_WATCHLIST_DETAILS, 0, screen_no)
        self.log(f"📨 기본정보 요청: {code}")

        self.tr_index += 1
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, self.send_next_tr)

    def send_retry_tr(self):
        if not self.retry_queue:
            self.log("✅ 누락 종목 재요청 완료")
            return

        code = self.retry_queue.pop(0)
        from modules.tr_codes import TR_WATCHLIST_DETAILS

        self.api.set_input_value("종목코드", code)
        rq_name = f"재요청TR_{code}"
        screen_no = f"93{code[-2:]}"
        self.api.send_request(rq_name, TR_WATCHLIST_DETAILS, 0, screen_no)
        self.log(f"🔁 재요청: {code}")

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, self.send_retry_tr)
