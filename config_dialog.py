from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout, QCheckBox

class ConfigDialog(QDialog):
    def __init__(self, saved_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(400, 400)

        layout = QVBoxLayout()
        form = QFormLayout()

        self.account_inputs = [QLineEdit() for _ in range(4)]
        for i, inp in enumerate(self.account_inputs):
            form.addRow(f"계좌{i+1} 번호", inp)

        self.sheet_id_input = QLineEdit()
        self.sheet_name_input = QLineEdit()
        self.telegram_token_input = QLineEdit()
        self.telegram_chat_id_input = QLineEdit()

        form.addRow("Google Sheet ID", self.sheet_id_input)
        form.addRow("시트 이름", self.sheet_name_input)
        form.addRow("텔레그램 Bot Token", self.telegram_token_input)
        form.addRow("Telegram Chat ID", self.telegram_chat_id_input)
        self.debug_checkbox = QCheckBox("일반 디버그 로그")
        self.verbose_buy_checkbox = QCheckBox("매수 평가 상세 로그")
        self.verbose_sell_checkbox = QCheckBox("매도 평가 상세 로그")
        form.addRow("디버그 모드", self.debug_checkbox)
        form.addRow("매수 평가 상세 로그", self.verbose_buy_checkbox)
        form.addRow("매도 평가 상세 로그", self.verbose_sell_checkbox)

        layout.addLayout(form)
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)
        self.setLayout(layout)

        if saved_config:
            self.load_config(saved_config)

    def load_config(self, config):
        for i in range(4):
            self.account_inputs[i].setText(config.get(f"account{i+1}", ""))
        self.sheet_id_input.setText(config.get("sheet_id", ""))
        self.sheet_name_input.setText(config.get("sheet_name", ""))
        self.telegram_token_input.setText(config.get("telegram_token", ""))
        self.telegram_chat_id_input.setText(config.get("telegram_chat_id", ""))
        self.debug_checkbox.setChecked(config.get("show_debug", False))
        self.verbose_buy_checkbox.setChecked(config.get("show_verbose_buy", False))
        self.verbose_sell_checkbox.setChecked(config.get("show_verbose_sell", False))

    def get_config(self):
        config = {
            f"account{i+1}": self.account_inputs[i].text().strip() for i in range(4)
        }
        config.update({
            "sheet_id": self.sheet_id_input.text().strip(),
            "sheet_name": self.sheet_name_input.text().strip(),
            "telegram_token": self.telegram_token_input.text().strip(),
            "telegram_chat_id": self.telegram_chat_id_input.text().strip(),
            "show_debug": self.debug_checkbox.isChecked(),
            "show_verbose_buy": self.verbose_buy_checkbox.isChecked(),
            "show_verbose_sell": self.verbose_sell_checkbox.isChecked(),
        })
        return config
