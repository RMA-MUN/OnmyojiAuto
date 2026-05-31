from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QSizePolicy, QHeaderView
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    PushButton, PrimaryPushButton, CardWidget, StrongBodyLabel,
    FluentIcon as FIF
)


class SyncPage(QWidget):
    refresh_windows = QtCore.pyqtSignal()
    select_all = QtCore.pyqtSignal()
    invert_selection = QtCore.pyqtSignal()
    set_main_window = QtCore.pyqtSignal()
    set_sub_windows = QtCore.pyqtSignal()
    start_sync = QtCore.pyqtSignal()
    stop_sync = QtCore.pyqtSignal()
    arrange = QtCore.pyqtSignal()
    show_instruction = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sync_page")
        self._setup_ui()

    def _setup_ui(self):
        settings_layout = QVBoxLayout(self)
        settings_layout.setContentsMargins(16, 16, 16, 16)
        settings_layout.setSpacing(16)

        sync_card = CardWidget(self)
        sync_layout = QVBoxLayout(sync_card)
        sync_layout.setSpacing(12)

        header = StrongBodyLabel("同步器")
        sync_layout.addWidget(header)

        buttons_widget = QWidget()
        buttons_layout = QGridLayout(buttons_widget)
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.sync_instruction_btn = PushButton(FIF.HELP, "使用说明")
        self.refresh_windows_btn = PushButton(FIF.UPDATE, "刷新窗口")
        self.select_all_btn = PushButton("全选")
        self.invert_selection_btn = PushButton("反选")
        self.capture_btn = PushButton(FIF.CAMERA, "没什么用的按钮")

        self.set_main_window_btn = PushButton("设为主窗口")
        self.set_sub_windows_btn = PushButton("设为副窗口")
        self.start_sync_btn = PrimaryPushButton(FIF.PLAY, "开始同步")
        self.stop_sync_btn = PushButton(FIF.CLOSE, "停止同步")
        self.arrange_btn = PushButton("窗口排列")

        for btn in [self.sync_instruction_btn, self.refresh_windows_btn,
                     self.select_all_btn, self.invert_selection_btn,
                     self.set_main_window_btn, self.set_sub_windows_btn,
                     self.start_sync_btn, self.stop_sync_btn, self.arrange_btn,
                     self.capture_btn]:
            btn.setMinimumHeight(32)
            size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setSizePolicy(size_policy)

        buttons_layout.addWidget(self.sync_instruction_btn, 0, 0)
        buttons_layout.addWidget(self.refresh_windows_btn, 0, 1)
        buttons_layout.addWidget(self.select_all_btn, 0, 2)
        buttons_layout.addWidget(self.invert_selection_btn, 0, 3)
        buttons_layout.addWidget(self.arrange_btn, 0, 4)

        buttons_layout.addWidget(self.set_main_window_btn, 1, 0)
        buttons_layout.addWidget(self.set_sub_windows_btn, 1, 1)
        buttons_layout.addWidget(self.start_sync_btn, 1, 2)
        buttons_layout.addWidget(self.stop_sync_btn, 1, 3)
        buttons_layout.addWidget(self.capture_btn, 1, 4)

        for i in range(5):
            buttons_layout.setColumnStretch(i, 1)

        sync_layout.addWidget(buttons_widget)

        self.window_table = QtWidgets.QTableWidget(self)
        self.window_table.setColumnCount(4)
        self.window_table.setHorizontalHeaderLabels(["选择", "窗口信息", "窗口句柄", "预览"])
        self.window_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.window_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.window_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.window_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.window_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.window_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive
        )
        table_sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.window_table.setSizePolicy(table_sp)
        self.window_table.setMinimumHeight(300)
        self.window_table.setAlternatingRowColors(True)

        sync_layout.addWidget(self.window_table)
        settings_layout.addWidget(sync_card)
        settings_layout.addStretch()
