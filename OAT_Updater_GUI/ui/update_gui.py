import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QPixmap

from OAT_Updater_GUI.utils.update_worker import UpdateWorker


class UpdateGUI(QWidget):
    """
    OAT更新程序主界面
    """

    def __init__(self, zip_path=None, update_log="", latest_version="OAT-v2.0.0", published_date="2026-02-24", parent=None):
        """
        初始化更新界面
        :param zip_path: 压缩包路径，可选
        :param update_log: 更新日志，可选
        :param latest_version: 最新版本号，可选
        :param published_date: 发布日期，可选
        :param parent: 父窗口
        """
        super().__init__(parent)
        self.zip_path = zip_path
        self.update_log = update_log
        self.latest_version = latest_version
        self.published_date = published_date
        self.update_worker = None
        self.dragging = False
        self.drag_start_position = QPoint()
        self.init_ui()
    
    def markdown_to_html(self, markdown: str) -> str:
        """
        将Markdown格式的文本转换为HTML格式
        
        Args:
            markdown: Markdown格式的文本
        
        Returns:
            HTML格式的文本
        """
        if not markdown:
            return "<p>暂无更新日志</p>"
        
        # 替换Markdown格式为HTML
        lines = markdown.split('\n')
        html_lines = []
        in_list = False
        in_code = False
        first_header_skipped = False
        
        for line in lines:
            # 处理代码块
            if line.startswith('```'):
                in_code = not in_code
                if in_code:
                    html_lines.append('<pre><code>')
                else:
                    html_lines.append('</code></pre>')
                continue
            
            if in_code:
                html_lines.append(line)
                continue
            
            # 处理标题，跳过第一个标题行（避免与版本信息重复）
            if line.startswith('# '):
                if not first_header_skipped:
                    first_header_skipped = True
                    continue
                html_lines.append(f'<h1>{line[2:]}</h1>')
                continue
            elif line.startswith('## '):
                html_lines.append(f'<h2>{line[3:]}</h2>')
                continue
            elif line.startswith('### '):
                html_lines.append(f'<h3>{line[4:]}</h3>')
                continue
            
            # 处理列表
            if line.startswith('- '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{line[2:]}</li>')
                continue
            elif in_list:
                html_lines.append('</ul>')
                in_list = False
            
            # 处理空行
            if not line.strip():
                if html_lines and not html_lines[-1].strip():
                    continue
                html_lines.append('')
                continue
            
            # 处理普通行（包含粗体和斜体）
            processed_line = line
            # 处理粗体
            processed_line = processed_line.replace('**', '<strong>').replace('**', '</strong>')
            # 处理斜体
            processed_line = processed_line.replace('*', '<em>').replace('*', '</em>')
            html_lines.append(f'<p>{processed_line}</p>')
        
        # 关闭未关闭的标签
        if in_list:
            html_lines.append('</ul>')
        if in_code:
            html_lines.append('</code></pre>')
        
        return '\n'.join(html_lines)

    def init_ui(self):
        """
        初始化UI界面
        :return: None
        """
        # 设置无边框窗口
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        self.setStyleSheet("background-color: white;")

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # 标题栏（自定义）
        title_layout = QHBoxLayout()

        # 应用图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'OAT', 'tools', 'uiResources', 'icon.ico')
        if os.path.exists(icon_path):
            icon_label = QLabel()
            icon_pixmap = QPixmap(icon_path)
            icon_pixmap = icon_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
            icon_label.setPixmap(icon_pixmap)
            title_layout.addWidget(icon_label)
            # 设置窗口图标
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        # 标题
        title_label = QLabel("OAT 更新程序")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)

        # 空出空间
        title_layout.addStretch()

        # 关闭按钮
        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                font-size: 20px;
                font-weight: bold;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                color: #333;
            }
        """)
        close_button.clicked.connect(self.close)
        title_layout.addWidget(close_button)

        main_layout.addLayout(title_layout)

        # 任务状态
        status_layout = QHBoxLayout()
        status_label = QLabel("当前状态:")
        self.status_value_label = QLabel("准备就绪")
        self.status_value_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.status_value_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # 版本信息栏
        version_layout = QHBoxLayout()
        # 获取当前版本
        current_version = "v1.9.0"
        try:
            import sys
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
            from OAT.tools.settings import APP_VERSION
            current_version = APP_VERSION
        except:
            pass
        
        # 使用传递进来的最新版本和发布日期
        latest_version = self.latest_version
        published_date = self.published_date
        
        # 格式化发布日期，从ISO格式转换为YYYY-MM-DD
        if published_date != "2026-02-24":
            from datetime import datetime
            try:
                published_date = datetime.fromisoformat(published_date).strftime('%Y-%m-%d')
            except:
                pass
        
        # 尝试从压缩包获取大小
        update_size = "XX MB"
        if self.zip_path and os.path.exists(self.zip_path):
            try:
                size = os.path.getsize(self.zip_path)
                size_mb = round(size / (1024 * 1024), 2)
                update_size = f"{size_mb} MB"
            except:
                pass
        
        version_info = QLabel(f"【当前版本 {current_version}】→【最新版本】{latest_version} | 发布日期: {published_date} | 更新包大小: {update_size}")
        version_info.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                background-color: #f5f5f5;
                font-family: 'Microsoft YaHei';
                font-size: 12px;
                color: #333333;
            }
        """)
        version_layout.addWidget(version_info)
        main_layout.addLayout(version_layout)

        # 更新日志
        log_layout = QVBoxLayout()
        log_title = QLabel("更新日志")
        log_title.setStyleSheet("font-weight: bold;")
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setObjectName("updateLogText")
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMaximumHeight(250)  # 增大更新日志区域的高度
        self.log_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # 自动换行
        self.log_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 垂直滚动条按需显示
        self.log_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 禁用水平滚动条
        self.log_text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 8px;
                background-color: #ffffff;
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
        # 显示更新日志
        if self.update_log:
            # 将Markdown转换为HTML并显示
            html_content = self.markdown_to_html(self.update_log)
            self.log_text_edit.setHtml(html_content)
        else:
            self.log_text_edit.setHtml("<p>暂无更新日志</p>")
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_text_edit)
        main_layout.addLayout(log_layout)

        # 合并进度条
        progress_layout = QVBoxLayout()
        progress_title = QLabel("更新进度:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)  # 总进度100%
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #f0f0f0;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 8px;
            }
        """)
        progress_layout.addWidget(progress_title)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)

        # 操作日志
        op_log_layout = QVBoxLayout()
        op_log_title = QLabel("操作日志")
        self.op_log_text_edit = QTextEdit()
        self.op_log_text_edit.setObjectName("operateLogText")
        self.op_log_text_edit.setReadOnly(True)
        self.op_log_text_edit.setMaximumHeight(100)  # 减小高度以节省空间
        self.op_log_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # 自动换行
        self.op_log_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 垂直滚动条按需显示
        self.op_log_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 禁用水平滚动条
        self.op_log_text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
                font-family: 'Microsoft YaHei';
                font-size: 10px;
                line-height: 1.3;
            }
            QScrollBar:vertical {
                width: 12px;
                background: #f3f4f6;
            }
            QScrollBar::handle:vertical {
                background: #9ca3af;
                border-radius: 6px;
            }
        """)
        op_log_layout.addWidget(op_log_title)
        op_log_layout.addWidget(self.op_log_text_edit)
        main_layout.addLayout(op_log_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 开始更新按钮
        self.start_button = QPushButton("开始更新")
        self.start_button.setMinimumWidth(120)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.start_button.clicked.connect(self.start_update)
        button_layout.addWidget(self.start_button)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # 如果提供了zip路径，自动填充
        if self.zip_path:
            self.op_log_text_edit.append(f"已指定压缩包: {self.zip_path}")
            self.status_value_label.setText("准备就绪")
        else:
            self.status_value_label.setText("等待压缩包")
            self.status_value_label.setStyleSheet("color: #F44336; font-weight: bold;")
            self.start_button.setEnabled(False)

    def start_update(self):
        """
        开始更新
        :return: None
        """
        if not self.zip_path:
            QMessageBox.warning(self, "提示", "未指定压缩包路径！")
            return

        if not os.path.exists(self.zip_path):
            QMessageBox.warning(self, "错误", "压缩包文件不存在！")
            return

        # 禁用按钮
        self.start_button.setEnabled(False)

        # 创建并启动更新工作线程
        self.update_worker = UpdateWorker(self.zip_path)

        # 连接信号
        self.update_worker.status_signal.connect(self.update_status)
        self.update_worker.unzip_progress_signal.connect(self.update_unzip_progress)
        self.update_worker.replace_progress_signal.connect(self.update_replace_progress)
        self.update_worker.log_signal.connect(self.log_message)
        self.update_worker.finished_signal.connect(self.update_finished)
        self.update_worker.error_signal.connect(self.update_error)

        # 启动线程
        self.update_worker.start()

    def update_status(self, status):
        """
        更新状态显示
        :param status: 状态文本
        :return: None
        """
        self.status_value_label.setText(status)
        if "正在" in status:
            self.status_value_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        elif "完成" in status:
            self.status_value_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif "错误" in status:
            self.status_value_label.setStyleSheet("color: #F44336; font-weight: bold;")

    def update_unzip_progress(self, value):
        """
        更新解压进度条
        :param value: 进度值 (0-100)
        :return: None
        """
        # 解压占总进度的50%
        progress = int(value / 2)
        self.progress_bar.setValue(progress)

    def update_replace_progress(self, value):
        """
        更新文件替换进度条
        :param value: 进度值 (0-100)
        :return: None
        """
        # 文件替换占总进度的50%，加上解压的50%
        progress = 50 + int(value / 2)
        self.progress_bar.setValue(progress)

    def log_message(self, message):
        """
        添加日志消息
        :param message: 日志文本
        :return: None
        """
        self.append_operate_log(message)
    
    def append_update_log(self, message: str) -> None:
        """
        追加更新日志并自动滚动到底部
        :param message: 日志文本
        :return: None
        """
        self.log_text_edit.append(message)
        self.log_text_edit.verticalScrollBar().setValue(self.log_text_edit.verticalScrollBar().maximum())
    
    def append_operate_log(self, message: str) -> None:
        """
        追加操作日志并自动滚动到底部
        :param message: 日志文本
        :return: None
        """
        self.op_log_text_edit.append(message)
        self.op_log_text_edit.verticalScrollBar().setValue(self.op_log_text_edit.verticalScrollBar().maximum())

    def update_finished(self):
        """
        更新完成
        :return: None
        """
        self.status_value_label.setText("更新完成")
        self.status_value_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.op_log_text_edit.append("更新完成！请重新启动应用程序。")
        QMessageBox.information(self, "完成", "更新完成！请重新启动应用程序。")

    def update_error(self, error_msg):
        """
        更新出错
        :param error_msg: 错误信息
        :return: None
        """
        self.status_value_label.setText("更新失败")
        self.status_value_label.setStyleSheet("color: #F44336; font-weight: bold;")
        self.op_log_text_edit.append(f"错误: {error_msg}")
        self.start_button.setEnabled(True)
        QMessageBox.critical(self, "错误", f"更新失败: {error_msg}")

    def mousePressEvent(self, event):
        """
        鼠标按下事件，用于窗口拖拽
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """
        鼠标移动事件，用于窗口拖拽
        """
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """
        鼠标释放事件，结束窗口拖拽
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            event.accept()