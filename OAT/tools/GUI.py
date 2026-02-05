import json

import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QPushButton, QAbstractItemView, QSizePolicy

from OAT.source.mode_config import mode_choice, mode_config

# 获取source目录的绝对路径
source_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source')
# 构建mode.json的绝对路径
mode_json_path = os.path.join(source_dir, 'mode.json')
# 加载模式配置
mode_config_data = mode_config(mode_json_path) or {}

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        """界面初始化"""
        # 主窗口基础设置
        Dialog.setObjectName("Dialog")
        # 获取屏幕分辨率
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        # 计算窗口大小
        width = (screen_geometry.width() // 3) + (screen_geometry.width() // 10)
        height = (screen_geometry.height() // 2) + (screen_geometry.height() // 10)
        Dialog.resize(width, height)

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
        
        Dialog.setLayout(QtWidgets.QVBoxLayout())
        Dialog.layout().addWidget(main_container)

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
        self.retranslateUi(Dialog)
        # 加载样式表
        self.load_stylesheet(Dialog)

        # 加载元对象
        QtCore.QMetaObject.connectSlotsByName(Dialog)

        # 连接设置页面菜单信号
        self.menu_general.clicked.connect(lambda: self.switch_settings_page(0))
        self.menu_display.clicked.connect(lambda: self.switch_settings_page(1))
        self.menu_synchronizer.clicked.connect(lambda: self.switch_settings_page(2))
        self.menu_about.clicked.connect(lambda: self.switch_settings_page(3))

        # 连接其他信号
        self.textBrowser_2.anchorClicked.connect(self.open_link)
        self.comboBox.currentIndexChanged.connect(self.on_mode_selected)

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
            nav_layout.addWidget(btn)
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
        self.groupBox.setTitle(_translate("Dialog", "功能"))
        group_box_layout = QtWidgets.QVBoxLayout(self.groupBox)

        # 模式选择下拉菜单
        self.comboBox = QtWidgets.QComboBox()
        self.comboBox.setObjectName("comboBox")
        modes = mode_choice(mode_json_path)
        if modes:
            for mode in modes:
                self.comboBox.addItem(mode)
        group_box_layout.addWidget(self.comboBox)

        # 挑战次数输入框
        self.spinBox = QtWidgets.QSpinBox()
        self.spinBox.setRange(1, 10000)  # 设置范围
        self.spinBox.setValue(1)  # 设置初始值
        self.spinBox.setObjectName("spinBox")
        self.label = QtWidgets.QLabel()
        self.label.setObjectName("label")
        self.label.setText(_translate("Dialog", "请输入要挑战的次数"))
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
        self.pushButton4 = QtWidgets.QPushButton()
        self.pushButton4.setObjectName("pushButton4")
        self.pushButton4.setText(_translate("Dialog", "刷新窗口"))
        self.pushButton = QtWidgets.QPushButton()
        self.pushButton.setObjectName("pushButton")
        self.pushButton.setText(_translate("Dialog", "窗口检测"))
        self.pushButton_2 = QtWidgets.QPushButton()
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_2.setText(_translate("Dialog", "开始挑战"))
        self.pushButton_3 = QtWidgets.QPushButton()
        self.pushButton_3.setObjectName("pushButton_3")
        self.pushButton_3.setText(_translate("Dialog", "紧急停止"))
        button_layout.addWidget(self.pushButton4, 0, 0)
        button_layout.addWidget(self.pushButton, 0, 1)
        button_layout.addWidget(self.pushButton_3, 1, 0)
        button_layout.addWidget(self.pushButton_2, 1, 1)
        group_box_layout.addLayout(button_layout)

        function_layout.addWidget(self.groupBox)

        # 日志区
        self.groupBox_2 = QtWidgets.QGroupBox()
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setTitle(_translate("Dialog", "日志"))
        log_layout = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.textBrowser = QtWidgets.QTextBrowser()
        self.textBrowser.setObjectName("textBrowser")
        log_layout.addWidget(self.textBrowser)

        # 说明区
        self.groupBox_4 = QtWidgets.QGroupBox()
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setTitle(_translate("Dialog", "更新日志"))
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
        self.sync_group.setTitle(_translate("Dialog", "同步器"))
        sync_layout = QtWidgets.QVBoxLayout(self.sync_group)  # 垂直布局
        sync_layout.setContentsMargins(15, 15, 15, 15)  # 增加内边距
        sync_layout.setSpacing(15)  # 增加组件间距

        # 同步操作按钮区域 - 使用网格布局将按钮分为两行
        sync_buttons_widget = QtWidgets.QWidget()
        sync_buttons_layout = QtWidgets.QGridLayout(sync_buttons_widget)
        sync_buttons_layout.setSpacing(12)  # 按钮间距
        sync_buttons_layout.setContentsMargins(0, 0, 0, 0)

        # 第一行按钮：窗口管理相关
        self.sync_instruction_btn = QtWidgets.QPushButton(_translate("Dialog", "使用说明"))
        self.refresh_windows_btn = QPushButton(_translate("Dialog", "刷新窗口"))
        self.select_all_btn = QPushButton(_translate("Dialog", "全选"))
        self.invert_selection_btn = QPushButton(_translate("Dialog", "反选"))
        self.capture_btn = QPushButton(_translate("Dialog", "窗口截图"))
        
        # 第二行按钮：同步控制相关
        self.set_main_window_btn = QPushButton(_translate("Dialog", "设为主窗口"))
        self.set_sub_windows_btn = QPushButton(_translate("Dialog", "设为副窗口"))
        self.start_sync_btn = QPushButton(_translate("Dialog", "开始同步"))
        self.stop_sync_btn = QPushButton(_translate("Dialog", "停止同步"))
        self.arrange_btn = QPushButton(_translate("Dialog", "窗口排列"))

        # 设置按钮固定大小，统一风格
        button_size = (100, 28)
        for btn in [self.sync_instruction_btn, self.refresh_windows_btn, self.select_all_btn, self.invert_selection_btn,
                    self.set_main_window_btn, self.set_sub_windows_btn, self.start_sync_btn, self.stop_sync_btn, self.arrange_btn, self.capture_btn]:
            btn.setFixedSize(*button_size)

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
        
        # 添加拉伸项，使按钮靠左排列
        sync_buttons_layout.setColumnStretch(5, 1)

        # 窗口列表表格
        self.window_table = QtWidgets.QTableWidget()
        self.window_table.setColumnCount(2)  # 两列
        self.window_table.setHorizontalHeaderLabels([_translate("Dialog", "选择"), _translate("Dialog", "窗口信息")])
        self.window_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # 第一列自适应
        self.window_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)  # 第二列拉伸
        self.window_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.window_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
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
        general_group.setStyleSheet("background-color: rgba(255, 255, 255, 0.8);")
        general_form = QtWidgets.QFormLayout()
        
        self.auto_start_check = QtWidgets.QCheckBox("启动时自动检测窗口")
        self.auto_start_check.setObjectName("settings_checkbox")
        general_form.addRow(self.auto_start_check)
        
        self.log_level_label = QtWidgets.QLabel("日志级别:")
        self.log_level_combo = QtWidgets.QComboBox()
        self.log_level_combo.setObjectName("settings_combo")
        self.log_level_combo.addItems(["调试", "信息", "警告", "错误"])
        general_form.addRow(self.log_level_label, self.log_level_combo)
        
        self.language_label = QtWidgets.QLabel("语言:")
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setObjectName("settings_combo")
        self.language_combo.addItems(["中文", "English"])
        general_form.addRow(self.language_label, self.language_combo)
        
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
        display_group.setStyleSheet("background-color: rgba(255, 255, 255, 0.8);")
        display_form = QtWidgets.QFormLayout()
        
        self.theme_label = QtWidgets.QLabel("主题:")
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.setObjectName("settings_combo")
        self.theme_combo.addItems(["默认", "深色"])
        display_form.addRow(self.theme_label, self.theme_combo)
        
        self.font_size_label = QtWidgets.QLabel("字体大小:")
        self.font_size_spin = QtWidgets.QSpinBox()
        self.font_size_spin.setObjectName("settings_spin")
        self.font_size_spin.setRange(10, 20)
        self.font_size_spin.setValue(12)
        display_form.addRow(self.font_size_label, self.font_size_spin)
        
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
        
        version_label = QtWidgets.QLabel("版本: 1.5.5")
        version_label.setObjectName("about_text")
        about_layout.addWidget(version_label)
        
        author_label = QtWidgets.QLabel("作者: RMA-MUN")
        author_label.setObjectName("about_text")
        about_layout.addWidget(author_label)
        
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
        Dialog.setWindowTitle(_translate("Dialog", "OAT"))

    def load_stylesheet(self, Dialog):
        try:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建样式表文件的绝对路径
            qss_path = os.path.join(current_dir, "QtSS.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                Dialog.setStyleSheet(f.read())
        except Exception as e:
            print(f"样式表加载失败: {str(e)}")


    def open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def get_text(self): 
         text = '''
            <div style="line-height: 1.0; margin: 0; padding: 0;">
                <span style="margin: 0;">1.优化界面布局</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">2.优化同步器功能，减少便宜</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">3.增加检查更新功能</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">4.重构布局代码</span>
                <br style="margin: 0;"/>
                <span style="margin: 0;">5.修复一些bug</span>
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
        if not mode_config_data or index < 0 or index >= self.comboBox.count():
            return
        
        # 获取当前选择的模式名称
        mode_name = self.comboBox.currentText()
        
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