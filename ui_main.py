import os, json  # 상단에 추가
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot,QDateTime
from PyQt5.QtCore import QTime
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QPushButton, QComboBox, QTextEdit,QDialog,
    QVBoxLayout, QHBoxLayout, QSizePolicy,QLineEdit,QButtonGroup, QTabWidget, QWidget,QApplication,QCheckBox
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
# from buy_sell_settings_groupbox import register_chejan_handler
from PyQt5.QtCore import QTimer
from modules.telegram_utils import configure_telegram
from modules.all_holdings_popup import AllHoldingsPopup
from modules.tr_codes import SCR_REALTIME_CONDITION
from log_manager import LogManager


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
        self.logger = LogManager(None, self.config)  # log_box는 아직 없음

        self.setup_fonts()
        self.setup_clock()
        self.setup_buttons()
        self.setup_strategy_ui()
        self.setup_schedule_timer()
        self.setup_tabs()
        self.setup_config()
        self.setup_tables()
        self.setup_log()  # 이때 self.logger.set_log_box 호출됨
        self.setup_account_sections()
        self.setup_misc_ui()
        self.setup_menu_actions()
        self.refresh_schedule_dropdown_main()
        self.connect_signals()

        self.received_balance_accounts = set()
        self.trade_start_button.setEnabled(False)

    def setup_fonts(self):
        self.setFont(QFont("맑은 고딕", 8))

    def setup_clock(self):
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(CLOCK_LABEL_STYLE)
        self.clock_label.setAlignment(Qt.AlignCenter)
        self.update_clock()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.topBar = self.findChild(QHBoxLayout, "topBar")
        self.topBar.addWidget(self.clock_label)

    def setup_buttons(self):
        button_names = [
            "login_button", "trade_start_button", "trade_stop_button",
            "strategy_save_button", "strategy_delete_button", "view_all_holdings_button",
            "schedule_enabled_button", "schedule_button", "config_button"
        ]
        for name in button_names:
            btn = self.findChild(QPushButton, name)
            if btn:
                btn.setStyleSheet(UNIFORM_BUTTON_STYLE)
                btn.setFixedWidth(100)

    def setup_strategy_ui(self):
        self.strategy_dropdown = self.findChild(QComboBox, "strategy_dropdown")
        self.strategy_name_input = self.findChild(QLineEdit, "strategy_name_input")
        self.strategy_name_input.setMaximumWidth(250)
        self.load_existing_strategies()

    def setup_schedule_timer(self):
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedule_and_apply)
        self.schedule_timer.start(1000 * 30)

    def setup_tabs(self):
        self.account_tab = self.findChild(QTabWidget, "account_tab")
        self.watchlist_tabwidget = self.findChild(QTabWidget, "watchlist_tabwidget")
        tab_font = QFont("맑은 고딕", 10)
        for tab in [self.account_tab, self.watchlist_tabwidget]:
            if tab:
                tab.setStyleSheet(TAB_STYLE)
                tab.tabBar().setFont(tab_font)
        if self.account_tab:
            self.account_tab.setTabText(0, "📊 잔고")
            self.account_tab.setTabText(1, "📦 미체결")
            self.account_tab.setTabText(2, "🧾 매매내역")

    def setup_config(self):
        self.config = load_user_config()

        # ✅ 설정에서 최대보유종목 수 불러오기 (기본값: 20)
        max_holdings_str = self.config.get("max_holdings", "20")
        self.max_holdings_input.setText(max_holdings_str)

        # ✅ LogManager에 설정 반영
        if hasattr(self, "logger"):
            self.logger.update_flags(self.config)

        self.sheet_id = self.config.get("sheet_id", "")
        self.sheet_name = self.config.get("sheet_name", "관심종목")

        token = self.config.get("telegram_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        if token and chat_id:
            configure_telegram(token, chat_id)


    def setup_tables(self):
        self.setup_core_objects()
        self.setup_stock_search_table()
        self.setup_holdings_table()
        self.setup_condition_table()
        self.setup_unsettled_table()
        self.setup_trade_log_table()
        self.setup_table_fonts()

    def setup_log(self):
        self.log_box = self.findChild(QTextEdit, "log_box")
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ✅ log_box 스타일 설정
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)

        # ✅ logger에 log_box 연결
        if hasattr(self, "logger") and self.logger:
            self.logger.set_log_box(self.log_box)

        # ✅ log_label 스타일 및 정렬
        log_label = self.findChild(QLabel, "log_label")
        if log_label:
            log_label.setStyleSheet(LABEL_STYLE)
            log_label.setAlignment(Qt.AlignLeft)

        # ✅ log_box가 속한 레이아웃의 마진 직접 설정
        if self.log_box:
            ancestor = self.log_box.parentWidget()
            while ancestor and not ancestor.layout():
                ancestor = ancestor.parentWidget()

            if ancestor and ancestor.layout():
                ancestor.layout().setContentsMargins(10, 0, 10, 10)  # 좌, 상, 우, 하

        # ✅ 로그 필터 체크박스 설정
        self.debug_checkbox = self.findChild(QCheckBox, "debug_checkbox")
        self.info_checkbox = self.findChild(QCheckBox, "info_checkbox")
        self.trade_checkbox = self.findChild(QCheckBox, "trade_checkbox")

        self.debug_checkbox.setChecked(self.logger.filter_debug)
        self.info_checkbox.setChecked(self.logger.filter_info)
        self.trade_checkbox.setChecked(self.logger.filter_trade)

        self.debug_checkbox.toggled.connect(self.on_debug_filter_changed)
        self.info_checkbox.toggled.connect(self.on_info_filter_changed)
        self.trade_checkbox.toggled.connect(self.on_trade_filter_changed)


    def setup_account_sections(self):
        buy_box = create_buy_settings_groupbox()
        sell_box = create_sell_settings_groupbox()
        self.buy_settings_group.layout().addWidget(buy_box)
        self.sell_settings_group.layout().addWidget(sell_box)

        self.buy_order_type_combo = buy_box.findChild(QComboBox, "buy_order_type_combo")
        self.buy_test_mode_checkbox = buy_box.findChild(QPushButton, "buy_test_mode_checkbox")
        self.buy_account_buttons = [buy_box.findChild(QPushButton, f"buy_account_button_{i+1}") for i in range(4)]
        self.buy_amount_inputs = [buy_box.findChild(QLineEdit, f"buy_amount_input_{i+1}") for i in range(4)]
        self.buy_drop_inputs = [buy_box.findChild(QLineEdit, f"buy_drop_input_{i+1}") for i in range(4)]

        self.sell_order_type_combo = sell_box.findChild(QComboBox, "sell_order_type_combo")
        self.sell_account_buttons = [sell_box.findChild(QPushButton, f"sell_account_button_{i+1}") for i in range(4)]
        self.sell_ratio_inputs = [sell_box.findChild(QLineEdit, f"sell_ratio_input_{i+1}") for i in range(4)]
        self.sell_profit_inputs = [sell_box.findChild(QLineEdit, f"sell_profit_input_{i+1}") for i in range(4)]

        self.max_holdings_input = self.findChild(QLineEdit, "max_holdings_input")
        max_holdings_str = self.config.get("max_holdings", "20")
        self.max_holdings_input.setText(max_holdings_str)
        self.max_holdings_input.setMaximumWidth(40)
        self.max_holdings_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.max_holdings_input.setAlignment(Qt.AlignCenter)
        font_input = self.max_holdings_input.font()
        font_input.setBold(True)
        self.max_holdings_input.setFont(font_input)

        self.setup_account_buttons()
        self.setup_table_styles()

    def setup_misc_ui(self):
        self.watchlist = []

        self.manager.set_ui_elements(
            self.account_combo,
            self.account_info_label,
            self.holdings_table,
            self.log_box,
            self.unsettled_table,
        )
        self.manager.trade_log_table = self.trade_log_table
        self.manager.stock_search_table = self.stock_search_table

        # logger 함수 래핑(필요시)
        self.condition_manager = ConditionManager(self.api, log_fn=lambda msg: self.logger.log(msg))

        self.manager.logger = self.logger
        self.executor.logger = self.logger

        self.api.ocx.OnEventConnect.connect(self.on_login_event)
        self.api.ocx.OnReceiveTrData.connect(self.handle_tr_data)
        self.api.ocx.OnReceiveRealData.connect(self.on_real_data)

        watchlist_label = self.findChild(QLabel, "watchlist_label")
        if watchlist_label:
            watchlist_label.setStyleSheet(LABEL_STYLE)
            watchlist_label.setAlignment(Qt.AlignLeft)

        tab_watchlist = self.findChild(QWidget, "tab_watchlist")
        if tab_watchlist:
            layout = tab_watchlist.layout()
            if layout:
                layout.setContentsMargins(10, 0, 10, 10)

        layout = self.findChild(QHBoxLayout, "topInfoLayout")
        if layout:
            layout.setStretch(0, 1)
            layout.setStretch(1, 1)
            layout.setStretch(2, 3)
            layout.setStretch(3, 3)

        self.condition_dropdown = self.findChild(QComboBox, "condition_dropdown")
        self.condition_search_button = self.findChild(QPushButton, "condition_search_button")
        self.is_fullscreen = False


    def setup_core_objects(self):
        self.api = KiwoomAPI(logger=self.logger)
        self.basic_info_map = {}

        self.manager = AccountManager(self.api, self.config)
        self.manager.ui = self
        self.manager.logger = self.logger  # ✅ logger 주입

        self.executor = AutoTradeExecutor(self.api)
        self.executor.set_manager(self.manager)
        self.executor.set_basic_info_map(self.basic_info_map)
        self.executor.logger = self.logger  # ✅ logger 주입

        self.manager.set_executor(self.executor)
        self.manager.basic_info_map = self.basic_info_map

        # ✅ 컨트롤러 초기화 (람다 제거)
        from modules.watchlist_controller import WatchlistController
        from modules.condition_controller import ConditionSearchController

        self.watchlist_controller = WatchlistController(self, self.api, log_fn=self.logger.log)
        self.condition_controller = ConditionSearchController(self, self.api, log_fn=self.logger.log)
        self.condition_controller.logger = self.logger  # ✅ 필요 시 내부에서 self.logger 사용 가능하게

        # ✅ 실시간 조건검색 이벤트 연결
        self.api.ocx.OnReceiveRealCondition.connect(self.condition_controller.on_receive_real_condition)

       
    def connect_signals(self):
        self.login_button.clicked.connect(self.login)
        self.trade_start_button.clicked.connect(self.handle_trade_start)
        self.trade_stop_button.clicked.connect(self.handle_trade_stop)
        self.buy_test_mode_checkbox.toggled.connect(self.on_test_mode_toggled)
        self.view_all_holdings_button.clicked.connect(self.show_all_holdings_popup)
        self.watchlist_button.clicked.connect(
            lambda: self.watchlist_controller.load_watchlist_from_google(self.sheet_id, self.sheet_name)
        )

        if self.schedule_button:
            self.schedule_button.setStyleSheet(UNIFORM_BUTTON_STYLE)
            self.schedule_button.clicked.connect(self.open_schedule_settings)

        if self.config_button:
            self.config_button.setStyleSheet(UNIFORM_BUTTON_STYLE)
            self.config_button.clicked.connect(lambda: self.open_config_dialog(first_time=False))

        self.schedule_enabled_button.setCheckable(True)
        self.schedule_enabled_button.toggled.connect(self.on_schedule_toggle)

        self.condition_auto_buy_checkbox.setChecked(False)  # 상태 확실히 False로 설정
        self.condition_auto_buy_checkbox.toggled.connect(self.toggle_condition_auto_buy)

        self.schedule_dropdown_main.currentTextChanged.connect(self.load_selected_schedule)
        self.strategy_save_button.clicked.connect(self.handle_save_strategy)
        self.strategy_delete_button.clicked.connect(self.handle_delete_strategy)
        self.strategy_dropdown.currentTextChanged.connect(self.handle_strategy_selected)

        self.account_combo.currentTextChanged.connect(self.manager.request_deposit_info)
        self.account_combo.currentTextChanged.connect(self.handle_account_selected)

        self.api.ocx.OnReceiveTrCondition.connect(self.condition_controller.on_receive_tr_condition)
        self.api.ocx.OnReceiveConditionVer.connect(self.condition_controller.on_condition_loaded)
        self.condition_search_button.clicked.connect(self.condition_controller.handle_search)
        self.api.ocx.OnReceiveRealCondition.connect(self.condition_controller.on_receive_real_condition)

    def setup_buttons(self):
        # 일반 버튼들: 스타일만 적용 (시그널 연결은 connect_signals에서)
        button_names = [
            "config_button", "schedule_button", "login_button",
            "trade_start_button", "trade_stop_button",
            "view_all_holdings_button", "watchlist_button",
            "strategy_save_button", "strategy_delete_button",
            "condition_search_button"
        ]

        for name in button_names:
            btn = self.findChild(QPushButton, name)
            if btn:
                btn.setStyleSheet(UNIFORM_BUTTON_STYLE)
                btn.setFixedWidth(100)

        # 체크 가능한 버튼: 체크 설정만 (시그널은 connect_signals에서)
        toggle_names = ["schedule_enabled_button", "condition_auto_buy_checkbox"]
        for name in toggle_names:
            btn = self.findChild(QPushButton, name)
            if btn:
                btn.setCheckable(True)

    def setup_holdings_table(self):
        # holdings_table 위젯을 찾는 부분
        self.holdings_table = self.findChild(QTableWidget, "holdings_table")
        if self.holdings_table:
            # 열 수를 10으로 설정 (기존 9개에서 1개 추가)
            self.holdings_table.setColumnCount(10)

            # 열 제목을 10개로 설정 (등락률(%) 추가)
            self.holdings_table.setHorizontalHeaderLabels([
                "종목명", "보유수량", "매입가", "현재가","등락률(%)", "목표단가", 
                "수익률(%)",  "매입금액", "평가금액", "평가손익"
            ])  # 새로운 열 제목으로 '등락률(%)'을 추가

            # 편집 불가 설정
            self.holdings_table.setEditTriggers(QTableWidget.NoEditTriggers)

            # 열 크기 자동 조정
            self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.holdings_table.verticalHeader().setDefaultSectionSize(30)
            self.holdings_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # holdings_table을 manager에 연결
            self.manager.holdings_table = self.holdings_table
        else:
            self.logger.log("❌ 'holdings_table' 위젯을 찾을 수 없습니다.")


    def setup_stock_search_table(self):
        self.stock_search_table = self.findChild(QTableWidget, "stock_search_table")
        if self.stock_search_table:
            self.stock_search_table.setColumnCount(7)
            self.stock_search_table.setHorizontalHeaderLabels([
                "종목코드", "종목명", "전일종가", "현재가", "등락률", "상태", "매수"
            ])
            self.stock_search_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.stock_search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.stock_search_table.verticalHeader().setDefaultSectionSize(30)
            self.stock_search_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            self.manager.stock_search_table = self.stock_search_table
        else:
            self.logger.log("❌ 'stock_search_table' 위젯을 찾을 수 없습니다.")

    def setup_condition_table(self):
        self.condition_table = self.findChild(QTableWidget, "condition_table")
        if self.condition_table:
            self.condition_table.setColumnCount(7)
            self.condition_table.setHorizontalHeaderLabels([
                "종목코드", "종목명", "전일종가", "현재가", "등락률", "조건식명", "매수"
            ])
            self.condition_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.condition_table.verticalHeader().setDefaultSectionSize(28)

            self.manager.condition_table = self.condition_table  # 필요시
        else:
            self.logger.log("❌ 'condition_table' 위젯을 찾을 수 없습니다.")
   
    def setup_unsettled_table(self):
        self.unsettled_table = self.findChild(QTableWidget, "unsettled_table")
        if self.unsettled_table:
            self.unsettled_table.setColumnCount(7)
            self.unsettled_table.setHorizontalHeaderLabels([
                "주문번호", "종목명", "구분", "주문수량", "체결수량", "잔량", "가격"
            ])
            self.unsettled_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.unsettled_table.verticalHeader().setDefaultSectionSize(28)

            self.manager.unsettled_table = self.unsettled_table  # 필요시
        else:
            self.logger.log("❌ 'unsettled_table' 위젯을 찾을 수 없습니다.")

    def setup_trade_log_table(self):
        self.trade_log_table = self.findChild(QTableWidget, "trade_log_table")
        if self.trade_log_table:
            self.trade_log_table.setColumnCount(14)
            self.trade_log_table.setHorizontalHeaderLabels([
                "일자", "시간", "계좌", "종목코드", "종목명", "구분",
                "수량", "가격", "체결금액", "수수료", "세금", "정산금액", "전략명", "비고"
            ])
            self.trade_log_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.trade_log_table.verticalHeader().setDefaultSectionSize(28)

            self.manager.trade_log_table = self.trade_log_table  # 필요시
        else:
            self.logger.log("❌ 'trade_log_table' 위젯을 찾을 수 없습니다.")

    def setup_table_fonts(self):
        font_header = QFont("맑은 고딕", 8)
        for table in [
            self.holdings_table,
            self.stock_search_table,
            self.condition_table,
            self.unsettled_table,
            self.trade_log_table
        ]:
            if table:
                table.horizontalHeader().setFont(font_header)
                
    def setup_table_styles(self):
        font_header = QFont("맑은 고딕", 9)  # 헤더: 굵고 크게
        font_body = QFont("맑은 고딕", 10)   # 본문: 일반 크기

        tables = [
            self.holdings_table,
            self.stock_search_table,
            self.condition_table,
            self.unsettled_table,
            self.trade_log_table,
        ]

        for table in tables:
            if table is None:
                continue

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

        # 로그창 스타일은 그대로 유지
        if hasattr(self, "log_box") and self.log_box:
            self.log_box.setStyleSheet("""
                QTextEdit {
                    background-color: black;
                    color: white;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                }
            """)
    def on_test_mode_toggled(self, checked):
        if hasattr(self, "executor"):
            self.executor.test_mode = checked
        status = "✅ [1주 매수 테스트 모드] 활성화됨" if checked else "🛑 [1주 매수 테스트 모드] 비활성화됨"
        self.logger.log(status)

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
    
    @pyqtSlot()
    def login(self):
        self.logger.log("🔑 로그인 요청 중...")
        self.api.connect()

    def on_login_event(self, err_code):
        self.manager.handle_login_event(err_code)

        if err_code != 0:
            self.logger.log(f"❌ 로그인 실패: 코드 {err_code}")
            return

        self.logger.log("✅ 로그인 성공")

        # ✅ 체결 이벤트 핸들러 등록
        self.api.register_chejan_handler(self.executor.handle_chejan_data)
        print("✅ 체결 이벤트 핸들러 등록 완료")

        # ✅ 계좌 목록 세팅
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

            def after_holdings_loaded():
                self.on_holdings_loaded()
                self.handle_account_selected(first_account)
                self.manager.request_today_profit(first_account)
                self.manager.request_estimated_asset(first_account)

            # ✅ 전체 잔고 요청 시작
            self.manager.request_all_holdings(accounts, on_complete=after_holdings_loaded)

            # ✅ 기본 전략 자동 로드
            if not hasattr(self, 'strategy_loaded') or not self.strategy_loaded:
                if self.strategy_dropdown and self.strategy_dropdown.findText("기본") != -1:
                    self.strategy_dropdown.setCurrentText("기본")
                    self.handle_strategy_selected("기본")
                    self.strategy_loaded = True  # 이미 로드된 전략은 다시 로드하지 않음

        # ✅ 조건식 로드 (한 번만 호출되도록 수정)
        if not hasattr(self, 'condition_loaded') or not self.condition_loaded:
            self.api.ocx.dynamicCall("GetConditionLoad()")
            self.condition_loaded = True  # 조건식 로드 완료 처리
            self.logger.log("✅ 조건식 로드 완료")  # 로그 추가



           

    def start_auto_trade(self):
        if not getattr(self.manager, "holdings_loaded", False):
            QMessageBox.warning(self, "⏳ 잔고 수신 중", "보유 종목 정보를 아직 수신되지 않았습니다.")
            return

        # ✅ 현재 선택된 전략명 확인
        selected_strategy = self.strategy_dropdown.currentText()
        if not selected_strategy:
            QMessageBox.warning(self, "❌ 전략 없음", "자동매매를 시작하기 전에 전략을 선택하세요.")
            return

        # ✅ 이미 같은 전략이 적용되어 있다면 중복 적용 방지
        if hasattr(self.executor, "current_strategy_name") and self.executor.current_strategy_name == selected_strategy:
            self.logger.log(f"⚠️ 전략 '{selected_strategy}'은 이미 적용되어 있습니다.")
        else:
            self.handle_strategy_selected(selected_strategy)

        if not self.executor.buy_settings.get("accounts"):
            QMessageBox.warning(self, "⚠️ 전략 설정 없음", "선택한 전략에 매수 조건이 없습니다.")
            return

        self.logger.log("✅ 자동매매 준비 중 → 상태 복원 중...")

        # ✅ 체결 대기 상태 초기화
        self.logger.log(f"🧹 pending_buys 초기화 전: {len(self.executor.pending_buys)}건")
        self.executor.pending_buys.clear()
        self.logger.log("🧹 체결대기 종목 초기화 완료")

        # ✅ 보유 상태 복원
        self.executor.holdings = self.manager.holdings
        self.executor.reconstruct_buy_history_from_holdings()
        self.executor.reconstruct_sell_history_from_holdings()
        self.logger.log("🔁 매수/매도 단계 자동 복원 완료")

        # ✅ 전략명 누락 방지
        if not hasattr(self.executor, "current_strategy_name") or self.executor.current_strategy_name == "전략미지정":
            self.logger.log("❗ 전략명이 적용되지 않았습니다. 전략을 다시 선택해 주세요.")
            return

        # ✅ 계좌가 하나 이상 있다면 명시적으로 첫 계좌 선택
        if self.executor.accounts:
            first_account = self.executor.accounts[0]
            self.account_combo.setCurrentText(first_account)  # 콤보박스 변경 → 잔고 로딩 유도
            self.manager.current_account = first_account

        # ✅ 자동매매 즉시 활성화
        self.executor.enabled = True
        self.logger.log("✅ 자동매매 즉시 활성화 완료")



    def enable_auto_trade(self):
        self.executor.enabled = True
        self.logger.log("✅ 자동매매 활성화 완료 (보유 종목 복원 이후)")

    def handle_trade_start(self):
        if not getattr(self.manager, "holdings_loaded", False):
            self.logger.log("❌ 매매 시작 실패: 잔고 수신이 아직 완료되지 않았습니다.")
            return

        self.start_auto_trade()
        self.trade_start_button.setText("매매중")
        self.trade_start_button.setStyleSheet(UNIFORM_BUTTON_STYLE + TRADING_STYLE)
        self.trade_stop_button.setStyleSheet(UNIFORM_BUTTON_STYLE)
        
    def stop_auto_trade(self):
        self.executor.enabled = False
        self.logger.log("🛑 자동매매 종료")
        
    def handle_trade_stop(self):
        self.stop_auto_trade()  # ✅ 기존 로직 호출
        self.trade_start_button .setText("매매 시작")
        self.trade_start_button .setStyleSheet(UNIFORM_BUTTON_STYLE)
        self.trade_stop_button.setStyleSheet(UNIFORM_BUTTON_STYLE)

    @pyqtSlot("QString", "QString", "QString")
    def on_real_data(self, code, real_type, data):
        try:
            if real_type == "주식체결":
                price_str = self.api.ocx.dynamicCall("GetCommRealData(QString, int)", code, 10).strip()

                if not price_str:
                    self.logger.log(f"⚠️ 실시간 현재가 없음, TR로 보완 요청: {code}")
                    self.request_price_tr_for_code(code)
                    return

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
                            self.logger.log(f"⚠️ 조건검색 테이블 갱신 실패: {code} / {e}")
                        break  # 조건검색 테이블에서 해당 종목만 업데이트

                # ✅ 자동매매가 켜진 경우만 평가
                if self.executor.enabled:
                    self.executor.evaluate_buy(code, price)
                    self.executor.evaluate_sell(code, price)

        except Exception as e:
            self.logger.log(f"❌ 실시간 데이터 처리 오류: {e}")

    def handle_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next):
        if rq_name.startswith("기본정보_"):
            handle_watchlist_tr_data(self.api, self.stock_search_table, self.basic_info_map, rq_name, tr_code)
        else:
            self.manager.handle_tr_data(scr_no, rq_name, tr_code, record_name, prev_next)

    def is_market_closed(self):
        now = datetime.datetime.now()
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute
        return weekday >= 5 or (hour > 15 or (hour == 15 and minute >= 30))
                   
    def manual_buy_clicked(self, code):
        account = self.executor.get_account_by_step(1)  # 계좌1

        # ✅ buy_settings
        buy_conf = self.executor.buy_settings.get("accounts", {}).get("계좌1", {})
        amount = buy_conf.get("amount", 0)

        # ✅ 드롭다운에서 주문 유형 가져오기
        order_type_ui = self.buy_order_type_combo.currentText()  # "시장가" 또는 "지정가"
        if order_type_ui == "시장가":
            s_order_type = 1
            s_hoga = "03"
        else:
            s_order_type = 1
            s_hoga = "00"

        # ✅ 현재가 및 종목명
        info = self.basic_info_map.get(code, {})
        current_price = info.get("price") or info.get("current_price", 0)
        name = info.get("name", code)

        self.logger.debug(f"[🛠 수동매수 진입] {code} / 현재가: {current_price}, 금액: {amount}, 이름: {name}")

        if current_price == 0:
            self.logger.log(f"❌ {code} 매수 실패: 현재가 없음 (TR 미도달 또는 실시간 미반영)")
            return
        if amount == 0:
            self.logger.log(f"❌ {code} 매수 실패: 전략 설정 금액 없음")
            return

        # ✅ 매수 확인창 메시지
        confirm = QMessageBox.question(
            self.window(),
            "매수 확인",
            f"[{code} - {name}]\n현재가 {current_price:,}원에\n"
            f"{'1주' if self.executor.test_mode else f'{amount:,}원'} **{order_type_ui}** 매수 진행할까요?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            # ✅ 수량 결정
            if self.executor.test_mode:
                qty = 1
                self.logger.log(f"[🧪 1주 테스트모드] 수동매수: {code} / 계좌: {account} / 1주 매수 실행")
            else:
                qty = max(int(amount // current_price), 1)

            s_rqname = f"수동매수:{code}"
            s_screen = "9999"
            s_account = account
            s_price = 0 if s_hoga == "03" else int(current_price)  # 시장가이면 가격 0

            if self.logger.debug_enabled:
                self.logger.debug(f"📡 SendOrder 호출됨:\n"
                                f"  📄 rqname      = {s_rqname}\n"
                                f"  🖥 screen_no   = {s_screen}\n"
                                f"  💳 acc_no      = {s_account}\n"
                                f"  🔁 order_type  = {s_order_type} ({order_type_ui})\n"
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
            self.logger.log(f"🛒 수동매수: {code} | {qty}주 | {order_type_ui} | 계좌: {s_account}")

            # ✅ 상태 갱신
            if hasattr(self, "stock_search_table"):
                update_watchlist_status(self.stock_search_table, code, "⏳ 체결 대기")

            # ✅ 잔고 갱신 요청
            if hasattr(self.manager, "request_holdings"):
                self.manager.request_holdings(s_account)



    def handle_strategy_selected(self, strategy_name):
        strategy = load_strategy(strategy_name, self.logger)  # 🟢 logger로 변경
        if not strategy:
            return
        self.strategy_name_input.setText(strategy_name)

        self.set_buy_settings_to_ui(strategy["buy"])
        self.set_sell_settings_to_ui(strategy["sell"])

        # ✅ executor가 존재할 때만 설정 업데이트
        if hasattr(self, "executor") and self.executor:
            self.executor.update_settings(strategy)
            self.executor.test_mode = strategy.get("buy", {}).get("test_mode", False)  # ✅ 추가
        else:
            self.logger.log("⚠️ 자동매매 실행기가 아직 초기화되지 않았습니다.")

    def handle_save_strategy(self):
        strategy_name = self.strategy_name_input.text().strip()
        if not strategy_name:
            self.logger.log("❌ 전략 이름을 입력하세요.")
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

        self.logger.log(f"✅ 전략 '{strategy_name}' 저장 완료")

        # ✅ 저장한 전략을 현재 자동매매에 즉시 반영
        if hasattr(self, 'executor'):
            self.executor.update_settings({
                "buy": buy_settings,
                "sell": sell_settings
            })
            self.executor.test_mode = buy_settings.get("test_mode", False)
            self.logger.log(f"🔁 전략 '{strategy_name}' 자동매매에 즉시 반영됨")
            
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
            self.logger.log("❌ 삭제할 전략을 선택하세요.")
            return

        if delete_strategy(strategy_name):
            # 드롭다운에서 제거
            index = self.strategy_dropdown.findText(strategy_name)
            if index >= 0:
                self.strategy_dropdown.removeItem(index)

            # 입력 필드 비우기
            self.strategy_name_input.setText("")
            self.logger.log(f"🗑 전략 '{strategy_name}' 삭제됨")
        else:
            self.logger.log(f"⚠️ 전략 '{strategy_name}' 삭제 실패")

    def show_all_holdings_popup(self):
        if not hasattr(self, 'accounts') or not self.accounts:
            self.logger.log("❗ 로그인 후 이용 가능합니다.")
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
                # ✅ 전략 자동 변경 (UI + 실행기 모두 반영)
                target_strategy = curr.get("strategy", "").strip()
                if target_strategy and target_strategy != self.strategy_dropdown.currentText():
                    self.strategy_dropdown.setCurrentText(target_strategy)
                    self.handle_strategy_selected(target_strategy)  # ✅ 전략 적용
                    self.logger.log(f"🧠 전략 자동 변경: {target_strategy}")

                # ✅ 조건검색 자동 실행
                condition = curr.get("condition", "")
                if condition and ":" in condition:
                    try:
                        index, name = condition.split(":")
                        index = int(index.strip())
                        name = name.strip()

                        self.condition_dropdown.setCurrentText(f"{index}: {name}")

                        self.api.ocx.dynamicCall(
                            "SendCondition(QString, QString, int, int)",
                            SCR_REALTIME_CONDITION, name, index, 1
                        )
                        self.logger.log(f"🔍 조건검색 자동 실행: {name}")
                    except Exception as e:
                        self.logger.log(f"❌ 조건검색 실행 실패: {e}")

                break  # ✅ 현재 구간만 실행

    def open_schedule_settings(self):
        strategy_list = [self.strategy_dropdown.itemText(i) for i in range(self.strategy_dropdown.count())]
        condition_list = [self.condition_dropdown.itemText(i) for i in range(self.condition_dropdown.count())]

        dialog = ScheduleSettingsDialog(strategy_list, condition_list, self.schedule_config if hasattr(self, "schedule_config") else None, self)

        current_schedule_name = self.schedule_dropdown_main.currentText()
        if current_schedule_name:
            dialog.set_selected_schedule(current_schedule_name)

        if dialog.exec_() == QDialog.Accepted:
            self.schedule_config = dialog.get_schedule_data()

            # ✅ 저장된 이름 적용
            if hasattr(dialog, "last_saved_name") and dialog.last_saved_name:
                name = dialog.last_saved_name
                self.refresh_schedule_dropdown_main(selected_name=name)
                self.logger.log(f"✅ 스케줄 '{name}' 설정이 적용됨")
            else:
                self.logger.log(f"✅ 스케줄 설정이 적용됨")
            
    def setup_menu_actions(self):
        self.actionOpenScheduleDialog = self.findChild(QAction, "actionOpenScheduleDialog")
        if self.actionOpenScheduleDialog:
            self.actionOpenScheduleDialog.triggered.connect(self.open_schedule_settings)

        self.actionOpenConfigDialog = self.findChild(QAction, "actionOpenConfigDialog")
        if self.actionOpenConfigDialog:
            self.actionOpenConfigDialog.triggered.connect(self.open_config_dialog)
         
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

        # ✔️ 적용 여부 판단해서 로그 분기
        if getattr(self, "schedule_enabled_button", None) and self.schedule_enabled_button.isChecked():
            self.logger.log(f"✅ 스케줄 '{name}' 로드됨 및 적용 준비됨: {self.schedule_config}")
        else:
            self.logger.log(f"📂 스케줄 '{name}' 불러옴 (적용은 스케줄 토글 ON 시 실행됨)")

    def on_schedule_toggle(self, checked):
        if checked:
            name = self.schedule_dropdown_main.currentText()
            self.load_selected_schedule(name)
            config = getattr(self, "schedule_config", None)
            if config:
                self.check_schedule_and_apply()
                self.logger.log(f"✅ 스케줄 '{name}' 선택됨 → 자동매매에 적용 완료됨")
            else:
                self.logger.log(f"⚠️ 스케줄 '{name}'을 불러올 수 없습니다.")
        else:
            self.logger.log("🛑 스케줄 적용 해제됨")

    def toggle_condition_auto_buy(self, checked):
        if hasattr(self.executor, "condition_auto_buy"):
            self.executor.condition_auto_buy = checked
            status = "✅ 조건검색 자동매수 활성화됨" if checked else "🛑 조건검색 자동매수 비활성화됨"
            self.logger.log(status)
        else:
            self.logger.log("⚠️ Executor가 초기화되지 않았습니다.")

    def open_config_dialog(self, first_time=False):
        dialog = ConfigDialog(self.config, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        self.config = dialog.get_config()
        # ✅ 최대보유종목 수 저장
        self.config["max_holdings"] = self.max_holdings_input.text().strip()
        save_user_config(self.config)
        self.logger.update_flags(self.config)
        self.logger.log("✅ 설정 저장 완료")

        # 새 계좌 리스트 반영
        accounts = [
            self.config.get("account1", ""),
            self.config.get("account2", ""),
            self.config.get("account3", ""),
            self.config.get("account4", ""),
        ]
        self.executor.set_accounts(accounts)

        # UI 콤보박스 갱신
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for acc in accounts:
            if acc:
                self.account_combo.addItem(acc)
        self.account_combo.blockSignals(False)

        # 현재 선택 계좌를 새 계좌 중 첫 번째로 변경 (필요 시)
        if accounts and accounts[0]:
            self.account_combo.setCurrentText(accounts[0])
            self.handle_account_selected(accounts[0])

        # 텔레그램 설정 적용
        token = self.config.get("telegram_token")
        chat_id = self.config.get("telegram_chat_id")
        if token and chat_id:
            configure_telegram(token, chat_id)
            self.logger.log("✅ 텔레그램 설정 적용 완료")
        else:
            self.logger.log("⚠️ 텔레그램 설정이 비어 있음")

        # 구글 시트 설정 적용
        self.sheet_id = self.config.get("sheet_id")
        self.sheet_name = self.config.get("sheet_name", "관심종목")

        if self.sheet_id:
            self.logger.log(f"📄 구글 시트 설정 적용 완료 → ID: {self.sheet_id}, 이름: {self.sheet_name}")
        else:
            self.logger.log("⚠️ 구글 시트 ID가 설정되어 있지 않습니다.")

        if first_time:
            QMessageBox.information(self, "설정 완료", "✅ 설정이 완료되었습니다. 프로그램을 시작할 수 있습니다.")
        else:
            QMessageBox.information(self, "설정 적용됨", "✅ 설정이 저장되었습니다.\n프로그램을 재시작하면 디버그 모드가 적용됩니다.")
            
    def on_debug_filter_changed(self, checked):
        self.logger.filter_debug = checked
        self.logger.apply_filters()

    def on_info_filter_changed(self, checked):
        self.logger.filter_info = checked
        self.logger.apply_filters()

    def on_trade_filter_changed(self, checked):
        self.logger.filter_trade = checked
        self.logger.apply_filters()


__all__ = ["AutoTradeUI"]
