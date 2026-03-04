import builtins
import json
import os
import threading
import traceback
import glob
from datetime import datetime

import cv2
import win32gui
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit
from PyQt6.QtWidgets import QMessageBox

from OAT.tools.GetDC import WindowCapture
from .ConfigManager import ConfigReader
from .GUI import UiDialog
from .ThreadManager import UpdateCheckThread
from .WindowSynchronizer import WindowSynchronizer
from ..config.check_update import UpdateChecker
from ..config.update_manager import UpdateManager
from ..source import *
from ..source import MODE_MAPPING
from ..tools import *
from ..utils.error_handler import setup_global_exception_handler, LOG_FILE
from ..utils.logging import LogRedirect
from OAT.tools.settings import APP_VERSION
from .ThreadManager import UpdateDownloadThread
from ..utils.markdown_to_html import markdown_to_html

# 设置全局异常处理程序
setup_global_exception_handler()

class MainWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.ui = UiDialog()
        self.ui.setup_ui(self)
        # 设置表格列数为 4
        self.ui.window_table.setColumnCount(4)
        self.ui.window_table.setHorizontalHeaderLabels(["选择", "窗口信息", "窗口句柄", "预览"])
        # 预览列显示的是一个链接，点击可以预览窗口截图
        self.main_config_reader = ConfigReader('config/config.yaml')
        self.main_config = self.main_config_reader.read_config()

        # 从设置中读取同步模式
        settings_file_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        try:
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
                self.sync_mode_value = settings_data.get('sync_mode', 'exactly_sync')
        except Exception as e:
            print(f"读取设置文件失败：{e}")
            self.sync_mode_value = 'exactly_sync'

        self.sync = WindowSynchronizer(sync_mode=self.sync_mode_value)
        self.sync_mode = False

        # 最大化和最小化按钮
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint | QtCore.Qt.WindowType.WindowMinMaxButtonsHint)

        # 添加图标
        icon_path = os.path.join(os.path.dirname(__file__), 'uiResources', self.main_config.get('icon_image'))
        self.setWindowIcon(QtGui.QIcon(icon_path))

        # 设置窗口背景
        background_path = os.path.join(os.path.dirname(__file__), 'uiResources', self.main_config.get('background_image'))
        self.background = QtGui.QPixmap(background_path)
        # alpha/255为透明度，值为1，则完全不透明，值为0，则完全透明
        self.alpha = 135

        self.window_title = "阴阳师-MuMu模拟器专版"

        # 信号与槽绑定
        self.ui.find_mode_combo.currentTextChanged.connect(self.handle_mode_change)
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
        self.ui.check_update_check.clicked.connect(self.check_is_update)

        # 给按钮绑定快捷键
        self.ui.window_detect_btn.setShortcut("Ctrl+W")
        self.ui.emergency_stop_btn.setShortcut("Ctrl+E")
        self.ui.start_challenge_btn.setShortcut("Return")
        self.ui.refresh_window_btn.setShortcut("Ctrl+R")

        # 设置工具提示
        self.ui.refresh_window_btn.setToolTip("刷新窗口 (Ctrl+R)")
        self.ui.window_detect_btn.setToolTip("窗口检测 (Ctrl+W)")
        
        # 程序启动时静默检查更新
        self.check_update_silently()
        self.ui.start_challenge_btn.setToolTip("开始挑战 (Enter)")
        self.ui.emergency_stop_btn.setToolTip("紧急停止 (Ctrl+E)")

        # 定向输出print
        self.log_redirect = LogRedirect(self.ui.textBrowser)
        builtins.print = self.log_redirect.print

        # 线程管理
        self.active_threads = []
        self.shutdown_flag = False

        # 创建线程锁
        self.lock = threading.Lock()

        # 刷新窗口按钮
        self.ui.refresh_window_btn.clicked.connect(self.refresh_window)

        # 设置界面样式
        # 加载外部样式表 - 由UI类统一管理主题样式
        pass

        # 信号连接，使用 clicked 信号
        # self.ui.checkBox.clicked.connect(self.update_window_title)
        # self.ui.checkBox1.clicked.connect(self.update_window_title)

        # 初始化 window_title
        # self.window_title = '阴阳师-网易游戏' if self.ui.checkBox.isChecked() else 'MuMu模拟器5'

    def update_window_title(self):
        # 根据下拉菜单的选择更新 window_title
        selected_client = self.ui.client_choose.currentText()
        self.window_title = selected_client
        print(f"选择客户端为:{self.window_title}")

    # 刷新窗口按钮
    def refresh_window(self):
        """
        刷新窗口，只刷新界面，清空文本，不影响正在进行的任务
        """
        timestamp = self.log_redirect.get_timestamp()

        # 界面刷新操作
        self.ui.textBrowser.clear()
        self.ui.textBrowser_2.clear()
        self.ui.textBrowser_2.setHtml(self.ui.get_text())
        self.ui.find_mode_combo.setCurrentIndex(0)
        self.ui.spinBox.setValue(1)

        # 打印刷新信息
        self.ui.textBrowser.append(f"{timestamp} - 窗口已刷新")
        self.log_redirect.print(f"{timestamp} - 窗口已刷新")

    # 重写绘制事件
    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        # 应用透明度
        painter.setOpacity(self.alpha / 255.0)
        painter.drawPixmap(self.rect(), self.background)

    @staticmethod
    def handle_mode_change(mode: str):
        print(f"选择模式：{mode}")

    def window_detection(self, *args):
        print("客户端窗口检测：")
        # 使用更新后的 window_title
        automation = OnmyojiAutomation(self.window_title)
        # 先检测窗口是否存在
        if automation.is_window_present() is False:
            QtWidgets.QMessageBox.warning(self, "警告", "未检测到阴阳师窗口，请先打开游戏")
            return

        automation.print_window_info()

        # 调用 get_window_size 函数获取窗口大小
        checker = WindowChecker()
        checker.set_window_title(self.window_title)
        window_size = checker.get_window_info()
        if window_size:
            print(f"当前客户端大小：宽度 {window_size[2][0]}，高度 {window_size[2][1]}")
        # 调用 connect_all 函数，检查并调整窗口大小
        checker.connect_all()

    # 清理死掉的线程
    def clean_threads(self):
        with self.lock:
            self.active_threads = [t for t in self.active_threads if t.is_alive()]

    def start_challenge(self, *args):
        """
        times: 挑战次数
        mode: 挑战模式
        """
        # 添加最大线程数限制
        self.clean_threads()
        MAX_THREADS = 5
        if len(self.active_threads) >= MAX_THREADS:
            QtWidgets.QMessageBox.warning(self, "提示", "已有任务在进行中，请等待完成")
            return
        times = self.ui.spinBox.value()
        mode: str = self.ui.find_mode_combo.currentText()
        sub_mode: str = ""

        # 动态获取子模式，不再硬编码判断
        if hasattr(self.ui, 'radioButton1') and hasattr(self.ui, 'radioButton2'):
            # 检查哪个单选按钮被选中
            if self.ui.radioButton1.isChecked():
                sub_mode = self.ui.radioButton1.text()
                print(f"选择：{mode}, {sub_mode}")
            elif self.ui.radioButton2.isChecked():
                sub_mode = self.ui.radioButton2.text()
                print(f"选择：{mode}, {sub_mode}")

        # 获取隐藏窗口捕获复选框状态
        if self.ui.hidden_window_checkbox.isChecked():
            hidden_window = True
            print("="*50)
            print("       已启用后台运行模式      ")
            print("  后台模式只要不将窗口最小化就不会影响程序的运行")
            print("     后台模式不支持模拟器，请前往桌面版使用    ")
            print("="*50)
        else:
            hidden_window = False

        # 检查是否启动同步模式
        if self.sync_mode is True:
            print("="*50)
            print("       已启用窗口同步模式      ")
            print("  窗口同步模式下，程序会自动同步主窗口的点击内容到副窗口")
            print("="*50)


        print(f"获取挑战次数：{times}，模式：{mode}")

        try:
            # 创建并管理线程
            thread = threading.Thread(target=self.safe_mode_choice, args=(mode, sub_mode, times, hidden_window, self.sync_mode))
            thread.daemon = True
            with self.lock:
                if self.shutdown_flag:
                    return
                self.active_threads.append(thread)
            thread.start()
        except ValueError:
            print("请输入有效的整数挑战次数。")

    # 用锁来确保模式的选择只会选择一个
    def safe_mode_choice(self,
                         mode: str, sub_mode: str, times: int,
                         hidden_window: bool=False, sync_mode: bool=False
                         ):
        try:
            with self.lock:  # 使用with语句自动管理锁
                if self.shutdown_flag:
                    return

            # 更新window_title
            window_title = self.window_title
            # 获取同步模式类型
            sync_type = getattr(self, 'sync_type', '完全同步')

            # 读取模式对应的子配置文件
            folder_info = MODE_MAPPING.get(mode)
            if folder_info:
                if isinstance(folder_info, dict):
                    folder_name = folder_info.get(sub_mode, folder_info['default'])
                else:
                    folder_name = folder_info
                sub_config_path = os.path.join('source', folder_name, 'config.json')
                sub_config_reader = ConfigReader(sub_config_path)
                sub_config = sub_config_reader.read_config()
                if sub_config:
                    # 获取synchronizer实例，如果存在的话
                    synchronizer = self.sync if hasattr(self, 'sync') else None
                    mode_choice(mode, sub_mode, times, config=sub_config, window_title=window_title,
                                hidden_window=hidden_window, sync_mode=sync_mode, synchronizer=synchronizer,
                                sync_mode_value=self.sync_mode_value)
                else:
                    print(f"读取 {sub_config_path} 配置文件失败。")
            else:
                print('暂不支持此模式，敬请期待！')

        except Exception as e:
            error_msg = f"执行挑战时出现异常: {e}"
            print(error_msg)
            self.log_redirect.log_to_file(error_msg)
            # 修改日志文件路径
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(traceback.format_exc() + '\n')
            QtWidgets.QMessageBox.critical(self, "错误", f"执行挑战时出现异常: {e}，请检查日志文件。")

        finally:
            # 通过current_thread()获取当前线程对象
            current_thread = threading.current_thread()
            with self.lock:
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)

    # 紧急停止函数
    def emergency_stop(self):
        for thread in self.active_threads[:]:
            if thread.is_alive():
                thread.join(timeout=0.5)
                if thread.is_alive():
                    print(f"警告：线程 {thread.ident} 无法正常终止")
        print("紧急停止，退出窗口")

        with self.lock:
            self.shutdown_flag = True
            print("正在终止所有进程... ...")
            # 终止所有活动线程
            for thread in self.active_threads:
                if thread.is_alive():
                    thread.join(timeout=0.5)
                    if thread.is_alive():
                        print(f"警告：线程 {thread.ident} 无法正常终止")

        # 关闭窗口
        QtWidgets.QApplication.quit()

    def update_window_table(self):
        """
        刷新窗口表格，从 WindowSynchronizer 获取窗口信息并更新到表格中。
        """
        # 读取client.json文件并获取value的值存储到列表内
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_path = os.path.join(script_dir, 'client.json')  # 改为client.json
        title_list = []
        # 读取client.json文件
        with open(client_path, 'r', encoding='utf-8') as file:
            titles_get = json.load(file)  # 改为json.load
            for key, value in titles_get['title'].items():
                title_list.append(value)
        # 使用WindowSynchronizer类中的方法获取窗口信息
        window_synchronizer = WindowSynchronizer()
        # 传入 window_titles 参数
        window_info = window_synchronizer.get_all_windows(window_titles=title_list)
        # 将窗口信息更新到表格中
        self.update_table_with_window_info(window_info)

    def update_table_with_window_info(self, window_info: list):
        """
        使用窗口信息更新表格。
        :param window_info: 包含窗口句柄和标题的列表
        """
        # 清空表格
        self.ui.window_table.setRowCount(0)
        # 遍历窗口信息并添加到表格中
        for row, (hwnd, title) in enumerate(window_info):
            # 插入新行
            self.ui.window_table.insertRow(row)
            # 设置单元格内容
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(checkbox_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.ui.window_table.setItem(row, 0, checkbox_item)
            self.ui.window_table.setItem(row, 1, QtWidgets.QTableWidgetItem(title))
            self.ui.window_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(hwnd)))
            # 第四列：预览按钮
            preview_button = QtWidgets.QPushButton("预览")
            preview_button.setObjectName(f"preview_btn_{hwnd}")
            # 连接点击事件，传递窗口句柄
            preview_button.clicked.connect(lambda checked, h=hwnd, t=title: self.preview_window(h, t))
            # 设置按钮样式
            preview_button.setStyleSheet("padding: 2px 8px;")
            # 将按钮添加到单元格
            self.ui.window_table.setCellWidget(row, 3, preview_button)

        # 设置表格列宽
        self.ui.window_table.setColumnWidth(0, 80)   # 选择列
        self.ui.window_table.setColumnWidth(1, 250)  # 窗口信息列
        self.ui.window_table.setColumnWidth(2, 150)  # 窗口句柄列
        self.ui.window_table.setColumnWidth(3, 100)  # 预览列
        # 显示表格
        self.ui.window_table.show()
        print("表格已刷新")

    def preview_window(self, hwnd: int, title: str):
        """
        预览窗口截图

        Args:
            hwnd: 窗口句柄
            title: 窗口标题
        """
        try:
            # 创建截图保存目录
            screenshot_dir = os.path.join('logs', 'screen_shot')
            if not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir)

            # 创建窗口捕获对象
            window_capture = WindowCapture(hwnd=hwnd)

            # 捕获窗口图像
            img = window_capture.capture_window()

            if img is not None:
                # 保存截图到logs/screen_shot目录
                temp_file_path = os.path.join(screenshot_dir, f"window_preview_{hwnd}.png")
                cv2.imwrite(temp_file_path, img)

                # 创建预览窗口
                self.show_preview_dialog(title, temp_file_path)

                # print(f"窗口截图已保存: {temp_file_path}")
            else:
                print(f"无法捕获窗口 {title} ({hwnd}) 的图像")
                self.show_error_message("截图失败", "无法捕获窗口图像")
        except Exception as e:
            print(f"预览窗口时出错: {str(e)}")
            self.show_error_message("预览错误", f"发生错误: {str(e)}")
    
    def show_preview_dialog(self, title: str, image_path: str):
        """
        显示窗口截图预览
        
        Args:
            title: 窗口标题
            image_path: 截图文件路径
        """
        
        # 创建对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"窗口预览 - {title}")
        dialog.setModal(True)
        
        # 设置布局
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # 创建图像标签
        label = QtWidgets.QLabel(dialog)
        pixmap = QPixmap(image_path)
        
        if not pixmap.isNull():
            # 调整图像大小，保持比例
            max_size = 800
            scaled_pixmap = pixmap.scaled(max_size, max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled_pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            label.setText("无法加载图像")
        
        layout.addWidget(label)
        
        # 创建按钮
        button_layout = QtWidgets.QHBoxLayout()
        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # 显示对话框
        dialog.exec()
    
    def show_error_message(self, title: str, message: str):
        """
        显示错误消息
        
        Args:
            title: 对话框标题
            message: 错误消息
        """
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.exec()

    # 全选方法
    def select_all(self):
        """
        全选表格中的所有复选框。
        """
        row_count = self.ui.window_table.rowCount()
        for row in range(row_count):
            checkbox_item = self.ui.window_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(QtCore.Qt.CheckState.Checked)

    # 反选方法
    def deselect_all(self):
        """
        反选表格中的所有复选框。
        """
        row_count = self.ui.window_table.rowCount()
        for row in range(row_count):
            checkbox_item = self.ui.window_table.item(row, 0)
            if checkbox_item:
                if checkbox_item.checkState() == QtCore.Qt.CheckState.Checked:
                    checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                else:
                    checkbox_item.setCheckState(QtCore.Qt.CheckState.Checked)

    # 获取选中的行索引
    def get_selected_rows(self):
        """
        获取表格中所有被选中的行索引
        :return: 选中行索引列表
        """
        return [row for row in range(self.ui.window_table.rowCount()) if
                self.ui.window_table.item(row, 0).checkState() == QtCore.Qt.CheckState.Checked]

    # 选择主窗口的事件
    def setMainWindow(self):
        """
        设置主窗口
        """
        selected_rows = self.get_selected_rows()

        if len(selected_rows) != 1:
            print("主窗口能且仅能设置一个！\n")
            return

        row = selected_rows[0]
        hwnd = self.ui.window_table.item(row, 2).text()
        self.main_window = hwnd
        # 输出表格里的row2和row1的内容
        for row in self.get_selected_rows():
            print(f"已设置主窗口为: {self.ui.window_table.item(row, 2).text()}， {self.ui.window_table.item(row, 1).text()} \n")
            self.main_window_title = self.ui.window_table.item(row, 1).text()
        return self.main_window, self.main_window_title

    # 选择副窗口的事件
    def setSubWindows(self):
        """
        设置副窗口
        """
        selected_rows = self.get_selected_rows()

        if len(selected_rows) == 0:
            print("注意：没有选择副窗口！\n")
            return
        # 获取所有选中窗口的句柄
        sub_windows_hwnd = [self.ui.window_table.item(row, 2).text() for row in selected_rows]
        self.sub_windows = sub_windows_hwnd
        self.sub_windows_title = [self.ui.window_table.item(row, 1).text() for row in selected_rows]

        # 用for循环输出被设置为副窗口的所有窗口名称和句柄
        for row in self.get_selected_rows():
            print(f"已设置副窗口为: {self.ui.window_table.item(row, 2).text()}， {self.ui.window_table.item(row, 1).text()} \n")

        return self.sub_windows, self.sub_windows_title

    # 同步方法
    def start_sync(self):
        if not hasattr(self, 'main_window') or not hasattr(self, 'sub_windows'):
            return

        # 创建线程来执行窗口调整和同步启动操作，避免阻塞UI线程
        def sync_thread_func():
            try:
                wc = WindowChecker()
                # 将所有相关窗口句柄收集起来
                window_handles = self.sub_windows + [self.main_window]
                
                # 从设置文件中直接读取最新的窗口大小设置
                settings_file_path = os.path.join(os.path.dirname(__file__), 'settings.json')
                try:
                    with open(settings_file_path, 'r', encoding='utf-8') as f:
                        settings_data = json.load(f)
                        # 获取最新的窗口大小设置
                        target_width = settings_data.get('custom_res_width', 1404)
                        target_height = settings_data.get('custom_res_height', 834)
                        print(f"从设置文件读取窗口尺寸: {target_width}x{target_height}")
                except Exception as e:
                    print(f"读取设置文件失败：{e}")
                    # 使用默认值
                    target_width = 1404
                    target_height = 834
                    print(f"使用默认窗口尺寸: {target_width}x{target_height}")
                
                for hwnd in window_handles:
                    try:
                        # 使用获取到的窗口大小来调整窗口
                        print(f"使用窗口尺寸: {target_width}x{target_height}")
                        
                        wc.set_window_handle(hwnd)
                        current_size = wc.get_window_info()
                        if current_size:
                            current_width, current_height = current_size[2]
                            if current_width != target_width or current_height != target_height:
                                wc.resize_window(target_width, target_height, hwnd=hwnd)
                                # 添加区域尺寸校验
                                wc.set_window_handle(hwnd)
                                updated_size = wc.get_window_info()
                                if updated_size and updated_size[2] != (target_width, target_height):
                                    raise ValueError(f"窗口(句柄:{hwnd})尺寸调整失败，当前尺寸：{updated_size[2]}")
                    except Exception as e:
                        print(e)

                # 重新从设置中读取同步模式，确保使用最新的设置
                settings_file_path = os.path.join(os.path.dirname(__file__), 'settings.json')
                try:
                    with open(settings_file_path, 'r', encoding='utf-8') as f:
                        settings_data = json.load(f)
                        latest_sync_mode = settings_data.get('sync_mode', 'exactly_sync')
                except Exception as e:
                    print(f"读取设置文件失败：{e}")
                    latest_sync_mode = 'exactly_sync'
                
                self.sync = WindowSynchronizer(sync_mode=latest_sync_mode)
                # 将句柄转换为整数类型并传递
                main_hwnd = int(self.main_window)
                sub_hwnds = [int(hwnd) for hwnd in self.sub_windows]
                self.sync.set_main_and_sub_windows(self.main_window_title, self.sub_windows_title, main_hwnd, sub_hwnds)
                self.sync.set_true_enable()
                # 输出当前同步模式
                current_mode = self.sync.get_sync_mode()
                # 将英文同步模式转换为中文,使用GUI.py里的sync_mode_reverse_map
                sync_mode_reverse_map = {
                    "exactly_sync": "完全同步",
                    "program_sync": "程序同步",
                    "input_sync": "键鼠同步"
                }
                current_mode = sync_mode_reverse_map.get(current_mode, current_mode)
                print(f"当前同步模式: {current_mode}")
                # 启动鼠标和键盘监听器
                self.sync.sync_controller()
                self.sync_mode = True

                print("窗口同步已启动")
                
            except Exception as e:
                print(f"同步失败: {str(e)}")
                self.log_redirect.log_to_file(f"同步异常: {traceback.format_exc()}")
            finally:
                # 将主窗口通过句柄激活到前台
                if hasattr(self, 'main_window'):
                    try:
                        win32gui.SetForegroundWindow(int(self.main_window))
                    except:
                        pass

        # 启动同步线程
        sync_thread = threading.Thread(target=sync_thread_func)
        sync_thread.daemon = True
        sync_thread.start()
        
        # 将线程添加到管理列表
        with self.lock:
            self.active_threads.append(sync_thread)
            
        return True

    # 停止同步方法
    def stop_sync(self):
        if self.sync_mode:
            self.sync.stop_all_sync()
            self.sync_mode = False
            print("窗口同步已停止")

    def arrange_connect(self):
        # 创建线程来执行窗口排列操作，避免阻塞UI线程
        def arrange_thread_func():
            try:
                # 获取主窗口的句柄
                main_window_hwnd = int(self.main_window)
                # 获取副窗口的句柄
                sub_window_hwnd = [int(hwnd) for hwnd in self.sub_windows]

                # 调用WindowSynchronizer的arrange_windows方法
                if hasattr(self, 'sync') and self.sync:
                    self.sync.arrange_windows(main_window_hwnd, sub_window_hwnd)
                else:
                    # 如果sync对象不存在，先创建它
                    self.sync = WindowSynchronizer()
                    main_hwnd = int(self.main_window)
                    sub_hwnds = [int(hwnd) for hwnd in self.sub_windows]
                    self.sync.set_main_and_sub_windows(self.main_window_title, self.sub_windows_title, main_hwnd, sub_hwnds)
                    self.sync.arrange_windows(main_window_hwnd, sub_window_hwnd)
            except Exception as e:
                print(f"窗口排列失败: {str(e)}")
                self.log_redirect.log_to_file(f"窗口排列异常: {traceback.format_exc()}")

        # 启动窗口排列线程
        arrange_thread = threading.Thread(target=arrange_thread_func)
        arrange_thread.daemon = True
        arrange_thread.start()
        
        # 将线程添加到管理列表
        with self.lock:
            self.active_threads.append(arrange_thread)

    def check_is_update(self):
        """检查是否存在更新"""
        # 创建更新检查线程
        self.update_thread = UpdateCheckThread()
        
        # 连接信号槽
        self.update_thread.update_available.connect(self.on_update_available)
        self.update_thread.update_not_available.connect(self.on_update_not_available)
        self.update_thread.update_error.connect(self.on_update_error)
        
        # 启动线程
        self.update_thread.start()
        
        # 显示正在检查的提示
        self.checking_msg = QMessageBox(self)
        self.checking_msg.setWindowTitle("检查更新")
        self.checking_msg.setText("正在检查更新...")
        self.checking_msg.setIcon(QMessageBox.Icon.Information)
        self.checking_msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        self.checking_msg.show()
    
    def check_update_silently(self):
        """静默检查是否存在更新，不显示检查提示，只在有更新时弹窗"""
        # 创建更新检查线程
        self.update_thread = UpdateCheckThread()
        
        # 连接信号槽
        self.update_thread.update_available.connect(self.on_update_available)
        self.update_thread.update_not_available.connect(self.on_update_not_available_silent)
        self.update_thread.update_error.connect(self.on_update_error_silent)
        
        # 启动线程
        self.update_thread.start()
    
    def on_update_not_available_silent(self):
        """处理没有更新的信号（静默模式）"""
        # 静默模式下，无更新时不做任何操作
        pass
    
    def on_update_error_silent(self, error_msg: str):
        """处理更新检查错误的信号（静默模式）"""
        # 静默模式下，错误时只记录日志，不显示提示
        self.log_redirect.log_to_file(f"检查更新时出错: {error_msg}")

    def on_update_available(self, latest_version: str, latest_info: dict):
        """
        处理发现更新的信号
        
        Args:
            latest_version: 最新版本号
            latest_info: 最新版本信息
        """
        # 关闭检查提示
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None
        
        try:
            update_checker = UpdateChecker()
            update_info = update_checker.get_update_info(latest_info) or "暂无更新日志"
            
            # 将Markdown转换为HTML
            html_content = markdown_to_html(update_info)
            
            # 创建自定义更新弹窗
            update_dialog = QDialog(self)
            update_dialog.setWindowTitle("发现新的版本")
            update_dialog.setFixedSize(600, 500)  # 固定窗口大小
            update_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            
            # 创建主布局
            main_layout = QVBoxLayout(update_dialog)
            
            # 添加版本信息
            version_label = QLabel(f"最新版本：{latest_version}")
            version_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            main_layout.addWidget(version_label)
            
            # 添加更新日志标题
            log_title = QLabel("更新日志")
            log_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
            main_layout.addWidget(log_title)
            
            # 添加支持HTML的文本编辑框
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
            
            # 设置HTML内容
            log_text_edit.setHtml(html_content)
            
            main_layout.addWidget(log_text_edit, 1)  # 占满剩余空间
            
            # 添加版本信息栏
            
            # 从latest_info中获取发布日期和更新包大小
            published_at = latest_info.get('published_at', '未知')
            if published_at != '未知':
                # 格式化发布日期，从ISO格式转换为YYYY-MM-DD
                try:
                    published_at = datetime.fromisoformat(published_at).strftime('%Y-%m-%d')
                except:
                    published_at = '未知'
            
            # 获取更新包大小
            update_size = 'XX MB'
            assets = latest_info.get('assets', [])
            if assets:
                # 找到第一个资产的大小
                for asset in assets:
                    size = asset.get('size', 0)
                    if size > 0:
                        # 转换为MB
                        size_mb = round(size / (1024 * 1024), 2)
                        update_size = f"{size_mb} MB"
                        break
            
            version_info = QLabel(f"【当前版本 {APP_VERSION}】→【最新版本】{latest_version} | 发布日期: {published_at} | 更新包大小: {update_size}")
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
            
            # 添加按钮布局
            button_layout = QHBoxLayout()
            
            # 添加按钮
            btn_ignore = QPushButton("忽略本版本")
            btn_later = QPushButton("下次再说")
            btn_update = QPushButton("立即更新")
            
            # 设置按钮样式
            # 忽略本版本 - 弱操作
            btn_ignore.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #666666;
                    font-size: 12px;
                    border: 1px solid #f0f0f0;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                }
            """)
            
            # 下次再说 - 次要操作
            btn_later.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #333333;
                    font-size: 14px;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #f9f9f9;
                }
            """)
            
            # 立即更新 - 主操作
            btn_update.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            
            # 添加按钮到布局（按照从左到右：忽略此版本 -> 下次再说 -> 立即更新）
            button_layout.addWidget(btn_ignore)
            button_layout.addStretch()
            button_layout.addWidget(btn_later)
            button_layout.addStretch()
            button_layout.addWidget(btn_update)
            
            main_layout.addLayout(button_layout)
            
            # 定义按钮点击事件处理函数
            def on_btn_update_clicked():
                update_dialog.close()
                # 开始下载并更新
                self.start_update_process(latest_info)
            
            def on_btn_later_clicked():
                update_dialog.close()
            
            def on_btn_ignore_clicked():
                # 添加二次确认弹窗
                reply = QMessageBox.question(
                    update_dialog, 
                    "确认忽略", 
                    f"确定要忽略 {latest_version} 版本吗？后续将不会再提醒此版本的更新",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    update_dialog.close()
                    # 忽略此版本
                    update_manager = UpdateManager()
                    update_manager.ignore_update(latest_version)
            
            # 连接按钮信号
            btn_update.clicked.connect(on_btn_update_clicked)
            btn_later.clicked.connect(on_btn_later_clicked)
            btn_ignore.clicked.connect(on_btn_ignore_clicked)
            
            # 显示对话框
            update_dialog.exec()
        except Exception as e:
            self.on_update_error(str(e))

    def start_update_process(self, latest_info: dict):
        """
        开始更新流程：下载压缩包并启动更新程序
        
        Args:
            latest_info: 最新版本信息
        """
        try:
            # 获取下载链接
            update_manager = UpdateManager()
            download_url = update_manager.get_download_url(latest_info)
            
            if not download_url:
                QMessageBox.warning(self, "更新失败", "无法获取更新包下载链接")
                return
            
            # 创建下载进度对话框
            self.download_dialog = self.create_download_dialog()
            
            # 创建下载线程
            self.update_download_thread = UpdateDownloadThread(download_url)
            
            # 连接信号
            self.update_download_thread.download_progress.connect(self.on_download_progress)
            self.update_download_thread.download_complete.connect(self.on_download_complete)
            self.update_download_thread.download_error.connect(self.on_download_error)
            
            # 显示下载对话框
            self.download_dialog.show()
            
            # 启动下载
            self.update_download_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "更新错误", f"启动更新失败: {str(e)}")
    
    def create_download_dialog(self):
        """
        创建下载进度对话框
        :return: QDialog对象
        """
        
        dialog = QDialog(self)
        dialog.setWindowTitle("正在下载更新")
        dialog.setMinimumWidth(450)
        dialog.setModal(True)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 下载信息标签
        self.download_info_label = QLabel("正在准备下载...")
        layout.addWidget(self.download_info_label)
        
        # 进度条
        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setMinimum(0)
        self.download_progress_bar.setMaximum(100)
        self.download_progress_bar.setValue(0)
        layout.addWidget(self.download_progress_bar)
        
        # 速度和剩余时间
        self.speed_label = QLabel("下载速度: 等待中...")
        layout.addWidget(self.speed_label)
        
        # 取消按钮
        self.cancel_download_btn = QPushButton("取消")
        self.cancel_download_btn.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_download_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        dialog.setLayout(layout)
        return dialog
    
    def cancel_download(self):
        """
        取消下载
        :return: None
        """
        if hasattr(self, 'update_download_thread') and self.update_download_thread:
            self.update_download_thread.terminate()
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()
    
    def on_download_progress(self, downloaded: int, total_size: int, speed: float, remaining: float):
        """
        更新下载进度
        
        Args:
            downloaded: 已下载字节数
            total_size: 总字节数
            speed: 下载速度 (字节/秒)
            remaining: 剩余时间 (秒)
        """
        if total_size > 0:
            progress = int((downloaded / total_size) * 100)
            self.download_progress_bar.setValue(progress)
            
            # 格式化显示
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            speed_kb = speed / 1024
            speed_mb = speed_kb / 1024
            
            if speed_mb > 1:
                speed_str = f"{speed_mb:.2f} MB/s"
            else:
                speed_str = f"{speed_kb:.2f} KB/s"
            
            if remaining > 60:
                remaining_min = int(remaining // 60)
                remaining_sec = int(remaining % 60)
                remaining_str = f"{remaining_min}分{remaining_sec}秒"
            else:
                remaining_str = f"{int(remaining)}秒"
            
            self.download_info_label.setText(f"已下载: {downloaded_mb:.2f} MB / {total_mb:.2f} MB")
            self.speed_label.setText(f"下载速度: {speed_str} | 预计剩余: {remaining_str}")

    def on_download_complete(self, zip_path: str):
        """
        下载完成，启动更新程序
        
        Args:
            zip_path: 下载的压缩包路径
        """
        # 关闭下载对话框
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()
        
        try:
            update_manager = UpdateManager()
            
            # 1. 首先检查 temp 目录
            if not zip_path:
                temp_dir = os.path.join(os.getcwd(), "temp")
                if os.path.exists(temp_dir):
                    zip_files = glob.glob(os.path.join(temp_dir, "*.zip"))
                    if zip_files:
                        # 按修改时间排序，取最新的
                        zip_files.sort(key=os.path.getmtime, reverse=True)
                        zip_path = zip_files[0]
            
            # 2. 如果没找到，扫描整个项目
            if not zip_path:
                for root, dirs, files in os.walk(os.getcwd()):
                    for file in files:
                        if file.endswith(".zip"):
                            file_path = os.path.join(root, file)
                            if not zip_path or os.path.getmtime(file_path) > os.path.getmtime(zip_path):
                                zip_path = file_path
            
            if not zip_path:
                QMessageBox.critical(self, "更新失败", "未找到更新压缩包")
                return
            
            # 获取更新日志
            update_checker = UpdateChecker()
            latest_info = update_checker.get_latest_release_info()
            update_log = update_checker.get_update_info(latest_info) or ""
            
            # 启动更新程序
            if update_manager.launch_updater(zip_path, update_log, latest_info):
                # 使用紧急退出函数关闭OAT程序
                self.emergency_stop()
            else:
                QMessageBox.critical(self, "更新失败", "无法启动更新程序，请确保OAT_Updater.exe或OAT_Updater_GUI存在于程序目录下")
        except Exception as e:
            QMessageBox.critical(self, "更新错误", f"启动更新程序失败: {str(e)}")

    def on_download_error(self, error_msg: str):
        """
        下载出错
        
        Args:
            error_msg: 错误信息
        """
        # 关闭下载对话框
        if hasattr(self, 'download_dialog') and self.download_dialog:
            self.download_dialog.close()
        
        QMessageBox.critical(self, "下载失败", f"下载更新包时出错: {error_msg}")
    
    def on_update_not_available(self):
        """处理没有更新的信号"""
        # 关闭检查提示
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("当前无新的版本")
        msg_box.setText("当前版本已是最新版本")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()
    
    def on_update_error(self, error_msg: str):
        """
        处理更新检查错误的信号
        
        Args:
            error_msg: 错误信息
        """
        # 关闭检查提示
        if hasattr(self, 'checking_msg') and self.checking_msg and self.checking_msg.isVisible():
            self.checking_msg.close()
            self.checking_msg.deleteLater()
            self.checking_msg = None
        
        # 记录错误并显示友好提示
        print(f"检查更新时出错: {error_msg}")
        error_msg_box = QMessageBox(self)
        error_msg_box.setWindowTitle("检查更新失败")
        error_msg_box.setText("检查更新时发生错误，请稍后重试")
        error_msg_box.setIcon(QMessageBox.Icon.Warning)
        error_msg_box.exec()


    def sync_instruction(self):
        """
        显示同步器使用说明的对话框
        """
        instruction_text = """
        同步器使用步骤：

    1. 刷新窗口：点击"刷新窗口"按钮获取当前所有符合条件的窗口列表，如果需要自定义窗口标题，可以在client.json文件里配置
    2. 选择窗口：在表格中勾选需要参与同步的窗口
    3. 预览窗口：表格内点击"预览"按钮，会在新的窗口内显示该行窗口的图像，用于确认同步范围
    4. 设置主窗口：选择一个窗口并点击"设置主窗口"，主窗口将作为操作源
    5. 设置副窗口：选择一个或多个窗口并点击"设置副窗口"，这些窗口将跟随主窗口操作
    6. 排列窗口：点击"窗口排列"按钮，系统会自动排列所有选择的窗口
    7. 开始同步：点击"开始同步"按钮启动同步功能
    8. 停止同步：点击"停止同步"按钮停止同步功能
    
    注意事项：
    - 主窗口只能设置一个
    - 副窗口至少设置一个
    - 如需调整同步窗口，建议先停止同步
    - 窗口同步会同步对主窗口的鼠标、键盘和本程序执行挑战时的操作
    """

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("同步器使用说明")
        msg_box.setText(instruction_text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()