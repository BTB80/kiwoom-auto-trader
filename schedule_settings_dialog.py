# schedule_settings_dialog.py
import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,QLineEdit,
    QTimeEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import QTime

class ScheduleSettingsDialog(QDialog):
    def __init__(self, strategy_list=None, condition_list=None, saved_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏰ 스케줄 설정")
        self.setFixedSize(600, 300)
        self.last_saved_name = None 
        layout = QVBoxLayout()

        # 🔸 저장/불러오기 UI 구성
        select_layout = QHBoxLayout()
        self.schedule_dropdown = QComboBox()
        self.schedule_name_input = QLineEdit()
        self.schedule_name_input.setPlaceholderText("스케줄 이름 입력")
        self.schedule_save_button = QPushButton("저장")
        self.schedule_delete_button = QPushButton("삭제")
        select_layout.addWidget(self.schedule_dropdown)
        select_layout.addWidget(self.schedule_name_input)
        select_layout.addWidget(self.schedule_save_button)
        select_layout.addWidget(self.schedule_delete_button)
        layout.addLayout(select_layout)

        # ✅ 매매 시작/종료 시간 입력
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("매매 시작"))
        self.trade_start_time = QTimeEdit()
        self.trade_start_time.setDisplayFormat("HH:mm")
        self.trade_start_time.setTime(QTime(9, 0))
        time_layout.addWidget(self.trade_start_time)

        time_layout.addWidget(QLabel("매매 종료"))
        self.trade_end_time = QTimeEdit()
        self.trade_end_time.setDisplayFormat("HH:mm")
        self.trade_end_time.setTime(QTime(15, 20))
        time_layout.addWidget(self.trade_end_time)

        layout.addLayout(time_layout)

        # ✅ 스케줄 전체 활성화 체크박스
        self.global_checkbox = QCheckBox("스케줄 전체 활성화")
        layout.addWidget(self.global_checkbox)

        # ✅ 구간 입력 3개
        self.blocks = []
        for i in range(3):
            block_layout = QHBoxLayout()
            enabled = QCheckBox(f"구간 {i+1}")
            time_edit = QTimeEdit()
            time_edit.setDisplayFormat("HH:mm")

            strategy_combo = QComboBox()
            condition_combo = QComboBox()

            # ✅ 폰트 크기 조절 (작게)
            font = condition_combo.font()
            font.setPointSize(8)
            condition_combo.setFont(font)

            # ✅ 툴팁 자동 업데이트
            condition_combo.setToolTip("")
            condition_combo.currentTextChanged.connect(lambda text, combo=condition_combo: combo.setToolTip(text))


            if strategy_list:
                strategy_combo.addItems(strategy_list)
            if condition_list:
                condition_combo.addItems(condition_list)

            block_layout.addWidget(enabled)
            block_layout.addWidget(QLabel("시작시간"))
            block_layout.addWidget(time_edit)
            block_layout.addWidget(QLabel("전략"))
            block_layout.addWidget(strategy_combo)
            block_layout.addWidget(QLabel("조건검색"))
            block_layout.addWidget(condition_combo)

            layout.addLayout(block_layout)

            self.blocks.append({
                "enabled": enabled,
                "time": time_edit,
                "strategy": strategy_combo,
                "condition": condition_combo
            })

        # ✅ 저장 버튼
        save_button = QPushButton("저장 후 닫기")
        save_button.clicked.connect(self.save_and_close)  # 👈 여기로 연결
        layout.addWidget(save_button)

        self.setLayout(layout)

        # ✅ 위젯 연결
        self.schedule_save_button.clicked.connect(self.save_schedule)
        self.schedule_delete_button.clicked.connect(self.delete_schedule)
        self.schedule_dropdown.currentTextChanged.connect(self.load_schedule)

        self.refresh_schedule_dropdown()
        if saved_config:
            self.apply_schedule_data(saved_config)
            
    def save_and_close(self):
        self.save_schedule()  # 저장 먼저 수행

        # 🔁 전략설정 박스 드롭다운도 즉시 반영
        if self.parent():
            if hasattr(self.parent(), "refresh_schedule_dropdown_main"):
                self.parent().refresh_schedule_dropdown_main(selected_name=self.last_saved_name)

            # ✅ 전략설정 드롭다운 값도 적용
            if hasattr(self.parent(), "schedule_dropdown_main"):
                dropdown = self.parent().schedule_dropdown_main
                if self.last_saved_name:
                    index = dropdown.findText(self.last_saved_name)
                    if index != -1:
                        dropdown.setCurrentIndex(index)

        self.accept()  # 다이얼로그 닫기


        
    def refresh_schedule_dropdown(self):
        self.schedule_dropdown.clear()
        if os.path.exists("schedules"):
            files = [f[:-5] for f in os.listdir("schedules") if f.endswith(".json")]
            self.schedule_dropdown.addItems(files)

    def save_schedule(self):
        name = self.schedule_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "경고", "스케줄 이름을 입력하세요.")
            return

        # 🔒 저장
        os.makedirs("schedules", exist_ok=True)
        with open(f"schedules/{name}.json", "w", encoding="utf-8") as f:
            json.dump(self.get_schedule_data(), f, ensure_ascii=False, indent=2)

        # 🔄 현재 창의 드롭다운 갱신 및 선택
        self.refresh_schedule_dropdown()
        self.schedule_dropdown.setCurrentText(name)

        # 🔄 메인 창 드롭다운 동기화
        if self.parent() and hasattr(self.parent(), "refresh_schedule_dropdown_main"):
            self.parent().refresh_schedule_dropdown_main(selected_name=name)
            
        self.last_saved_name = name
        # 🟢 메시지
        QMessageBox.information(self, "저장 완료", f"'{name}' 스케줄이 저장되었습니다.")



    def load_schedule(self, name):
        path = f"schedules/{name}.json"
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.schedule_name_input.setText(name)  # ✅ 선택한 이름을 입력창에도 반영
        self.apply_schedule_data(config)


    def delete_schedule(self):
        name = self.schedule_dropdown.currentText()
        path = f"schedules/{name}.json"
        if os.path.exists(path):
            os.remove(path)
            self.refresh_schedule_dropdown()

    def apply_schedule_data(self, config):
        self.global_checkbox.setChecked(config.get("enabled", False))
        self.trade_start_time.setTime(QTime.fromString(config.get("start_time", "09:00"), "HH:mm"))
        self.trade_end_time.setTime(QTime.fromString(config.get("end_time", "15:20"), "HH:mm"))

        for i, block in enumerate(config.get("blocks", [])):
            if i < len(self.blocks):
                self.blocks[i]["enabled"].setChecked(block.get("enabled", False))
                self.blocks[i]["time"].setTime(QTime.fromString(block.get("time", "00:00"), "HH:mm"))
                self.blocks[i]["strategy"].setCurrentText(block.get("strategy", ""))
                self.blocks[i]["condition"].setCurrentText(block.get("condition", ""))

    def get_schedule_data(self):
        return {
            "enabled": self.global_checkbox.isChecked(),
            "start_time": self.trade_start_time.time().toString("HH:mm"),
            "end_time": self.trade_end_time.time().toString("HH:mm"),
            "blocks": [
                {
                    "enabled": block["enabled"].isChecked(),
                    "time": block["time"].time().toString("HH:mm"),
                    "strategy": block["strategy"].currentText(),
                    "condition": block["condition"].currentText()
                } for block in self.blocks
            ]
        }
        
    def accept(self):
        super().accept()
        if self.parent() and hasattr(self.parent(), "refresh_schedule_dropdown_main"):
            self.parent().refresh_schedule_dropdown_main()