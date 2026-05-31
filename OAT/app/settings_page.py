import os
import json
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from qfluentwidgets import (
    ComboBox, Slider, SwitchButton, PushButton,
    SettingCardGroup, SwitchSettingCard, PushSettingCard,
    HyperlinkCard, ExpandGroupSettingCard, SettingCard,
    OptionsSettingCard,
    FluentIcon as FIF,
    InfoBar, InfoBarPosition, SpinBox, LineEdit,
    CheckBox, RadioButton, PrimaryPushButton,
    StrongBodyLabel, CaptionLabel, BodyLabel,
    qconfig
)

from OAT.tools.settings import APP_VERSION, settings_data, update_settings


class SettingsPage(QWidget):
    transparency_changed = QtCore.pyqtSignal(int)
    close_program_changed = QtCore.pyqtSignal(bool)
    close_game_changed = QtCore.pyqtSignal(bool)
    capture_mode_changed = QtCore.pyqtSignal(str)
    find_mode_changed = QtCore.pyqtSignal(str)
    find_threshold_changed = QtCore.pyqtSignal(int)
    sync_mode_changed = QtCore.pyqtSignal(str)
    window_arrange_changed = QtCore.pyqtSignal(str)
    windows_per_row_changed = QtCore.pyqtSignal(int)
    custom_res_changed = QtCore.pyqtSignal(int, int)
    check_update = QtCore.pyqtSignal()
    clear_cache = QtCore.pyqtSignal()
    open_mode_editor = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_page")
        self._setup_ui()

    def _setup_ui(self):
        scroll_widget = QWidget(self)
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(20)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._create_general_group(scroll_layout)
        self._create_display_group(scroll_layout)
        self._create_sync_group(scroll_layout)
        self._create_about_group(scroll_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setWidget(scroll_widget)
        scroll_area.viewport().setStyleSheet("background-color: transparent;")
        main_layout.addWidget(scroll_area)

    def _create_setting_card(self, icon, title, content, parent, widget=None):
        card = SettingCard(icon, title, content, parent)
        if widget is not None:
            card.hBoxLayout.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight)
            card.hBoxLayout.addSpacing(16)
        return card

    def _create_general_group(self, parent_layout):
        group = SettingCardGroup("常规设置", self)

        self.close_program_card = SwitchSettingCard(
            FIF.CONNECT, "挑战执行完毕后关闭程序",
            "挑战结束后自动退出本程序",
            parent=self
        )
        self.close_program_card.checkedChanged.connect(
            lambda checked: self.close_program_changed.emit(bool(checked))
        )
        self.close_program_checkbox = self.close_program_card.switchButton
        self.close_program_checkbox.setChecked(
            settings_data.get('close_program_after_challenge', False)
        )
        group.addSettingCard(self.close_program_card)

        self.close_game_card = SwitchSettingCard(
            FIF.GAME, "挑战执行完毕后关闭游戏",
            "挑战结束后自动关闭游戏窗口",
            parent=self
        )
        self.close_game_card.checkedChanged.connect(
            lambda checked: self.close_game_changed.emit(bool(checked))
        )
        self.close_game_checkbox = self.close_game_card.switchButton
        self.close_game_checkbox.setChecked(
            settings_data.get('close_game_after_challenge', False)
        )
        group.addSettingCard(self.close_game_card)

        self.capture_window_mode = ComboBox(self)
        self.capture_window_mode.addItems(["PrintWindow", "BitBlt"])
        capture_val = settings_data.get('capture_window_mode', 'PrintWindow')
        idx = self.capture_window_mode.findText(capture_val)
        if idx >= 0:
            self.capture_window_mode.setCurrentIndex(idx)
        self.capture_window_mode.currentTextChanged.connect(
            self.capture_mode_changed.emit
        )
        self.capture_mode_card = self._create_setting_card(
            FIF.CAMERA, "后台获取图像模式", "选择窗口截图的方式",
            self, self.capture_window_mode
        )
        group.addSettingCard(self.capture_mode_card)

        self.recognition_mode_combo = ComboBox(self)
        self.recognition_mode_combo.addItems(["opencv", "pyscreeze"])
        find_mode = settings_data.get('find_mode', 'opencv')
        idx2 = self.recognition_mode_combo.findText(find_mode)
        if idx2 >= 0:
            self.recognition_mode_combo.setCurrentIndex(idx2)
        self.recognition_mode_combo.currentTextChanged.connect(
            self.find_mode_changed.emit
        )
        self.recognition_card = self._create_setting_card(
            FIF.SEARCH, "识别模式", "图像识别算法",
            self, self.recognition_mode_combo
        )
        group.addSettingCard(self.recognition_card)

        threshold_default = settings_data.get('find_value', 85)

        self.img_find_threshold = Slider(QtCore.Qt.Orientation.Horizontal)
        self.img_find_threshold.setRange(70, 100)
        self.img_find_threshold.setValue(threshold_default)
        self.img_find_threshold.setFixedWidth(200)
        self.img_find_threshold.valueChanged.connect(self._on_threshold_changed)

        self.find_value_label_value = BodyLabel(f"{threshold_default}%")
        self.find_value_label_value.setFixedWidth(40)
        self.find_value_label_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        threshold_widget = QWidget()
        thr_layout = QHBoxLayout(threshold_widget)
        thr_layout.setContentsMargins(0, 0, 0, 0)
        thr_layout.setSpacing(8)
        thr_layout.addWidget(self.img_find_threshold)
        thr_layout.addWidget(self.find_value_label_value)

        self.threshold_card = self._create_setting_card(
            FIF.ZOOM, "识别阈值", f"当前值: {threshold_default}%",
            self, threshold_widget
        )
        group.addSettingCard(self.threshold_card)

        self.edit_mode_card = PushSettingCard(
            "编辑模式和图像", FIF.EDIT,
            "模式和图像编辑", "编辑游戏模式的图像配置", self
        )
        self.edit_mode_card.clicked.connect(self.open_mode_editor.emit)
        self.edit_mode_and_img_btn = self.edit_mode_card.button
        group.addSettingCard(self.edit_mode_card)

        self.check_update_card = PushSettingCard(
            "检查更新", FIF.DOWNLOAD,
            "检查更新", "检查是否有新版本可用", self
        )
        self.check_update_card.clicked.connect(self.check_update.emit)
        self.check_update_check = self.check_update_card.button
        group.addSettingCard(self.check_update_card)

        self.clear_cache_card = PushSettingCard(
            "清理缓存", FIF.DELETE,
            "清理缓存", "清理截图画廊和日志文件", self
        )
        self.clear_cache_card.clicked.connect(self.clear_cache.emit)
        self.clear_cache_button = self.clear_cache_card.button
        group.addSettingCard(self.clear_cache_card)

        parent_layout.addWidget(group)

    def _create_display_group(self, parent_layout):
        group = SettingCardGroup("显示设置", self)

        self.theme_card = OptionsSettingCard(
            qconfig.themeMode, FIF.PALETTE,
            "主题", "选择应用程序主题",
            texts=["浅色", "深色", "自动"],
            parent=self
        )
        group.addSettingCard(self.theme_card)

        init_trans = settings_data.get('transparency', 50)
        self.transparency_slider = Slider(QtCore.Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(20, 100)
        self.transparency_slider.setValue(init_trans)
        self.transparency_slider.setFixedWidth(200)
        self.transparency_slider.valueChanged.connect(self._on_transparency_value_changed)

        self.transparency_slider_value = BodyLabel(f"{init_trans}%")
        self.transparency_slider_value.setFixedWidth(40)
        self.transparency_slider_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        trans_widget = QWidget()
        trans_layout = QHBoxLayout(trans_widget)
        trans_layout.setContentsMargins(0, 0, 0, 0)
        trans_layout.setSpacing(8)
        trans_layout.addWidget(self.transparency_slider)
        trans_layout.addWidget(self.transparency_slider_value)

        self.transparency_card = self._create_setting_card(
            FIF.TRANSPARENT, "透明度", "窗口背景透明度",
            self, trans_widget
        )
        group.addSettingCard(self.transparency_card)

        parent_layout.addWidget(group)

    def _create_sync_group(self, parent_layout):
        group = SettingCardGroup("同步器设置", self)

        self.sync_mode_combo = ComboBox(self)
        self.sync_mode_combo.addItems(["完全同步", "程序同步", "键鼠同步"])
        sync_mode = settings_data.get('sync_mode', 'exactly_sync')
        sync_map = {'exactly_sync': '完全同步', 'program_sync': '程序同步', 'input_sync': '键鼠同步'}
        sync_text = sync_map.get(sync_mode, '完全同步')
        idx3 = self.sync_mode_combo.findText(sync_text)
        if idx3 >= 0:
            self.sync_mode_combo.setCurrentIndex(idx3)
        self.sync_mode_combo.currentIndexChanged.connect(self._on_sync_mode_idx_changed)
        self.sync_mode_card = self._create_setting_card(
            FIF.SYNC, "同步模式", "选择窗口同步模式",
            self, self.sync_mode_combo
        )
        group.addSettingCard(self.sync_mode_card)

        self.window_arrange_combo = ComboBox(self)
        self.window_arrange_combo.addItems(["对角线排列", "平铺排列"])
        arrange_mode = settings_data.get('window_arrange_mode', 'diagonal')
        arrange_text = "对角线排列" if arrange_mode == "diagonal" else "平铺排列"
        idx4 = self.window_arrange_combo.findText(arrange_text)
        if idx4 >= 0:
            self.window_arrange_combo.setCurrentIndex(idx4)
        self.window_arrange_combo.currentIndexChanged.connect(self._on_arrange_idx_changed)
        self.arrange_mode_card = self._create_setting_card(
            FIF.TILES, "窗口排列方式", "设置多窗口的排列方式",
            self, self.window_arrange_combo
        )
        group.addSettingCard(self.arrange_mode_card)

        self.windows_per_row_label = BodyLabel("一行窗口数量:")
        self.windows_per_row_input = QtWidgets.QSpinBox()
        self.windows_per_row_input.setMinimum(1)
        self.windows_per_row_input.setMaximum(10)
        self.windows_per_row_input.setValue(settings_data.get('windows_per_row', 3))
        self.windows_per_row_input.valueChanged.connect(self._on_windows_per_row_changed)

        if arrange_mode != 'tile':
            self.windows_per_row_label.setVisible(False)
            self.windows_per_row_input.setVisible(False)

        per_row_widget = QWidget()
        per_row_layout = QHBoxLayout(per_row_widget)
        per_row_layout.setContentsMargins(0, 0, 0, 0)
        per_row_layout.setSpacing(8)
        per_row_layout.addWidget(self.windows_per_row_label)
        per_row_layout.addWidget(self.windows_per_row_input)
        per_row_layout.addStretch()

        self.per_row_card = self._create_setting_card(
            FIF.EDIT, "一行窗口数量", "平铺排列时每行的窗口数",
            self, per_row_widget
        )
        group.addSettingCard(self.per_row_card)

        res_container = QWidget()
        res_container_layout = QVBoxLayout(res_container)
        res_container_layout.setContentsMargins(0, 0, 0, 0)
        res_container_layout.setSpacing(4)

        self.custom_res_width_input = LineEdit(self)
        self.custom_res_width_input.setPlaceholderText("例如: 1404")
        self.custom_res_height_input = LineEdit(self)
        self.custom_res_height_input.setPlaceholderText("例如: 834")

        res_input_row = QHBoxLayout()
        res_input_row.setSpacing(8)
        w_label = BodyLabel("宽:")
        h_label = BodyLabel("高:")
        res_input_row.addWidget(w_label)
        res_input_row.addWidget(self.custom_res_width_input)
        res_input_row.addSpacing(16)
        res_input_row.addWidget(h_label)
        res_input_row.addWidget(self.custom_res_height_input)
        res_input_row.addStretch()
        res_container_layout.addLayout(res_input_row)

        self.custom_res_warning = CaptionLabel(
            "提示:自定义宽高后，自动挑战将无法正常使用!"
        )
        self.custom_res_warning.setStyleSheet("color: #ff6666;")
        res_container_layout.addWidget(self.custom_res_warning)

        self.res_card = self._create_setting_card(
            FIF.FIT_PAGE, "自定义同步时的窗口大小",
            "宽1404 高834 时才可以使用自动挑战",
            self, res_container
        )
        group.addSettingCard(self.res_card)

        self.load_custom_resolution_settings()

        parent_layout.addWidget(group)

    def _create_about_group(self, parent_layout):
        group = SettingCardGroup("关于", self)

        version_card = PushSettingCard(
            f"版本: {APP_VERSION}", FIF.INFO,
            "OAT 阴阳师自动化工具",
            "作者: RMA-MUN | 邮箱: n3032747608@163.com", self
        )
        group.addSettingCard(version_card)

        github_card = HyperlinkCard(
            "https://github.com/RMA-MUN/OnmyoujiAuto",
            "前往 GitHub", FIF.GITHUB,
            "GitHub 仓库",
            "如果您觉得本工具对您有帮助，在Github给个star支持一下！",
            self
        )
        group.addSettingCard(github_card)

        disclaimer_card = SettingCard(
            FIF.INFO,
            "免责声明",
            "本工具仅供学习交流，禁止商用及违规使用；使用风险自负", self
        )
        group.addSettingCard(disclaimer_card)

        parent_layout.addWidget(group)

    def _on_threshold_changed(self, value):
        self.threshold_card.setContent(f"当前值: {value}%")
        self.find_value_label_value.setText(f"{value}%")
        self.find_threshold_changed.emit(value)

    def _on_transparency_value_changed(self, value):
        self.transparency_slider_value.setText(f"{value}%")
        self.transparency_changed.emit(value)

    def _on_sync_mode_idx_changed(self, index):
        mode_text = self.sync_mode_combo.currentText()
        sync_map = {"完全同步": "exactly_sync", "程序同步": "program_sync", "键鼠同步": "input_sync"}
        mode_value = sync_map.get(mode_text, "exactly_sync")
        self.sync_mode_changed.emit(mode_value)

    def _on_arrange_idx_changed(self, index):
        mode_text = self.window_arrange_combo.currentText()
        arrange_map = {"对角线排列": "diagonal", "平铺排列": "tile"}
        mode_value = arrange_map.get(mode_text, "diagonal")
        self.window_arrange_changed.emit(mode_value)

        if mode_value == 'tile':
            self.windows_per_row_label.setVisible(True)
            self.windows_per_row_input.setVisible(True)
        else:
            self.windows_per_row_label.setVisible(False)
            self.windows_per_row_input.setVisible(False)

    def _on_windows_per_row_changed(self, value):
        self.windows_per_row_changed.emit(value)

    def on_width_changed(self, text):
        try:
            width = int(text)
            height = int(round(width * 834 / 1404))
            self.custom_res_height_input.blockSignals(True)
            self.custom_res_height_input.setText(str(height))
            self.custom_res_height_input.blockSignals(False)
            self.save_custom_resolution_settings()
        except ValueError:
            self.custom_res_height_input.blockSignals(True)
            self.custom_res_height_input.clear()
            self.custom_res_height_input.blockSignals(False)

    def on_height_changed(self, text):
        try:
            height = int(text)
            width = int(round(height * 1404 / 834))
            self.custom_res_width_input.blockSignals(True)
            self.custom_res_width_input.setText(str(width))
            self.custom_res_width_input.blockSignals(False)
            self.save_custom_resolution_settings()
        except ValueError:
            self.custom_res_width_input.blockSignals(True)
            self.custom_res_width_input.clear()
            self.custom_res_width_input.blockSignals(False)

    def load_custom_resolution_settings(self):
        width = settings_data.get('custom_res_width', 1404)
        height = settings_data.get('custom_res_height', 834)
        self.custom_res_width_input.setText(str(width))
        self.custom_res_height_input.setText(str(height))

    def save_custom_resolution_settings(self):
        try:
            width_text = self.custom_res_width_input.text()
            height_text = self.custom_res_height_input.text()
            if width_text and height_text:
                width = int(width_text)
                height = int(height_text)
                update_settings('custom_res_width', width)
                update_settings('custom_res_height', height)
        except ValueError:
            pass
