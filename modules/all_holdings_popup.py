from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHBoxLayout, QGridLayout, QGroupBox, QHeaderView, QDesktopWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

class AllHoldingsPopup(QDialog):
    def __init__(self, holdings, basic_info_map, account_manager):
        super().__init__()
        self.setWindowTitle("📂 모든 계좌 잔고")

        # 👉 창 크기 적당히 조정
        self.setMinimumSize(800, 500)
        self.resize(1000, 600)
        # 또는 아래처럼 화면 크기 비율로 자동 조정 가능
        # screen = QDesktopWidget().screenGeometry()
        # self.resize(int(screen.width() * 0.7), int(screen.height() * 0.6))

        self.holdings = holdings
        self.basic_info_map = basic_info_map
        self.account_manager = account_manager

        layout = QVBoxLayout()
        self.label = QLabel("📋 계좌별 잔고 내역")
        layout.addWidget(self.label)

        self.tables = []
        accounts = account_manager.get_allowed_accounts()

        tables_layout = QGridLayout()

        for i, account in enumerate(accounts):
            group_box = QGroupBox(account_manager.get_alias_by_account(account))
            group_layout = QVBoxLayout()
            table = QTableWidget()
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels([
                "종목명", "수량", "매입가", "현재가", "수익률 (%)", "매입금액", "평가금액"
            ])
            table.setSortingEnabled(True)

            # 👉 헤더를 테이블에 꽉차게
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            group_layout.addWidget(table)
            group_box.setLayout(group_layout)
            tables_layout.addWidget(group_box, i // 2, i % 2)
            self.tables.append((account, table))

        layout.addLayout(tables_layout)
        self.setLayout(layout)
        self.refresh()

    def refresh(self):
        for account, table in self.tables:
            table.setRowCount(0)
            row_index = 0

            for code, account_data in self.holdings.items():
                if account not in account_data:
                    continue

                info = account_data[account]
                code_with_prefix = "A" + code if not code.startswith("A") else code
                stock_name = self.basic_info_map.get(code, {}).get("name", code)
                current_price = self.basic_info_map.get(code_with_prefix, {}).get("price", info.get("current", 0))

                qty = info.get("qty", 0)
                buy_price = info.get("buy_price", 0)

                profit_rate = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0
                buy_amt = qty * buy_price
                eval_amt = qty * current_price

                name_item = QTableWidgetItem(stock_name)
                qty_item = QTableWidgetItem(f"{qty:,}")
                buy_item = QTableWidgetItem(f"{buy_price:,}")
                current_item = QTableWidgetItem(f"{current_price:,}")
                rate_item = QTableWidgetItem(f"{profit_rate:.2f}")
                buy_amt_item = QTableWidgetItem(f"{buy_amt:,}")
                eval_amt_item = QTableWidgetItem(f"{eval_amt:,}")

                # 정렬 설정
                for item in [name_item]:
                    item.setTextAlignment(Qt.AlignCenter)
                for item in [qty_item, buy_item, current_item, rate_item, buy_amt_item, eval_amt_item]:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # 수익률 색상 표시
                if profit_rate > 0:
                    rate_item.setForeground(QColor("Red"))
                elif profit_rate < 0:
                    rate_item.setForeground(QColor("Blue"))

                table.insertRow(row_index)
                table.setItem(row_index, 0, name_item)
                table.setItem(row_index, 1, qty_item)
                table.setItem(row_index, 2, buy_item)
                table.setItem(row_index, 3, current_item)
                table.setItem(row_index, 4, rate_item)
                table.setItem(row_index, 5, buy_amt_item)
                table.setItem(row_index, 6, eval_amt_item)

                row_index += 1
