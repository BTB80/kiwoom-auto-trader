from PyQt5.QtWidgets import QGroupBox, QGridLayout, QLabel, QComboBox, QPushButton, QLineEdit, QWidget,QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator

def format_with_commas(line_edit, text):
    raw = text.replace(",", "")
    if raw.isdigit():
        formatted = f"{int(raw):,}"
        # 커서 위치 유지
        cursor_pos = line_edit.cursorPosition()
        line_edit.blockSignals(True)
        line_edit.setText(formatted)
        # 커서가 맨 뒤로 가는 현상 보완
        offset = len(formatted) - len(text)
        line_edit.setCursorPosition(max(0, cursor_pos + offset))
        line_edit.blockSignals(False)


def create_buy_settings_groupbox():
    container = QWidget()
    layout = QGridLayout()

    # ✅ 매수종류 드롭다운 + 1주 매수모드 + 조건검색 자동매수 버튼 추가
    order_type_combo = QComboBox()
    order_type_combo.addItems(["시장가", "지정가"])
    order_type_combo.setObjectName("buy_order_type_combo")

    one_unit_checkbox = QPushButton("1주 매수 모드 (테스트)")
    one_unit_checkbox.setCheckable(True)
    one_unit_checkbox.setObjectName("buy_test_mode_checkbox")

    top_row = QHBoxLayout()
    top_row.addWidget(QLabel("매수종류"))
    top_row.addWidget(order_type_combo)
    top_row.addWidget(one_unit_checkbox)


    layout.addLayout(top_row, 0, 0, 1, 5)  # 하나의 줄로 5칸 차지

    # ✅ 계좌별 입력 구성
    for i in range(4):
        row = i + 1
        account_button = QPushButton(f"계좌{i+1}")
        account_button.setCheckable(True)
        account_button.setObjectName(f"buy_account_button_{i+1}")

        amount_input = QLineEdit()
        amount_input.setPlaceholderText("금액 예: 10,000")
        amount_input.setObjectName(f"buy_amount_input_{i+1}")
        amount_input.setAlignment(Qt.AlignRight)
        amount_input.setValidator(QIntValidator(0, 999999999))
        amount_input.textChanged.connect(lambda text, inp=amount_input: format_with_commas(inp, text))

        drop_rate_input = QLineEdit()
        drop_rate_input.setPlaceholderText("하락률 예: -2.0")
        drop_rate_input.setObjectName(f"buy_drop_input_{i+1}")
        drop_rate_input.setAlignment(Qt.AlignRight)

        layout.addWidget(account_button, row, 0)
        layout.addWidget(QLabel("금액"), row, 1)
        layout.addWidget(amount_input, row, 2)
        layout.addWidget(QLabel("하락률(%)"), row, 3)
        layout.addWidget(drop_rate_input, row, 4)

    container.setLayout(layout)
    return container

def create_sell_settings_groupbox():
    container = QWidget()
    layout = QGridLayout()

    # 매도종류 드롭다운
    order_type_combo = QComboBox()
    order_type_combo.addItems(["시장가", "지정가"])
    order_type_combo.setObjectName("sell_order_type_combo")  # ✅

    layout.addWidget(QLabel("매도종류"), 0, 0)
    layout.addWidget(order_type_combo, 0, 1)

    # 계좌별 매도 설정
    for i in range(4):
        row = i + 1
        account_button = QPushButton(f"계좌{i+1}")
        account_button.setCheckable(True)
        account_button.setObjectName(f"sell_account_button_{i+1}")  # ✅

        ratio_input = QLineEdit()
        ratio_input.setPlaceholderText("비율 예: 100")
        ratio_input.setObjectName(f"sell_ratio_input_{i+1}")  # ✅
        ratio_input.setAlignment(Qt.AlignRight)

        profit_rate_input = QLineEdit()
        profit_rate_input.setPlaceholderText("수익률 예: 3.0")
        profit_rate_input.setObjectName(f"sell_profit_input_{i+1}")  # ✅
        profit_rate_input.setAlignment(Qt.AlignRight)

        layout.addWidget(account_button, row, 0)
        layout.addWidget(QLabel("비율(%)"), row, 1)
        layout.addWidget(ratio_input, row, 2)
        layout.addWidget(QLabel("수익률(%)"), row, 3)
        layout.addWidget(profit_rate_input, row, 4)

    container.setLayout(layout)
    return container

# def register_chejan_handler(api, handler):
#     api.ocx.OnReceiveChejanData.connect(handler)  # ✅ 올바른 시그널 이름
#     print("✅ 체결 이벤트 핸들러 연결 완료")