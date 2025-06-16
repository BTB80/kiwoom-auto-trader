from PyQt5.QtWidgets import QApplication,QSizePolicy
from PyQt5.QtCore import Qt
import sys
from ui_main import AutoTradeUI
from utils import update_debug_flags
from config_manager import load_user_config


if __name__ == "__main__":
    # 고해상도 디스플레이 대응
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    update_debug_flags(load_user_config())
    app = QApplication(sys.argv)
    window = AutoTradeUI()

    # 고정 해상도 기반 실행 (중앙 위치로 실행 가능)
    window.setMinimumSize(1200, 650)
    window.resize(1200, 650)         # 기본 크기
    window.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.show()

    sys.exit(app.exec_())
