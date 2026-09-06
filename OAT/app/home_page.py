import os
import json
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from qfluentwidgets import (
    ComboBox, SpinBox, CheckBox, RadioButton,
    PushButton, PrimaryPushButton,
    CardWidget, BodyLabel, CaptionLabel, StrongBodyLabel,
    TextBrowser, TogglePushButton, ProgressBar,
    RoundMenu, Action,
    FluentIcon as FIF
)

from OAT.source.mode_config import mode_choice, mode_config
from OAT.utils import pause_state
from OAT.utils.logging import logger

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

        # 绘卷刷分专属：每轮刷分内的探索次数（仅绘卷刷分模式显示）
        self.explore_options = QWidget(self)
        explore_layout = QVBoxLayout(self.explore_options)
        explore_layout.setContentsMargins(0, 0, 0, 0)
        explore_layout.setSpacing(8)
        self.explore_spin = SpinBox(self)
        self.explore_spin.setRange(1, 99)
        self.explore_spin.setValue(5)
        self.explore_spin.setToolTip("绘卷刷分模式：每轮刷分先探索N次，再打一轮结界突破")
        explore_label = BodyLabel("绘卷刷分 - 每轮探索次数")
        explore_layout.addWidget(explore_label)
        explore_layout.addWidget(self.explore_spin)
        self.explore_options.hide()
        card_layout.addWidget(self.explore_options)

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

        # 工具栏：进度 + 暂停
        log_toolbar = QHBoxLayout()
        log_toolbar.setContentsMargins(0, 0, 0, 0)
        log_toolbar.setSpacing(8)

        self.log_progress_widget = QWidget(self)
        _progress_layout = QHBoxLayout(self.log_progress_widget)
        _progress_layout.setContentsMargins(0, 0, 0, 0)
        _progress_layout.setSpacing(8)
        self.log_progress_label = BodyLabel("挑战进度 0/0", self.log_progress_widget)
        self.log_progress_bar = ProgressBar(self.log_progress_widget)
        self.log_progress_bar.setRange(0, 100)
        self.log_progress_bar.setValue(0)
        self.log_progress_bar.setFixedWidth(120)
        _progress_layout.addWidget(self.log_progress_label)
        _progress_layout.addWidget(self.log_progress_bar)
        try:
            from OAT.utils.logging import logger as _progress_logger
            _progress_logger.progress_updated.connect(self._on_log_progress)
        except Exception:
            pass

        self.log_pause_btn = TogglePushButton('暂停', self)
        self.log_pause_btn.setCheckable(True)
        self.log_pause_btn.setChecked(False)
        self.log_pause_btn.setFixedWidth(72)
        self.log_pause_btn.toggled.connect(self._on_log_pause_toggled)

        log_toolbar.addWidget(self.log_progress_widget, 0)
        log_toolbar.addWidget(self.log_pause_btn, 0)
        log_layout.addLayout(log_toolbar)

        self.textBrowser = TextBrowser(self)
        self.textBrowser.setObjectName("log_browser")
        self.textBrowser.document().setMaximumBlockCount(5000)
        try:
            self.textBrowser.setProperty('logAutoScroll', True)
        except Exception:
            pass
        try:
            self.textBrowser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.textBrowser.customContextMenuRequested.connect(self._on_log_context_menu)
        except Exception:
            pass
        log_layout.addWidget(self.textBrowser)

        parent_layout.addWidget(log_card)

    def _on_log_progress(self, done, total):
        try:
            try:
                d = int(done)
            except Exception:
                d = 0
            try:
                t = int(total)
            except Exception:
                t = 0
            # 新开局（进度清零）：工作线程的 begin_run 已取消暂停，
            # 把按钮拨回“暂停”；blockSignals 避免触发 toggled 副作用（resume+日志噪音）。
            if d == 0 and t > 0:
                try:
                    try:
                        self.log_pause_btn.blockSignals(True)
                    except Exception:
                        pass
                    try:
                        self.log_pause_btn.setChecked(False)
                    except Exception:
                        pass
                    try:
                        self.log_pause_btn.setText('暂停')
                    except Exception:
                        pass
                finally:
                    try:
                        self.log_pause_btn.blockSignals(False)
                    except Exception:
                        pass
            try:
                self.log_progress_label.setText(f"挑战进度 {d}/{t}")
            except Exception:
                pass
            try:
                if t <= 0:
                    v = 0
                else:
                    v = int(100 * d / t)
                    if v < 0:
                        v = 0
                    elif v > 100:
                        v = 100
                self.log_progress_bar.setValue(v)
            except Exception:
                pass
        except Exception:
            pass

    def _on_log_pause_toggled(self, checked):
        try:
            paused = bool(checked)
        except Exception:
            paused = False
        try:
            if paused:
                pause_state.pause()
            else:
                pause_state.resume()
        except Exception:
            pass
        try:
            self.log_pause_btn.setText('继续' if paused else '暂停')
        except Exception:
            pass
        try:
            logger.info("已暂停挑战" if paused else "已继续挑战")
        except Exception:
            pass

    def _on_log_context_menu(self, pos):
        try:
            menu = RoundMenu(parent=self.textBrowser)
        except Exception:
            return
        try:
            try:
                auto = self.textBrowser.property('logAutoScroll')
                auto_on = True if auto is None else bool(auto)
            except Exception:
                auto_on = True
            act_clear = Action('清空', parent=menu)
            act_scroll = Action(f"自动滚动：{'开' if auto_on else '关'}", parent=menu)
            try:
                act_scroll.setCheckable(True)
                act_scroll.setChecked(bool(auto_on))
            except Exception:
                pass
            act_open = Action('打开日志目录', parent=menu)
            act_copy = Action('复制诊断', parent=menu)
            menu.addAction(act_clear)
            menu.addAction(act_scroll)
            menu.addAction(act_open)
            menu.addAction(act_copy)
            try:
                act_clear.triggered.connect(lambda: self.textBrowser.clear())
            except Exception:
                pass
            try:
                act_scroll.triggered.connect(self._on_log_autoscroll_toggled)
            except Exception:
                pass
            try:
                act_open.triggered.connect(self._on_log_open_dir)
            except Exception:
                pass
            try:
                act_copy.triggered.connect(self._on_log_copy_diag)
            except Exception:
                pass
            try:
                menu.exec(self.textBrowser.mapToGlobal(pos), ani=True)
            except Exception:
                try:
                    menu.exec(self.textBrowser.mapToGlobal(pos))
                except Exception:
                    pass
        except Exception:
            pass

    def _on_log_autoscroll_toggled(self):
        try:
            auto = self.textBrowser.property('logAutoScroll')
            cur = True if auto is None else bool(auto)
            self.textBrowser.setProperty('logAutoScroll', (not cur))
        except Exception:
            pass

    def _on_log_open_dir(self):
        try:
            log_dir = os.path.abspath('logs')
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                pass
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))
        except Exception:
            pass

    def _on_log_copy_diag(self):
        try:
            text = self.textBrowser.toPlainText()
        except Exception:
            return
        try:
            QtWidgets.QApplication.clipboard().setText(text)
        except Exception:
            pass

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
                <span style="margin: 0;">1.新增绘卷刷分模式（探索+结界突破组合，每轮探索次数可配）</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">2.日志区新增挑战进度条、暂停/继续按钮与右键菜单</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">3.新开局自动回收旧线程，急停可干净退出</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">4.修复截图标题栏偏移与前后台点击对齐问题</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">5.管道任务支持滑动/等待动作与连续匹配预算</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">6.日志改为按天轮转保留30天</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">7.修复图像配置编辑器格式落后于pipeline的问题</span>
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
        self.explore_options.hide()

        if not mode_config_data or index < 0 or index >= self.find_mode_combo.count():
            return

        mode_name = self.find_mode_combo.currentText()
        mode_data = mode_config_data.get(mode_name)

        # 绘卷刷分模式：显示每轮探索次数选择
        if mode_name == "绘卷刷分":
            self.explore_options.show()

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
