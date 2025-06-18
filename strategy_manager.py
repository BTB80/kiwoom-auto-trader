
import os
import json
from utils import log, SHOW_DEBUG  # utils에서 불러온다고 가정
STRATEGY_FOLDER = "strategies"

def save_current_strategy(strategy_name, buy_settings, sell_settings):
    if not strategy_name:
        print("❌ 전략 이름을 입력하세요.")
        return

    os.makedirs(STRATEGY_FOLDER, exist_ok=True)
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")

    strategy_data = {
        "buy": buy_settings,
        "sell": sell_settings
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategy_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 전략 '{strategy_name}' 저장 완료: {path}")


def load_strategy(strategy_name, log_box=None):
    """
    전략 이름에 해당하는 JSON 파일을 불러와 딕셔너리로 반환합니다.
    log_box가 주어지면 UI 로그창에 메시지를 출력합니다.
    """
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")
    if not os.path.exists(path):
        msg = f"❌ 전략 파일이 존재하지 않습니다: {path}"
        if log_box:
            log(log_box, msg)
        elif SHOW_DEBUG:
            print(msg)
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    msg = f"📥 전략 '{strategy_name}' 로드 완료"
    if log_box:
        log(log_box, msg)
    elif SHOW_DEBUG:
        print(msg)

    return data


def delete_strategy(strategy_name):
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")
    if os.path.exists(path):
        os.remove(path)
        print(f"🗑 전략 '{strategy_name}' 삭제 완료: {path}")
        return True
    else:
        print(f"⚠️ 전략 파일이 존재하지 않음: {path}")
        return False