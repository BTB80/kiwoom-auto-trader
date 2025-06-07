
from functools import partial
from PyQt5.QtCore import Qt
from utils import to_int
from PyQt5.QtWidgets import QTableWidgetItem, QPushButton, QSizePolicy, QHeaderView



def display_watchlist(table_widget, stocks, manual_buy_handler):
    table_widget.setRowCount(0)
    table_widget.setColumnCount(7)
    table_widget.setHorizontalHeaderLabels(["종목코드", "종목명", "전일종가", "현재가", "등락률", "상태", "매수"])

    for row_idx, stock in enumerate(stocks):
        try:
            code, name, tag = stock
        except ValueError:
            code, name = stock
            tag = ""

        table_widget.insertRow(row_idx)

        # 종목코드
        item_code = QTableWidgetItem(code)
        item_code.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 0, item_code)

        # 종목명
        item_name = QTableWidgetItem(name)
        item_name.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 1, item_name)

        # 전일종가
        item_prev = QTableWidgetItem("-")
        item_prev.setTextAlignment(Qt.AlignRight)
        table_widget.setItem(row_idx, 2, item_prev)

        # 현재가
        item_current = QTableWidgetItem("-")
        item_current.setTextAlignment(Qt.AlignRight)
        table_widget.setItem(row_idx, 3, item_current)

        # 등락률
        item_rate = QTableWidgetItem("-")
        item_rate.setTextAlignment(Qt.AlignRight)
        table_widget.setItem(row_idx, 4, item_rate)

        # 상태
        item_status = QTableWidgetItem("")
        item_status.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 5, item_status)

        # 매수 버튼
        buy_button = QPushButton("매수")
        buy_button.clicked.connect(partial(manual_buy_handler, code))
        table_widget.setCellWidget(row_idx, 6, buy_button)

    # ✅ 테이블 전체 크기를 꽉 채우도록 설정
    header = table_widget.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 종목코드
    header.setSectionResizeMode(1, QHeaderView.Stretch)           # 종목명
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 전일종가
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 현재가
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 등락률
    header.setSectionResizeMode(5, QHeaderView.Stretch)           # 상태
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 매수 버튼

    table_widget.resizeRowsToContents()
    table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


def update_watchlist_price(table_widget, basic_info_map, code, current_price):
    for row in range(table_widget.rowCount()):
        if table_widget.item(row, 0).text() == code:
            # ✅ 현재가 (우측 정렬)
            item_price = QTableWidgetItem(f"{current_price:,}")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table_widget.setItem(row, 3, item_price)

            # ✅ 등락률 계산 후 우측 정렬 + 색상 적용
            prev_close_item = table_widget.item(row, 2)
            if prev_close_item:
                try:
                    prev_close = int(prev_close_item.text().replace(",", ""))
                    change = current_price - prev_close
                    rate = (change / prev_close) * 100 if prev_close else 0.0

                    item_rate = QTableWidgetItem(f"{rate:.2f}%")
                    item_rate.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                    # 색상 적용: 빨간색(양수), 파란색(음수), 기본색(0%)
                    if rate > 0:
                        item_rate.setForeground(Qt.red)
                    elif rate < 0:
                        item_rate.setForeground(Qt.blue)

                    table_widget.setItem(row, 4, item_rate)
                except ValueError:
                    error_item = QTableWidgetItem("계산오류")
                    error_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    table_widget.setItem(row, 4, error_item)
            break

def update_watchlist_status(table_widget, code, status):
    for row in range(table_widget.rowCount()):
        item = table_widget.item(row, 0)  # 종목코드 열
        if item and item.text() == code:
            item_status = QTableWidgetItem(status)
            item_status.setTextAlignment(Qt.AlignCenter)  # ✅ 중앙 정렬
            table_widget.setItem(row, 5, item_status)
            break


def display_condition_results(table_widget, results, manual_buy_handler):
    table_widget.setRowCount(0)
    table_widget.setColumnCount(7)
    table_widget.setHorizontalHeaderLabels(["종목코드", "종목명", "전일종가", "현재가", "등락률", "상태", "매수"])

    for row_idx, row_data in enumerate(results):
        if len(row_data) < 6:
            continue

        code, name, prev_price, curr_price, rate, condition_name = row_data

        table_widget.insertRow(row_idx)

        # 종목코드
        item_code = QTableWidgetItem(code)
        item_code.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 0, item_code)

        # 종목명
        item_name = QTableWidgetItem(name)
        item_name.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 1, item_name)

        # 전일종가
        # item_prev = QTableWidgetItem(f"{to_int(prev_price):,}")
        item_prev = QTableWidgetItem(f"{int(prev_price):,}")
        item_prev.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_widget.setItem(row_idx, 2, item_prev)

        # 현재가
        # item_curr = QTableWidgetItem(f"{to_int(curr_price):,}")
        item_curr = QTableWidgetItem(f"{int(curr_price):,}")
        item_curr.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_widget.setItem(row_idx, 3, item_curr)

        # 등락률
        try:
            rate_val = float(rate)
            item_rate = QTableWidgetItem(f"{rate_val:.2f}%")
            item_rate.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if rate_val > 0:
                item_rate.setForeground(Qt.red)
            elif rate_val < 0:
                item_rate.setForeground(Qt.blue)
        except:
            item_rate = QTableWidgetItem("계산불가")
            item_rate.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_widget.setItem(row_idx, 4, item_rate)

        # 상태 (조건식명으로 표시)
        item_status = QTableWidgetItem(condition_name)
        item_status.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row_idx, 5, item_status)

        # 매수 버튼
        buy_button = QPushButton("매수")
        buy_button.clicked.connect(partial(manual_buy_handler, code))
        table_widget.setCellWidget(row_idx, 6, buy_button)

    # ✅ 테이블 크기 자동 맞춤
    header = table_widget.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 종목코드
    header.setSectionResizeMode(1, QHeaderView.Stretch)           # 종목명
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 전일종가
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 현재가
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 등락률
    header.setSectionResizeMode(5, QHeaderView.Stretch)           # 상태(조건식명)
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 매수 버튼

    table_widget.resizeRowsToContents()
    table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
