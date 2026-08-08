import builtins
import json
import os
import threading
import traceback
import glob
from datetime import datetime
from functools import lru_cache

import cv2
import win32gui
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QDialog, QMessageBox
)

from qfluentwidgets import (
    ComboBox, PushButton, PrimaryPushButton,
    InfoBar, InfoBarPosition,
    FluentIcon as FIF, setTheme, Theme, qconfig, FluentWindow,
)

from OAT.tools.GetDC import WindowCapture
from OAT.tools.ConfigManager import ConfigReader
from OAT.tools.WindowSynchronizer import WindowSynchronizer
from OAT.tools.ThreadManager import UpdateCheckThread, UpdateDownloadThread
from OAT.tools.OnmyojiAuto import OnmyojiAutomation
from OAT.tools.WindowChecker import WindowChecker
from OAT.tools import settings
from OAT.config.check_update import UpdateChecker
from OAT.config.update_manager import UpdateManager
from OAT.source import *
from OAT.source import MODE_MAPPING
from OAT.tools import *
from OAT.utils.error_handler import setup_global_exception_handler, LOG_FILE, log_error
from OAT.utils.logging import LogRedirect, logger
from OAT.utils.warning_box import warning_box
from OAT.utils.error_box import error_box
from OAT.tools.settings import APP_VERSION, settings_data, update_settings
from OAT.utils.markdown_to_html import markdown_to_html
from OAT.tools.edit_mode_and_img import ModeEditorDialog
from OAT.tools.MultiInstanceManager import MultiInstanceManager

from .home_page import HomePage
from .sync_page import SyncPage
from .settings_page import SettingsPage
from .multi_instance_page import MultiInstancePage

setup_global_exception_handler()


class AppUI:
    def __init__(self, window: FluentWindow):
        self.window = window

        self.home_page = HomePage(window)
        self.sync_page = SyncPage(window)
        self.settings_page = SettingsPage(window)
        self.multi_instance_page = MultiInstancePage(window)

        window.addSubInterface(self.home_page, FIF.HOME, "首页")
        window.addSubInterface(self.sync_page, FIF.TILES, "同步器")
        window.addSubInterface(self.multi_instance_page, FIF.GAME, "多开管理")
        window.addSubInterface(self.settings_page, FIF.SETTING, "设置")

        self._setup_proxies()

    def _setup_proxies(self):
        self.find_mode_combo = self.home_page.find_mode_combo
        self.spinBox = self.home_page.spinBox
        self.client_choose = self.home_page.client_choose
        self.hidden_window_checkbox = self.home_page.hidden_window_checkbox
        self.radioButton1 = self.home_page.radioButton1
        self.radioButton2 = self.home_page.radioButton2
        self.soul_land_options = self.home_page.soul_land_options
        self.soul_land_group = self.home_page.soul_land_group
        self.refresh_window_btn = self.home_page.refresh_window_btn
        self.window_detect_btn = self.home_page.window_detect_btn
        self.start_challenge_btn = self.home_page.start_challenge_btn
        self.emergency_stop_btn = self.home_page.emergency_stop_btn
        self.textBrowser = self.home_page.textBrowser
        self.textBrowser_2 = self.home_page.textBrowser_2

        self.window_table = self.sync_page.window_table
        self.sync_instruction_btn = self.sync_page.sync_instruction_btn
        self.refresh_windows_btn = self.sync_page.refresh_windows_btn
        self.select_all_btn = self.sync_page.select_all_btn
        self.invert_selection_btn = self.sync_page.invert_selection_btn
        self.set_main_window_btn = self.sync_page.set_main_window_btn
        self.set_sub_windows_btn = self.sync_page.set_sub_windows_btn
        self.start_sync_btn = self.sync_page.start_sync_btn
        self.stop_sync_btn = self.sync_page.stop_sync_btn
        self.arrange_btn = self.sync_page.arrange_btn

        self.close_program_checkbox = self.settings_page.close_program_checkbox
        self.close_game_checkbox = self.settings_page.close_game_checkbox
        self.capture_window_mode = self.settings_page.capture_window_mode
        self.recognition_mode_combo = self.settings_page.recognition_mode_combo
        self.img_find_threshold = self.settings_page.img_find_threshold
        self.find_value_label_value = self.settings_page.find_value_label_value
        self.edit_mode_and_img_btn = self.settings_page.edit_mode_and_img_btn
        self.check_update_check = self.settings_page.check_update_check
        self.clear_cache_button = self.settings_page.clear_cache_button
        self.transparency_slider = self.settings_page.transparency_slider
        self.transparency_slider_value = self.settings_page.transparency_slider_value
        self.sync_mode_combo = self.settings_page.sync_mode_combo
        self.window_arrange_combo = self.settings_page.window_arrange_combo
        self.windows_per_row_label = self.settings_page.windows_per_row_label
        self.windows_per_row_input = self.settings_page.windows_per_row_input
        self.custom_res_width_input = self.settings_page.custom_res_width_input
        self.custom_res_height_input = self.settings_page.custom_res_height_input
        self.custom_res_warning = self.settings_page.custom_res_warning

        self.exe_path_input = self.multi_instance_page.exe_path_input
        self.browse_btn = self.multi_instance_page.browse_btn
        self.launch_count = self.multi_instance_page.launch_count
        self.launch_btn = self.multi_instance_page.launch_btn
        self.close_selected_btn = self.multi_instance_page.close_selected_btn
        self.close_all_btn = self.multi_instance_page.close_all_btn
        self.refresh_btn = self.multi_instance_page.refresh_btn
        self.instance_table = self.multi_instance_page.instance_table

    def get_text(self):
        return self.home_page.get_text()

    def on_mode_selected(self, index):
        self.home_page.on_mode_selected(index)

    def on_width_changed(self, text):
        self.settings_page.on_width_changed(text)

    def on_height_changed(self, text):
        self.settings_page.on_height_changed(text)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setMicaEffectEnabled(False)
        self.ui = AppUI(self)

        self.ui.window_table.setColumnCount(4)
        self.ui.window_table.setHorizontalHeaderLabels(["选择", "窗口信息", "窗口句柄", "预览"])

        self.main_config_reader = ConfigReader('config/config.yaml')
        self.main_config = self.main_config_reader.read_config()

        settings_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools', 'settings.json')
        try:
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                sd = json.load(f)
                self.sync_mode_value = sd.get('sync_mode', 'exactly_sync')
        except Exception as e:
            logger.error(f"读取设置文件失败：{e}")
            self.sync_mode_value = 'exactly_sync'

        self.sync = WindowSynchronizer(sync_mode=self.sync_mode_value)
        self.sync_mode_flag = False

        self.multi_instance_manager = MultiInstanceManager()

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'tools', 'uiResources', self.main_config.get('icon_image', 'icon.ico')
        )
        self.setWindowIcon(QtGui.QIcon(icon_path))

        self.window_title = "阴阳师-MuMu模拟器专版"

        self._connect_page_signals()
        self._connect_main_signals()
        self._setup_shortcuts()
        self._setup_logging()

        self._init_theme()

        qconfig.themeChanged.connect(self._on_theme_changed)

        self.active_threads = []
        self.shutdown_flag = False
        self.lock = threading.Lock()

        self.check_update_silently()

    def _connect_page_signals(self):
        self.ui.settings_page.transparency_changed.connect(self.on_transparency_changed)
        self.ui.settings_page.close_program_changed.connect(self.save_close_program_setting)
        self.ui.settings_page.close_game_changed.connect(self.save_close_game_setting)
        self.ui.settings_page.capture_mode_changed.connect(self.save_backend_get_img_mode_settings)
        self.ui.settings_page.find_mode_changed.connect(self.save_find_img_mode_settings)
        self.ui.settings_page.find_threshold_changed.connect(self.save_find_value_settings)
        self.ui.settings_page.sync_mode_changed.connect(self.on_sync_value_changed)
        self.ui.settings_page.window_arrange_changed.connect(self.on_window_arrange_changed)
        self.ui.settings_page.windows_per_row_changed.connect(self.on_windows_per_row_changed)
        self.ui.settings_page.check_update.connect(self.check_is_update)
        self.ui.settings_page.clear_cache.connect(self.clean_cache)
        self.ui.settings_page.open_mode_editor.connect(self.open_mode_editor_dialog)

    def _connect_main_signals(self):
        self.ui.find_mode_combo.currentTextChanged.connect(self.handle_mode_change)
        self.ui.find_mode_combo.currentIndexChanged.connect(self.ui.on_mode_selected)
        self.ui.window_detect_btn.clicked.connect(self.window_detection)
        self.ui.start_challenge_btn.clicked.connect(self.start_challenge)
        self.ui.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.ui.sync_instruction_btn.clicked.connect(self.sync_instruction)
        self.ui.refresh_windows_btn.clicked.connect(self.update_window_table)
        self.ui.select_all_btn.clicked.connect(self.select_all)
        self.ui.invert_selection_btn.clicked.connect(self.deselect_all)
        self.ui.set_main_window_btn.clicked.connect(self.setMainWindow)
        self.ui.set_sub_windows_btn.clicked.connect(self.setSubWindows)
        self.ui.start_sync_btn.clicked.connect(self.start_sync)
        self.ui.stop_sync_btn.clicked.connect(self.stop_sync)
        self.ui.arrange_btn.clicked.connect(self.arrange_connect)
        self.ui.client_choose.currentTextChanged.connect(self.update_window_title)
        self.ui.refresh_window_btn.clicked.connect(self.refresh_window)

        self.ui.custom_res_width_input.textChanged.connect(self.ui.on_width_changed)
        self.ui.custom_res_height_input.textChanged.connect(self.ui.on_height_changed)

        self.ui.multi_instance_page.launch_btn.clicked.connect(self.launch_game_instances)
        self.ui.multi_instance_page.close_selected_btn.clicked.connect(self.close_selected_instances)
        self.ui.multi_instance_page.close_all_btn.clicked.connect(self.close_all_instances)
        self.ui.multi_instance_page.refresh_btn.clicked.connect(self.refresh_instance_list)
        self.ui.multi_instance_page.close_instance.connect(self.close_instance_by_id)
        self.ui.multi_instance_page.launch_finished.connect(
            lambda: self.ui.multi_instance_page.launch_btn.setEnabled(True)
        )

    def _setup_shortcuts(self):
        self.ui.window_detect_btn.setShortcut("Ctrl+W")
        self.ui.emergency_stop_btn.setShortcut("Ctrl+E")
        self.ui.start_challenge_btn.setShortcut("Return")
        self.ui.refresh_window_btn.setShortcut("Ctrl+R")

    def _setup_logging(self):
        self.log_redirect = LogRedirect(self.ui.textBrowser)
        builtins.print = self.log_redirect.print
        logger.set_text_browser(self.ui.textBrowser)

    def _init_theme(self):
        """从保存的设置中初始化主题，并加载对应 QSS 样式表。"""
        theme_str = settings_data.get('theme', 'light')
        target_theme = Theme.DARK if theme_str == "dark" else Theme.LIGHT
        setTheme(target_theme)
        self._load_theme_qss(theme_str)

    def _load_theme_qss(self, theme_str=None):
        """根据当前主题加载并应用自定义 QSS 样式表。"""
        if theme_str is None:
            theme_str = settings_data.get('theme', 'light')
        theme_file = "QtSS_dark.qss" if theme_str == "dark" else "QtSS.qss"
        qss_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'tools', theme_file
        )
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            logger.error(f"加载样式表失败: {str(e)}")

    def _on_theme_changed(self, theme):
        """处理 qfluentwidgets 主题切换事件，同步更新 QSS。"""
        setTheme(theme)
        theme_str = "dark" if theme == Theme.DARK else "light"
        update_settings('theme', theme_str)
        self._load_theme_qss(theme_str)

    def update_window_title(self):
        selected_client = self.ui.client_choose.currentText()
        self.window_title = selected_client
        logger.info(f"选择客户端为:{self.window_title}")

    def refresh_window(self):
        timestamp = self.log_redirect.get_timestamp()
        self.ui.textBrowser.clear()
        self.ui.textBrowser_2.clear()
        self.ui.textBrowser_2.setHtml(self.ui.get_text())
        self.ui.find_mode_combo.setCurrentIndex(0)
        self.ui.spinBox.setValue(1)

        self.ui.textBrowser.append(f"{timestamp} - 窗口已刷新")
        self.log_redirect.print(f"{timestamp} - 窗口已刷新")

    @staticmethod
    def handle_mode_change(mode: str):
        logger.info(f"选择模式：{mode}")

    def window_detection(self, *args):
        logger.info("客户端窗口检测：")
        automation = OnmyojiAutomation(self.window_title)
        if automation.is_window_present() is False:
            warning_box("未检测到阴阳师窗口，请先打开游戏")
            return
        automation.print_window_info()
        checker = WindowChecker()
        checker.set_window_title(self.window_title)
        window_size = checker.get_window_info()
        if window_size:
            logger.info(f"当前客户端大小：宽度 {window_size[2][0]}，高度 {window_size[2][1]}")
        checker.connect_all()

    def clean_threads(self):
        with self.lock:
            self.active_threads = [t for t in self.active_threads if t.is_alive()]

    def start_challenge(self, *args):
        self.clean_threads()
        MAX_THREADS = 5
        if len(self.active_threads) >= MAX_THREADS:
            warning_box("已有任务在进行中，请等待完成")
            return
        times = self.ui.spinBox.value()
        mode: str = self.ui.find_mode_combo.currentText()
        sub_mode: str = ""

        if hasattr(self.ui, 'radioButton1') and hasattr(self.ui, 'radioButton2'):
            if self.ui.radioButton1.isChecked():
                sub_mode = self.ui.radioButton1.text()
                logger.info(f"选择：{mode}, {sub_mode}")
            elif self.ui.radioButton2.isChecked():
                sub_mode = self.ui.radioButton2.text()
                logger.info(f"选择：{mode}, {sub_mode}")

        if self.ui.hidden_window_checkbox.isChecked():
            hidden_window = True
            logger.info("=" * 50)
            logger.info("       已启用后台运行模式      ")
            logger.info("  后台模式只要不将窗口最小化就不会影响程序的运行")
            logger.info("     后台模式不支持模拟器，请前往桌面版使用    ")
            logger.info("=" * 50)
        else:
            hidden_window = False

        if self.sync_mode_flag is True:
            logger.info("=" * 50)
            logger.info("       已启用窗口同步模式      ")
            logger.info("  窗口同步模式下，程序会自动同步主窗口的点击内容到副窗口")
            logger.info("=" * 50)

        logger.info(f"获取挑战次数：{times}，模式：{mode}")

        try:
            thread = threading.Thread(
                target=self.safe_mode_choice,
                args=(mode, sub_mode, times, hidden_window, self.sync_mode_flag)
            )
            thread.daemon = True
            with self.lock:
                if self.shutdown_flag:
                    return
                self.active_threads.append(thread)
            thread.start()
        except ValueError:
            logger.info("请输入有效的整数挑战次数。")

    def safe_mode_choice(self, mode, sub_mode, times, hidden_window=False, sync_mode=False):
        try:
            with self.lock:
                if self.shutdown_flag:
                    return
            window_title = self.window_title
            sync_type = getattr(self, 'sync_type', '完全同步')

            folder_info = MODE_MAPPING.get(mode)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            if not folder_info:
                mode_json_path = os.path.join(project_root, 'OAT', 'source', 'mode.json')
                try:
                    with open(mode_json_path, 'r', encoding='utf-8') as f:
                        mode_config = json.load(f)
                    mode_data = mode_config.get(mode)
                    if mode_data:
                        if isinstance(mode_data, dict):
                            folder_name = mode_data.get(sub_mode, mode_data.get('default', ''))
                        else:
                            folder_name = mode_data
                    else:
                        logger.info('暂不支持此模式，敬请期待！')
                        return
                except Exception as e:
                    logger.error(f"读取mode.json文件失败: {e}")
                    logger.info('暂不支持此模式，敬请期待！')
                    return
            else:
                if isinstance(folder_info, dict):
                    folder_name = folder_info.get(sub_mode, folder_info['default'])
                else:
                    folder_name = folder_info

            sub_config_path = os.path.join(project_root, 'OAT', 'source', folder_name, 'config.json')
            sub_config_reader = ConfigReader(sub_config_path)
            sub_config = sub_config_reader.read_config()

            if sub_config:
                synchronizer = self.sync if hasattr(self, 'sync') else None
                mode_choice(mode, sub_mode, times, config=sub_config, window_title=window_title,
                            hidden_window=hidden_window, sync_mode=sync_mode, synchronizer=synchronizer,
                            sync_mode_value=self.sync_mode_value)
            else:
                error_msg = f"读取 {sub_config_path} 配置文件失败。"
                logger.error(error_msg)
                error_box(error_msg)
        except Exception as e:
            error_msg = f"执行挑战时出现异常: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            error_box(f"执行挑战时出现异常: {e}，请检查日志文件。")
        finally:
            current_thread = threading.current_thread()
            with self.lock:
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)

    def emergency_stop(self):
        for thread in self.active_threads[:]:
            if thread.is_alive():
                thread.join(timeout=0.5)
                if thread.is_alive():
                    logger.warn(f"警告：线程 {thread.ident} 无法正常终止")
        logger.info("紧急停止，退出窗口")
        with self.lock:
            self.shutdown_flag = True
            logger.info("正在终止所有进程... ...")
            for thread in self.active_threads:
                if thread.is_alive():
                    thread.join(timeout=0.5)
                    if thread.is_alive():
                        logger.warn(f"警告：线程 {thread.ident} 无法正常终止")
        QtWidgets.QApplication.quit()

    def update_window_table(self):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        client_path = os.path.join(script_dir, 'tools', 'client.json')
        title_list = []
        with open(client_path, 'r', encoding='utf-8') as file:
            titles_get = json.load(file)
            for _, value in titles_get['title'].items():
                title_list.append(value)
        window_synchronizer = WindowSynchronizer()
        window_info = window_synchronizer.get_all_windows(window_titles=title_list)
        self.update_table_with_window_info(window_info)

    def update_table_with_window_info(self, window_info):
        self.ui.window_table.setRowCount(0)
        for row, (hwnd, title) in enumerate(window_info):
            self.ui.window_table.insertRow(row)
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(checkbox_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.ui.window_table.setItem(row, 0, checkbox_item)
            self.ui.window_table.setItem(row, 1, QtWidgets.QTableWidgetItem(title))
            self.ui.window_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(hwnd)))
            preview_button = QPushButton("预览")
            preview_button.setObjectName(f"preview_btn_{hwnd}")
            preview_button.clicked.connect(lambda checked, h=hwnd, t=title: self.preview_window(h, t))
            preview_button.setStyleSheet("padding: 2px 8px;")
            self.ui.window_table.setCellWidget(row, 3, preview_button)
        self.ui.window_table.setColumnWidth(0, 80)
        self.ui.window_table.setColumnWidth(1, 250)
        self.ui.window_table.setColumnWidth(2, 150)
        self.ui.window_table.setColumnWidth(3, 100)
        self.ui.window_table.show()
        logger.info("表格已刷新")

    def preview_window(self, hwnd, title):
        try:
            screenshot_dir = os.path.join('logs', 'screen_shot')
            if not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir)
            window_capture = WindowCapture(hwnd=hwnd)
            img = window_capture.capture_window()
            if img is not None:
                temp_file_path = os.path.join(screenshot_dir, f"window_preview_{hwnd}.png")
                cv2.imwrite(temp_file_path, img)
                self.show_preview_dialog(title, temp_file_path)
            else:
                logger.error(f"无法捕获窗口 {title} ({hwnd}) 的图像")
                self.show_error_message("截图失败", "无法捕获窗口图像")
        except Exception as e:
            logger.error(f"预览窗口时出错: {str(e)}")
            self.show_error_message("预览错误", f"发生错误: {str(e)}")

    def show_preview_dialog(self, title, image_path):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"窗口预览 - {title}")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        label = QLabel(dialog)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            max_size = 800
            scaled_pixmap = pixmap.scaled(
                max_size, max_size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            label.setText("无法加载图像")
        layout.addWidget(label)
        button_layout = QHBoxLayout()
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        dialog.exec()

    def show_error_message(self, title, message):
        warning_box(message)
        log_error(f"{title}: {message}")

    def select_all(self):
        row_count = self.ui.window_table.rowCount()
        for row in range(row_count):
            checkbox_item = self.ui.window_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(QtCore.Qt.CheckState.Checked)

    def deselect_all(self):
        row_count = self.ui.window_table.rowCount()
        for row in range(row_count):
            checkbox_item = self.ui.window_table.item(row, 0)
            if checkbox_item:
                if checkbox_item.checkState() == QtCore.Qt.CheckState.Checked:
                    checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                else:
                    checkbox_item.setCheckState(QtCore.Qt.CheckState.Checked)

    def get_selected_rows(self):
        return [row for row in range(self.ui.window_table.rowCount()) if
                self.ui.window_table.item(row, 0).checkState() == QtCore.Qt.CheckState.Checked]

    def setMainWindow(self):
        selected_rows = self.get_selected_rows()
        if len(selected_rows) != 1:
            logger.info("主窗口能且仅能设置一个！\n")
            return
        row = selected_rows[0]
        hwnd = self.ui.window_table.item(row, 2).text()
        self.main_window = hwnd
        for r in self.get_selected_rows():
            logger.info(f"已设置主窗口为: {self.ui.window_table.item(r, 2).text()}， {self.ui.window_table.item(r, 1).text()} \n")
            self.main_window_title = self.ui.window_table.item(r, 1).text()
        return self.main_window, self.main_window_title

    def setSubWindows(self):
        selected_rows = self.get_selected_rows()
        if len(selected_rows) == 0:
            logger.info("注意：没有选择副窗口！\n")
            return
        sub_windows_hwnd = [self.ui.window_table.item(row, 2).text() for row in selected_rows]
        self.sub_windows = sub_windows_hwnd
        self.sub_windows_title = [self.ui.window_table.item(row, 1).text() for row in selected_rows]
        for r in self.get_selected_rows():
            logger.info(f"已设置副窗口为: {self.ui.window_table.item(r, 2).text()}， {self.ui.window_table.item(r, 1).text()} \n")
        return self.sub_windows, self.sub_windows_title

    def start_sync(self):
        if not hasattr(self, 'main_window') or not hasattr(self, 'sub_windows'):
            return

        def sync_thread_func():
            try:
                wc = WindowChecker()
                window_handles = self.sub_windows + [self.main_window]
                settings_file_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), 'tools', 'settings.json'
                )
                try:
                    with open(settings_file_path, 'r', encoding='utf-8') as f:
                        sd = json.load(f)
                        target_width = sd.get('custom_res_width', 1404)
                        target_height = sd.get('custom_res_height', 834)
                        logger.info(f"从设置文件读取窗口尺寸: {target_width}x{target_height}")
                except Exception as e:
                    logger.error(f"读取设置文件失败：{e}")
                    target_width = 1404
                    target_height = 834

                for hwnd in window_handles:
                    try:
                        wc.set_window_handle(int(hwnd))
                        current_size = wc.get_window_info()
                        if current_size:
                            current_width, current_height = current_size[2]
                            if current_width != target_width or current_height != target_height:
                                wc.resize_window(target_width, target_height, hwnd=int(hwnd))
                    except Exception as e:
                        logger.error(str(e))

                try:
                    with open(settings_file_path, 'r', encoding='utf-8') as f:
                        sd = json.load(f)
                        latest_sync_mode = sd.get('sync_mode', 'exactly_sync')
                except:
                    latest_sync_mode = 'exactly_sync'

                self.sync = WindowSynchronizer(sync_mode=latest_sync_mode)
                main_hwnd = int(self.main_window)
                sub_hwnds = [int(hwnd) for hwnd in self.sub_windows]
                self.sync.set_main_and_sub_windows(
                    self.main_window_title, self.sub_windows_title, main_hwnd, sub_hwnds
                )
                self.sync.set_true_enable()
                current_mode = self.sync.get_sync_mode()
                sync_mode_reverse_map = {
                    "exactly_sync": "完全同步",
                    "program_sync": "程序同步",
                    "input_sync": "键鼠同步"
                }
                current_mode = sync_mode_reverse_map.get(current_mode, current_mode)
                logger.info(f"当前同步模式: {current_mode}")
                self.sync.sync_controller()
                self.sync_mode_flag = True
                logger.info("窗口同步已启动")
            except Exception as e:
                logger.error(f"同步失败: {str(e)}")
                logger.error(f"同步异常: {traceback.format_exc()}")
            finally:
                if hasattr(self, 'main_window'):
                    try:
                        win32gui.SetForegroundWindow(int(self.main_window))
                    except:
                        pass

        sync_thread = threading.Thread(target=sync_thread_func)
        sync_thread.daemon = True
        sync_thread.start()
        with self.lock:
            self.active_threads.append(sync_thread)
        return True

    def stop_sync(self):
        if self.sync_mode_flag:
            self.sync.stop_all_sync()
            self.sync_mode_flag = False
            logger.info("窗口同步已停止")

    def arrange_connect(self):
        def arrange_thread_func():
            try:
                main_window_hwnd = int(self.main_window)
                sub_window_hwnd = [int(hwnd) for hwnd in self.sub_windows]
                if hasattr(self, 'sync') and self.sync:
                    self.sync.arrange_windows(main_window_hwnd, sub_window_hwnd)
                else:
                    self.sync = WindowSynchronizer()
                    main_hwnd = int(self.main_window)
                    sub_hwnds = [int(hwnd) for hwnd in self.sub_windows]
                    self.sync.set_main_and_sub_windows(
                        self.main_window_title, self.sub_windows_title, main_hwnd, sub_hwnds
                    )
                    self.sync.arrange_windows(main_window_hwnd, sub_window_hwnd)
            except Exception as e:
                logger.error(f"窗口排列失败: {str(e)}")
                logger.error(f"窗口排列异常: {traceback.format_exc()}")

        arrange_thread = threading.Thread(target=arrange_thread_func)
        arrange_thread.daemon = True
        arrange_thread.start()
        with self.lock:
            self.active_threads.append(arrange_thread)

    def check_is_update(self):
        self.update_thread = UpdateCheckThread()
        self.update_thread.update_available.connect(self.on_update_available)
        self.update_thread.update_not_available.connect(self.on_update_not_available)
        self.update_thread.update_error.connect(self.on_update_error)
        self.update_thread.start()

        self.checking_msg = QMessageBox(self)
        self.checking_msg.setWindowTitle("检查更新")
        self.checking_msg.setText("正在检查更新...")
        self.checking_msg.setIcon(QMessageBox.Icon.Information)
        self.checking_msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        self.checking_msg.show()

    def check_update_silently(self):
        self.update_thread = UpdateCheckThread()
        self.update_thread.update_available.connect(self.on_update_available)
        self.update_thread.update_not_available.connect(self.on_update_not_available_silent)
        self.update_thread.update_error.connect(self.on_update_error_silent)
        self.update_thread.start()

    def on_update_not_available_silent(self):
        pass

    def on_update_error_silent(self, error_msg):
        self.log_redirect.log_to_file(f"检查更新时出错: {error_msg}")

    def on_update_available(self, latest_version, latest_info):
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None

        try:
            update_checker = UpdateChecker()
            update_info = update_checker.get_update_info(latest_info) or "暂无更新日志"
            html_content = markdown_to_html(update_info)

            update_dialog = QDialog(self)
            update_dialog.setWindowTitle("发现新的版本")
            update_dialog.setFixedSize(600, 500)
            update_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

            main_layout = QVBoxLayout(update_dialog)
            version_label = QLabel(f"最新版本：{latest_version}")
            version_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            main_layout.addWidget(version_label)

            log_title = QLabel("更新日志")
            log_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
            main_layout.addWidget(log_title)

            log_text_edit = QTextEdit()
            log_text_edit.setReadOnly(True)
            log_text_edit.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: 'Microsoft YaHei';
                    font-size: 14px;
                    line-height: 1.5;
                }
                QScrollBar:vertical {
                    width: 16px;
                    background: #f3f4f6;
                }
                QScrollBar::handle:vertical {
                    background: #9ca3af;
                    border-radius: 8px;
                }
            """)
            log_text_edit.setHtml(html_content)
            main_layout.addWidget(log_text_edit, 1)

            published_at = latest_info.get('published_at', '未知')
            if published_at != '未知':
                try:
                    published_at = datetime.fromisoformat(published_at).strftime('%Y-%m-%d')
                except:
                    published_at = '未知'

            update_size = 'XX MB'
            assets = latest_info.get('assets', [])
            if assets:
                for asset in assets:
                    size = asset.get('size', 0)
                    if size > 0:
                        size_mb = round(size / (1024 * 1024), 2)
                        update_size = f"{size_mb} MB"
                        break

            version_info = QLabel(
                f"【当前版本 {APP_VERSION}】→【最新版本】{latest_version} | "
                f"发布日期: {published_at} | 更新包大小: {update_size}"
            )
            version_info.setStyleSheet("""
                QLabel {
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    padding: 8px;
                    background-color: #f5f5f5;
                    font-family: 'Microsoft YaHei';
                    font-size: 12px;
                    color: #333333;
                    margin-top: 10px;
                }
            """)
            main_layout.addWidget(version_info)

            button_layout = QHBoxLayout()
            btn_ignore = QPushButton("忽略本版本")
            btn_later = QPushButton("下次再说")
            btn_update = QPushButton("立即更新")

            btn_ignore.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #666666; font-size: 12px;
                    border: 1px solid #f0f0f0; border-radius: 4px; padding: 6px 12px;
                }
                QPushButton:hover { background-color: #f5f5f5; }
            """)
            btn_later.setStyleSheet("""
                QPushButton {
                    background-color: white; color: #333333; font-size: 14px;
                    border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px 16px;
                }
                QPushButton:hover { background-color: #f9f9f9; }
            """)
            btn_update.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3; color: white; font-size: 14px;
                    font-weight: bold; border: none; border-radius: 4px; padding: 8px 16px;
                }
                QPushButton:hover { background-color: #1976D2; }
            """)

            button_layout.addWidget(btn_ignore)
            button_layout.addStretch()
            button_layout.addWidget(btn_later)
            button_layout.addStretch()
            button_layout.addWidget(btn_update)
            main_layout.addLayout(button_layout)

            def on_btn_update_clicked():
                update_dialog.close()
                self.start_update_process(latest_info)

            def on_btn_later_clicked():
                update_dialog.close()

            def on_btn_ignore_clicked():
                reply = QMessageBox.question(
                    update_dialog, "确认忽略",
                    f"确定要忽略 {latest_version} 版本吗？后续将不会再提醒此版本的更新",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    update_dialog.close()
                    update_manager = UpdateManager()
                    update_manager.ignore_update(latest_version)

            btn_update.clicked.connect(on_btn_update_clicked)
            btn_later.clicked.connect(on_btn_later_clicked)
            btn_ignore.clicked.connect(on_btn_ignore_clicked)

            update_dialog.exec()
        except Exception as e:
            self.on_update_error(str(e))

    def start_update_process(self, latest_info):
        try:
            update_manager = UpdateManager()
            download_url = update_manager.get_download_url(latest_info)
            if not download_url:
                warning_box("无法获取更新包下载链接")
                return

            self.download_dialog = self.create_download_dialog()
            self.update_download_thread = UpdateDownloadThread(download_url)
            self.update_download_thread.download_progress.connect(self.on_download_progress)
            self.update_download_thread.download_complete.connect(self.on_download_complete)
            self.update_download_thread.download_error.connect(self.on_download_error)

            self.download_dialog.show()
            self.update_download_thread.start()
        except Exception as e:
            error_box(f"启动更新失败: {str(e)}")

    def create_download_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("正在下载更新")
        dialog.setMinimumWidth(450)
        dialog.setModal(True)
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.download_info_label = QLabel("正在准备下载...")
        layout.addWidget(self.download_info_label)

        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setMinimum(0)
        self.download_progress_bar.setMaximum(100)
        self.download_progress_bar.setValue(0)
        layout.addWidget(self.download_progress_bar)

        self.speed_label = QLabel("下载速度: 等待中...")
        layout.addWidget(self.speed_label)

        self.cancel_download_btn = QPushButton("取消")
        self.cancel_download_btn.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_download_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dialog.setLayout(layout)
        return dialog

    def cancel_download(self):
        if hasattr(self, 'update_download_thread') and self.update_download_thread:
            self.update_download_thread.terminate()
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()

    def on_download_progress(self, downloaded, total_size, speed, remaining):
        if total_size > 0:
            progress = int((downloaded / total_size) * 100)
            self.download_progress_bar.setValue(progress)
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            speed_kb = speed / 1024
            speed_mb = speed_kb / 1024
            speed_str = f"{speed_mb:.2f} MB/s" if speed_mb > 1 else f"{speed_kb:.2f} KB/s"
            if remaining > 60:
                remaining_min = int(remaining // 60)
                remaining_sec = int(remaining % 60)
                remaining_str = f"{remaining_min}分{remaining_sec}秒"
            else:
                remaining_str = f"{int(remaining)}秒"
            self.download_info_label.setText(f"已下载: {downloaded_mb:.2f} MB / {total_mb:.2f} MB")
            self.speed_label.setText(f"下载速度: {speed_str} | 预计剩余: {remaining_str}")

    def on_download_complete(self, zip_path):
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()
        try:
            update_manager = UpdateManager()
            if not zip_path:
                temp_dir = os.path.join(os.getcwd(), "temp")
                if os.path.exists(temp_dir):
                    zip_files = glob.glob(os.path.join(temp_dir, "*.zip"))
                    if zip_files:
                        zip_files.sort(key=os.path.getmtime, reverse=True)
                        zip_path = zip_files[0]
            if not zip_path:
                for root, dirs, files in os.walk(os.getcwd()):
                    for file in files:
                        if file.endswith(".zip"):
                            file_path = os.path.join(root, file)
                            if not zip_path or os.path.getmtime(file_path) > os.path.getmtime(zip_path):
                                zip_path = file_path
            if not zip_path:
                error_box("未找到更新压缩包")
                return
            update_checker = UpdateChecker()
            latest_info = update_checker.get_latest_release_info()
            update_log = update_checker.get_update_info(latest_info) or ""
            if update_manager.launch_updater(zip_path, update_log, latest_info):
                self.emergency_stop()
            else:
                error_box("无法启动更新程序，请确保OAT_Updater.exe存在于程序目录下")
        except Exception as e:
            error_box(f"启动更新程序失败: {str(e)}")

    def on_download_error(self, error_msg):
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()
        error_box(f"下载更新包时出错: {error_msg}")

    def on_update_not_available(self):
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("当前无新的版本")
        msg_box.setText("当前版本已是最新版本")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()

    def on_update_error(self, error_msg):
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None
        logger.error(f"检查更新时出错: {error_msg}")
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("检查更新失败")
        msg_box.setText("检查更新时发生错误，请稍后重试")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.exec()

    def sync_instruction(self):
        instruction_text = """
        同步器使用步骤：

    1. 刷新窗口：点击"刷新窗口"按钮获取当前所有符合条件的窗口列表
    2. 选择窗口：在表格中勾选需要参与同步的窗口
    3. 预览窗口：表格内点击"预览"按钮查看窗口截图
    4. 设置主窗口：选择一个窗口并点击"设置主窗口"
    5. 设置副窗口：选择一个或多个窗口并点击"设置副窗口"
    6. 排列窗口：点击"窗口排列"按钮自动排列窗口
    7. 开始同步：点击"开始同步"按钮启动同步功能
    8. 停止同步：点击"停止同步"按钮停止同步功能

    注意事项：
    - 主窗口只能设置一个
    - 副窗口至少设置一个
    - 窗口同步会同步对主窗口的鼠标、键盘和程序操作
    """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("同步器使用说明")
        msg_box.setText(instruction_text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()

    def save_close_program_setting(self, close_program: bool):
        update_settings('close_program_after_challenge', close_program)

    def save_close_game_setting(self, close_game: bool):
        update_settings('close_game_after_challenge', close_game)

    def save_find_value_settings(self, find_value: int):
        update_settings('find_value', find_value)
        settings.FIND_THRESHOLD = find_value
        settings.FIND_THRESHOLD_VALUE = find_value / 100.0

    def save_find_img_mode_settings(self, find_mode: str):
        update_settings('find_mode', find_mode)
        settings.FIND_MODE = find_mode

    def save_backend_get_img_mode_settings(self, mode: str):
        update_settings('capture_window_mode', mode)

    def on_transparency_changed(self, value: int):
        update_settings('transparency', value)

    def on_sync_value_changed(self, sync_mode: str):
        update_settings('sync_mode', sync_mode)

    def on_window_arrange_changed(self, mode: str):
        update_settings('window_arrange_mode', mode)

    def on_windows_per_row_changed(self, value: int):
        update_settings('windows_per_row', value)

    def clean_cache(self):
        logger.info("cleaning cache")
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        logs_dir = os.path.join(project_root, "logs")
        temp_dir = os.path.join(project_root, "temp")
        try:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                logger.info("残留安装包已清理")
            if os.path.exists(logs_dir):
                import shutil
                screen_shot_dir = os.path.join(logs_dir, "screen_shot")
                if os.path.exists(screen_shot_dir):
                    shutil.rmtree(screen_shot_dir)
                    logger.info("窗口预览缓存已清理")
                log_file_path = os.path.join(logs_dir, "log.log")
                if os.path.exists(log_file_path):
                    with open(log_file_path, "w", encoding="utf-8") as f:
                        f.write("")
                    logger.info("log.log文件已清理")
        except Exception as e:
            logger.error(f"清理缓存时出错: {e}")

    def open_mode_editor_dialog(self):
        dialog = ModeEditorDialog(self)
        dialog.exec()
        self.ui.home_page.reload_modes()
        self.ui.on_mode_selected(self.ui.find_mode_combo.currentIndex())

    def launch_game_instances(self):
        exe_path = self.ui.multi_instance_page.get_exe_path()
        if not exe_path:
            warning_box("请先选择游戏exe文件路径")
            return

        if not os.path.exists(exe_path):
            warning_box(f"文件不存在: {exe_path}")
            return

        count = self.ui.multi_instance_page.get_launch_count()
        interval = self.ui.multi_instance_page.get_launch_interval()
        logger.info(f"启动 {count} 个游戏实例: {exe_path}, 间隔 {interval}s")

        launch_btn = self.ui.multi_instance_page.launch_btn
        launch_btn.setEnabled(False)

        def launch_thread():
            try:
                instances = self.multi_instance_manager.launch_instances(exe_path, count, interval)
                for instance in instances:
                    self.ui.multi_instance_page.instance_added.emit(
                        instance.instance_id,
                        instance.pid or 0,
                        instance.status,
                        instance.launched_at
                    )
                    logger.info(f"实例 {instance.instance_id} 已启动, 状态: {instance.status}")
            except Exception as e:
                logger.error(f"启动实例失败: {e}")
                error_box(f"启动失败: {str(e)}")
            finally:
                self.ui.multi_instance_page.launch_finished.emit()

        thread = threading.Thread(target=launch_thread, daemon=True)
        thread.start()

    def close_selected_instances(self):
        selected_ids = self.ui.multi_instance_page.get_selected_instance_ids()
        if not selected_ids:
            warning_box("请先选择要关闭的实例")
            return

        for instance_id in selected_ids:
            self.close_instance_by_id(instance_id)

    def close_all_instances(self):
        closed = self.multi_instance_manager.close_all()
        self.ui.multi_instance_page.clear_instances()
        logger.info(f"已关闭 {closed} 个实例")

    def refresh_instance_list(self):
        self.multi_instance_manager.refresh_all_status()
        instances = self.multi_instance_manager.get_all_instances()

        for instance_id, instance in instances.items():
            self.ui.multi_instance_page.update_instance(
                instance_id,
                pid=instance.pid,
                status=instance.status
            )

    def close_instance_by_id(self, instance_id: int):
        success = self.multi_instance_manager.close_instance(instance_id)
        if success:
            self.ui.multi_instance_page.update_instance(instance_id, status="已关闭")
            logger.info(f"实例 {instance_id} 已关闭")
        else:
            logger.error(f"关闭实例 {instance_id} 失败")
