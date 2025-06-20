import os
import json
STRATEGY_FOLDER = "strategies"

def save_current_strategy(strategy_name, buy_settings, sell_settings, logger=None):
    if not strategy_name:
        msg = "❌ 전략 이름을 입력하세요."
        print(msg)
        if logger:
            logger.log(msg)
        return

    os.makedirs(STRATEGY_FOLDER, exist_ok=True)
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")

    strategy_data = {
        "buy": buy_settings,
        "sell": sell_settings
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategy_data, f, ensure_ascii=False, indent=2)

    msg = f"✅ 전략 '{strategy_name}' 저장 완료: {path}"
    print(msg)
    if logger:
        logger.log(msg)


def load_strategy(strategy_name, logger=None):
    """
    전략 이름에 해당하는 JSON 파일을 불러와 딕셔너리로 반환합니다.
    logger가 주어지면 로그 출력합니다.
    """
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")
    if not os.path.exists(path):
        msg = f"❌ 전략 파일이 존재하지 않습니다: {path}"
        print(msg)
        if logger and hasattr(logger, "log") and callable(logger.log):
            logger.log(msg)
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    msg = f"📥 전략 '{strategy_name}' 로드 완료"
    print(msg)
    if logger and hasattr(logger, "log") and callable(logger.log):
        logger.log(msg)

    return data


def delete_strategy(strategy_name, logger=None):
    path = os.path.join(STRATEGY_FOLDER, f"{strategy_name}.json")
    if os.path.exists(path):
        os.remove(path)
        msg = f"🗑 전략 '{strategy_name}' 삭제 완료: {path}"
        print(msg)
        if logger:
            logger.log(msg)
        return True
    else:
        msg = f"⚠️ 전략 파일이 존재하지 않음: {path}"
        print(msg)
        if logger:
            logger.log(msg)
        return False
