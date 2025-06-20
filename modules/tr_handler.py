from log_manager import to_int, LogManager
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt
from modules.watchlist_view import update_watchlist_price

def handle_watchlist_tr_data(api, table_widget, basic_info_map, rq_name, tr_code, target=None):
    logger = getattr(api.manager, "logger", None) or LogManager()

    try:
        code = rq_name.split("_")[-1]

        # 전일종가 / 현재가 추출
        prev_close_raw = api.get_comm_data(tr_code, rq_name, 0, "전일종가").strip().replace(",", "")
        curr_price_raw = api.get_comm_data(tr_code, rq_name, 0, "현재가").strip().replace(",", "")

        prev_close = to_int(prev_close_raw)
        curr_price = abs(to_int(curr_price_raw))

        # ❗ 전일종가 또는 현재가가 누락되면 재요청 큐에 추가
        if (prev_close_raw == "-" or prev_close == 0 or curr_price == 0):
            logger.log(f"⚠️ {code} 기본정보 누락 (전일종가: {prev_close_raw}, 현재가: {curr_price_raw}) → 재요청 대상")
            if hasattr(api, "manager") and hasattr(api.manager, "retry_watchlist_queue"):
                if code not in api.manager.retry_watchlist_queue:
                    api.manager.retry_watchlist_queue.append(code)
            return

        # 조건검색 전용 처리
        if target == "조건검색":
            name = api.get_master_code_name(code)
            rate = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0.0
            ui = api.manager.ui
            ui.condition_result_data.append([code, name, prev_close, curr_price, rate, ui.current_condition_name])
            return

        # 관심종목 테이블 처리 (default)
        stock_name = ""
        for row in range(table_widget.rowCount()):
            item_code = table_widget.item(row, 0)
            item_name = table_widget.item(row, 1)
            if item_code and item_code.text().strip() == code:
                stock_name = item_name.text().strip() if item_name else ""
                break

        # 기본 정보 저장
        basic_info_map[code] = {
            "prev_price": prev_close,
            "current_price": curr_price,
            "price": curr_price,
        }

        # 전일종가 테이블 반영
        for row in range(table_widget.rowCount()):
            item = table_widget.item(row, 0)
            if item and item.text().strip() == code:
                item_prev = QTableWidgetItem(f"{prev_close:,}")
                item_prev.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table_widget.setItem(row, 2, item_prev)
                break

        # 현재가 반영
        update_watchlist_price(table_widget, basic_info_map, code, curr_price)

        logger.log(f"📘 {code} 전일:{prev_close:,} 현재:{curr_price:,}")

    except Exception as e:
        logger.log(f"❌ 기본정보 TR 처리 오류: {e}")
