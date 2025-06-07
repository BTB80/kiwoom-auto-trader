from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt
from functools import partial

class ConditionSearchPopup(QDialog):
    def __init__(self, api, condition_list, on_search_triggered):
        super().__init__()
        self.api = api
        self.setWindowTitle("🔍 조건검색")
        self.resize(800, 600)
        
        self.condition_list = condition_list
        self.on_search_triggered = on_search_triggered
        self.manual_buy_handler = None  # 안전 기본값
        self.condition_auto_buy_enabled = False
        
        layout = QVBoxLayout()

        self.label = QLabel("조건식 선택")
        self.dropdown = QComboBox()
        self.dropdown.addItems(condition_list)

        self.search_button = QPushButton("조건검색 실행")
        self.search_button.clicked.connect(self.handle_search)

        layout.addWidget(self.label)
        layout.addWidget(self.dropdown)
        layout.addWidget(self.search_button)
        
        # self.refresh_button = QPushButton("🔄 가격 갱신")
        # self.refresh_button.clicked.connect(self.refresh)
        # layout.addWidget(self.refresh_button)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["종목코드", "종목명", "전일종가", "현재가", "등락률", "조건식명", "매수"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def set_manual_buy_handler(self, handler):
        self.manual_buy_handler = handler

    def populate_table(self, rows):
        self.table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, cell in enumerate(rows[row_idx]):
                if col_idx == 6 and cell == "매수":
                    button = QPushButton("매수")

                    if self.manual_buy_handler:
                        # partial을 이용해 정확한 코드값을 전달
                        button.clicked.connect(partial(self.manual_buy_handler, row[0]))
                    else:
                        button.setEnabled(False)

                    self.table.setCellWidget(row_idx, 6, button)
                else:
                    item = QTableWidgetItem(str(cell))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, col_idx, item)

    def handle_search(self):
        condition_name = self.dropdown.currentText()
        results = self.on_search_triggered(condition_name)

        if results:
            self.populate_table(results)
            
    def set_table_data(self, rows):
        self.populate_table(rows)

    def handle_manual_buy(self, row_data):
        code = row_data[0]
        if self.manual_buy_handler:
            self.manual_buy_handler(code)
            
    def refresh(self):
        """
        현재 테이블에 있는 종목들의 실시간 가격을 갱신하고,
        조건검색 자동매수 옵션이 켜져 있다면 자동 매수도 수행.
        """
        for row in range(self.table.rowCount()):
            code_item = self.table.item(row, 0)
            prev_item = self.table.item(row, 2)

            if not code_item or not prev_item:
                continue

            code = code_item.text().strip()
            try:
                prev = int(prev_item.text().replace(",", ""))
            except:
                continue

            current = self.api.get_master_last_price(code)
            self.table.setItem(row, 3, QTableWidgetItem(f"{current:,}"))

            rate = ((current - prev) / prev) * 100 if prev else 0
            rate_item = QTableWidgetItem(f"{rate:.2f}%")
            rate_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, rate_item)

            # ✅ 자동매수 체크된 경우 계좌1에 자동 매수 시도
            if self.condition_auto_buy_enabled and self.manual_buy_handler:
                self.manual_buy_handler(code)


    def set_condition_auto_buy_enabled(self, enabled: bool):
        self.condition_auto_buy_enabled = enabled
            
    def refresh_with_prices(self, stock_rows):
        """
        실시간 가격 업데이트용
        :param stock_rows: [ [code, name, prev_price, current_price, rate, cond_name], ... ]
        """
        self.table.setRowCount(len(stock_rows))
        for row, data in enumerate(stock_rows):
            for col in range(6):  # 마지막 열(매수)은 제외
                item = QTableWidgetItem(str(data[col]))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

            buy_btn = QPushButton("매수")
            buy_btn.clicked.connect(lambda _, c=data[0]: self.manual_buy_handler(c))
            self.table.setCellWidget(row, 6, buy_btn)

    def update_price(self, code, current, prev):
        for row in range(self.table.rowCount()):
            code_item = self.table.item(row, 0)
            if code_item and code_item.text() == code:
                self.table.setItem(row, 3, QTableWidgetItem(f"{current:,}"))  # 현재가
                rate = ((current - prev) / prev * 100) if prev else 0
                self.table.setItem(row, 4, QTableWidgetItem(f"{rate:.2f}%"))  # 등락률

                # ✅ 자동매수 조건 확인 후 실행
                if self.condition_auto_buy_enabled and self.manual_buy_handler:
                    self.manual_buy_handler(code)
                break
