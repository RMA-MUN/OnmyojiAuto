from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QFileDialog
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
        card_layout.addWidget(header)

        config_widget = QWidget()
        config_layout = QHBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(12)

        exe_label = BodyLabel("游戏路径:")
        self.exe_path_input = LineEdit(self)
        self.exe_path_input.setPlaceholderText("请选择游戏exe文件路径...")
        self.browse_btn = PushButton(FIF.FOLDER, "浏览", self)
        self.browse_btn.clicked.connect(self._on_browse_clicked)

        count_label = BodyLabel("启动数量:")
        self.launch_count = SpinBox(self)
        self.launch_count.setRange(1, 20)
        self.launch_count.setValue(1)

        interval_label = BodyLabel("启动间隔(秒):")
        self.launch_interval = SpinBox(self)
        self.launch_interval.setRange(0, 120)
        self.launch_interval.setValue(5)

        config_layout.addWidget(exe_label)
        config_layout.addWidget(self.exe_path_input, 1)
        config_layout.addWidget(self.browse_btn)
        config_layout.addSpacing(16)
        config_layout.addWidget(count_label)
        config_layout.addWidget(self.launch_count)
        config_layout.addSpacing(16)
        config_layout.addWidget(interval_label)
        config_layout.addWidget(self.launch_interval)

        card_layout.addWidget(config_widget)

        self.launch_btn = PrimaryPushButton(FIF.PLAY, "启动实例", self)
        self.launch_btn.setMinimumHeight(32)
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.launch_btn.setSizePolicy(size_policy)

        card_layout.addWidget(self.launch_btn)
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
