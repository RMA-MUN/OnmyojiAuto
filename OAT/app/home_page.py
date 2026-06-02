import os
import json
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout

from qfluentwidgets import (
    ComboBox, SpinBox, CheckBox, RadioButton,
    PushButton, PrimaryPushButton,
    CardWidget, BodyLabel, CaptionLabel, StrongBodyLabel,
    TextBrowser,
    FluentIcon as FIF
)

from OAT.source.mode_config import mode_choice, mode_config

source_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source')
mode_json_path = os.path.join(source_dir, 'mode.json')
mode_config_data = mode_config(mode_json_path) or {}


class HomePage(QWidget):
    mode_changed = QtCore.pyqtSignal(str)
    detect_window = QtCore.pyqtSignal()
    start_challenge = QtCore.pyqtSignal()
    emergency_stop = QtCore.pyqtSignal()
    refresh_window = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("home_page")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)

        self._create_function_area(left_layout)
        self._create_changelog_area(left_layout)
        left_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self._create_log_area(right_layout)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 1)

    def _create_function_area(self, parent_layout):
        function_card = CardWidget(self)
        card_layout = QVBoxLayout(function_card)
        card_layout.setSpacing(12)

        header = StrongBodyLabel("功能")
        card_layout.addWidget(header)

        self.find_mode_combo = ComboBox(self)
        self.find_mode_combo.setPlaceholderText("请选择模式")
        modes = mode_choice(mode_json_path)
        if modes:
            self.find_mode_combo.addItems(modes)
        card_layout.addWidget(self.find_mode_combo)

        self.spinBox = SpinBox(self)
        self.spinBox.setRange(1, 10000)
        self.spinBox.setValue(1)
        spin_label = BodyLabel("请输入要挑战的次数")
        card_layout.addWidget(spin_label)
        card_layout.addWidget(self.spinBox)

        client_label = BodyLabel("选择您的登录客户端")
        card_layout.addWidget(client_label)

        self.client_choose = ComboBox(self)
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        client_path = os.path.join(script_dir, 'tools', 'client.json')
        try:
            with open(client_path, 'r', encoding='utf-8') as f:
                client_info = json.load(f)
                for _, value in client_info['title'].items():
                    self.client_choose.addItem(value)
        except Exception:
            pass
        card_layout.addWidget(self.client_choose)

        self.hidden_window_checkbox = CheckBox("启用后台模式", self)
        self.hidden_window_checkbox.setChecked(True)
        self.hidden_window_checkbox.setToolTip(
            "勾选此项后，游戏窗口可以被其他程序遮挡，程序依然可以正常执行任务"
        )
        card_layout.addWidget(self.hidden_window_checkbox)

        self.soul_land_options = QWidget(self)
        soul_layout = QHBoxLayout(self.soul_land_options)
        soul_layout.setContentsMargins(0, 8, 0, 8)
        soul_layout.setSpacing(20)
        self.soul_land_group = QtWidgets.QButtonGroup(self)
        self.radioButton1 = RadioButton("", self)
        self.radioButton2 = RadioButton("", self)
        self.soul_land_group.addButton(self.radioButton1)
        self.soul_land_group.addButton(self.radioButton2)
        soul_layout.addWidget(self.radioButton1)
        soul_layout.addWidget(self.radioButton2)
        self.soul_land_options.hide()
        card_layout.addWidget(self.soul_land_options)

        button_grid = QGridLayout()
        button_grid.setSpacing(8)

        self.refresh_window_btn = PushButton(FIF.UPDATE, "刷新窗口", self)
        self.window_detect_btn = PushButton(FIF.SEARCH, "窗口检测", self)
        self.start_challenge_btn = PrimaryPushButton(FIF.PLAY, "开始挑战", self)
        self.emergency_stop_btn = PushButton(FIF.CLOSE, "紧急停止", self)

        for btn in [self.refresh_window_btn, self.window_detect_btn,
                     self.start_challenge_btn, self.emergency_stop_btn]:
            btn.setMinimumHeight(36)

        button_grid.addWidget(self.refresh_window_btn, 0, 0)
        button_grid.addWidget(self.window_detect_btn, 0, 1)
        button_grid.addWidget(self.emergency_stop_btn, 1, 0)
        button_grid.addWidget(self.start_challenge_btn, 1, 1)
        card_layout.addLayout(button_grid)

        parent_layout.addWidget(function_card)

    def _create_log_area(self, parent_layout):
        log_card = CardWidget(self)
        log_layout = QVBoxLayout(log_card)

        log_header = StrongBodyLabel("日志")
        log_layout.addWidget(log_header)

        self.textBrowser = TextBrowser(self)
        self.textBrowser.setObjectName("log_browser")
        log_layout.addWidget(self.textBrowser)

        parent_layout.addWidget(log_card)

    def _create_changelog_area(self, parent_layout):
        changelog_card = CardWidget(self)
        changelog_layout = QVBoxLayout(changelog_card)

        changelog_header = StrongBodyLabel("更新日志")
        changelog_layout.addWidget(changelog_header)

        self.textBrowser_2 = TextBrowser(self)
        self.textBrowser_2.setObjectName("changelog_browser")
        font = QtGui.QFont()
        font.setPointSize(12)
        self.textBrowser_2.setFont(font)
        self.textBrowser_2.setHtml(self.get_text())
        changelog_layout.addWidget(self.textBrowser_2)

        parent_layout.addWidget(changelog_card)

    def get_text(self):
        return '''
            <div style="line-height: 1.0; margin: 0; padding: 0;">
                <span style="margin: 0;">1.重构GUI界面，基于Fluent-Widgets实现</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">2.识别实现参考MAA的pipeline</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">3.修复错误引用logger.warning引发的报错</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">4.修复close_game关闭失败但return True的问题</span>
            </div>
        '''

    def reload_modes(self):
        new_config = mode_config(mode_json_path) or {}
        mode_config_data.clear()
        mode_config_data.update(new_config)
        self.find_mode_combo.clear()
        modes = mode_choice(mode_json_path)
        if modes:
            self.find_mode_combo.addItems(modes)

    def on_mode_selected(self, index):
        self.soul_land_options.hide()
        self.soul_land_group.setExclusive(False)
        self.radioButton1.setChecked(False)
        self.radioButton2.setChecked(False)
        self.soul_land_group.setExclusive(True)

        if not mode_config_data or index < 0 or index >= self.find_mode_combo.count():
            return

        mode_name = self.find_mode_combo.currentText()
        mode_data = mode_config_data.get(mode_name)

        if isinstance(mode_data, dict) and len(mode_data) > 1:
            sub_modes = [key for key in mode_data.keys() if key != 'default']
            if len(sub_modes) >= 1:
                self.radioButton1.setText(sub_modes[0])
            if len(sub_modes) >= 2:
                self.radioButton2.setText(sub_modes[1])
                self.radioButton2.show()
            else:
                self.radioButton2.hide()
            self.soul_land_options.show()
        else:
            self.soul_land_options.hide()
