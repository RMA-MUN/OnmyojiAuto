import builtins
import datetime
import json
import sys
import threading
import traceback
import os
import win32gui

from typing import TextIO
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QMessageBox

from ..source import MODE_MAPPING
from .WindowSynchronizer import WindowSynchronizer
from ..source import *
from ..tools import *
from .config_manager import ConfigReader

# 创建 logs 文件夹
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 日志文件路径
LOG_FILE = os.path.join(LOGS_DIR, 'log.log')


def log_exception(exc_type, exc_value, exc_traceback):
    """
    捕获全局异常并写入日志文件，方便后续调试。
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f: TextIO  # 明确类型注解
        f.write(f"{timestamp} - Uncaught exception:\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)


# 设置全局异常处理程序
sys.excepthook = log_exception


import inspect

class LogRedirect(QtCore.QObject):
    append_log = QtCore.pyqtSignal(str)

    def __init__(self, text_browser):
        super().__init__()
        self.text_browser = text_browser
        self.append_log.connect(self._safe_append)

    # 将print函数输出的内容定向写入到textBrowser中
    def _safe_append(self, text):
        if self.text_browser:
            self.text_browser.append(text)
            scroll_bar = self.text_browser.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

    def get_caller_info(self):
        stack = inspect.stack()
        # 遍历调用栈，找到实际的print触发位置
        # 跳过当前方法(get_caller_info)、log方法、info/warn/error方法和print方法
        # 寻找第一个不在logging.py和mainGui.py中的调用点
        for i in range(3, len(stack)):
            frame = stack[i]
            module = inspect.getmodule(frame[0])
            # 检查是否为目标调用点
            if module and not module.__name__.startswith('OAT.utils.logging') and not module.__name__.startswith('OAT.tools.mainGui'):
                return f"{module.__name__}:{frame.lineno}"

        # 如果没有找到合适的调用点，回退到原逻辑
        frame = stack[3] if len(stack) > 3 else stack[-1]
        module = inspect.getmodule(frame[0])
        module_name = module.__name__ if module else 'unknown'
        return f"{module_name}:{frame.lineno}"

    def get_timestamp(self):
        # ISO 8601标准时间格式
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, message, level='INFO'):
        timestamp = self.get_timestamp()
        caller_info = self.get_caller_info()
        # 文本浏览器显示格式（保持可读性）
        display_text = f"{timestamp} - {message}"
        self.append_log.emit(display_text)

        # 日志文件JSON格式（便于后续分析）
        log_data = {
            'timestamp': timestamp,
            'level': level,
            'module': caller_info,
            'message': message
        }
        self.log_to_file(log_data)

    def info(self, message):
        self.log(message, 'INFO')

    def warn(self, message):
        self.log(message, 'WARN')

    def error(self, message):
        self.log(message, 'ERROR')

    def print(self, *args, **kwargs):
        # 保持原print功能，默认INFO级别
        self.info(' '.join(map(str, args)))

    def log_to_file(self, log_data):
        import json
        # 修改日志文件路径
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            # 写入JSON格式日志
            json.dump(log_data, f, ensure_ascii=False)
            f.write('\n')



class MainWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        # 设置表格列数为 3
        self.ui.window_table.setColumnCount(3)
        self.ui.window_table.setHorizontalHeaderLabels(["选择", "窗口信息", "窗口句柄"])
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
        # 加载外部样式表
        qss_file = QtCore.QFile("./QtSS.qss")
        if qss_file.open(QtCore.QFile.OpenModeFlag.ReadOnly | QtCore.QFile.OpenModeFlag.Text):
            style_sheet = QtCore.QTextStream(qss_file).readAll()
            self.setStyleSheet(style_sheet)
            qss_file.close()

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

        # 设置表格列宽
        self.ui.window_table.setColumnWidth(0, 150)  # 句柄列
        self.ui.window_table.setColumnWidth(1, 200)  # 标题列
        # 显示表格
        self.ui.window_table.show()
        print("表格已刷新")

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

    def sync_instruction(self):
        """
        显示同步器使用说明的对话框
        """
        instruction_text = """
        同步器使用步骤：

    1. 刷新窗口：点击"刷新窗口"按钮获取当前所有符合条件的窗口列表，如果需要自定义窗口标题，可以在client.json文件里配置
    2. 选择窗口：在表格中勾选需要参与同步的窗口
    3. 设置主窗口：选择一个窗口并点击"设置主窗口"，主窗口将作为操作源
    4. 设置副窗口：选择一个或多个窗口并点击"设置副窗口"，这些窗口将跟随主窗口操作
    5. 排列窗口：点击"窗口排列"按钮，系统会自动排列所有选择的窗口
    6. 开始同步：点击"开始同步"按钮启动同步功能
    7. 停止同步：点击"停止同步"按钮停止同步功能
    
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