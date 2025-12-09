import yaml
import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QPushButton, QLineEdit, QSizePolicy, QAbstractItemView

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

        # 导航栏
        self.nav_bar = QtWidgets.QWidget()
        self.nav_bar.setObjectName("nav_bar")
        self.nav_bar.setFixedHeight(20)
        nav_layout = QtWidgets.QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)

        # 导航按钮（保持原有两个按钮）
        self.btn_main = QtWidgets.QPushButton('首页')
        self.btn_subprocess = QtWidgets.QPushButton('多开')
        for btn in [self.btn_main, self.btn_subprocess]:
            btn.setFixedSize(50, 24)
            btn.setObjectName("nav_button")
        nav_layout.addWidget(self.btn_main)
        nav_layout.addWidget(self.btn_subprocess)
        nav_layout.addStretch()

        # 页面容器
        self.stacked_widget = QtWidgets.QStackedWidget()

        # 将导航栏和页面容器加入主布局
        main_layout.addWidget(self.nav_bar)
        main_layout.addWidget(self.stacked_widget)
        Dialog.setLayout(QtWidgets.QVBoxLayout())
        Dialog.layout().addWidget(main_container)

        # 原主布局内容迁移到新页面
        original_main_widget = QtWidgets.QWidget()
        original_main_layout = QtWidgets.QHBoxLayout(original_main_widget)

        # 功能区域布局
        function_widget = QtWidgets.QWidget()
        function_layout = QtWidgets.QVBoxLayout(function_widget)

        # 模式选择组合框
        self.groupBox = QtWidgets.QGroupBox()
        self.groupBox.setObjectName("groupBox")
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
        group_box_layout.addWidget(self.label)
        group_box_layout.addWidget(self.spinBox)

        # 客户端选择区域
        self.label_info = QtWidgets.QLabel("选择您的登录客户端")
        self.system = QtWidgets.QWidget()
        self.system.setObjectName("system")

        # 隐藏窗口捕获复选框
        self.hidden_window_checkbox = QtWidgets.QCheckBox("启用后台模式")
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
        client_path = os.path.join(script_dir, 'client.yaml')
        # 读取client.yaml文件
        with open(client_path, 'r', encoding='utf-8') as file:
            client_info = yaml.safe_load(file)
            # 只根据配置文件中的键值对数量添加选项
            for key, value in client_info['title'].items():
                self.client_choose.addItem(value)
        # 添加下拉菜单到垂直布局
        system_main_layout.addWidget(self.client_choose)

        # 添加隐藏窗口捕获复选框（移到客户端选择下拉菜单下方）
        system_main_layout.addWidget(self.hidden_window_checkbox)

        group_box_layout.addWidget(self.system)
        main_layout.addWidget(self.groupBox)

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
        self.pushButton = QtWidgets.QPushButton()
        self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton()
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_3 = QtWidgets.QPushButton()
        self.pushButton_3.setObjectName("pushButton_3")
        button_layout.addWidget(self.pushButton4, 0, 0)
        button_layout.addWidget(self.pushButton, 0, 1)
        button_layout.addWidget(self.pushButton_3, 1, 0)
        button_layout.addWidget(self.pushButton_2, 1, 1)
        group_box_layout.addLayout(button_layout)

        function_layout.addWidget(self.groupBox)

        # 日志区
        self.groupBox_2 = QtWidgets.QGroupBox()
        self.groupBox_2.setObjectName("groupBox_2")
        log_layout = QtWidgets.QVBoxLayout(self.groupBox_2)
        self.textBrowser = QtWidgets.QTextBrowser()
        self.textBrowser.setObjectName("textBrowser")
        log_layout.addWidget(self.textBrowser)

        # 说明区
        self.groupBox_4 = QtWidgets.QGroupBox()
        self.groupBox_4.setObjectName("groupBox_4")
        instruction_layout = QtWidgets.QVBoxLayout(self.groupBox_4)
        self.textBrowser_2 = QtWidgets.QTextBrowser()
        font = QtGui.QFont()
        font.setPointSize(12)
        self.textBrowser_2.setFont(font)
        self.textBrowser_2.setObjectName("textBrowser_2")
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

        # 创建设置页面（多开+同步器在同一页面）
        settings_page = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(settings_page)

        # 多开设置区域
        self.settings_group = QtWidgets.QGroupBox('多开设置')
        settings_form = QtWidgets.QFormLayout()

        # 创建文件路径输入框
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("未选择文件")
        self.file_path_edit.setObjectName("file_path_edit")
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.file_path_edit.setSizePolicy(size_policy)

        # 创建文件选择按钮
        self.select_button = QPushButton("选择文件")
        self.select_button.setFixedSize(80, 26)
        self.select_button.setObjectName("select_button")

        # 创建清除按钮
        self.clear_button = QPushButton("清除")
        self.clear_button.setFixedSize(60, 26)
        self.clear_button.setObjectName("clear_button")

        settings_form.addRow("程序路径:", self.file_path_edit)

        # 按钮容器
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(5)
        btn_layout.addWidget(self.select_button)
        btn_layout.addWidget(self.clear_button)

        # 执行多开按钮
        self.start_button = QPushButton("执行多开")
        self.start_button.setFixedSize(80, 26)
        self.start_button.setObjectName("start_button")
        btn_layout.addWidget(self.start_button)
        btn_layout.addStretch()

        # 多开数量输入框
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("多开数量")
        self.number_input.setObjectName("number_input")
        self.number_input.setFixedSize(60, 26)
        self.number_input.setValidator(QtGui.QIntValidator())
        self.number_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        settings_form.addRow("多开数量:", self.number_input)

        # 延迟时间输入框
        self.delay_input = QLineEdit()
        self.delay_input.setPlaceholderText("延迟时间")
        self.delay_input.setObjectName("delay_input")
        self.delay_input.setFixedSize(60, 26)
        self.delay_input.setValidator(QtGui.QIntValidator())
        self.delay_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        settings_form.addRow("多开延迟:", self.delay_input)

        settings_form.addRow("", btn_container)
        settings_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.settings_group.setLayout(settings_form)

        # 同步器设置区域（独立groupBox，放在多开设置下方）
        self.sync_group = QtWidgets.QGroupBox('同步器设置')
        sync_layout = QtWidgets.QVBoxLayout(self.sync_group)  # 垂直布局

        # 同步操作按钮区域
        sync_buttons_widget = QtWidgets.QWidget()
        sync_buttons_layout = QtWidgets.QHBoxLayout(sync_buttons_widget)
        sync_buttons_layout.setSpacing(10)  # 按钮间距

        self.refresh_windows_btn = QPushButton("刷新窗口")
        self.select_all_btn = QPushButton("全选")
        self.invert_selection_btn = QPushButton("反选")
        self.set_main_window_btn = QPushButton("设置为主窗口")
        self.set_sub_windows_btn = QPushButton("设置为副窗口")
        self.start_sync_btn = QPushButton("开始同步")
        self.stop_sync_btn = QPushButton("停止同步")
        self.arrange_btn = QPushButton("窗口排列")

        for btn in [self.refresh_windows_btn, self.select_all_btn, self.invert_selection_btn,
                    self.set_main_window_btn, self.set_sub_windows_btn, self.arrange_btn,
                    self.start_sync_btn, self.stop_sync_btn]:
            sync_buttons_layout.addWidget(btn)
        sync_buttons_layout.addStretch()  # 右侧留白

        # 窗口列表表格
        self.window_table = QtWidgets.QTableWidget()
        self.window_table.setColumnCount(2)  # 两列
        self.window_table.setHorizontalHeaderLabels(["选择", "窗口信息"])
        self.window_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # 第一列自适应
        self.window_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)  # 第二列拉伸
        self.window_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.window_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # 同步模式选择
        sync_mode_widget = QtWidgets.QWidget()
        sync_mode_layout = QtWidgets.QHBoxLayout(sync_mode_widget)
        sync_mode_layout.setSpacing(10)
        self.sync_mode_label = QtWidgets.QLabel("同步模式:")
        self.sync_mode_combo = QtWidgets.QComboBox()
        self.sync_mode_combo.addItems(["点击同步", "键盘同步", "完全同步"])
        sync_mode_layout.addWidget(self.sync_mode_label)
        sync_mode_layout.addWidget(self.sync_mode_combo)
        sync_mode_layout.addStretch()

        # 组装同步器布局
        sync_layout.addWidget(sync_buttons_widget)  # 按钮在上
        sync_layout.addWidget(self.window_table)    # 表格在中
        sync_layout.addWidget(sync_mode_widget)     # 模式选择在下

        # 将两个groupBox加入多开页面布局（上下排列）
        settings_layout.addWidget(self.settings_group)  # 多开设置在上
        settings_layout.addWidget(self.sync_group)      # 同步器设置在下
        settings_layout.addStretch()  # 底部留白

        # 添加页面到堆叠容器
        self.stacked_widget.addWidget(main_page)
        self.stacked_widget.addWidget(settings_page)

        # 连接导航按钮
        self.btn_main.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_subprocess.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        # 初始化文本翻译
        self.retranslateUi(Dialog)
        # 加载样式表
        self.load_stylesheet(Dialog)

        # 加载元对象
        QtCore.QMetaObject.connectSlotsByName(Dialog)

        # 连接信号
        self.textBrowser_2.anchorClicked.connect(self.open_link)
        self.comboBox.currentIndexChanged.connect(self.on_mode_selected)

        # 初始化窗口列表
        self.initialize_window_list()

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "OAT-v1.4"))
        self.groupBox.setTitle(_translate("Dialog", "功能"))


        # self.comboBox.setItemText(0, _translate("Dialog", "请选择模式"))
        # self.comboBox.setItemText(1, _translate("Dialog", "魂土"))
        # self.comboBox.setItemText(2, _translate("Dialog", "魂王"))
        # self.comboBox.setItemText(3, _translate("Dialog", "业原火"))
        # self.comboBox.setItemText(4, _translate("Dialog", "觉醒"))
        # self.comboBox.setItemText(5, _translate("Dialog", "爬塔"))
        # self.comboBox.setItemText(6, _translate("Dialog", "灵染试炼"))
        # self.comboBox.setItemText(7, _translate("Dialog", "契灵探查"))

        self.label.setText(_translate("Dialog", "请输入要挑战的次数"))
        self.pushButton4.setText(_translate("Dialog", "刷新窗口"))
        self.pushButton.setText(_translate("Dialog", "窗口检测"))
        self.pushButton_2.setText(_translate("Dialog", "开始挑战"))
        self.pushButton_3.setText(_translate("Dialog", "紧急停止"))
        self.groupBox_2.setTitle(_translate("Dialog", "日志"))
        self.groupBox_4.setTitle(_translate("Dialog", "说明"))

        # 同步器文本
        self.sync_group.setTitle(_translate("Dialog", "同步器设置"))
        self.refresh_windows_btn.setText(_translate("Dialog", "刷新窗口"))
        self.select_all_btn.setText(_translate("Dialog", "全选"))
        self.invert_selection_btn.setText(_translate("Dialog", "反选"))
        self.start_sync_btn.setText(_translate("Dialog", "开始同步"))
        self.stop_sync_btn.setText(_translate("Dialog", "停止同步"))
        self.sync_mode_label.setText(_translate("Dialog", "同步模式:"))

        text = self.get_text()
        self.textBrowser_2.setHtml(text)

    def load_stylesheet(self, Dialog):
        import os
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
        text = (
            "更新日志：""<br>"
            "1.新增后台运行模式，勾选后，窗口可以被完全遮挡，但是不能最小化""<br>"
            "2.新增窗口同步器的功能，在一个游戏的操作可以同步到其他游戏""<br>"
            "3.修复已知bug""<br>"
            " <a href='https://github.com/RMA-MUN/OnmyoujiAuto'>"
            "点击跳转至仓库！"
            "</a>"
        )
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