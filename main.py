from PyQt5.QtWidgets import QApplication
import sys
import ui_main

from ui_main import AutoTradeUI
print("🚀 AutoTradeUI 클래스 불러오기 성공")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoTradeUI()
    window.show()
    sys.exit(app.exec_())
