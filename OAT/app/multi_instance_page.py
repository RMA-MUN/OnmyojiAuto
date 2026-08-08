import os
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSizePolicy, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    PushButton, PrimaryPushButton, CardWidget, StrongBodyLabel,
    BodyLabel, LineEdit, SpinBox, FluentIcon as FIF
)


class MultiInstancePage(QWidget):
    close_instance = QtCore.pyqtSignal(int)
    instance_added = QtCore.pyqtSignal(int, int, str, str)
    instance_updated = QtCore.pyqtSignal(int, object, object)
    instances_cleared = QtCore.pyqtSignal()
    launch_finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("multi_instance_page")
        self._instance_id_to_row: dict[int, int] = {}
        self._setup_ui()
        self.instance_added.connect(self.add_instance)
        self.instance_updated.connect(self.update_instance)
        self.instances_cleared.connect(self.clear_instances)

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

        config_layout.addWidget(exe_label)
        config_layout.addWidget(self.exe_path_input, 1)
        config_layout.addWidget(self.browse_btn)
        config_layout.addSpacing(16)
        config_layout.addWidget(count_label)
        config_layout.addWidget(self.launch_count)

        interval_label = BodyLabel("启动间隔(秒):")
        self.launch_interval = SpinBox(self)
        self.launch_interval.setRange(0, 120)
        self.launch_interval.setValue(5)
        config_layout.addWidget(interval_label)
        config_layout.addWidget(self.launch_interval)

        card_layout.addWidget(config_widget)

        buttons_widget = QWidget()
        buttons_layout = QGridLayout(buttons_widget)
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.launch_btn = PrimaryPushButton(FIF.PLAY, "启动实例", self)
        self.close_selected_btn = PushButton(FIF.CLOSE, "关闭选中", self)
        self.close_all_btn = PushButton(FIF.DELETE, "全部关闭", self)
        self.refresh_btn = PushButton(FIF.UPDATE, "刷新列表", self)

        for btn in [self.launch_btn, self.close_selected_btn,
                     self.close_all_btn, self.refresh_btn]:
            btn.setMinimumHeight(32)
            size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setSizePolicy(size_policy)

        buttons_layout.addWidget(self.launch_btn, 0, 0)
        buttons_layout.addWidget(self.close_selected_btn, 0, 1)
        buttons_layout.addWidget(self.close_all_btn, 0, 2)
        buttons_layout.addWidget(self.refresh_btn, 0, 3)

        for i in range(4):
            buttons_layout.setColumnStretch(i, 1)

        card_layout.addWidget(buttons_widget)

        self.instance_table = QtWidgets.QTableWidget(self)
        self.instance_table.setColumnCount(6)
        self.instance_table.setHorizontalHeaderLabels(
            ["选择", "实例ID", "进程PID", "状态", "启动时间", "操作"]
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.instance_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.instance_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.instance_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table_sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.instance_table.setSizePolicy(table_sp)
        self.instance_table.setMinimumHeight(300)
        self.instance_table.setAlternatingRowColors(True)

        card_layout.addWidget(self.instance_table)
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

    def add_instance(self, instance_id: int, pid: int = 0, status: str = "运行中", launched_at: str = ""):
        row = self.instance_table.rowCount()
        self.instance_table.insertRow(row)

        self._instance_id_to_row[instance_id] = row

        checkbox_item = QtWidgets.QTableWidgetItem()
        checkbox_item.setFlags(checkbox_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.instance_table.setItem(row, 0, checkbox_item)

        self.instance_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(instance_id)))
        self.instance_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(pid) if pid else "-"))
        self.instance_table.setItem(row, 3, QtWidgets.QTableWidgetItem(status))
        self.instance_table.setItem(row, 4, QtWidgets.QTableWidgetItem(launched_at))

        close_btn = PushButton(FIF.CLOSE, "关闭", self)
        close_btn.setMinimumHeight(28)
        close_btn.clicked.connect(lambda checked, iid=instance_id: self._on_close_instance(iid))
        self.instance_table.setCellWidget(row, 5, close_btn)

    def update_instance(self, instance_id: int, pid: int = None, status: str = None, launched_at: str = None):
        row = self._instance_id_to_row.get(instance_id)
        if row is None:
            return

        if pid is not None:
            pid_item = self.instance_table.item(row, 2)
            if pid_item:
                pid_item.setText(str(pid) if pid else "-")

        if status is not None:
            status_item = self.instance_table.item(row, 3)
            if status_item:
                status_item.setText(status)

        if launched_at is not None:
            time_item = self.instance_table.item(row, 4)
            if time_item:
                time_item.setText(launched_at)

    def remove_instance(self, instance_id: int):
        row = self._instance_id_to_row.get(instance_id)
        if row is not None:
            self.instance_table.removeRow(row)
            del self._instance_id_to_row[instance_id]
            self._rebuild_id_map()

    def _rebuild_id_map(self):
        self._instance_id_to_row.clear()
        for row in range(self.instance_table.rowCount()):
            id_item = self.instance_table.item(row, 1)
            if id_item:
                instance_id = int(id_item.text())
                self._instance_id_to_row[instance_id] = row

    def clear_instances(self):
        self.instance_table.setRowCount(0)
        self._instance_id_to_row.clear()

    def get_selected_instance_ids(self) -> list[int]:
        ids = []
        for row in range(self.instance_table.rowCount()):
            checkbox_item = self.instance_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == QtCore.Qt.CheckState.Checked:
                id_item = self.instance_table.item(row, 1)
                if id_item:
                    ids.append(int(id_item.text()))
        return ids

    def _on_close_instance(self, instance_id: int):
        self.close_instance.emit(instance_id)
