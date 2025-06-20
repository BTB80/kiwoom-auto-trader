from modules.tr_codes import (
    TR_DEPOSIT_INFO,
    TR_HOLDINGS_INFO,
    TR_TODAY_PROFIT,
    TR_ORDER_HISTORY,
)
from datetime import datetime
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt
from modules.google_writer import append_trade_log
from log_manager import to_int  # 유틸 함수만 import


def handle_account_tr_data(manager, scr_no, rq_name, tr_code, record_name, prev_next):
    logger = getattr(manager, "logger", None)

    if rq_name == TR_DEPOSIT_INFO:
        raw = manager.api.get_comm_data(tr_code, rq_name, 0, "예수금").replace(",", "")
        manager.deposit = to_int(raw)
        logger.log(f"💰 예수금: {manager.deposit:,} 원")

        available_raw = manager.api.get_comm_data(tr_code, rq_name, 0, "주문가능금액").replace(",", "")
        manager.available_cash = to_int(available_raw)
        logger.log(f"🧾 주문가능금액: {manager.available_cash:,} 원")

        manager.request_holdings(manager.current_account)

    elif rq_name == TR_HOLDINGS_INFO:
        logger.log("🔍 보유종목조회 TR 수신 시작")
        count = manager.api.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name)
        logger.log(f"📊 수신된 종목 수: {count}")

        account = manager.scr_account_map.get(scr_no, manager.current_account)
        if logger.debug_enabled:
            logger.debug(f"[보유 TR] scr_no={scr_no} → account={account}")

        for index in range(count):
            name = manager.api.get_comm_data(tr_code, rq_name, index, "종목명").strip()
            raw_code = manager.api.get_comm_data(tr_code, rq_name, index, "종목번호").strip()
            code = raw_code[1:] if raw_code.startswith("A") else raw_code
            if not name or not code:
                continue

            qty = to_int(manager.api.get_comm_data(tr_code, rq_name, index, "보유수량"))
            buy = to_int(manager.api.get_comm_data(tr_code, rq_name, index, "매입가"))
            price = to_int(manager.api.get_comm_data(tr_code, rq_name, index, "현재가"))
            prev_price = to_int(manager.api.get_comm_data(tr_code, rq_name, index, "전일종가"))

            # Calculate rate of change (등락률)
            rate_of_change = ((price - prev_price) / prev_price * 100) if prev_price else 0.0

            logger.debug(f"[잔고TR] {code} / qty={qty} / buy={buy} / current={price} / prev={prev_price} / rate_of_change={rate_of_change:.2f}%")
            
            # Store the data along with rate_of_change
            manager.holdings.setdefault(code, {})[account] = {
                "name": name,
                "qty": qty,
                "buy_price": buy,
                "current": price,
                "rate_of_change": rate_of_change  # Store rate of change here
            }

            if hasattr(manager, "executor") and manager.executor:
                manager.executor.basic_info_map[code] = {
                    "name": name,
                    "price": price
                }

            logger.debug(f"➡️ {code} {name} (계좌: {account}) qty:{qty} buy:{buy} price:{price} rate_of_change:{rate_of_change:.2f}%")

        manager.refresh_holdings_ui()

        if manager.holdings:
            manager.start_realtime_updates()
        else:
            logger.log("⚠️ 실시간 등록 생략: holdings 없음")

        if hasattr(manager, "executor") and manager.executor:
            manager.executor.holdings = {}
            for code, acc_dict in manager.holdings.items():
                manager.executor.holdings[code] = {}
                for acc, info in acc_dict.items():
                    buy_price = info.get("buy_price", 0)
                    qty = info.get("qty", 0)
                    logger.debug(f"[executor.holdings 저장] {code} / 계좌:{acc} / qty={qty} / buy_price={buy_price}")
                    manager.executor.holdings[code][acc] = {
                        "buy_price": buy_price,
                        "qty": qty
                    }

            manager.executor.reconstruct_buy_history_from_holdings()
            manager.executor.reconstruct_sell_history_from_holdings()
            logger.log("🔁 매수/매도 단계 자동 복원 완료")

        if hasattr(manager, "handle_holdings_response_complete"):
            manager.handle_holdings_response_complete(account)


    elif rq_name == TR_TODAY_PROFIT:
        count = manager.api.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name)
        logger.debug(f"📥 실현손익 수신 / 반복건수: {count}")

        for i in range(count):
            name = manager.api.get_comm_data(tr_code, rq_name, i, "종목명").strip()
            profit_str = manager.api.get_comm_data(tr_code, rq_name, i, "실현손익").strip().replace(",", "")
            try:
                profit = int(profit_str)
                manager.today_profit += profit
                logger.debug(f"🧾 {name} 실현손익: {profit}")
            except ValueError:
                logger.debug(f"⚠️ 실현손익 변환 실패: '{profit_str}'")

        if prev_next == "0":
            logger.log(f"💰 [총합 실현손익] {manager.today_profit:,} 원")
            manager.update_ui()

    elif rq_name == TR_ORDER_HISTORY:
        table = manager.trade_log_table
        count = manager.api.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name)
        logger.log(f"📥 체결내역 수신: {count}건")

        account = manager.last_requested_order_account

        for i in range(count):
            name = manager.api.get_comm_data(tr_code, rq_name, i, "종목명").strip()
            code = manager.api.get_comm_data(tr_code, rq_name, i, "종목코드").strip()
            time = manager.api.get_comm_data(tr_code, rq_name, i, "주문시간").strip()
            order_type = manager.api.get_comm_data(tr_code, rq_name, i, "주문구분").strip()
            qty = int(manager.api.get_comm_data(tr_code, rq_name, i, "체결수량").replace(",", "") or 0)
            price = int(manager.api.get_comm_data(tr_code, rq_name, i, "체결단가").replace(",", "") or 0)
            amount = qty * price
            fee = int(manager.api.get_comm_data(tr_code, rq_name, i, "수수료").replace(",", "") or 0)
            tax = int(manager.api.get_comm_data(tr_code, rq_name, i, "세금").replace(",", "") or 0)
            settled = amount - fee - tax

            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = f"{time[:2]}:{time[2:4]}:{time[4:6]}" if len(time) == 6 else time

            key = f"{date_str}_{time_str}_{account}_{code}"
            if key in manager.existing_trade_keys:
                logger.log(f"⏭️ 중복 기록 생략됨: {key}")
                continue

            row = [
                date_str, time_str, account, code, name, order_type,
                qty, price, amount, fee, tax, settled, "복원", ""
            ]

            if table:
                row_pos = table.rowCount()
                table.insertRow(row_pos)
                for col, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter if col in [0, 1, 2, 3, 5, 12] else Qt.AlignRight)
                    table.setItem(row_pos, col, item)

            manager.existing_trade_keys.add(key)

    elif rq_name == "추정자산조회":
        raw = manager.api.get_comm_data(tr_code, rq_name, 0, "추정예탁자산").strip()
        manager.estimated_asset = to_int(raw.replace(",", ""))
        logger.log(f"📈 [추정예탁자산] {manager.estimated_asset:,} 원")
        manager.update_ui()
