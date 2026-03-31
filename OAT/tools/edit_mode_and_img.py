import os
import json
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QLineEdit, QLabel, QFileDialog, QListWidget, QListWidgetItem, QMessageBox, QSplitter
from PyQt6.QtGui import QPixmap

class ImageConfigDialog(QDialog):
    def __init__(self, parent=None, image_name="", config_data={}, config_path="", image_list=[]):
        super().__init__(parent)
        self.setWindowTitle("图像配置")
        self.resize(500, 400)
        
        self.image_name = image_name
        self.config_data = config_data
        self.config_path = config_path
        self.image_list = image_list
        
        # 初始化UI
        self.setup_ui()
    
    def setup_ui(self):
        """
        设置UI界面
        """
        main_layout = QVBoxLayout(self)
        
        # 图像名称
        name_layout = QHBoxLayout()
        name_label = QLabel("图像名称:")
        self.name_line_edit = QLineEdit(self.image_name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_line_edit)
        main_layout.addLayout(name_layout)
        
        # 路径
        path_layout = QHBoxLayout()
        path_label = QLabel("路径:")
        self.path_line_edit = QLineEdit(self.config_data.get("path", self.image_name))
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_line_edit)
        main_layout.addLayout(path_layout)
        
        # 是否是挑战开始
        self.is_challenge_start_checkbox = QtWidgets.QCheckBox("是否是挑战开始")
        self.is_challenge_start_checkbox.setChecked(self.config_data.get("is_challenge_start", False))
        main_layout.addWidget(self.is_challenge_start_checkbox)
        
        # 消息
        message_layout = QHBoxLayout()
        message_label = QLabel("消息:")
        self.message_line_edit = QLineEdit(self.config_data.get("message", ""))
        message_layout.addWidget(message_label)
        message_layout.addWidget(self.message_line_edit)
        main_layout.addLayout(message_layout)
        
        # is_global配置
        self.is_global_checkbox = QtWidgets.QCheckBox("是否全局")
        self.is_global_checkbox.setChecked(self.config_data.get("is_global", False))
        main_layout.addWidget(self.is_global_checkbox)
        
        # next_image配置
        next_img_layout = QHBoxLayout()
        next_img_label = QLabel("下一张图片:")
        self.next_img_combo = QtWidgets.QComboBox()
        # 添加空选项
        self.next_img_combo.addItem("")
        # 添加当前模式的所有图片
        for img in self.image_list:
            self.next_img_combo.addItem(img)
        # 设置当前值
        current_next_img = self.config_data.get("next_image", "")
        # 尝试直接查找
        index = self.next_img_combo.findText(current_next_img)
        if index == -1 and current_next_img:
            # 如果找不到，尝试查找带后缀的版本
            for img in self.image_list:
                if os.path.splitext(img)[0] == current_next_img:
                    index = self.next_img_combo.findText(img)
                    break
        if index != -1:
            self.next_img_combo.setCurrentIndex(index)
        next_img_layout.addWidget(next_img_label)
        next_img_layout.addWidget(self.next_img_combo)
        main_layout.addLayout(next_img_layout)
        
        # 点击区域设置
        click_area_group = QtWidgets.QGroupBox("点击区域设置")
        click_area_layout = QVBoxLayout(click_area_group)
        
        # 点击方式
        self.click_method_group = QtWidgets.QButtonGroup()
        self.click_image_radio = QtWidgets.QRadioButton("点击图片区域")
        self.click_custom_radio = QtWidgets.QRadioButton("点击自定义区域")
        
        # 默认选择点击图片区域
        self.click_image_radio.setChecked(not self.config_data.get("click_area"))
        self.click_custom_radio.setChecked("click_area" in self.config_data)
        
        self.click_method_group.addButton(self.click_image_radio)
        self.click_method_group.addButton(self.click_custom_radio)
        
        click_area_layout.addWidget(self.click_image_radio)
        click_area_layout.addWidget(self.click_custom_radio)
        
        # 自定义区域
        custom_area_layout = QHBoxLayout()
        custom_area_label = QLabel("自定义区域:")
        self.custom_area_line_edit = QLineEdit(str(self.config_data.get("click_area", [100, 200, 200, 400])))
        custom_area_layout.addWidget(custom_area_label)
        custom_area_layout.addWidget(self.custom_area_line_edit)
        click_area_layout.addLayout(custom_area_layout)
        
        main_layout.addWidget(click_area_group)
        
        # OCR配置
        ocr_group = QtWidgets.QGroupBox("OCR配置")
        ocr_layout = QVBoxLayout(ocr_group)
        
        # 是否启用OCR
        self.is_ocr_enabled_checkbox = QtWidgets.QCheckBox("是否启用OCR")
        self.is_ocr_enabled_checkbox.setChecked(self.config_data.get("ocr_enabled", False))
        ocr_layout.addWidget(self.is_ocr_enabled_checkbox)
        
        # OCR识别文本
        ocr_text_layout = QHBoxLayout()
        ocr_text_label = QLabel("OCR识别文本:")
        self.ocr_text_edit = QLineEdit(self.config_data.get("ocr_target_text", ""))
        ocr_text_layout.addWidget(ocr_text_label)
        ocr_text_layout.addWidget(self.ocr_text_edit)
        ocr_layout.addLayout(ocr_text_layout)
        
        # OCR识别阈值
        ocr_threshold_layout = QHBoxLayout()
        ocr_threshold_label = QLabel("OCR识别阈值:")
        self.ocr_threshold_edit = QLineEdit(str(self.config_data.get("ocr_confidence_threshold", 0.8)))
        ocr_threshold_layout.addWidget(ocr_threshold_label)
        ocr_threshold_layout.addWidget(self.ocr_threshold_edit)
        ocr_layout.addLayout(ocr_threshold_layout)
        
        # OCR识别后的操作
        ocr_action_layout = QHBoxLayout()
        ocr_action_label = QLabel("OCR识别后的操作:")
        self.ocr_action_combo = QtWidgets.QComboBox()
        self.ocr_action_combo.addItem("点击文字所在区域")
        self.ocr_action_combo.addItem("点击点击区域设置的区域")
        current_action = self.config_data.get("ocr_action", "点击文字所在区域")
        index = self.ocr_action_combo.findText(current_action)
        if index != -1:
            self.ocr_action_combo.setCurrentIndex(index)
        ocr_action_layout.addWidget(ocr_action_label)
        ocr_action_layout.addWidget(self.ocr_action_combo)
        ocr_layout.addLayout(ocr_action_layout)
        
        main_layout.addWidget(ocr_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # 连接信号
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.reject)
    
    def save(self):
        """
        保存配置
        """
        # 更新配置数据
        new_name = self.name_line_edit.text()
        self.config_data["path"] = self.path_line_edit.text()
        self.config_data["is_challenge_start"] = self.is_challenge_start_checkbox.isChecked()
        self.config_data["message"] = self.message_line_edit.text()
        self.config_data["is_global"] = self.is_global_checkbox.isChecked()
        # 存储不带后缀的文件名
        next_img_value = self.next_img_combo.currentText()
        if next_img_value:
            next_img_value = os.path.splitext(next_img_value)[0]
        self.config_data["next_image"] = next_img_value
        
        # 处理点击区域
        if self.click_image_radio.isChecked():
            # 移除click_area字段
            if "click_area" in self.config_data:
                del self.config_data["click_area"]
        else:
            # 设置自定义区域
            try:
                # 尝试解析输入的区域
                area = eval(self.custom_area_line_edit.text())
                if isinstance(area, list) and len(area) == 4:
                    self.config_data["click_area"] = area
                else:
                    # 使用默认值
                    self.config_data["click_area"] = [100, 100, 100, 400]
            except:
                # 使用默认值
                self.config_data["click_area"] = [100, 200, 200, 400]
        
        # 保存OCR配置
        self.config_data["ocr_enabled"] = self.is_ocr_enabled_checkbox.isChecked()
        
        # OCR识别文本
        self.config_data["ocr_target_text"] = self.ocr_text_edit.text()
        
        # OCR识别阈值
        try:
            threshold = float(self.ocr_threshold_edit.text())
            self.config_data["ocr_confidence_threshold"] = threshold
        except:
            self.config_data["ocr_confidence_threshold"] = 0.8
        
        # OCR识别后的操作
        self.config_data["ocr_action"] = self.ocr_action_combo.currentText()
        
        # 保存到文件
        if self.config_path:
            try:
                # 确保目录存在
                config_dir = os.path.dirname(self.config_path)
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir)
                
                # 读取现有配置或创建新配置
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    config = {"image_paths": {}}
                
                # 更新image_paths
                if "image_paths" not in config:
                    config["image_paths"] = {}
                
                # 获取旧的图像键名（去除扩展名）
                old_image_key = os.path.splitext(self.image_name)[0]
                
                # 获取新的图像键名（去除扩展名）
                new_image_key = os.path.splitext(new_name)[0]
                
                # 如果名称改变，需要删除旧的配置并添加新的
                if new_image_key != old_image_key:
                    if old_image_key in config["image_paths"]:
                        del config["image_paths"][old_image_key]
                
                config["image_paths"][new_image_key] = self.config_data
                
                # 保存配置
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", "配置保存成功")
                self.accept()
            except Exception as e:
                QMessageBox.warning(self, "警告", f"保存配置失败: {e}")

class ModeEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模式和图像编辑器")
        self.resize(800, 600)
        
        # 获取source目录的绝对路径
        self.source_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source')
        # 构建mode.json的绝对路径
        self.mode_json_path = os.path.join(self.source_dir, 'mode.json')
        # 加载模式配置
        self.mode_config_data = self.load_mode_config()
        # 临时模式配置数据（用于存储未保存的模式）
        self.temp_mode_config = self.mode_config_data.copy()
        
        # 初始化UI
        self.setup_ui()
        
    def load_mode_config(self):
        """
        加载模式配置文件
        
        Returns:
            dict: 模式配置数据
        """
        try:
            with open(self.mode_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载模式配置失败: {e}")
            return {}
    
    def save_mode_config(self):
        """
        保存模式配置到文件
        """
        try:
            with open(self.mode_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.mode_config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存模式配置失败: {e}")
            return False
    
    def setup_ui(self):
        """
        设置UI界面
        """
        main_layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # 左侧：模式管理区域
        mode_widget = QtWidgets.QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        
        # 模式树
        self.mode_tree = QTreeWidget()
        self.mode_tree.setHeaderLabel("模式列表")
        self.mode_tree.setMinimumWidth(200)
        self.load_mode_tree()
        mode_layout.addWidget(self.mode_tree)
        
        # 模式操作按钮
        mode_buttons_layout = QHBoxLayout()
        self.add_mode_btn = QPushButton("添加模式")
        self.add_submode_btn = QPushButton("添加子模式")
        self.delete_mode_btn = QPushButton("删除模式")
        self.rename_mode_btn = QPushButton("重命名模式")
        
        mode_buttons_layout.addWidget(self.add_mode_btn)
        mode_buttons_layout.addWidget(self.add_submode_btn)
        mode_buttons_layout.addWidget(self.delete_mode_btn)
        mode_buttons_layout.addWidget(self.rename_mode_btn)
        
        mode_layout.addLayout(mode_buttons_layout)
        
        # 右侧：图像管理区域
        img_widget = QtWidgets.QWidget()
        img_layout = QVBoxLayout(img_widget)
        
        # 模式信息
        self.mode_info_label = QLabel("请选择一个模式")
        img_layout.addWidget(self.mode_info_label)
        
        # 图像列表
        self.img_list = QListWidget()
        self.img_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.img_list.setIconSize(QtCore.QSize(100, 100))
        self.img_list.setMinimumWidth(300)
        img_layout.addWidget(self.img_list)
        
        # 图像操作按钮
        img_buttons_layout = QHBoxLayout()
        self.add_img_btn = QPushButton("添加图像")
        self.delete_img_btn = QPushButton("删除图像")
        self.edit_img_config_btn = QPushButton("编辑图像配置")
        self.usage_instructions_btn = QPushButton("查看使用说明")
        
        img_buttons_layout.addWidget(self.add_img_btn)
        img_buttons_layout.addWidget(self.delete_img_btn)
        img_buttons_layout.addWidget(self.edit_img_config_btn)
        img_buttons_layout.addWidget(self.usage_instructions_btn)
        
        img_layout.addLayout(img_buttons_layout)
        
        # 将两个区域添加到分割器
        splitter.addWidget(mode_widget)
        splitter.addWidget(img_widget)
        splitter.setSizes([200, 600])
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.cancel_btn)
        
        main_layout.addWidget(splitter)
        main_layout.addLayout(bottom_layout)
        
        # 连接信号
        self.connect_signals()
    
    def load_mode_tree(self):
        """
        加载模式树
        """
        self.mode_tree.clear()
        
        for mode_name, mode_data in self.temp_mode_config.items():
            root_item = QTreeWidgetItem([mode_name])
            
            if isinstance(mode_data, dict):
                for submode_name in mode_data.keys():
                    if submode_name != 'default':
                        sub_item = QTreeWidgetItem([submode_name])
                        root_item.addChild(sub_item)
            
            self.mode_tree.addTopLevelItem(root_item)
    
    def connect_signals(self):
        """
        连接信号和槽
        """
        # 模式树选择变化
        self.mode_tree.currentItemChanged.connect(self.on_mode_selected)
        
        # 模式操作按钮
        self.add_mode_btn.clicked.connect(self.add_mode)
        self.add_submode_btn.clicked.connect(self.add_submode)
        self.delete_mode_btn.clicked.connect(self.delete_mode)
        self.rename_mode_btn.clicked.connect(self.rename_mode)
        
        # 图像操作按钮
        self.add_img_btn.clicked.connect(self.add_image)
        self.delete_img_btn.clicked.connect(self.delete_image)
        self.edit_img_config_btn.clicked.connect(self.edit_image_config)
        self.usage_instructions_btn.clicked.connect(self.show_usage_instructions)
        
        # 底部按钮
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.reject)
    
    def on_mode_selected(self, current, previous):
        """
        处理模式选择事件
        
        Args:
            current: 当前选中的项
            previous: 之前选中的项
        """
        if not current:
            self.mode_info_label.setText("请选择一个模式")
            self.img_list.clear()
            return
        
        # 获取模式路径
        mode_path = []
        item = current
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        if len(mode_path) == 1:
            # 顶级模式
            mode_name = mode_path[0]
            self.mode_info_label.setText(f"当前模式: {mode_name}")
        else:
            # 子模式
            mode_name = mode_path[0]
            submode_name = mode_path[1]
            self.mode_info_label.setText(f"当前模式: {mode_name} -> {submode_name}")
        
        # 加载该模式的图像
        self.load_images(mode_path)
    
    def load_images(self, mode_path):
        """
        加载模式的图像
        
        Args:
            mode_path: 模式路径列表
        """
        self.img_list.clear()
        
        # 构建模式目录
        if len(mode_path) == 1:
            # 顶级模式
            mode_name = mode_path[0]
            # 从临时模式配置中获取模式对应的目录名
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get('default', '')
            else:
                dir_name = mode_data
        else:
            # 子模式
            mode_name = mode_path[0]
            submode_name = mode_path[1]
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get(submode_name, '')
            else:
                dir_name = mode_data
        
        # 构建图像目录路径
        if dir_name:
            mode_dir = os.path.join(self.source_dir, dir_name)
            if os.path.exists(mode_dir):
                # 加载配置文件
                config_path = os.path.join(mode_dir, 'config.json')
                config_data = {}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                    except Exception as e:
                        print(f"加载配置文件失败: {e}")
                
                # 加载图像
                for file in os.listdir(mode_dir):
                    if file.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        item = QListWidgetItem()
                        item.setText(file)
                        
                        # 加载图像预览
                        img_path = os.path.join(mode_dir, file)
                        pixmap = QPixmap(img_path)
                        if not pixmap.isNull():
                            pixmap = pixmap.scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                            item.setIcon(QtGui.QIcon(pixmap))
                        
                        self.img_list.addItem(item)
    
    def add_mode(self):
        """
        添加新模式
        """
        # 弹出输入对话框获取模式名称
        mode_name, ok = QtWidgets.QInputDialog.getText(self, "添加模式", "请输入模式名称:")
        if not (ok and mode_name):
            return
        
        # 弹出输入对话框获取模式目录名称
        dir_name, ok = QtWidgets.QInputDialog.getText(self, "添加模式", "请输入模式目录名称(请使用英文命名):")
        if not (ok and dir_name):
            return
        
        # 检查目录名称是否为英文
        if not dir_name.isascii() or not dir_name.replace('_', '').isalnum():
            QMessageBox.warning(self, "警告", "目录名称必须使用英文、数字或下划线")
            return
        
        if mode_name not in self.temp_mode_config:
            self.temp_mode_config[mode_name] = dir_name
            self.load_mode_tree()
        else:
            QMessageBox.warning(self, "警告", "模式名称已存在")
    
    def add_submode(self):
        """
        添加子模式
        """
        current_item = self.mode_tree.currentItem()
        if not current_item or current_item.parent():
            QMessageBox.warning(self, "警告", "请先选择一个顶级模式")
            return
        
        # 弹出输入对话框获取子模式名称
        submode_name, ok = QtWidgets.QInputDialog.getText(self, "添加子模式", "请输入子模式名称:")
        if not (ok and submode_name):
            return
        
        # 弹出输入对话框获取子模式目录名称
        submode_dir, ok = QtWidgets.QInputDialog.getText(self, "添加子模式", "请输入子模式目录名称(请使用英文命名):")
        if not (ok and submode_dir):
            return
        
        # 检查目录名称是否为英文
        if not submode_dir.isascii() or not submode_dir.replace('_', '').isalnum():
            QMessageBox.warning(self, "警告", "目录名称必须使用英文、数字或下划线")
            return
        
        mode_name = current_item.text(0)
        
        # 如果模式数据不是字典，转换为字典
        if not isinstance(self.temp_mode_config[mode_name], dict):
            self.temp_mode_config[mode_name] = {"default": self.temp_mode_config[mode_name]}
        
        if submode_name not in self.temp_mode_config[mode_name]:
            self.temp_mode_config[mode_name][submode_name] = submode_dir
            self.load_mode_tree()
        else:
            QMessageBox.warning(self, "警告", "子模式名称已存在")
    
    def delete_mode(self):
        """
        删除模式
        """
        current_item = self.mode_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个模式")
            return
        
        # 获取模式路径
        mode_path = []
        item = current_item
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        # 确认删除
        if QMessageBox.question(self, "确认删除", f"确定要删除{' -> '.join(mode_path)}吗？", 
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if len(mode_path) == 1:
                # 删除顶级模式
                del self.temp_mode_config[mode_path[0]]
            else:
                # 删除子模式
                mode_name = mode_path[0]
                submode_name = mode_path[1]
                del self.temp_mode_config[mode_name][submode_name]
            
            self.load_mode_tree()
            self.img_list.clear()
            self.mode_info_label.setText("请选择一个模式")
    
    def rename_mode(self):
        """
        重命名模式
        """
        current_item = self.mode_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个模式")
            return
        
        # 获取模式路径
        mode_path = []
        item = current_item
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        # 弹出输入对话框
        new_name, ok = QtWidgets.QInputDialog.getText(self, "重命名模式", "请输入新的模式名称:", 
                                                     text=mode_path[-1])
        if ok and new_name:
            if len(mode_path) == 1:
                # 重命名顶级模式
                if new_name != mode_path[0]:
                    if new_name not in self.temp_mode_config:
                        self.temp_mode_config[new_name] = self.temp_mode_config[mode_path[0]]
                        del self.temp_mode_config[mode_path[0]]
                        self.load_mode_tree()
                    else:
                        QMessageBox.warning(self, "警告", "模式名称已存在")
            else:
                # 重命名子模式
                mode_name = mode_path[0]
                submode_name = mode_path[1]
                if new_name != submode_name:
                    if new_name not in self.temp_mode_config[mode_name]:
                        self.temp_mode_config[mode_name][new_name] = self.temp_mode_config[mode_name][submode_name]
                        del self.temp_mode_config[mode_name][submode_name]
                        self.load_mode_tree()
                    else:
                        QMessageBox.warning(self, "警告", "子模式名称已存在")
    
    def add_image(self):
        """
        添加图像
        """
        current_item = self.mode_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个模式")
            return
        
        # 获取模式路径
        mode_path = []
        item = current_item
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        # 构建模式目录
        if len(mode_path) == 1:
            # 顶级模式
            mode_name = mode_path[0]
            # 从临时模式配置中获取模式对应的目录名
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get('default', '')
            else:
                dir_name = mode_data
        else:
            # 子模式
            mode_name = mode_path[0]
            submode_name = mode_path[1]
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get(submode_name, '')
            else:
                dir_name = mode_data
        
        # 打开文件选择对话框
        files, _ = QFileDialog.getOpenFileNames(self, "选择图像", "", "图像文件 (*.png *.jpg *.jpeg *.bmp)")
        if files:
            # 构建图像目录路径
            if dir_name:
                mode_dir = os.path.join(self.source_dir, dir_name)
                if not os.path.exists(mode_dir):
                    os.makedirs(mode_dir)
                
                # 复制文件
                for file in files:
                    filename = os.path.basename(file)
                    dest_path = os.path.join(mode_dir, filename)
                    if not os.path.exists(dest_path):
                        try:
                            import shutil
                            shutil.copy(file, dest_path)
                        except Exception as e:
                            QMessageBox.warning(self, "警告", f"复制文件失败: {e}")
                    else:
                        QMessageBox.warning(self, "警告", f"文件 {filename} 已存在")
                
                # 构建配置文件路径
                config_path = os.path.join(mode_dir, 'config.json')
                
                # 重新加载图像
                self.load_images(mode_path)
                
                # 弹出图像配置对话框
                for file in files:
                    filename = os.path.basename(file)
                    # 查找新添加的图像项
                    for i in range(self.img_list.count()):
                        item = self.img_list.item(i)
                        if item.text() == filename:
                            # 选择该图像
                            self.img_list.setCurrentItem(item)
                            # 获取当前模式的所有图像名称
                            image_list = []
                            for i in range(self.img_list.count()):
                                item = self.img_list.item(i)
                                image_list.append(item.text())
                            
                            # 打开配置对话框
                            dialog = ImageConfigDialog(self, filename, {}, config_path, image_list)
                            if dialog.exec() == QDialog.DialogCode.Accepted:
                                # 检查是否需要重命名文件
                                new_name = dialog.name_line_edit.text()
                                if new_name != filename:
                                    # 构建旧文件和新文件的路径
                                    old_path = os.path.join(mode_dir, filename)
                                    new_path = os.path.join(mode_dir, new_name)
                                    # 重命名文件
                                    try:
                                        os.rename(old_path, new_path)
                                    except Exception as e:
                                        QMessageBox.warning(self, "警告", f"重命名文件失败: {e}")
                                # 重新加载图像
                                self.load_images(mode_path)
                            break
            else:
                QMessageBox.warning(self, "警告", "模式对应的目录名未设置")
    
    def delete_image(self):
        """
        删除图像
        """
        current_item = self.img_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个图像")
            return
        
        # 获取模式路径
        mode_tree_item = self.mode_tree.currentItem()
        mode_path = []
        item = mode_tree_item
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        # 构建模式目录
        if len(mode_path) == 1:
            # 顶级模式
            mode_name = mode_path[0]
            # 从临时模式配置中获取模式对应的目录名
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get('default', '')
            else:
                dir_name = mode_data
        else:
            # 子模式
            mode_name = mode_path[0]
            submode_name = mode_path[1]
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get(submode_name, '')
            else:
                dir_name = mode_data
        
        # 构建图像路径
        if dir_name:
            img_name = current_item.text()
            img_path = os.path.join(self.source_dir, dir_name, img_name)
            
            # 确认删除
            if QMessageBox.question(self, "确认删除", f"确定要删除 {img_name} 吗？", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                if os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                        self.img_list.takeItem(self.img_list.row(current_item))
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"删除文件失败: {e}")
     
    def edit_image_config(self):
        """
        编辑图像配置
        """
        current_item = self.img_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个图像")
            return
        
        # 获取模式路径
        mode_tree_item = self.mode_tree.currentItem()
        mode_path = []
        item = mode_tree_item
        while item:
            mode_path.insert(0, item.text(0))
            item = item.parent()
        
        # 构建模式目录
        if len(mode_path) == 1:
            # 顶级模式
            mode_name = mode_path[0]
            # 从临时模式配置中获取模式对应的目录名
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get('default', '')
            else:
                dir_name = mode_data
        else:
            # 子模式
            mode_name = mode_path[0]
            submode_name = mode_path[1]
            mode_data = self.temp_mode_config.get(mode_name)
            if isinstance(mode_data, dict):
                dir_name = mode_data.get(submode_name, '')
            else:
                dir_name = mode_data
        
        # 构建配置文件路径
        if dir_name:
            config_path = os.path.join(self.source_dir, dir_name, 'config.json')
            image_name = current_item.text()
            
            # 加载配置文件
            config_data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    # 获取图像配置
                    image_key = os.path.splitext(image_name)[0]
                    config_data = config.get("image_paths", {}).get(image_key, {})
                except Exception as e:
                    print(f"加载配置文件失败: {e}")
            
            # 获取当前模式的所有图像名称
            image_list = []
            for i in range(self.img_list.count()):
                item = self.img_list.item(i)
                image_list.append(item.text())
            
            # 打开图像配置对话框
            dialog = ImageConfigDialog(self, image_name, config_data, config_path, image_list)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 重新加载图像
                self.load_images(mode_path)
    
    def show_usage_instructions(self):
        """
        显示使用说明
        """
        # 创建自定义对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("使用说明")
        dialog.resize(600, 400)  # 减小弹窗大小
        
        # 创建布局
        main_layout = QVBoxLayout(dialog)
        
        # 创建富文本编辑器
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        
        # 富文本内容
        rich_text = """
<h2 style="color: #333; margin-bottom: 10px;">使用说明</h2>

<h3 style="color: #555; margin-top: 15px; margin-bottom: 10px;">一、模式管理</h3>
<ol style="margin-left: 20px;">
<li><strong>添加模式</strong>：点击"添加模式"按钮，输入模式名称和目录名称（建议使用英文）</li>
<li><strong>添加子模式</strong>：选择一个顶级模式后，点击"添加子模式"按钮</li>
<li><strong>删除模式</strong>：选择要删除的模式，点击"删除模式"按钮</li>
<li><strong>重命名模式</strong>：选择要重命名的模式，点击"重命名模式"按钮</li>
</ol>

<h3 style="color: #555; margin-top: 15px; margin-bottom: 10px;">二、图像管理</h3>
<ol style="margin-left: 20px;">
<li><strong>添加图像</strong>：选择一个模式后，点击"添加图像"按钮，选择本地图像文件</li>
<li><strong>删除图像</strong>：选择要删除的图像，点击"删除图像"按钮</li>
<li><strong>编辑图像配置</strong>：选择图像后，点击"编辑图像配置"按钮</li>
<li><strong><span style="color: #d9534f;">注意：添加的本地的图片必须在执行窗口检测之后的游戏窗口内截图，否则会导致识别失败</span></strong></li>
</ol>

<h3 style="color: #555; margin-top: 15px; margin-bottom: 10px;">三、图像配置说明</h3>
<ol style="margin-left: 20px;">
<li><strong>图像名称</strong>：图像文件的名称（可修改）</li>
<li><strong>路径</strong>：图像在配置中的路径（通常与文件名相同）</li>
<li><strong>是否是挑战开始</strong>：标记该图像是否为挑战开始的标识</li>
<li><strong>消息</strong>：识别到该图像时显示的消息</li>
<li><strong>是否全局</strong>：是否在全局范围内搜索该图像</li>
<li><strong>下一张图片</strong>：识别到该图像后，下一个要识别的图像</li>
<li><strong>点击区域设置</strong>：
<ul style="margin-left: 20px;">
<li>点击图片区域：点击识别到的图像区域</li>
<li>点击自定义区域：点击指定的坐标区域，格式为[left, top, width, height]</li>
</ul>
</li>
<li><strong>OCR配置</strong>：
<ul style="margin-left: 20px;">
<br>
<strong><span style="color: #d9534f;">关于OCR：OCR是文字识别技术，在这里主要是识别游戏窗口内出现的文字内容，用于提高识别的精准度，但是会增加识别时间，建议在图像识别无法识别到时使用OCR</span></strong>
<li>是否启用OCR：启用后会进行文字识别，默认值根据配置文件中的ocr_enabled字段</li>
<li>OCR识别文本：需要识别的单个文本内容</li>
<li>OCR识别阈值：OCR识别的置信度阈值，默认值为0.8</li>
<li>OCR识别后的操作：识别到文本后执行的操作（点击文字所在区域、点击点击区域设置的区域）</li>
</ul>
</li>
</ol>

<h3 style="color: #555; margin-top: 15px; margin-bottom: 10px;">四、配置文件结构</h3>
<ul style="margin-left: 20px;">
<li><strong>mode.json</strong>：存储模式和子模式的配置</li>
<li><strong>每个模式目录下的config.json</strong>：存储该模式的图像配置</li>
</ul>

<h3 style="color: #555; margin-top: 15px; margin-bottom: 10px;">五、注意事项</h3>
<ol style="margin-left: 20px;">
<li>图像文件建议使用PNG格式，确保图像清晰</li>
<li>目录名称必须使用英文、数字或下划线</li>
<li>配置修改后需要点击"保存"按钮才能生效</li>
<li>新添加的模式需要手动添加图像并配置</li>
</ol>
        """
        
        text_edit.setHtml(rich_text)
        main_layout.addWidget(text_edit)
        
        # 添加关闭按钮
        button_layout = QHBoxLayout()
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
        # 显示对话框
        dialog.exec()

    def save(self):
        """
        保存配置
        """
        # 将临时模式配置数据保存到正式的模式配置数据中
        self.mode_config_data = self.temp_mode_config.copy()
        
        # 自动创建模式目录
        for mode_name, mode_data in self.mode_config_data.items():
            if isinstance(mode_data, str) and mode_data:
                # 顶级模式，直接使用字符串作为目录名
                dir_path = os.path.join(self.source_dir, mode_data)
                if not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path)
                        # 创建默认的config.json文件
                        config_path = os.path.join(dir_path, 'config.json')
                        if not os.path.exists(config_path):
                            with open(config_path, 'w', encoding='utf-8') as f:
                                json.dump({"image_paths": {}}, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"创建目录 {mode_data} 失败: {e}")
            elif isinstance(mode_data, dict):
                # 有子模式的情况，为每个子模式创建目录
                for submode_name, submode_dir in mode_data.items():
                    if submode_dir:
                        dir_path = os.path.join(self.source_dir, submode_dir)
                        if not os.path.exists(dir_path):
                            try:
                                os.makedirs(dir_path)
                                # 创建默认的config.json文件
                                config_path = os.path.join(dir_path, 'config.json')
                                if not os.path.exists(config_path):
                                    with open(config_path, 'w', encoding='utf-8') as f:
                                        json.dump({"image_paths": {}}, f, ensure_ascii=False, indent=2)
                            except Exception as e:
                                QMessageBox.warning(self, "警告", f"创建目录 {submode_dir} 失败: {e}")
        
        if self.save_mode_config():
            QMessageBox.information(self, "成功", "配置保存成功")
            self.accept()
        else:
            QMessageBox.warning(self, "警告", "配置保存失败")