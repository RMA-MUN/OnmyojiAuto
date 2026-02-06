import builtins
import json
import os
import threading
import traceback

import win32gui
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QMessageBox

from .WindowSynchronizer import WindowSynchronizer
from .config_manager import ConfigReader
from .thread_manager import UpdateCheckThread
from ..config.check_update import UpdateChecker
from ..config.update_manager import UpdateManager
from ..source import *
from ..source import MODE_MAPPING
from ..tools import *
from ..utils.error_handler import setup_global_exception_handler, LOG_FILE
from ..utils.logging import LogRedirect

# 设置全局异常处理程序
setup_global_exception_handler()

class MainWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        # 设置表格列数为 4
        self.ui.window_table.setColumnCount(4)
        self.ui.window_table.setHorizontalHeaderLabels(["选择", "窗口信息", "窗口句柄", "预览"])
        # 预览列显示的是一个链接，点击可以预览窗口截图
        self.main_config_reader = ConfigReader('config/config.yaml')
        self.main_config = self.main_config_reader.read_config()

        self.sync = WindowSynchronizer()
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
        self.ui.comboBox.currentTextChanged.connect(self.handle_mode_change)
        self.ui.pushButton.clicked.connect(self.window_detection)
        self.ui.pushButton_2.clicked.connect(self.start_challenge)
        self.ui.pushButton_3.clicked.connect(self.emergency_stop)
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
        self.ui.pushButton.setShortcut("Ctrl+W")
        self.ui.pushButton_3.setShortcut("Ctrl+E")
        self.ui.pushButton_2.setShortcut("Return")
        self.ui.pushButton4.setShortcut("Ctrl+R")

        # 设置工具提示
        self.ui.pushButton4.setToolTip("刷新窗口 (Ctrl+R)")
        self.ui.pushButton.setToolTip("窗口检测 (Ctrl+W)")
        self.ui.pushButton_2.setToolTip("开始挑战 (Enter)")
        self.ui.pushButton_3.setToolTip("紧急停止 (Ctrl+E)")

        # 定向输出print
        self.log_redirect = LogRedirect(self.ui.textBrowser)
        builtins.print = self.log_redirect.print

        # 线程管理
        self.active_threads = []
        self.shutdown_flag = False

        # 创建线程锁
        self.lock = threading.Lock()

        # 刷新窗口按钮
        self.ui.pushButton4.clicked.connect(self.refresh_window)

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
        self.ui.comboBox.setCurrentIndex(0)
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

    def handle_mode_change(self, mode: str):
        print(f"选择模式：{mode}")

    def window_detection(self, *args):
        print("客户端窗口检测：")
        # 使用更新后的 window_title
        automation = OnmyjiAutomation(self.window_title)
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
        mode: str = self.ui.comboBox.currentText()
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
                                hidden_window=hidden_window, sync_mode=sync_mode, synchronizer=synchronizer)
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
        from OAT.tools.get_DC import WindowCapture
        import os
        import tempfile
        import cv2
        
        try:
            # 创建临时目录存储截图
            temp_dir = tempfile.gettempdir()
            
            # 创建窗口捕获对象
            window_capture = WindowCapture(hwnd=hwnd)
            
            # 捕获窗口图像
            img = window_capture.capture_window()
            
            if img is not None:
                # 保存截图
                temp_file_path = os.path.join(temp_dir, f"window_preview_{hwnd}.png")
                cv2.imwrite(temp_file_path, img)
                
                # 创建预览窗口
                self.show_preview_dialog(title, temp_file_path)
                
                print(f"窗口截图已保存: {temp_file_path}")
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
                for hwnd in window_handles:
                    try:
                        # 直接使用句柄调整窗口大小
                        target_width = 1404
                        target_height = 834
                        wc.set_window_handle(hwnd)
                        current_size = wc.get_window_info()
                        if current_size:
                            current_width, current_height = current_size[2]
                            if current_width != target_width or current_height != target_height:
                                wc.resize_window(target_width, target_height, hwnd=hwnd)
                                # 添加区域尺寸校验
                                wc.set_window_handle(hwnd)
                                updated_size = wc.get_window_info()
                                if updated_size[2] != (target_width, target_height):
                                    raise ValueError(f"窗口(句柄:{hwnd})尺寸调整失败，当前尺寸：{updated_size[2]}")
                    except Exception as e:
                        print(e)

                self.sync = WindowSynchronizer()
                # 将句柄转换为整数类型并传递
                main_hwnd = int(self.main_window)
                sub_hwnds = [int(hwnd) for hwnd in self.sub_windows]
                self.sync.set_main_and_sub_windows(self.main_window_title, self.sub_windows_title, main_hwnd, sub_hwnds)
                self.sync.set_true_enable()
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
            
            # 创建并配置消息框
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("发现新的版本")
            msg_box.setText(f"最新版本：{latest_version}\n\n更新日志：\n{update_info.replace('# 更新日志', '').strip()}\n\n自动更新功能敬请期待")
            msg_box.setIcon(QMessageBox.Icon.Information)
            
            # 添加自定义按钮
            btn_update = msg_box.addButton("前往更新", QMessageBox.ButtonRole.AcceptRole)
            btn_later = msg_box.addButton("下次再说", QMessageBox.ButtonRole.RejectRole)
            btn_ignore = msg_box.addButton("忽略本版本", QMessageBox.ButtonRole.ActionRole)
            
            # 执行消息框
            msg_box.exec()
            
            # 处理用户选择
            clicked_button = msg_box.clickedButton()
            if clicked_button == btn_update:
                # 前往更新页面
                if 'html_url' in latest_info:
                    QDesktopServices.openUrl(QUrl(latest_info['html_url']))
            elif clicked_button == btn_ignore:
                # 忽略此版本
                update_manager = UpdateManager()
                update_manager.ignore_update(latest_version)
        except Exception as e:
            self.on_update_error(str(e))
    
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
        msg_box = None