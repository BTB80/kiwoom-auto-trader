import os
import json

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".autotrade_config.json")

def load_user_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            # ❌ 더 이상 사용하지 않는 키 제거
            config.pop("show_debug", None)
            config.pop("show_verbose_buy", None)
            config.pop("show_verbose_sell", None)
            return config
    return {}

def save_user_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
