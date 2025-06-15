import os, json  # 상단에 추가
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot,QDateTime
from PyQt5.QtCore import QTime
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QPushButton, QComboBox, QTextEdit,QDialog,
    QVBoxLayout, QHBoxLayout, QSizePolicy,QLineEdit,QButtonGroup, QTabWidget, QWidget,QApplication
)
from PyQt5.QtWidgets import QAction
from config_dialog import ConfigDialog
from config_manager import save_user_config, load_user_config
from schedule_settings_dialog import ScheduleSettingsDialog
from PyQt5.QtWidgets import QMessageBox
import datetime
from PyQt5.QtCore import Qt
from kiwoom_api import KiwoomAPI
from strategy_manager import save_current_strategy
from strategy_manager import load_strategy
from account_manager import AccountManager
from utils import log
from modules.watchlist_view import update_watchlist_status, display_condition_results
# 📦 관심종목 기능 관련 모듈
from modules.condition_manager import ConditionManager
from modules.google_loader import fetch_google_sheet_data
from modules.watchlist_view import display_watchlist, update_watchlist_price
from modules.tr_handler import handle_watchlist_tr_data
from modules.tr_codes import TR_WATCHLIST_DETAILS
from buy_sell_settings_groupbox import create_buy_settings_groupbox, create_sell_settings_groupbox
# from strategy_selector_widget import create_strategy_selector_widget
from strategy_manager import delete_strategy
from strategy_executor import AutoTradeExecutor
from buy_sell_settings_groupbox import register_chejan_handler
from PyQt5.QtCore import QTimer
from modules.all_holdings_popup import AllHoldingsPopup
from utils import log_trade
from utils import (
    log_debug,
    log_info,
    log_trade,
    SHOW_DEBUG,
    SHOW_VERBOSE_BUY_EVAL,
    SHOW_VERBOSE_SELL_EVAL
)

# ✅ 스타일 상수 추가
UNIFORM_BUTTON_STYLE = """
QPushButton {
    min-width: 100px;
    max-width: 100px;
    min-height: 20px;
    max-height: 20px;
    font-size: 12px;
    padding: 4px;
}
"""
TRADING_STYLE = """
QPushButton {
    background-color: #ff4d4d;   /* 빨간색 배경 */
    color: white;                /* 흰색 글자 */
    font-weight: bold;
    border: 1px solid #cc0000;   /* 진한 테두리 */
    border-radius: 6px;
    padding: 4px 12px;
}
"""
SELECTED_STYLE = """
QPushButton {
    background-color: #cce5ff;
    color: black;
    border: 1px solid #3399ff;
    font-size: 12px;
    font-weight: normal;
    border-radius: 6px;
    padding: 4px 12px;
}
"""
LOGIN_STYLE = """
QPushButton {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    border: 1px solid #2e7d32;
    border-radius: 6px;
    padding: 4px 12px;
    min-width: 100px;
    max-width: 100px;
}
"""
UNSELECTED_STYLE = """
QPushButton {
    background-color: #f9f9f9;
    color: #333;
    border: 1px solid #ccc;
    font-size: 12px;
    font-weight: normal;
    border-radius: 6px;
    padding: 4px 12px;
}
QPushButton:hover {
    background-color: #eaeaea;
}
"""
LABEL_STYLE = """
QLabel {
    font-size: 13px;
    font-weight: bold;
    color: #333;
}
"""
TAB_STYLE = """
QTabBar::tab {
    font-size: 12px;
    font-weight: bold;
    font-family: "맑은 고딕";       /* 폰트 명시적으로 설정 */
    padding: 4px 8px;
    min-height: 20px;
    color: #333333;
}
"""

# ✅ 그룹박스 스타일 상수
GROUPBOX_STYLE = """
QGroupBox {
    font-size: 12px;
    font-weight: bold;
    color: #333333;
}
"""
CLOCK_LABEL_STYLE = """
QLabel {
    background-color: black;
    color: yellow;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 12px;
    min-height: 20px;
}
"""
class AutoTradeUI(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/autotrade.ui", self)

        self.config = load_user_config()

        # # 🔸 최초 실행 시 설정 없으면 설정창 강제 실행
        # if not self.config.get("account1"):
        #     self.open_config_dialog(first_time=True)
        
        # # 설정된 계좌 등록
        # self.executor.set_accounts([
        #     self.config.get("account1", ""),
        #     self.config.get("account2", ""),
        #     self.config.get("account3", ""),
        #     self.config.get("account4", ""),
        # ])


        # 전역 기본 폰트
        default_font = QFont("맑은 고딕", 8)
        self.setFont(default_font)

        # 테이블 헤더 전용 폰트
        font_header = QFont("맑은 고딕", 8)
        for table in [self.holdings_table, self.stock_search_table, self.condition_table, self.unsettled_table,self.trade_log_table]:
            table.horizontalHeader().setFont(font_header)

        # 탭 제목 폰트
        tab_font = QFont("맑은 고딕", 10)
        self.account_tab.tabBar().setFont(tab_font)
        self.watchlist_tabwidget.tabBar().setFont(tab_font)
                    
        # ✅ 시계 라벨 생성
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(CLOCK_LABEL_STYLE)
        self.clock_label.setAlignment(Qt.AlignCenter)
        # ✅ 현재 시간으로 초기화
        self.update_clock()

        # ✅ 1초마다 시계 갱신 타이머
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
       
        self.trade_log_table = self.findChild(QTableWidget, "trade_log_table")
        self.trade_log_table.setColumnCount(14)
        self.trade_log_table.setHorizontalHeaderLabels([
            "일자", "시간", "계좌", "종목코드", "종목명", "구분",
            "수량", "가격", "체결금액", "수수료", "세금", "정산금액", "전략명", "비고"
        ])
        self.trade_log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trade_log_table.verticalHeader().setDefaultSectionSize(28)
        
        self.unsettled_table = self.findChild(QTableWidget, "unsettled_table")
        self.unsettled_table.setColumnCount(7)
        self.unsettled_table.setHorizontalHeaderLabels([
            "주문번호", "종목명", "구분", "주문수량", "체결수량", "잔량", "가격"
        ])
        self.unsettled_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.unsettled_table.verticalHeader().setDefaultSectionSize(28)

        # ✅ 매수/매도 설정 박스 생성 및 삽입
        buy_box = create_buy_settings_groupbox()
        sell_box = create_sell_settings_groupbox()
        self.buy_settings_group.layout().addWidget(buy_box)
        self.sell_settings_group.layout().addWidget(sell_box)
        
        
        self.max_holdings_input = self.findChild(QLineEdit, "max_holdings_input")
        self.max_holdings_input.setText("10")  # 기본값
        self.trade_start_button = self.findChild(QPushButton, "trade_start_button")
        self.trade_stop_button = self.findChild(QPushButton, "trade_stop_button")
        self.schedule_enabled_button = self.findChild(QPushButton, "schedule_enabled_button")
        
        for btn in [self.login_button, self.trade_start_button, self.trade_stop_button]:
            btn.setStyleSheet(UNIFORM_BUTTON_STYLE)
        
        self.schedule_enabled_button.toggled.connect(self.on_schedule_toggle)

        self.trade_start_button.clicked.connect(self.handle_trade_start)
        self.trade_stop_button.clicked.connect(self.handle_trade_stop)

        # ✅ 전략 위젯 요소 연결
        self.strategy_dropdown = self.findChild(QComboBox, "strategy_dropdown")
        self.strategy_name_input = self.findChild(QLineEdit, "strategy_name_input")
        self.strategy_name_input.setMaximumWidth(250)
        self.strategy_save_button = self.findChild(QPushButton, "strategy_save_button")
        self.strategy_delete_button = self.findChild(QPushButton, "strategy_delete_button")        
        self.load_existing_strategies()

        self.condition_auto_buy_checkbox = self.findChild(QPushButton, "condition_auto_buy_checkbox")
        self.condition_auto_buy_checkbox.toggled.connect(self.toggle_condition_auto_buy)
        self.schedule_dropdown_main = self.findChild(QComboBox, "schedule_dropdown_main")
        
        # ✅ 전략 위젯 시그널 연결
        self.strategy_save_button.clicked.connect(self.handle_save_strategy)
        self.strategy_delete_button.clicked.connect(self.handle_delete_strategy)
        self.strategy_dropdown.currentTextChanged.connect(self.handle_strategy_selected)
        
        # ✅ 전체잔고보기 버튼
        self.view_all_holdings_button = self.findChild(QPushButton, "view_all_holdings_button")
        self.view_all_holdings_button.clicked.connect(self.show_all_holdings_popup)
        
        # ✅ 시계창
        self.topBar.addWidget(self.clock_label)  
        
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedule_and_apply)
        self.schedule_timer.start(1000 * 30)  # 30초마다 확인
        
        # ✅ 테이블 설정
        self.stock_search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stock_search_table.verticalHeader().setDefaultSectionSize(30)
        self.holdings_table.verticalHeader().setDefaultSectionSize(30)
        self.stock_search_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.holdings_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 탭 위젯 연결
        self.account_tab = self.findChild(QTabWidget, "account_tab")
        self.watchlist_tabwidget = self.findChild(QTabWidget, "watchlist_tabwidget")

        # 스타일 일괄 적용
        for tab in [self.account_tab, self.watchlist_tabwidget]:
            if tab:
                tab.setStyleSheet(TAB_STYLE)

        # ✅ 테이블 컬럼 정의
        self.holdings_table.setColumnCount(9)
        self.holdings_table.setHorizontalHeaderLabels(["종목명", "보유수량", "매입가", "현재가", "목표단가", "수익률(%)",  "매입금액", "평가금액", "평가손익"
        ])
        self.holdings_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.stock_search_table.setColumnCount(7)
        self.stock_search_table.setHorizontalHeaderLabels(
            ["종목코드", "종목명", "전일종가", "현재가", "등락률", "상태", "매수"]
        )
        self.stock_search_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.api = KiwoomAPI()
        self.basic_info_map = {}
        self.manager = AccountManager(self.api)
        self.manager.ui = self
        
        self.executor = AutoTradeExecutor(self.api)
        self.executor.set_manager(self.manager) 
        self.executor.set_basic_info_map(self.basic_info_map)
        
        self.manager.set_executor(self.executor)
        
        
        
        # ✅ 실시간 종목 감시용 목록
        self.watchlist = []
        self.basic_info_map = {}

        # ✅ UI 요소 연결 이후에 set_ui_elements 호출
        self.manager.set_ui_elements(
            self.account_combo,
            self.account_info_label,
            self.holdings_table,
            self.log_box,
            self.unsettled_table,
        )
        self.manager.trade_log_table = self.trade_log_table
        
        # ✅ 관심종목 테이블 연결 추가
        self.manager.stock_search_table = self.stock_search_table
        self.manager.basic_info_map = self.basic_info_map

        # ✅ log_box가 준비된 이후에 ConditionManager 초기화
        
        self.condition_manager = ConditionManager(self.api, log_fn=lambda msg: log(self.log_box, msg))
        # ✅ 조건식 목록 불러오기 (여기 추가!)
        

        # ✅ 조건검색 결과 시그널 연결
        self.api.ocx.OnReceiveTrCondition.connect(self.on_receive_tr_condition)
        self.api.ocx.OnReceiveRealCondition.connect(self.on_receive_real_condition)
        
        # ✅ 로그 기록 위젯 지정
        log_trade.log_widget = self.log_box
        
        # ✅ Qt 시그널 연결
        self.api.ocx.OnEventConnect.connect(self.on_login_event)
        self.api.ocx.OnReceiveTrData.connect(self.handle_tr_data)
        self.api.ocx.OnReceiveRealData.connect(self.on_real_data)
        self.login_button.clicked.connect(self.login)
        self.account_combo.currentTextChanged.connect(self.manager.request_deposit_info)
        self.watchlist_button = self.findChild(QPushButton, "watchlist_button")
        self.watchlist_button.clicked.connect(self.load_watchlist_from_google)

        # ✅ 매수/매도 위젯 연결
        self.buy_order_type_combo = buy_box.findChild(QComboBox, "buy_order_type_combo")
        self.buy_test_mode_checkbox = buy_box.findChild(QPushButton, "buy_test_mode_checkbox")
        self.buy_account_buttons = [buy_box.findChild(QPushButton, f"buy_account_button_{i+1}") for i in range(4)]
        self.buy_amount_inputs = [buy_box.findChild(QLineEdit, f"buy_amount_input_{i+1}") for i in range(4)]
        self.buy_drop_inputs = [buy_box.findChild(QLineEdit, f"buy_drop_input_{i+1}") for i in range(4)]

        self.sell_order_type_combo = sell_box.findChild(QComboBox, "sell_order_type_combo")
        self.sell_account_buttons = [sell_box.findChild(QPushButton, f"sell_account_button_{i+1}") for i in range(4)]
        self.sell_ratio_inputs = [sell_box.findChild(QLineEdit, f"sell_ratio_input_{i+1}") for i in range(4)]
        self.sell_profit_inputs = [sell_box.findChild(QLineEdit, f"sell_profit_input_{i+1}") for i in range(4)]
        
        self.setup_account_buttons()
        self.setup_table_styles()
        self.account_combo.currentTextChanged.connect(self.handle_account_selected)
        
        # 레이아웃 stretch 설정
        self.topBar = self.findChild(QHBoxLayout, "topBar")
        layout = self.findChild(QHBoxLayout, "topInfoLayout")
        if layout:
            layout.setStretch(0, 1)
            layout.setStretch(1, 1)
            layout.setStretch(2, 3)
            layout.setStretch(3, 3)
        
        # 폼 요소 사이즈 제한
        self.max_holdings_input.setMaximumWidth(40)
        self.max_holdings_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # 👉 입력란 가운데 정렬 + 진하게
        self.max_holdings_input.setAlignment(Qt.AlignCenter)
        font_input = self.max_holdings_input.font()
        font_input.setBold(True)
        self.max_holdings_input.setFont(font_input)

        # ✅ 분할매수 / 분할매도 제목 스타일 및 텍스트 변경
        buy_settings_group = self.findChild(QGroupBox, "buy_settings_group")
        if buy_settings_group:
            buy_settings_group.setTitle("📈 분할매수")
            buy_settings_group.setStyleSheet(GROUPBOX_STYLE)

        sell_settings_group = self.findChild(QGroupBox, "sell_settings_group")
        if sell_settings_group:
            sell_settings_group.setTitle("📉 분할매도")
            sell_settings_group.setStyleSheet(GROUPBOX_STYLE)
            
        # 관심종목 및 조건검색 테이블 연결
        self.stock_search_table = self.findChild(QTableWidget, "stock_search_table")

        watchlist_label = self.findChild(QLabel, "watchlist_label")
        if watchlist_label:
            watchlist_label.setStyleSheet(LABEL_STYLE)
            watchlist_label.setAlignment(Qt.AlignLeft)

            # ⛳ 탭 내부 위젯에서 직접 layout 추출
            tab_watchlist = self.findChild(QWidget, "tab_watchlist")
            if tab_watchlist:
                layout = tab_watchlist.layout()
                if layout:
                    layout.setContentsMargins(10, 0, 10, 10)  # 좌우 마진
                    
        # 로그 라벨 스타일 적용
        log_label = self.findChild(QLabel, "log_label")
        if log_label:
            log_label.setStyleSheet(LABEL_STYLE)
            log_label.setAlignment(Qt.AlignLeft)
        
        uniform_width = 100
        for name in [
            "login_button", "trade_start_button", "trade_stop_button",
            "strategy_save_button", "strategy_delete_button", "view_all_holdings_button"
        ]:
            btn = self.findChild(QPushButton, name)
            if btn:
                btn.setFixedWidth(uniform_width)

            
        account_tab = self.findChild(QTabWidget, "account_tab")
        if account_tab:
            account_tab.setStyleSheet(TAB_STYLE)
            account_tab.setTabText(0, "📊 잔고")
            account_tab.setTabText(1, "📦 미체결")
            account_tab.setTabText(2, "🧾 매매내역")
        
        self.api.ocx.OnReceiveConditionVer.connect(self.on_condition_loaded)
        
        self.condition_dropdown = self.findChild(QComboBox, "condition_dropdown")
        self.condition_search_button = self.findChild(QPushButton, "condition_search_button")
        if self.condition_search_button:
            self.condition_search_button.clicked.connect(self.handle_condition_search)
        self.condition_table = self.findChild(QTableWidget, "condition_table")
        self.condition_table.setColumnCount(7)
        self.condition_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "전일종가", "현재가", "등락률", "조건식명", "매수"
        ])
        self.condition_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.condition_table.verticalHeader().setDefaultSectionSize(28)
        self.is_fullscreen = False
        # 로그 VBox 마진 조정
        log_container = self.log_label.parentWidget()
        if log_container:
            layout = log_container.layout()
            if layout:
                layout.setContentsMargins(10, 0, 10, 10)  # 좌측 5px, 우측 10px
                
        self.log_box = self.findChild(QTextEdit, "log_box")
        self.setup_menu_actions()
        self.refresh_schedule_dropdown_main()
        self.schedule_dropdown_main.currentTextChanged.connect(self.load_selected_schedule)
        self.manager.on_login_complete = self.on_login_complete
        
    def set_buy_settings_to_ui(self, buy_data):
        self.buy_order_type_combo.setCurrentText(buy_data.get("order_type", "시장가"))
        self.buy_test_mode_checkbox.setChecked(buy_data.get("test_mode", False))

        for i, acc in enumerate(["계좌1", "계좌2", "계좌3", "계좌4"]):
            acc_data = buy_data["accounts"].get(acc, {})
            self.buy_account_buttons[i].setChecked(acc_data.get("enabled", False))
            amount = int(acc_data.get("amount", 0))
            self.buy_amount_inputs[i].setText(f"{amount:,}")
            self.buy_drop_inputs[i].setText(str(acc_data.get("drop_rate", 0.0)))

    def set_sell_settings_to_ui(self, sell_data):
        self.sell_order_type_combo.setCurrentText(sell_data.get("order_type", "시장가"))

        for i, acc in enumerate(["계좌1", "계좌2", "계좌3", "계좌4"]):
            acc_data = sell_data["accounts"].get(acc, {})
            self.sell_account_buttons[i].setChecked(acc_data.get("enabled", False))
            self.sell_ratio_inputs[i].setText(str(acc_data.get("ratio", 0)))
            self.sell_profit_inputs[i].setText(str(acc_data.get("profit_rate", 0.0)))      
            
            
    def setup_table_styles(self):
        font_header = QFont("맑은 고딕", 9)     # 헤더: 굵고 크게
        font_body = QFont("맑은 고딕", 10)                  # 본문: 일반 크기

        for table in [self.holdings_table, self.stock_search_table, self.condition_table, self.unsettled_table,self.trade_log_table]:
            # 본문 글꼴 설정
            table.setFont(font_body)

            # 헤더 글꼴 설정 (수평 헤더만 조정)
            header = table.horizontalHeader()
            header.setFont(font_header)

            # 스타일 보완 (색상만 스타일시트로)
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #f0f0f0;
                }
                QHeaderView::section {
                    background-color: #e6e6e6;
                    padding: 2px;
                    border: 1px solid #aaa;
                }
            """)

        # 로그창은 기존대로 유지
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        
    def setup_account_buttons(self):
        self.account_buttons = [
            self.findChild(QPushButton, "account_button_1"),
            self.findChild(QPushButton, "account_button_2"),
            self.findChild(QPushButton, "account_button_3"),
            self.findChild(QPushButton, "account_button_4"),
        ]

        self.account_button_group = QButtonGroup()
        self.account_button_group.setExclusive(True)  # ✅ 단일 선택만 가능

        for i, btn in enumerate(self.account_buttons):
            btn.setCheckable(True)
            self.account_button_group.addButton(btn, i)

        self.account_button_group.buttonClicked[int].connect(self.handle_account_button_clicked)

    def handle_account_button_clicked(self, index):
        if hasattr(self, 'executor') and self.executor.accounts:
            account = self.executor.accounts[index]
            self.account_combo.setCurrentText(account)

        for i, btn in enumerate(self.account_buttons):
            if i == index:
                btn.setStyleSheet(SELECTED_STYLE)
            else:
                btn.setStyleSheet(UNSELECTED_STYLE)

    def handle_account_selected(self, account):
        is_same_account = account == self.manager.current_account
        self.current_account = account
        self.manager.current_account = account  # ✅ 상태 동기화

        self.manager.request_deposit_info(account)
        self.manager.request_estimated_asset(account)

        # ✅ 중복 요청 방지: 동일 계좌 + 잔고 이미 로드된 경우 생략
        if not is_same_account or not self.manager.holdings_loaded:
            self.manager.request_holdings(account)

        self.manager.request_today_profit(account)
        self.manager.request_order_history(account)

        if not is_same_account:
            self.manager.refresh_holdings_ui()  # 테이블은 계좌 변경 시만 갱신

        # 버튼 시각 동기화
        for i, acc in enumerate(self.executor.accounts):
            if acc == account:
                self.account_buttons[i].setChecked(True)
                self.account_buttons[i].setStyleSheet(SELECTED_STYLE)
            else:
                self.account_buttons[i].setChecked(False)
                self.account_buttons[i].setStyleSheet(UNSELECTED_STYLE)


    @pyqtSlot()
    def start_realtime_updates(self):
        self.manager.start_realtime_updates()
        
    def on_holdings_loaded(self):
        print("✅ 잔고 수신 완료 → 매매 시작 버튼 활성화")
        self.manager.holdings_loaded = True
        self.trade_start_button.setEnabled(True)

        # ✅ 여기서 보유 기반 복원 로직 실행
        self.executor.holdings = self.manager.holdings
        self.executor.reconstruct_buy_history_from_holdings()
        self.executor.reconstruct_sell_history_from_holdings()
        self.executor.reconstruct_pending_buys_from_unsettled()
    
        
    @pyqtSlot("int")
    def on_login_event(self, err_code):
        self.manager.handle_login_event(err_code)

        if err_code == 0:
            # ✅ 체결 이벤트 핸들러 등록
            self.api.register_chejan_handler(self.executor.handle_chejan_data)
            print("✅ 체결 이벤트 핸들러 등록 완료")

            accounts = [self.account_combo.itemText(i) for i in range(self.account_combo.count())]
            self.accounts = accounts
            self.executor.set_accounts(accounts)

            # ✅ holdings 추적용 세팅
            self.manager.expected_accounts = set(accounts)
            self.manager.received_accounts = set()
            self.manager.holdings_loaded = False

            if accounts:
                first_account = accounts[0]
                self.first_account = first_account
                self.account_combo.setCurrentText(first_account)

                # ✅ 잔고 수신 완료 후 계좌 선택 및 기타 요청 실행
                def after_holdings_loaded():
                    self.on_holdings_loaded()
                    self.handle_account_selected(first_account)
                    self.manager.request_today_profit(first_account)
                    self.manager.request_estimated_asset(first_account)

                self.manager.request_all_holdings(
                    accounts,
                    on_complete=after_holdings_loaded
                )

            # ✅ 기본 전략 자동 로드
            if self.strategy_dropdown and self.strategy_dropdown.findText("기본") != -1:
                self.strategy_dropdown.setCurrentText("기본")
                self.handle_strategy_selected("기본")

            # ✅ 조건식 로드
            self.api.ocx.dynamicCall("GetConditionLoad()")

        else:
            log(self.log_box, f"❌ 로그인 실패: 코드 {err_code}")

            
    def on_login_complete(self):
                self.trade_start_button.setEnabled(False)  # 🔒 먼저 비활성화
                self.login_button.setStyleSheet(LOGIN_STYLE)
                self.manager.request_all_holdings(
                    accounts=self.manager.accounts,
                    on_complete=self.on_holdings_loaded   
            )

    @pyqtSlot()
    def login(self):
        log(self.log_box, "\U0001F511 로그인 요청 중...")
        self.api.connect()
                    

    def start_auto_trade(self):
            if not getattr(self.manager, "holdings_loaded", False):
                QMessageBox.warning(self, "⏳ 잔고 수신 중", "보유 종목 정보를 아직 수신되지 않았습니다.")
                return

            log(self.log_box, "✅ 자동매매 준비 중 → 상태 복원 중...")

            # 보유정보를 executor에 복사
            self.executor.holdings = self.manager.holdings

            # 🔁 buy/sell history 재구성
            self.executor.reconstruct_buy_history_from_holdings()
            self.executor.reconstruct_sell_history_from_holdings()

            log(self.log_box, "🔁 매수/매도 단계 자동 복원 완료")

            # 일시적으로 비활성화
            self.executor.enabled = False

            if len(self.executor.accounts) > 1:
                self.handle_account_button_clicked(1)
                QTimer.singleShot(1000, lambda: self.handle_account_button_clicked(0))

            # 7초 뒤 자동매매 활성화
            QTimer.singleShot(7000, self.enable_auto_trade)

    def enable_auto_trade(self):
        self.executor.enabled = True
        log(self.log_box, "✅ 자동매매 활성화 완료 (보유 종목 복원 이후)")


    def stop_auto_trade(self):
        self.executor.enabled = False
        log(self.log_box, "🛑 자동매매 종료")
        
    def handle_trade_start(self):
        if not getattr(self.manager, "holdings_loaded", False):
            log(self.log_box, "❌ 매매 시작 실패: 잔고 수신이 아직 완료되지 않았습니다.")
            return

        self.start_auto_trade()
        self.trade_start_button.setText("매매중")
        self.trade_start_button.setStyleSheet(UNIFORM_BUTTON_STYLE + TRADING_STYLE)
        self.trade_stop_button.setStyleSheet(UNIFORM_BUTTON_STYLE)
        

    def handle_trade_stop(self):
        self.stop_auto_trade()  # ✅ 기존 로직 호출
        self.trade_start_button .setText("매매 시작")
        self.trade_start_button .setStyleSheet(UNIFORM_BUTTON_STYLE)
        self.trade_stop_button.setStyleSheet(UNIFORM_BUTTON_STYLE)

    @pyqtSlot("QString", "QString", "QString")
    def on_real_data(self, code, real_type, data):
        # print(f"[실시간 수신] {code} / {real_type} / enabled={self.executor.enabled}")
        if real_type == "주식체결":
            price_str = self.api.ocx.dynamicCall("GetCommRealData(QString, int)", code, 10).strip()

            if not price_str:
                log(self.log_box, f"⚠️ 실시간 현재가 없음, TR로 보완 요청: {code}")
                self.request_price_tr_for_code(code)
                return

            try:
                price = abs(int(price_str))

                # ✅ 기본 정보 반영
                self.basic_info_map[code] = {
                    **self.basic_info_map.get(code, {}),
                    "price": price
                }

                # ✅ 관심종목 현재가 갱신
                self.manager.update_real_time_price(code, price)
                update_watchlist_price(self.stock_search_table, self.basic_info_map, code, price)

                # ✅ 조건검색 테이블 갱신 (조건검색 결과에 포함된 종목만)
                for row in range(self.condition_table.rowCount()):
                    item_code = self.condition_table.item(row, 0)
                    item_prev = self.condition_table.item(row, 2)
                    if item_code and item_code.text() == code and item_prev:
                        try:
                            prev = int(item_prev.text().replace(",", ""))
                            rate = ((price - prev) / prev * 100) if prev else 0.0

                            self.condition_table.setItem(row, 3, QTableWidgetItem(f"{price:,}"))  # 현재가
                            rate_item = QTableWidgetItem(f"{rate:.2f}%")
                            rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            if rate > 0:
                                rate_item.setForeground(Qt.red)
                            elif rate < 0:
                                rate_item.setForeground(Qt.blue)
                            self.condition_table.setItem(row, 4, rate_item)
                        except Exception as e:
                            log(self.log_box, f"⚠️ 조건검색 테이블 갱신 실패: {code} / {e}")
                        break  # 조건검색 테이블에서 해당 종목만 업데이트

                # ✅ 자동매매가 켜진 경우만 평가
                if self.executor.enabled:
                    self.executor.evaluate_buy(code, price)
                    self.executor.evaluate_sell(code, price)

            except Exception as e:
                log(self.log_box, f"❌ 현재가 변환 실패: {code} → '{price_str}' / {e}")



    def handle_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next):
        if rq_name.startswith("기본정보_"):
            handle_watchlist_tr_data(self.api, self.stock_search_table, self.basic_info_map, rq_name, tr_code)
        else:
            self.manager.handle_tr_data(scr_no, rq_name, tr_code, record_name, prev_next)
            
            
            
            
            
            

    def load_watchlist_from_google(self):
        try:
            sheet_id = "1ebHJV_SOg50092IH88yNK5ecPgx_0UBWu5EybpBWuuU"
            self.watchlist = fetch_google_sheet_data(sheet_id)
            display_watchlist(self.stock_search_table, self.watchlist, self.manual_buy_clicked)
            for stock in self.watchlist:
                try:
                    code, name, tag = stock
                except ValueError:
                    code, name = stock
                    tag = ""
                log(self.log_box, f"🔎 관심종목: {code} | {name} | {tag}")
            self.request_basic_info_for_watchlist()
            self.start_watchlist_realtime()

            if self.is_market_closed():
                self.request_all_watchlist_prices_by_tr()
        except Exception as e:
            log(self.log_box, f"❌ 관심종목 불러오기 실패: {e}")

    def request_basic_info_for_watchlist(self):
        if not getattr(self, "watchlist", []):
            log(self.log_box, "⚠️ 관심종목 없음: 기본정보 요청 생략")
            return

        self.watchlist_tr_index = 0
        self.retry_watchlist_queue = []
        self.send_next_watchlist_tr()

    def start_watchlist_realtime(self):
        if not getattr(self, "watchlist", []):
            log(self.log_box, "⚠️ 실시간 등록 실패: watchlist 비어 있음")
            return

        try:
            code_list = ";".join([stock[0] for stock in self.watchlist])
            screen_no = "9100"
            self.api.ocx.dynamicCall(
                "SetRealReg(QString, QString, QString, QString)",
                screen_no, code_list, "10;11;12", "0"
            )
            log(self.log_box, f"📡 관심종목 실시간 등록 완료 ({len(self.watchlist)} 종목)")
        except Exception as e:
            log(self.log_box, f"❌ 관심종목 실시간 등록 실패: {e}")

    def is_market_closed(self):
        now = datetime.datetime.now()
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute
        return weekday >= 5 or (hour > 15 or (hour == 15 and minute >= 30))

    def request_all_watchlist_prices_by_tr(self):
        if not getattr(self, "watchlist", []):
            log(self.log_box, "⚠️ 관심종목 없음: TR 요청 생략")
            return

        self.watchlist_tr_index = 0
        self.retry_watchlist_queue = []  # ❗ 재요청 큐 초기화
        self.send_next_watchlist_tr()

    def send_next_watchlist_tr(self):
        if self.watchlist_tr_index >= len(self.watchlist):
            log(self.log_box, f"✅ 관심종목 1차 TR 요청 완료, 누락종목 수: {len(self.retry_watchlist_queue)}")
            QTimer.singleShot(3000, self.send_retry_watchlist_tr)
            return

        stock = self.watchlist[self.watchlist_tr_index]
        code = stock[0]
        self.api.set_input_value("종목코드", code)
        rq_name = f"보완TR_{code}"
        screen_no = f"{9100 + int(code[-2:]):04d}"
        self.api.send_request(rq_name, TR_WATCHLIST_DETAILS, 0, screen_no)
        log(self.log_box, f"📨 기본정보 요청: {code}")

        self.watchlist_tr_index += 1
        QTimer.singleShot(1500, self.send_next_watchlist_tr)

    def send_retry_watchlist_tr(self):
        log(self.log_box, f"🔁 재요청 진입 → 큐 크기: {len(self.retry_watchlist_queue)}")
        
        if not self.retry_watchlist_queue:
            log(self.log_box, "✅ 누락 종목 재요청 완료")
            return

        code = self.retry_watchlist_queue.pop(0)
        self.api.set_input_value("종목코드", code)
        rq_name = f"재요청TR_{code}"
        screen_no = f"{9300 + int(code[-2:]):04d}"
        self.api.send_request(rq_name, TR_WATCHLIST_DETAILS, 0, screen_no)
        log(self.log_box, f"🔁 재요청: {code}")

        QTimer.singleShot(1500, self.send_retry_watchlist_tr)
                   
    def manual_buy_clicked(self, code):
        account = self.executor.get_account_by_step(1)  # 계좌1

        # ✅ buy_settings
        buy_conf = self.executor.buy_settings.get("accounts", {}).get("계좌1", {})
        amount = buy_conf.get("amount", 0)

        # ✅ 지정가 사용
        order_type_ui = "지정가"
        s_order_type = 1
        s_hoga = "00"

        # ✅ 현재가 및 종목명
        info = self.basic_info_map.get(code, {})
        current_price = info.get("price") or info.get("current_price", 0)
        name = info.get("name", code)

        log_debug(self.log_box, f"[🛠 수동매수 진입] {code} / 현재가: {current_price}, 금액: {amount}, 이름: {name}")

        if current_price == 0:
            log(self.log_box, f"❌ {code} 매수 실패: 현재가 없음 (TR 미도달 또는 실시간 미반영)")
            return
        if amount == 0:
            log(self.log_box, f"❌ {code} 매수 실패: 전략 설정 금액 없음")
            return

        confirm = QMessageBox.question(
            self.window(),  # 명확한 parent 설정
            "매수 확인",
            f"[{code} - {name}]\n현재가 {current_price:,}원에\n{amount:,}원 **지정가** 매수 진행할까요?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            qty = max(int(amount // current_price), 1)
            s_rqname = f"수동매수:{code}"
            s_screen = "9999"
            s_account = account
            s_price = int(current_price)

            if SHOW_DEBUG:
                log_debug(self.log_box, f"📡 SendOrder 호출됨:\n"
                                        f"  📄 rqname      = {s_rqname}\n"
                                        f"  🖥 screen_no   = {s_screen}\n"
                                        f"  💳 acc_no      = {s_account}\n"
                                        f"  🔁 order_type  = {s_order_type} (1: 지정가)\n"
                                        f"  🧾 code        = {code}\n"
                                        f"  🔢 qty         = {qty}\n"
                                        f"  💰 price       = {s_price}\n"
                                        f"  🎯 hoga        = {s_hoga}")

            res = self.api.send_order(
                rqname=s_rqname,
                screen_no=s_screen,
                acc_no=s_account,
                order_type=s_order_type,
                code=code,
                qty=qty,
                price=s_price,
                hoga=s_hoga,
                org_order_no=""
            )

            self.executor.pending_buys.add((code, account))
            log(self.log_box, f"🛒 수동매수: {code} | {qty}주 | 지정가 | 계좌: {s_account}")

            # ✅ 상태 갱신
            if hasattr(self, "stock_search_table"):
                update_watchlist_status(self.stock_search_table, code, "⏳ 체결 대기")

            # ✅ 잔고 갱신 요청
            if hasattr(self.manager, "request_holdings"):
                self.manager.request_holdings(s_account)

    def handle_strategy_selected(self, strategy_name):
        strategy = load_strategy(strategy_name, self.log_box)  # ✅ 로그 출력 추가
        if not strategy:
            return
        self.strategy_name_input.setText(strategy_name)

        self.set_buy_settings_to_ui(strategy["buy"])
        self.set_sell_settings_to_ui(strategy["sell"])

        # ✅ executor가 존재할 때만 설정 업데이트
        if hasattr(self, "executor") and self.executor:
            self.executor.update_settings(strategy)
        else:
            log(self.log_box, "⚠️ 자동매매 실행기가 아직 초기화되지 않았습니다.")

    def handle_save_strategy(self):
        strategy_name = self.strategy_name_input.text().strip()
        if not strategy_name:
            log(self.log_box, "❌ 전략 이름을 입력하세요.")
            return

        # 매수 설정 추출
        buy_settings = {
            "order_type": self.buy_order_type_combo.currentText(),
            "test_mode": self.buy_test_mode_checkbox.isChecked(),
            "accounts": {}
        }

        for i, acc in enumerate(["계좌1", "계좌2", "계좌3", "계좌4"]):
            buy_settings["accounts"][acc] = {
                "enabled": self.buy_account_buttons[i].isChecked(),
                "amount": float(self.buy_amount_inputs[i].text().replace(",", "") or 0),
                "drop_rate": float(self.buy_drop_inputs[i].text() or 0)
            }

        # 매도 설정 추출
        sell_settings = {
            "order_type": self.sell_order_type_combo.currentText(),
            "accounts": {}
        }

        for i, acc in enumerate(["계좌1", "계좌2", "계좌3", "계좌4"]):
            sell_settings["accounts"][acc] = {
                "enabled": self.sell_account_buttons[i].isChecked(),
                "ratio": float(self.sell_ratio_inputs[i].text() or 0),
                "profit_rate": float(self.sell_profit_inputs[i].text() or 0)
            }

        # 전략 저장
        save_current_strategy(strategy_name, buy_settings, sell_settings)

        # 드롭다운에 전략 없으면 추가
        existing = [self.strategy_dropdown.itemText(i) for i in range(self.strategy_dropdown.count())]
        if strategy_name not in existing:
            self.strategy_dropdown.addItem(strategy_name)

        log(self.log_box, f"✅ 전략 '{strategy_name}' 저장 완료")

        # ✅ 저장한 전략을 현재 자동매매에 즉시 반영
        if hasattr(self, 'executor'):
            self.executor.update_settings({
                "buy": buy_settings,
                "sell": sell_settings
            })
            log(self.log_box, f"🔁 전략 '{strategy_name}' 자동매매에 즉시 반영됨")
            
    def load_existing_strategies(self):
        strategy_dir = "strategies"
        if not os.path.exists(strategy_dir):
            return

        for file in os.listdir(strategy_dir):
            if file.endswith(".json"):
                name = file.replace(".json", "")
                if self.strategy_dropdown.findText(name) == -1:
                    self.strategy_dropdown.addItem(name)
                  
    def handle_delete_strategy(self):
        strategy_name = self.strategy_dropdown.currentText().strip()
        if not strategy_name:
            log(self.log_box, "❌ 삭제할 전략을 선택하세요.")
            return

        if delete_strategy(strategy_name):
            # 드롭다운에서 제거
            index = self.strategy_dropdown.findText(strategy_name)
            if index >= 0:
                self.strategy_dropdown.removeItem(index)

            # 입력 필드 비우기
            self.strategy_name_input.setText("")
            log(self.log_box, f"🗑 전략 '{strategy_name}' 삭제됨")
        else:
            log(self.log_box, f"⚠️ 전략 '{strategy_name}' 삭제 실패")
                       


    



    def show_all_holdings_popup(self):
        if not hasattr(self, 'accounts') or not self.accounts:
            log(self.log_box, "❗ 로그인 후 이용 가능합니다.")
            return

        # ✅ holdings 요청 완료 후 창 생성
        def after_loaded():
            self.all_holdings_popup = AllHoldingsPopup(self.manager.holdings, self.executor.basic_info_map, self.manager)
            self.all_holdings_popup.setWindowModality(Qt.NonModal)
            self.all_holdings_popup.setWindowFlags(Qt.Window)
            self.all_holdings_popup.show()

            self.all_holdings_popup.finished.connect(lambda: self.holdings_refresh_timer.stop())

            self.holdings_refresh_timer = QTimer(self)
            self.holdings_refresh_timer.timeout.connect(lambda: self.all_holdings_popup.refresh())
            self.holdings_refresh_timer.start(1500)

        self.manager.request_all_holdings(self.accounts, on_complete=after_loaded)

    def update_clock(self):
        now = QDateTime.currentDateTime()
        day_of_week = ["일", "월", "화", "수", "목", "금", "토"][now.date().dayOfWeek() % 7]
        time_str = now.toString(f"MM-dd({day_of_week}) HH:mm:ss")
        self.clock_label.setText(time_str)
        

    def fetch_next_condition_stock(self):
        # 재시도 큐 초기화 (최초 호출 시)
        if not hasattr(self, "condition_retry_queue"):
            self.condition_retry_queue = []

        if self.condition_result_index >= len(self.condition_result_codes):
            if self.condition_retry_queue:
                log(self.log_box, f"🔁 누락 종목 재시도 시작 ({len(self.condition_retry_queue)}건)")
                QTimer.singleShot(1000, self.fetch_retry_condition_stock)
                return

            if self.condition_result_data:
                log(self.log_box, f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료")
                display_condition_results(self.condition_table, self.condition_result_data, self.manual_buy_clicked)
            else:
                log(self.log_box, "⚠️ 조건검색 결과가 없습니다. (가격정보 누락 또는 조회 실패 가능)")
                self.condition_table.setRowCount(0)
            return

        code = self.condition_result_codes[self.condition_result_index]
        rq_name = f"조건식_TR_{code}"
        screen_no = f"60{code[-2:]}"
        self.api.set_input_value("종목코드", code)
        self.api.send_request(rq_name, "opt10001", 0, screen_no)

        # ✅ 일단 누락 후보로 추가 (성공 시 별도 제거)
        if code not in self.condition_retry_queue:
            self.condition_retry_queue.append(code)

        self.condition_result_index += 1
        QTimer.singleShot(200, self.fetch_next_condition_stock)

    def fetch_retry_condition_stock(self):
        if not self.condition_retry_queue:
            if self.condition_result_data:
                log(self.log_box, f"📥 조건검색 결과 {len(self.condition_result_data)}건 반영 완료 (재시도 포함)")
                display_condition_results(self.condition_table, self.condition_result_data, self.manual_buy_clicked)
            else:
                log(self.log_box, "⚠️ 재시도 후에도 조건검색 결과 없음")
                self.condition_table.setRowCount(0)
            return

        code = self.condition_retry_queue.pop(0)
        rq_name = f"조건재요청_TR_{code}"
        screen_no = f"61{code[-2:]}"
        self.api.set_input_value("종목코드", code)
        self.api.send_request(rq_name, "opt10001", 0, screen_no)

        QTimer.singleShot(700, self.fetch_retry_condition_stock)




    

    
# 조건검색 드롭다운 + 실행 버튼 연결 예시
    def initialize_condition_dropdown(self):
        cond_list = self.condition_manager.load_condition_list()
        self.condition_dropdown.clear()

        if not cond_list:
            log(self.log_box, "⚠️ 조건식이 없습니다.")
            return

        for index, name in cond_list:
            self.condition_dropdown.addItem(f"{index}: {name}")

        self.condition_list = cond_list  # 필요 시 저장




    def handle_condition_search(self):
        current_text = self.condition_dropdown.currentText()
        if not current_text or ":" not in current_text:
            log(self.log_box, "⚠️ 조건식을 선택하세요.")
            return

        index_str, name = current_text.split(":", 1)
        try:
            index = int(index_str.strip())
        except ValueError:
            log(self.log_box, "❌ 조건식 인덱스가 올바르지 않습니다.")
            return

        name = name.strip()
        screen_no = "5000"
        log(self.log_box, f"🔍 조건검색 실행: {index} - {name}")
        self.api.ocx.dynamicCall("SendCondition(QString, QString, int, int)", screen_no, name, index, 1)


    @pyqtSlot("QString", "QString", "QString", int, int)
    def on_receive_tr_condition(self, screen_no, codes, condition_name, condition_index, next_):
        if not codes:
            log(self.log_box, f"⚠️ 조건 '{condition_name}' 결과 없음")
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

        log(self.log_box, f"✅ 조건 '{condition_name}' 결과 수신: {len(code_list)}건, 실시간 등록 및 TR 조회 시작")

        
    def set_condition_auto_buy_enabled(self, enabled: bool):
        self.auto_buy_enabled = enabled
        
    @pyqtSlot("int", "QString")
    def on_condition_loaded(self, ret, msg):
        if ret == 1:
            log(self.log_box, "✅ 조건식 로드 완료")
            self.initialize_condition_dropdown()  # ✅ 수정된 함수 호출
        else:
            log(self.log_box, "❌ 조건식 로드 실패")
            
    def check_schedule_and_apply(self):
        if not self.executor.enabled:
            return

        if not self.schedule_enabled_button.isChecked():
            return

        config = getattr(self, "schedule_config", None)
        if not config or not config.get("enabled"):
            return

        start_time = QTime.fromString(config.get("start_time", "09:00"), "HH:mm")
        end_time = QTime.fromString(config.get("end_time", "15:20"), "HH:mm")
        now = QTime.currentTime()

        # ✅ 매매 시작/종료 시간에 따른 자동 제어
        if start_time <= now < end_time:
            if not self.executor.enabled:
                self.handle_trade_start()
        else:
            if self.executor.enabled:
                self.handle_trade_stop()
            return  # 거래시간 외에는 구간 적용도 스킵

        # ✅ 구간 전략/조건 적용 (현재 시간에 해당하는 구간 1개만 실행)
        blocks = [b for b in config.get("blocks", []) if b.get("enabled")]
        for i in range(len(blocks)):
            curr = blocks[i]
            curr_time = QTime.fromString(curr.get("time", "00:00"), "HH:mm")
            next_time = QTime.fromString(blocks[i+1].get("time", "23:59"), "HH:mm") if i + 1 < len(blocks) else end_time

            if curr_time <= now < next_time:
                # 전략 자동 변경
                if curr.get("strategy") and curr["strategy"] != self.strategy_dropdown.currentText():
                    self.strategy_dropdown.setCurrentText(curr["strategy"])
                    log(self.log_box, f"🧠 전략 자동 변경: {curr['strategy']}")

                # 조건검색 자동 실행
                condition = curr.get("condition", "")
                if condition and ":" in condition:
                    try:
                        index, name = condition.split(":")
                        index = int(index.strip())
                        name = name.strip()

                        # ✅ UI 드롭다운도 동기화
                        self.condition_dropdown.setCurrentText(f"{index}: {name}")

                        self.api.ocx.dynamicCall(
                            "SendCondition(QString, QString, int, int)",
                            "5000", name, index, 1
                        )
                        log(self.log_box, f"🔍 조건검색 자동 실행: {name}")
                    except Exception as e:
                        log(self.log_box, f"❌ 조건검색 실행 실패: {e}")

                break  # ✅ 구간 1개만 실행 후 종료

    def on_receive_real_condition(self, screen_no, code, event_type, condition_name):
        if event_type != "I":
            return

        if not self.condition_auto_buy_checkbox.isChecked():
            return

        # 종목 정보 확보
        name = self.api.get_master_code_name(code)
        price = self.api.get_master_last_price(code)

        # 계좌1 설정 확인
        step = 1
        account = self.executor.get_account_by_step(step)
        buy_conf = self.executor.buy_settings.get("accounts", {}).get("계좌1", {})
        amount = buy_conf.get("amount", 0)
        enabled = buy_conf.get("enabled", False)

        if not enabled or amount <= 0:
            return

        # 중복 매수 방지
        if self.executor.holdings.get(code, {}).get(account, {}).get("qty", 0) > 0:
            log(self.log_box, f"[조건매수 스킵] {code}: 이미 계좌1에서 보유 중")
            return
        if (code, account) in self.executor.pending_buys:
            log(self.log_box, f"[조건매수 스킵] {code}: 체결 대기 중")
            return

        # 매수 실행
        log(self.log_box, f"[조건검색 실시간 매수] {code} / {name} / 현재가 {price:,} / 금액 {amount:,}")
        self.executor.send_buy_order(code, amount, step=step, current_price=price)
        self.executor.pending_buys.add((code, account))

            

    def open_schedule_settings(self):
        strategy_list = [self.strategy_dropdown.itemText(i) for i in range(self.strategy_dropdown.count())]
        condition_list = [self.condition_dropdown.itemText(i) for i in range(self.condition_dropdown.count())]

        # ✅ 이전 스케줄 데이터 전달
        dialog = ScheduleSettingsDialog(strategy_list, condition_list, self.schedule_config if hasattr(self, "schedule_config") else None, self)

        if dialog.exec_() == QDialog.Accepted:
            self.schedule_config = dialog.get_schedule_data()

            # ✅ 저장된 이름 적용
            if hasattr(dialog, "last_saved_name") and dialog.last_saved_name:
                name = dialog.last_saved_name
                self.refresh_schedule_dropdown_main(selected_name=name)
                log(self.log_box, f"✅ 스케줄 '{name}' 설정이 적용됨")
            else:
                log(self.log_box, f"✅ 스케줄 설정이 적용됨")
            
    def setup_menu_actions(self):
        self.actionOpenScheduleDialog = self.findChild(QAction, "actionOpenScheduleDialog")
        if self.actionOpenScheduleDialog:
            self.actionOpenScheduleDialog.triggered.connect(self.open_schedule_settings)

        self.actionOpenConfigDialog = self.findChild(QAction, "actionOpenConfigDialog")
        if self.actionOpenConfigDialog:
            self.actionOpenConfigDialog.triggered.connect(self.open_config_dialog)


    def open_config_dialog(self, first_time=False):
        dialog = ConfigDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config = dialog.get_config()
            save_user_config(self.config)
            log(self.log_box, "✅ 설정 저장 완료")

            self.executor.set_accounts([
                self.config.get("account1", ""),
                self.config.get("account2", ""),
                self.config.get("account3", ""),
                self.config.get("account4", ""),
            ])

            if first_time:
                QMessageBox.information(self, "설정 완료", "✅ 설정이 완료되었습니다. 프로그램을 시작할 수 있습니다.")
                
    def refresh_schedule_dropdown_main(self, selected_name=None):
        if not hasattr(self, "schedule_dropdown_main"):
            return

        self.schedule_dropdown_main.blockSignals(True)
        self.schedule_dropdown_main.clear()

        if os.path.exists("schedules"):
            names = [f[:-5] for f in os.listdir("schedules") if f.endswith(".json")]
            self.schedule_dropdown_main.addItems(sorted(names))

            if selected_name and selected_name in names:
                self.schedule_dropdown_main.setCurrentText(selected_name)

        self.schedule_dropdown_main.blockSignals(False)



    def load_selected_schedule(self, name):
        path = f"schedules/{name}.json"
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.schedule_config = config
        log(self.log_box, f"✅ 스케줄 '{name}' 로드됨: {self.schedule_config}")
            
    def on_schedule_toggle(self, checked):
        if checked:
            name = self.schedule_dropdown_main.currentText()
            self.load_selected_schedule(name)  # ✅ 먼저 설정을 불러오고
            config = getattr(self, "schedule_config", None)
            if config:
                self.check_schedule_and_apply()  # ✅ 이제 적용 실행
                log(self.log_box, f"✅ 스케줄 설정 적용됨: {config}")
            else:
                log(self.log_box, "⚠️ 선택한 스케줄을 찾을 수 없습니다.")
        else:
            log(self.log_box, "🛑 스케줄 적용 해제됨")
            
            
    def toggle_condition_auto_buy(self, checked):
        if checked:
            log(self.log_box, "✅ 조건검색 자동매수 활성화됨")
        else:
            log(self.log_box, "🛑 조건검색 자동매수 비활성화됨")


            
__all__ = ["AutoTradeUI"]
