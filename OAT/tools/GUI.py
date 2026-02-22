import os
import shutil
import json
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QPushButton, QAbstractItemView, QSizePolicy

from OAT.source.mode_config import mode_choice, mode_config
from OAT.tools.settings import APP_VERSION, settings_data, update_settings
from OAT.tools.settings import THEME, TRANSPARENCY, FIND_MODE, FIND_THRESHOLD

# 获取source目录的绝对路径
source_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source')
# 构建mode.json的绝对路径
mode_json_path = os.path.join(source_dir, 'mode.json')
# 加载模式配置
mode_config_data = mode_config(mode_json_path) or {}

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 构建项目根目录
project_root = os.path.dirname(os.path.dirname(current_dir))

# 当前主题设置
current_theme = THEME

class UiDialog(object):
    # 同步模式映射：中文选项 -> 英文值
    sync_mode_map = {
        "完全同步": "exactly_sync",
        "程序同步": "program_sync",
        "键鼠同步": "input_sync"
    }
    # 反向映射：英文值 -> 中文选项
    sync_mode_reverse_map = {
        "exactly_sync": "完全同步",
        "program_sync": "程序同步",
        "input_sync": "键鼠同步"
    }
    def setup_ui(self, dialog):
        """界面初始化"""
        # 主窗口基础设置
        dialog.setObjectName("dialog")
        # 获取屏幕分辨率
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            screen_geometry = screen.geometry()
            # 计算窗口大小
            width = (screen_geometry.width() // 3) + (screen_geometry.width() // 10)
            height = (screen_geometry.height() // 2) + (screen_geometry.height() // 10)
        else:
            # 如果获取不到屏幕信息，使用默认值
            width = 800
            height = 600
        dialog.resize(width, height)

        # 主布局容器
        main_container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建导航栏
        self._create_nav_bar(main_layout)

        # 页面容器
        self.stacked_widget = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        dialog.setLayout(QtWidgets.QVBoxLayout())
        dialog.layout().addWidget(main_container)

        # 保存dialog引用
        self.dialog = dialog

        # 创建各个页面
        main_page = self._create_main_page()
        sync_page = self._create_sync_page()
        settings_page = self._create_settings_page()

        # 添加页面到堆叠容器
        self.stacked_widget.addWidget(main_page)  # 首页 - 索引0
        self.stacked_widget.addWidget(sync_page)  # 窗口管理 - 索引1
        self.stacked_widget.addWidget(settings_page)  # 设置 - 索引2

        # 连接导航按钮
        self.btn_main.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_window.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.btn_settings.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        # 初始化文本翻译
        self.retranslateUi(dialog)
        # 加载样式表
        self.load_stylesheet(dialog)

        # 连接主题选择信号
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        # 设置默认主题选择
        self.theme_combo.setCurrentIndex(0 if current_theme == "light" else 1)
        
        # 连接透明度滑块信号
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)
        # 设置默认透明度值
        current_transparency = settings_data.get('transparency', 50)
        self.transparency_slider.setValue(current_transparency)
        # 设置透明度值显示标签的初始值
        self.transparency_slider_value.setText(f"{current_transparency}%")

        # 加载元对象
        QtCore.QMetaObject.connectSlotsByName(dialog)

        # 连接设置页面菜单信号
        self.menu_general.clicked.connect(lambda: self.switch_settings_page(0))
        self.menu_display.clicked.connect(lambda: self.switch_settings_page(1))
        self.menu_synchronizer.clicked.connect(lambda: self.switch_settings_page(2))
        self.menu_about.clicked.connect(lambda: self.switch_settings_page(3))

        # 连接其他信号
        self.textBrowser_2.anchorClicked.connect(self.open_link)
        self.find_mode_combo.currentIndexChanged.connect(self.on_mode_selected)
        
        # 设置默认同步模式值
        current_sync_mode = settings_data.get('sync_mode', 'exactly_sync')
        # 验证同步模式值是否有效
        if current_sync_mode not in self.sync_mode_reverse_map:
            # 弹窗提示用户配置文件被意外修改
            QtWidgets.QMessageBox.warning(
                dialog, "配置错误", "同步模式配置被意外修改，将使用默认值（完全同步）"
            )
            # 使用默认值
            current_sync_mode = 'exactly_sync'
        # 根据英文值获取对应的中文选项
        sync_mode_text = self.sync_mode_reverse_map.get(current_sync_mode, "完全同步")
        # 获取对应的索引
        sync_mode_index = self.sync_mode_combo.findText(sync_mode_text)
        if sync_mode_index != -1:
            self.sync_mode_combo.setCurrentIndex(sync_mode_index)
        else:
            # 如果找不到对应的选项，使用默认值（完全同步）
            self.sync_mode_combo.setCurrentIndex(0)

        # 初始化窗口列表
        self.initialize_window_list()

    def _create_nav_bar(self, main_layout):
        """创建导航栏"""
        self.nav_bar = QtWidgets.QWidget()
        self.nav_bar.setObjectName("nav_bar")
        self.nav_bar.setFixedHeight(36)
        nav_layout = QtWidgets.QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # 导航按钮
        self.btn_main = QtWidgets.QPushButton('首页')
        self.btn_window = QtWidgets.QPushButton('同步器')
        self.btn_settings = QtWidgets.QPushButton('设置')
        
        # 设置所有导航按钮
        nav_buttons = [self.btn_main, self.btn_window, self.btn_settings]
        for i, btn in enumerate(nav_buttons):
            btn.setFixedHeight(36)
            btn.setMinimumWidth(80)
            btn.setObjectName("nav_button")
            
            # 设置按钮大小策略为可扩展，随窗口变化而变化
            size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setSizePolicy(size_policy)
            
            nav_layout.addWidget(btn)
        
        # 添加拉伸项，使按钮左对齐，不填满整个导航栏
        nav_layout.addStretch()

        main_layout.addWidget(self.nav_bar)

    def _create_main_page(self):
        """创建首页"""
        _translate = QtCore.QCoreApplication.translate
        # 功能区域布局
        function_widget = QtWidgets.QWidget()
        function_layout = QtWidgets.QVBoxLayout(function_widget)

        # 模式选择组合框
        self.groupBox = QtWidgets.QGroupBox()
        self.groupBox.setObjectName("groupBox")
        self.groupBox.setTitle(_translate("dialog", "功能"))
        group_box_layout = QtWidgets.QVBoxLayout(self.groupBox)

        # 模式选择下拉菜单
        self.find_mode_combo = QtWidgets.QComboBox()
        self.find_mode_combo.setObjectName("find_mode_combo")
        modes = mode_choice(mode_json_path)
        if modes:
            for mode in modes:
                self.find_mode_combo.addItem(mode)
        group_box_layout.addWidget(self.find_mode_combo)

        # 挑战次数输入框
        self.spinBox = QtWidgets.QSpinBox()
        self.spinBox.setRange(1, 10000)  # 设置范围
        self.spinBox.setValue(1)  # 设置初始值
        self.spinBox.setObjectName("spinBox")
        self.label = QtWidgets.QLabel()
        self.label.setObjectName("label")
        self.label.setText(_translate("dialog", "请输入要挑战的次数"))
        group_box_layout.addWidget(self.label)
        group_box_layout.addWidget(self.spinBox)

        # 客户端选择区域
        self.label_info = QtWidgets.QLabel("选择您的登录客户端")
        self.system = QtWidgets.QWidget()
        self.system.setObjectName("system")

        # 隐藏窗口捕获复选框
        self.hidden_window_checkbox = QtWidgets.QCheckBox("启用后台模式")
        self.hidden_window_checkbox.setChecked(True)
        self.hidden_window_checkbox.setObjectName("hidden_window_checkbox")
        self.hidden_window_checkbox.setToolTip("勾选此项后，游戏窗口可以被其他程序遮挡，程序依然可以正常执行任务")

        # 创建垂直布局用于放置label_info和水平布局
        system_main_layout = QtWidgets.QVBoxLayout(self.system)
        system_main_layout.setContentsMargins(0, 10, 0, 10)  # 上下边距 10px

        # 添加label_info到垂直布局
        system_main_layout.addWidget(self.label_info)

        # 创建水平布局用于放置checkbox
        checkbox_layout = QtWidgets.QHBoxLayout()
        checkbox_layout.setSpacing(20)  # 按钮间距 20px
        checkbox_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)  # 左对齐

        self.client_choose = QtWidgets.QComboBox()
        self.client_choose.setObjectName("client_choose")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_path = os.path.join(script_dir, 'client.json')
        # 读取client.json文件
        with open(client_path, 'r', encoding='utf-8') as file:
            client_info = json.load(file)
            # 只根据配置文件中的键值对数量添加选项
            for key, value in client_info['title'].items():
                self.client_choose.addItem(value)
        # 添加下拉菜单到垂直布局
        system_main_layout.addWidget(self.client_choose)

        # 添加隐藏窗口捕获复选框（移到客户端选择下拉菜单下方）
        system_main_layout.addWidget(self.hidden_window_checkbox)

        group_box_layout.addWidget(self.system)

        # 子选项区域水平布局
        self.soul_land_options = QtWidgets.QWidget()
        self.soul_land_options.setObjectName("soul_land_options")
        soul_land_layout = QtWidgets.QHBoxLayout(self.soul_land_options)  # 水平布局
        soul_land_layout.setContentsMargins(0, 10, 0, 10)  # 上下边距 10px
        soul_land_layout.setSpacing(20)  # 按钮间距 20px
        soul_land_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)  # 左对齐

        # 创建不同御魂模式的子选项按钮（水平排列）
        self.soul_land_group = QtWidgets.QButtonGroup()
        self.radioButton1 = QtWidgets.QRadioButton("")
        self.radioButton2 = QtWidgets.QRadioButton("")
        self.soul_land_group.addButton(self.radioButton1)
        self.soul_land_group.addButton(self.radioButton2)

        soul_land_layout.addWidget(self.radioButton1)
        soul_land_layout.addWidget(self.radioButton2)

        # 默认隐藏子选项
        self.soul_land_options.hide()
        group_box_layout.addWidget(self.soul_land_options)

        # 功能按钮布局
        button_layout = QtWidgets.QGridLayout()
        self.refresh_window_btn = QtWidgets.QPushButton()
        self.refresh_window_btn.setObjectName("refresh_window_btn")
        self.refresh_window_btn.setText(_translate("dialog", "刷新窗口"))
        self.window_detect_btn = QtWidgets.QPushButton()
        self.window_detect_btn.setObjectName("window_detect_btn")
        self.window_detect_btn.setText(_translate("dialog", "窗口检测"))
        self.start_challenge_btn = QtWidgets.QPushButton()
        self.start_challenge_btn.setObjectName("start_challenge_btn")
        self.start_challenge_btn.setText(_translate("dialog", "开始挑战"))
        self.emergency_stop_btn = QtWidgets.QPushButton()
        self.emergency_stop_btn.setObjectName("emergency_stop_btn")
        self.emergency_stop_btn.setText(_translate("dialog", "紧急停止"))
        button_layout.addWidget(self.refresh_window_btn, 0, 0)
        button_layout.addWidget(self.window_detect_btn, 0, 1)
        button_layout.addWidget(self.emergency_stop_btn, 1, 0)
        button_layout.addWidget(self.start_challenge_btn, 1, 1)
        group_box_layout.addLayout(button_layout)

        function_layout.addWidget(self.groupBox)

        # 日志区
        self.groupBox_2 = QtWidgets.QGroupBox()
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setTitle(_translate("dialog", "日志"))
        log_layout = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.textBrowser = QtWidgets.QTextBrowser()
        self.textBrowser.setObjectName("textBrowser")
        log_layout.addWidget(self.textBrowser)

        # 说明区
        self.groupBox_4 = QtWidgets.QGroupBox()
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setTitle(_translate("dialog", "更新日志"))
        instruction_layout = QtWidgets.QVBoxLayout(self.groupBox_4)
        self.textBrowser_2 = QtWidgets.QTextBrowser()
        font = QtGui.QFont()
        font.setPointSize(12)
        self.textBrowser_2.setFont(font)
        self.textBrowser_2.setObjectName("textBrowser_2")
        text = self.get_text()
        self.textBrowser_2.setHtml(text)
        instruction_layout.addWidget(self.textBrowser_2)

        # 将功能区和日志区添加到主布局
        function_and_instruction_widget = QtWidgets.QWidget()
        function_and_instruction_layout = QtWidgets.QVBoxLayout(function_and_instruction_widget)
        function_and_instruction_layout.addWidget(function_widget)
        function_and_instruction_layout.addWidget(self.groupBox_4)

        # 创建主页内容容器
        main_page = QtWidgets.QWidget()
        main_page_layout = QtWidgets.QHBoxLayout(main_page)
        main_page_layout.addWidget(function_and_instruction_widget)
        main_page_layout.addWidget(self.groupBox_2)

        return main_page

    def _create_sync_page(self):
        """创建同步器页面"""
        _translate = QtCore.QCoreApplication.translate
        sync_page = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(sync_page)

        # 同步器设置区域
        self.sync_group = QtWidgets.QGroupBox()
        self.sync_group.setObjectName("sync_group")
        self.sync_group.setTitle(_translate("dialog", "同步器"))
        sync_layout = QtWidgets.QVBoxLayout(self.sync_group)  # 垂直布局
        sync_layout.setContentsMargins(15, 15, 15, 15)  # 增加内边距
        sync_layout.setSpacing(15)  # 增加组件间距

        # 同步操作按钮区域 - 使用网格布局将按钮分为两行
        sync_buttons_widget = QtWidgets.QWidget()
        sync_buttons_layout = QtWidgets.QGridLayout(sync_buttons_widget)
        sync_buttons_layout.setSpacing(12)  # 按钮间距
        sync_buttons_layout.setContentsMargins(0, 0, 0, 0)

        # 第一行按钮：窗口管理相关
        self.sync_instruction_btn = QtWidgets.QPushButton(_translate("dialog", "使用说明"))
        self.refresh_windows_btn = QPushButton(_translate("dialog", "刷新窗口"))
        self.select_all_btn = QPushButton(_translate("dialog", "全选"))
        self.invert_selection_btn = QPushButton(_translate("dialog", "反选"))
        self.capture_btn = QPushButton(_translate("dialog", "没什么用的按钮"))
        
        # 第二行按钮：同步控制相关
        self.set_main_window_btn = QPushButton(_translate("dialog", "设为主窗口"))
        self.set_sub_windows_btn = QPushButton(_translate("dialog", "设为副窗口"))
        self.start_sync_btn = QPushButton(_translate("dialog", "开始同步"))
        self.stop_sync_btn = QPushButton(_translate("dialog", "停止同步"))
        self.arrange_btn = QPushButton(_translate("dialog", "窗口排列"))

        # 设置按钮大小策略，使其能够适应窗口大小变化
        for btn in [self.sync_instruction_btn, self.refresh_windows_btn, self.select_all_btn, self.invert_selection_btn,
                    self.set_main_window_btn, self.set_sub_windows_btn, self.start_sync_btn, self.stop_sync_btn, self.arrange_btn, self.capture_btn]:
            # 设置按钮大小策略为可扩展
            size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setSizePolicy(size_policy)
            # 设置按钮最小大小
            btn.setMinimumSize(100, 28)

        # 将按钮添加到网格布局
        sync_buttons_layout.addWidget(self.sync_instruction_btn, 0, 0)
        sync_buttons_layout.addWidget(self.refresh_windows_btn, 0, 1)
        sync_buttons_layout.addWidget(self.select_all_btn, 0, 2)
        sync_buttons_layout.addWidget(self.invert_selection_btn, 0, 3)
        sync_buttons_layout.addWidget(self.arrange_btn, 0, 4)
        
        sync_buttons_layout.addWidget(self.set_main_window_btn, 1, 0)
        sync_buttons_layout.addWidget(self.set_sub_windows_btn, 1, 1)
        sync_buttons_layout.addWidget(self.start_sync_btn, 1, 2)
        sync_buttons_layout.addWidget(self.stop_sync_btn, 1, 3)
        sync_buttons_layout.addWidget(self.capture_btn, 1, 4)
        
        # 为每个按钮所在的列设置相同的拉伸因子，使按钮能够均匀分配可用空间
        for i in range(5):
            sync_buttons_layout.setColumnStretch(i, 1)

        # 窗口列表表格
        self.window_table = QtWidgets.QTableWidget()
        self.window_table.setColumnCount(4)  # 四列
        self.window_table.setHorizontalHeaderLabels([_translate("dialog", "选择"), _translate("dialog", "窗口信息"), _translate("dialog", "窗口句柄"), _translate("dialog", "预览")])
        self.window_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # 第一列自适应
        self.window_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)  # 第二列拉伸
        self.window_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # 第三列自适应
        self.window_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.window_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.window_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive) # 第四列较大，但不会拉伸其他列

        # 设置表格高度策略，使其能够自适应窗口大小
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.window_table.setSizePolicy(size_policy)
        self.window_table.setMinimumHeight(300)  # 设置最小高度

        # 组装同步器布局
        sync_layout.addWidget(sync_buttons_widget)  # 按钮在上
        sync_layout.addWidget(self.window_table)    # 表格在中

        # 将同步器设置加入页面布局
        settings_layout.addWidget(self.sync_group)      # 同步器设置
        settings_layout.addStretch()  # 底部留白

        return sync_page

    def _create_settings_page(self):
        """创建设置页面"""
        settings_page = QtWidgets.QWidget()
        settings_page.setObjectName("settings_page")
        settings_layout = QtWidgets.QHBoxLayout(settings_page)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(0)

        # 左侧菜单栏
        self.settings_menu = QtWidgets.QWidget()
        self.settings_menu.setObjectName("settings_menu")
        self.settings_menu.setFixedWidth(160)
        menu_layout = QtWidgets.QVBoxLayout(self.settings_menu)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(0)

        # 菜单项
        self.menu_general = QtWidgets.QPushButton("常规设置")
        self.menu_general.setObjectName("settings_menu_item")
        self.menu_general.setCheckable(True)
        self.menu_general.setChecked(True)
        
        self.menu_display = QtWidgets.QPushButton("显示设置")
        self.menu_display.setObjectName("settings_menu_item")
        self.menu_display.setCheckable(True)

        self.menu_synchronizer = QtWidgets.QPushButton("同步器设置")
        self.menu_synchronizer.setObjectName("settings_menu_item")
        self.menu_synchronizer.setCheckable(True)
        
        self.menu_about = QtWidgets.QPushButton("关于")
        self.menu_about.setObjectName("settings_menu_item")
        self.menu_about.setCheckable(True)

        # 添加菜单项到布局
        menu_layout.addWidget(self.menu_general)
        menu_layout.addWidget(self.menu_display)
        menu_layout.addWidget(self.menu_synchronizer)
        menu_layout.addWidget(self.menu_about)
        menu_layout.addStretch()

        # 右侧内容区域
        self.settings_content = QtWidgets.QStackedWidget()
        self.settings_content.setObjectName("settings_content")

        # 创建设置子页面
        general_page = self._create_general_settings_page()
        display_page = self._create_display_settings_page()
        sync_settings_page = self._create_sync_settings_page()
        about_page = self._create_about_page()

        # 添加所有页面到内容区域
        self.settings_content.addWidget(general_page)      # 索引0
        self.settings_content.addWidget(display_page)      # 索引1
        self.settings_content.addWidget(sync_settings_page)# 索引2
        self.settings_content.addWidget(about_page)        # 索引3

        # 添加左侧菜单和右侧内容到设置页面
        settings_layout.addWidget(self.settings_menu)
        settings_layout.addWidget(self.settings_content)

        return settings_page

    def _create_general_settings_page(self):
        """创建常规设置页面"""
        general_page = QtWidgets.QWidget()
        general_page.setStyleSheet("background-color: transparent;")
        general_layout = QtWidgets.QVBoxLayout(general_page)
        general_layout.setContentsMargins(20, 20, 20, 20)

        general_group = QtWidgets.QGroupBox("常规设置")
        general_form = QtWidgets.QFormLayout()

        # 添加挑战执行完毕后关闭程序的复选框
        self.close_program_checkbox = QtWidgets.QCheckBox("挑战执行完毕后关闭程序")
        self.close_program_checkbox.setObjectName("close_program_checkbox")
        # 加载设置值
        self.close_program_checkbox.setChecked(settings_data.get('close_program_after_challenge', False))
        # 连接信号
        self.close_program_checkbox.stateChanged.connect(self.on_close_program_setting_changed)
        general_form.addRow(self.close_program_checkbox)

        # 添加挑战执行完毕后关闭游戏的复选框
        self.close_game_checkbox = QtWidgets.QCheckBox("挑战执行完毕后关闭游戏")
        self.close_game_checkbox.setObjectName("close_game_checkbox")
        # 加载设置值
        self.close_game_checkbox.setChecked(settings_data.get('close_game_after_challenge', False))
        # 连接信号
        self.close_game_checkbox.stateChanged.connect(self.on_close_game_setting_changed)
        general_form.addRow(self.close_game_checkbox)

        # 图像识别相关配置
        self.recognition_mode_combo = QtWidgets.QComboBox()
        self.recognition_mode_combo.setObjectName("find_mode")
        self.recognition_mode_combo.addItem("opencv", "opencv")
        self.recognition_mode_combo.addItem("pyscreeze", "pyscreeze")
        # 加载设置值
        find_mode_setting = settings_data.get('find_mode', 'opencv')
        find_mode_index = self.recognition_mode_combo.findText(find_mode_setting)
        if find_mode_index != -1:
            self.recognition_mode_combo.setCurrentIndex(find_mode_index)
        else:
            self.recognition_mode_combo.setCurrentIndex(0)
        general_form.addRow("识别模式:", self.recognition_mode_combo)
        # 连接识别模式的信号
        self.recognition_mode_combo.currentTextChanged.connect(self.save_find_img_mode_settings)

        # 图像识别相似度阈值
        self.img_find_threshold = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.img_find_threshold.setObjectName("img_find_threshold")
        self.img_find_threshold.setMinimum(70)  # 最小识别阙值
        self.img_find_threshold.setMaximum(100)  # 最大识别阙值
        self.img_find_threshold.setSingleStep(1)
        # 加载设置值
        find_value_setting = settings_data.get('find_value', 85)
        self.img_find_threshold.setValue(find_value_setting)
        self.find_value_label = QtWidgets.QLabel("识别阙值:")
        self.find_value_label.setObjectName("find_value_label")
        self.find_value_label_value = QtWidgets.QLabel(f"{find_value_setting}%")
        self.find_value_label_value.setObjectName("find_value_label_value")
        self.find_value_label_value.setMinimumWidth(50)
        self.find_value_label_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # 当前阙值显示
        find_threshold_widget = QtWidgets.QWidget()
        find_threshold_layout = QtWidgets.QHBoxLayout(find_threshold_widget)
        find_threshold_layout.setContentsMargins(0, 0, 0, 0)
        find_threshold_layout.setSpacing(10)
        find_threshold_layout.addWidget(self.img_find_threshold)
        find_threshold_layout.addWidget(self.find_value_label_value)

        general_form.addRow(self.find_value_label, find_threshold_widget)
        # 连接相似度阈值滑块信号
        self.img_find_threshold.valueChanged.connect(self.save_find_value_settings)
        self.img_find_threshold.valueChanged.connect(lambda value: self.find_value_label_value.setText(f"{value}%"))

        self.check_update_check = QtWidgets.QPushButton("检查更新")
        self.check_update_check.setObjectName("settings_button")
        general_form.addRow(self.check_update_check)

        # 添加清理缓存按钮
        self.clear_cache_button = QtWidgets.QPushButton("清理缓存")
        self.clear_cache_button.setObjectName("clear_cache_button")
        general_form.addRow(self.clear_cache_button)
        # 连接清理缓存按钮信号
        self.clear_cache_button.clicked.connect(self.clean_cache)

        general_group.setLayout(general_form)
        general_layout.addWidget(general_group)
        general_layout.addStretch()

        return general_page

    def _create_display_settings_page(self):
        """创建显示设置页面"""
        display_page = QtWidgets.QWidget()
        display_page.setStyleSheet("background-color: transparent;")
        display_layout = QtWidgets.QVBoxLayout(display_page)
        display_layout.setContentsMargins(20, 20, 20, 20)
        
        display_group = QtWidgets.QGroupBox("显示设置")
        display_form = QtWidgets.QFormLayout()
        
        self.theme_label = QtWidgets.QLabel("主题:")
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.setObjectName("settings_combo")
        self.theme_combo.addItems(["亮色", "深色"])
        display_form.addRow(self.theme_label, self.theme_combo)

        # 添加透明度滑块和值显示标签
        transparency_widget = QtWidgets.QWidget()
        transparency_layout = QtWidgets.QHBoxLayout(transparency_widget)
        transparency_layout.setContentsMargins(0, 0, 0, 0)
        transparency_layout.setSpacing(10)
        
        self.transparency_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.transparency_slider.setObjectName("transparency_slider")
        self.transparency_slider.setMinimum(20)  # 最小透明度20%
        self.transparency_slider.setMaximum(100)  # 最大透明度100%
        self.transparency_slider.setSingleStep(1)
        # 设置默认值为50%
        self.transparency_slider.setValue(50)
        
        # 添加透明度值显示标签
        self.transparency_slider_value = QtWidgets.QLabel("50%")
        self.transparency_slider_value.setObjectName("transparency_slider_value")
        self.transparency_slider_value.setMinimumWidth(50)
        self.transparency_slider_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_slider_value)
        
        self.transparency_label = QtWidgets.QLabel("透明度:")
        display_form.addRow(self.transparency_label, transparency_widget)

        display_group.setLayout(display_form)
        display_layout.addWidget(display_group)
        display_layout.addStretch()

        return display_page

    def _create_sync_settings_page(self):
        """创建同步器设置页面"""
        sync_settings_page = QtWidgets.QWidget()
        sync_settings_page.setStyleSheet("background-color: transparent;")
        sync_settings_layout = QtWidgets.QVBoxLayout(sync_settings_page)
        sync_settings_layout.setContentsMargins(20, 20, 20, 20)
        sync_settings_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        sync_group = QtWidgets.QGroupBox("同步器设置")
        sync_form = QtWidgets.QFormLayout()

        # 同步模式选择: 完全同步、程序同步、键鼠同步
        # 完全同步: 自动同步所有操作
        # 程序同步: 仅同步程序操作
        # 键鼠同步: 仅同步键鼠操作
        self.sync_mode_label = QtWidgets.QLabel("同步模式:")
        self.sync_mode_combo = QtWidgets.QComboBox()
        self.sync_mode_combo.setObjectName("settings_combo")
        self.sync_mode_combo.addItems(["完全同步", "程序同步", "键鼠同步"])
        sync_form.addRow(self.sync_mode_label, self.sync_mode_combo)
        # 连接信号
        self.sync_mode_combo.currentIndexChanged.connect(self.on_sync_mode_changed)

        sync_group.setLayout(sync_form)
        sync_settings_layout.addWidget(sync_group)
        sync_settings_layout.addStretch()

        return sync_settings_page

    def _create_about_page(self):
        """创建关于页面"""
        about_page = QtWidgets.QWidget()
        about_page.setStyleSheet("background-color: transparent;")
        about_layout = QtWidgets.QVBoxLayout(about_page)
        about_layout.setContentsMargins(20, 20, 20, 20)
        about_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        about_label = QtWidgets.QLabel("OAT 阴阳师自动化工具")
        about_label.setObjectName("about_title")
        about_layout.addWidget(about_label)

        version_label = QtWidgets.QLabel(f"版本: {APP_VERSION}")
        version_label.setObjectName("about_text")
        about_layout.addWidget(version_label)
        
        author_label = QtWidgets.QLabel("作者: RMA-MUN")
        author_label.setObjectName("about_text")
        about_layout.addWidget(author_label)

        connect_author_label = QtWidgets.QLabel("联系作者: n3032747608@163.com")
        connect_author_label.setObjectName("about_text")
        about_layout.addWidget(connect_author_label)

        warning_text = QtWidgets.QLabel("免责声明:\n  1. 本工具仅供学习交流，禁止商用及违规使用；\n  2. 使用风险自负，开发者不承担任何责任；\n  3. 请勿违反游戏运营方相关规定。 ")
        warning_text.setObjectName("about_text")
        about_layout.addWidget(warning_text)

        link_label = QtWidgets.QLabel("<a href='https://github.com/RMA-MUN/OnmyoujiAuto'>GitHub 仓库</a>")
        link_label.setObjectName("about_link")
        link_label.setOpenExternalLinks(True)
        about_layout.addWidget(link_label)

        return about_page

    def switch_settings_page(self, page_index: int):
        """
        切换设置页面的内容
        
        Args:
            page_index: 要切换的页面索引
        """
        # 取消所有菜单项的选中状态
        for btn in [self.menu_general, self.menu_display, self.menu_synchronizer, self.menu_about]:
            btn.setChecked(False)
        
        # 选中当前点击的菜单项
        if page_index == 0:
            self.menu_general.setChecked(True)
        elif page_index == 1:
            self.menu_display.setChecked(True)
        elif page_index == 2:
            self.menu_synchronizer.setChecked(True)
        elif page_index == 3:
            self.menu_about.setChecked(True)
        
        # 切换内容页面
        self.settings_content.setCurrentIndex(page_index)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("dialog", "OAT"))

    def load_stylesheet(self, Dialog):
        try:
            # 根据当前主题选择样式表文件
            theme_file = "QtSS.qss" if current_theme == "light" else "QtSS_dark.qss"
            # 构建样式表文件的绝对路径
            qss_path = os.path.join(current_dir, theme_file)
            with open(qss_path, "r", encoding="utf-8") as f:
                Dialog.setStyleSheet(f.read())
        except Exception as e:
            print(f"样式表加载失败: {str(e)}")

    def save_setting(self, key: str, value: Any, update_global: bool = False, global_var_name: str = None, global_var_value: Any = None):
        """
        保存设置到配置文件
        
        Args:
            key: 设置的键名
            value: 设置的值
            update_global: 是否更新全局变量
            global_var_name: 全局变量名
            global_var_value: 全局变量值
        """
        # 更新全局变量（如果需要）
        if update_global and global_var_name:
            globals()[global_var_name] = global_var_value
        
        # 使用settings.py中的update_settings函数保存配置
        update_settings(key, value)

    def save_theme_setting(self, theme: str):
        """
        保存主题设置到配置文件
        
        Args:
            theme: 主题名称 (light/dark)
        """
        self.save_setting('theme', theme, True, 'current_theme', theme)

    def save_transparency_setting(self, transparency: int):
        """
        保存透明度设置到配置文件
        
        Args:
            transparency: 透明度值 (50-100)
        """
        self.save_setting('transparency', transparency)

    def save_close_program_setting(self, close_program: bool):
        """
        保存挑战执行完毕后关闭程序的设置到配置文件
        
        Args:
            close_program: 是否关闭程序
        """
        self.save_setting('close_program_after_challenge', close_program)

    def save_close_game_setting(self, close_game: bool):
        """
        保存挑战执行完毕后关闭游戏的设置到配置文件
        
        Args:
            close_game: 是否关闭游戏
        """
        self.save_setting('close_game_after_challenge', close_game)

    def save_find_value_settings(self, find_value: int ):
        """
        保存识别阙值设置到配置文件

        Args:
            find_value: 识别阙值 (85-100)
        """
        self.save_setting('find_value', find_value)

    def save_find_img_mode_settings(self, find_mode: str="opencv"):
        """
        保存识别模式设置到配置文件

        Args:
            find_mode: 识别模式(opencv/pyscreeze)
        """
        self.save_setting('find_mode', find_mode)


    def on_close_program_setting_changed(self, state: int):
        """
        处理挑战执行完毕后关闭程序的设置变化事件
        
        Args:
            state: 复选框状态 (2表示选中, 0表示未选中)
        """
        close_program = bool(state)
        self.save_close_program_setting(close_program)

    def on_close_game_setting_changed(self, state: int):
        """
        处理挑战执行完毕后关闭游戏的设置变化事件
        
        Args:
            state: 复选框状态 (2表示选中, 0表示未选中)
        """
        close_game = bool(state)
        self.save_close_game_setting(close_game)

    def on_theme_changed(self, index: int):
        """
        处理主题选择变化事件
        
        Args:
            index: 主题组合框的索引
        """
        theme = "light" if index == 0 else "dark"
        self.save_theme_setting(theme)
        
        # 重新加载样式表
        if hasattr(self, 'dialog'):
            self.load_stylesheet(self.dialog)

    def on_transparency_changed(self, value: int):
        """
        处理透明度滑块变化事件
        
        Args:
            value: 透明度值 (20-100)
        """
        # 保存透明度设置
        self.save_transparency_setting(value)
        
        # 更新透明度值显示标签
        self.transparency_slider_value.setText(f"{value}%")
        
        # 计算透明度因子 (0.2-1.0)
        opacity = value / 100.0
        
        # 更新组件透明度
        if hasattr(self, 'dialog'):
            try:
                # 读取原始样式表
                theme_file = "QtSS.qss" if current_theme == "light" else "QtSS_dark.qss"
                qss_path = os.path.join(current_dir, theme_file)
                
                with open(qss_path, "r", encoding="utf-8") as f:
                    original_stylesheet = f.read()
                
                # 构建新的样式表，只修改组件的透明度
                new_stylesheet = ""
                lines = original_stylesheet.split('\n')
                
                for line in lines:
                    # 处理包含 rgba 的行
                    if 'rgba(' in line:
                        # 查找 rgba(...) 模式
                        import re
                        rgba_pattern = r'rgba\((\d+,\s*\d+,\s*\d+),\s*[^)]*\)'
                        
                        def replace_opacity(match):
                            color_part = match.group(1)
                            return f'rgba({color_part}, {opacity})'
                        
                        # 替换透明度值
                        modified_line = re.sub(rgba_pattern, replace_opacity, line)
                        new_stylesheet += modified_line + '\n'
                    else:
                        new_stylesheet += line + '\n'
                
                # 应用新的样式表
                self.dialog.setStyleSheet(new_stylesheet)
                
                # 强制刷新界面
                self.dialog.repaint()
            except Exception as e:
                # 仅在开发时启用错误输出
                # print(f"透明度设置失败: {str(e)}")
                # import traceback
                # traceback.print_exc()
                pass
    
    def on_sync_mode_changed(self, index: int):
        """
        处理同步模式选择变化事件
        
        Args:
            index: 同步模式组合框的索引
        """
        # 获取选择的中文选项
        sync_mode_text = self.sync_mode_combo.currentText()
        # 获取对应的英文值
        sync_mode_value = self.sync_mode_map.get(sync_mode_text, 'exactly_sync')
        # 保存同步模式设置
        self.save_setting('sync_mode', sync_mode_value)

    def clean_cache(self):
        """清理缓存，删除logs/screen_shot文件夹，然后给log.log里的内容都替换为一个空字符串"""
        print("cleaning cache")
        try:
            # 获取项目根目录的logs文件夹路径
            logs_dir = os.path.join(project_root, "logs")
            # 检查log文件夹是否存在，如果存在，则删除
            if os.path.exists(logs_dir):
                # 构建screen_shot文件夹路径
                screen_shot_dir = os.path.join(logs_dir, "screen_shot")
                # 检查screen_shot文件夹是否存在，如果存在，则删除
                if os.path.exists(screen_shot_dir):
                    shutil.rmtree(screen_shot_dir)
                    print("screen_shot文件夹已清理")
                # 构建log.log文件路径
                log_file_path = os.path.join(logs_dir, "log.log")
                # 检查log.log文件是否存在，如果存在，则清空内容
                if os.path.exists(log_file_path):
                    with open(log_file_path, "w", encoding="utf-8") as f:
                        f.write("")
                    print("log.log文件已清理")
        except Exception as e:
            print(f"清理缓存时出错: {e}")


    def open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def get_text(self): 
         text = '''
            <div style="line-height: 1.0; margin: 0; padding: 0;">
                <span style="margin: 0;">1.增加同步器模式自选,可在同步设置页面选择</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">2.增加挑战结束后自动关闭游戏和程序功能</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">3.增加缓存清理功能</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">4.增加组件透明度设置</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">5.修复已知bug</span>
            </div>
         '''
         return text

    def on_mode_selected(self, index):
        """处理模式选择事件，根据mode.json动态显示子选项"""
        # 隐藏子选项
        self.soul_land_options.hide()
        self.soul_land_group.setExclusive(False)
        self.radioButton1.setChecked(False)
        self.radioButton2.setChecked(False)
        self.soul_land_group.setExclusive(True)
        
        # 如果没有有效的模式配置，直接返回
        if not mode_config_data or index < 0 or index >= self.find_mode_combo.count():
            return
        
        # 获取当前选择的模式名称
        mode_name = self.find_mode_combo.currentText()
        
        # 从配置中查找当前模式的配置
        mode_data = mode_config_data.get(mode_name)
        
        # 如果模式配置是字典类型且包含子选项（排除default）
        if isinstance(mode_data, dict) and len(mode_data) > 1:
            # 获取子选项列表，排除'default'
            sub_modes = [key for key in mode_data.keys() if key != 'default']
            
            # 如果有子选项，显示并设置
            if len(sub_modes) >= 1:
                self.radioButton1.setText(sub_modes[0])
                
            if len(sub_modes) >= 2:
                self.radioButton2.setText(sub_modes[1])
            else:
                # 如果只有一个子选项，隐藏第二个单选按钮或设置为空
                self.radioButton2.hide()
            
            # 显示子选项区域
            self.soul_land_options.show()

    # 同步器功能实现
    def initialize_window_list(self):
        """初始化窗口列表（示例数据）"""
        self.window_table.setRowCount(0)
        example_windows = [
            {"id": "1", "title": "游戏名字几个字"},
            {"id": "2", "title": "游戏名字几个字"},
            {"id": "3", "title": "游戏名字几个字"}
        ]
        for i, window in enumerate(example_windows):
            self.window_table.insertRow(i)
            # 第一列放置复选框
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            checkbox.setObjectName(f"window_checkbox_{window['id']}")
            self.window_table.setCellWidget(i, 0, checkbox)
            # 第二列放置窗口信息
            info_item = QtWidgets.QTableWidgetItem(f"{window['title']}")
            self.window_table.setItem(i, 1, info_item)