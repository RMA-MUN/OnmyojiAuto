from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
    PushButton, PrimaryPushButton, CardWidget, StrongBodyLabel,
    BodyLabel, LineEdit, SpinBox, FluentIcon as FIF
)


class MultiInstancePage(QWidget):
    launch_finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("multi_instance_page")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        multi_card = CardWidget(self)
        card_layout = QVBoxLayout(multi_card)
        card_layout.setSpacing(12)

        header = StrongBodyLabel("多开管理")
        header_hbox = QHBoxLayout()
        header_hbox.addStretch()
        header_hbox.addWidget(header)
        header_hbox.addStretch()
        card_layout.addLayout(header_hbox)

        exe_label = BodyLabel("游戏路径")
        card_layout.addWidget(exe_label)

        self.exe_path_input = LineEdit(self)
        self.exe_path_input.setPlaceholderText("请选择游戏exe文件路径...")
        self.browse_btn = PushButton(FIF.FOLDER, "浏览", self)
        self.browse_btn.clicked.connect(self._on_browse_clicked)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(self.exe_path_input, 1)
        path_row.addWidget(self.browse_btn)
        card_layout.addLayout(path_row)

        card_layout.addSpacing(4)

        config_row = QHBoxLayout()
        config_row.setSpacing(24)

        count_col = QVBoxLayout()
        count_col.setSpacing(6)
        count_label = BodyLabel("启动数量")
        self.launch_count = SpinBox(self)
        self.launch_count.setRange(1, 20)
        self.launch_count.setValue(1)
        self.launch_count.setFixedWidth(200)
        count_col.addWidget(count_label)
        count_col.addWidget(self.launch_count)

        interval_col = QVBoxLayout()
        interval_col.setSpacing(6)
        interval_label = BodyLabel("启动间隔(秒)")
        self.launch_interval = SpinBox(self)
        self.launch_interval.setRange(0, 120)
        self.launch_interval.setValue(5)
        self.launch_interval.setFixedWidth(200)
        interval_col.addWidget(interval_label)
        interval_col.addWidget(self.launch_interval)

        config_row.addLayout(count_col)
        config_row.addStretch()
        config_row.addLayout(interval_col)
        card_layout.addLayout(config_row)

        interval_hint = BodyLabel("推荐5秒，小于3秒可能导致启动不完全")
        hint_hbox = QHBoxLayout()
        hint_hbox.addStretch()
        hint_hbox.addWidget(interval_hint)
        hint_hbox.addStretch()
        card_layout.addLayout(hint_hbox)

        btn_hbox = QHBoxLayout()
        btn_hbox.addStretch()
        self.launch_btn = PrimaryPushButton(FIF.PLAY, "启动实例", self)
        self.launch_btn.setMinimumHeight(36)
        self.launch_btn.setFixedWidth(220)
        btn_hbox.addWidget(self.launch_btn)
        btn_hbox.addStretch()
        card_layout.addSpacing(8)
        card_layout.addLayout(btn_hbox)

        main_layout.addWidget(multi_card)
        main_layout.addStretch()

    def _on_browse_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏exe文件", "",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if file_path:
            self.exe_path_input.setText(file_path)

    def get_exe_path(self) -> str:
        return self.exe_path_input.text()

    def get_launch_count(self) -> int:
        return self.launch_count.value()

    def get_launch_interval(self) -> int:
        return self.launch_interval.value()
