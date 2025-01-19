"""
Alpha设置窗口模块
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QLineEdit, QPushButton, QGroupBox, QSpinBox,
                           QMessageBox, QInputDialog, QDialog, QTextEdit, QFileDialog,
                           QTreeWidget, QTreeWidgetItem, QMenu)
from PyQt6.QtCore import Qt, QDateTime
from core.alpha_processor import AlphaProcessor
from core.config_manager import ConfigManager
import json
from pathlib import Path

class TemplateDialog(QDialog):
    """模板信息对话框"""
    def __init__(self, parent=None, template_data=None):
        super().__init__(parent)
        self.setWindowTitle("模板信息")
        self.setMinimumWidth(400)
        self.setup_ui(template_data)
        
    def setup_ui(self, template_data=None):
        layout = QVBoxLayout(self)
        
        # 模板名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("模板名称:"))
        self.name_edit = QLineEdit()
        if template_data and 'name' in template_data:
            self.name_edit.setText(template_data['name'])
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # 模板分类
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("分类:"))
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(["动量", "反转", "基本面", "技术指标", "其他"])
        if template_data and 'category' in template_data:
            self.category_combo.setCurrentText(template_data['category'])
        category_layout.addWidget(self.category_combo)
        layout.addLayout(category_layout)
        
        # 模板描述
        layout.addWidget(QLabel("描述:"))
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("请输入模板描述...")
        if template_data and 'description' in template_data:
            self.description_edit.setText(template_data['description'])
        layout.addWidget(self.description_edit)
        
        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def get_template_info(self):
        """获取模板信息"""
        return {
            'name': self.name_edit.text(),
            'category': self.category_combo.currentText(),
            'description': self.description_edit.toPlainText(),
            'created_time': QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
        }

class AlphaSettingsWindow(QWidget):
    """Alpha设置窗口类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alpha设置")
        self.alpha_processor = AlphaProcessor()
        self.config_manager = ConfigManager()
        self.setup_ui()
        
    def _create_param_group(self, label, items=None, spin=False, suffix=""):
        """创建参数组布局"""
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        
        if spin:
            widget = QSpinBox()
            if suffix:
                widget.setSuffix(suffix)
        else:
            widget = QComboBox()
            if items:
                widget.addItems(items)
                
        layout.addWidget(widget)
        # 返回布局和控件
        return layout, widget
        
    def setup_ui(self):
        """初始化UI"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 创建上方的设置区域
        settings_group = QGroupBox("Alpha设置")
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(15, 20, 15, 15)
        settings_layout.setSpacing(12)

        # Alpha表达式输入
        alpha_layout = QHBoxLayout()
        alpha_layout.setSpacing(10)
        alpha_label = QLabel("Alpha表达式:")
        self.alpha_input = QLineEdit()
        self.alpha_input.setPlaceholderText("输入Alpha表达式，变量需要用$括起来，如: $close$ / $open$")
        self.alpha_input.textChanged.connect(self._validate_expression)
        alpha_layout.addWidget(alpha_label)
        alpha_layout.addWidget(self.alpha_input)
        settings_layout.addLayout(alpha_layout)

        # 参数设置组
        param_group = QGroupBox("参数设置")
        param_layout = QVBoxLayout()
        
        # 第一行
        row1_layout = QHBoxLayout()
        # Language
        language_layout, self.language_combo = self._create_param_group("LANGUAGE", ["Fast Expression", "Python"])
        row1_layout.addLayout(language_layout)
        # Instrument Type
        instrument_layout, self.instrument_combo = self._create_param_group("INSTRUMENT TYPE", ["Equity", "Future"])
        row1_layout.addLayout(instrument_layout)
        param_layout.addLayout(row1_layout)
        
        # 第二行
        row2_layout = QHBoxLayout()
        # Region
        region_layout, self.region_combo = self._create_param_group("REGION", ["USA", "CN", "HK"])
        row2_layout.addLayout(region_layout)
        # Universe
        universe_layout, self.universe_combo = self._create_param_group("UNIVERSE", ["TOP3000"])
        row2_layout.addLayout(universe_layout)
        # Delay
        delay_layout, self.delay_spin = self._create_param_group("DELAY", spin=True)
        self.delay_spin.setRange(0, 100)  # 设置范围
        row2_layout.addLayout(delay_layout)
        param_layout.addLayout(row2_layout)
        
        # 第三行
        row3_layout = QHBoxLayout()
        # Neutralization
        neutral_layout, self.neutral_combo = self._create_param_group("NEUTRALIZATION", ["None", "Industry", "Subindustry"])
        row3_layout.addLayout(neutral_layout)
        # Decay
        decay_layout, self.decay_spin = self._create_param_group("DECAY", spin=True)
        self.decay_spin.setRange(0, 100)  # 设置范围
        row3_layout.addLayout(decay_layout)
        # Truncation
        trunc_layout, self.trunc_spin = self._create_param_group("TRUNCATION", spin=True, suffix="%")
        self.trunc_spin.setRange(0, 100)  # 设置范围
        row3_layout.addLayout(trunc_layout)
        param_layout.addLayout(row3_layout)
        
        # 第四行
        row4_layout = QHBoxLayout()
        # Pasteurization
        past_layout, self.past_combo = self._create_param_group("PASTEURIZATION", ["On", "Off"])
        row4_layout.addLayout(past_layout)
        # Unit Handling
        unit_layout, self.unit_combo = self._create_param_group("UNIT HANDLING", ["Verify", "Ignore"])
        row4_layout.addLayout(unit_layout)
        # NAN Handling
        nan_layout, self.nan_combo = self._create_param_group("NAN HANDLING", ["On", "Off"])
        row4_layout.addLayout(nan_layout)
        param_layout.addLayout(row4_layout)
        
        param_group.setLayout(param_layout)
        settings_layout.addWidget(param_group)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # 添加模板管理区域到底部
        templates_group = QGroupBox("模板管理")
        templates_layout = QVBoxLayout()
        templates_layout.setContentsMargins(15, 20, 15, 15)
        templates_layout.setSpacing(12)

        # 创建树形视图
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabels(["名称", "分类", "创建时间"])
        self.template_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.template_tree.customContextMenuRequested.connect(self.show_template_context_menu)
        self.template_tree.itemSelectionChanged.connect(self._on_template_selected)
        templates_layout.addWidget(self.template_tree)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # 模板操作按钮
        new_template_btn = QPushButton("新建模板")
        new_template_btn.clicked.connect(self.create_template)
        self.clear_settings_btn = QPushButton("清空设置")
        self.clear_settings_btn.clicked.connect(self.clear_settings)
        import_btn = QPushButton("导入模板")
        import_btn.clicked.connect(self.import_template)
        export_btn = QPushButton("导出模板")
        export_btn.clicked.connect(self.export_template)

        button_layout.addWidget(new_template_btn)
        button_layout.addWidget(self.clear_settings_btn)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(export_btn)
        button_layout.addStretch()

        templates_layout.addLayout(button_layout)
        templates_group.setLayout(templates_layout)

        # 添加到主布局
        main_layout.addWidget(templates_group)
        
        self.setLayout(main_layout)
        self._load_templates()
        
    def _load_templates(self):
        """加载所有模板到树形视图"""
        self.template_tree.clear()
        templates = self.config_manager.load_alpha_templates()
        
        # 按分类组织模板
        categories = {}
        for name, data in templates.items():
            category = data.get('category', '未分类')
            if category not in categories:
                categories[category] = QTreeWidgetItem([category])
                self.template_tree.addTopLevelItem(categories[category])
            
            template_item = QTreeWidgetItem([
                name,
                category,
                data.get('created_time', '')
            ])
            categories[category].addChild(template_item)
            
        self.template_tree.expandAll()
        
    def show_template_context_menu(self, position):
        """显示模板右键菜单"""
        item = self.template_tree.itemAt(position)
        if not item or not item.parent():  # 忽略分类项
            return
            
        menu = QMenu()
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        export_action = menu.addAction("导出")
        
        action = menu.exec(self.template_tree.viewport().mapToGlobal(position))
        if action == edit_action:
            self.edit_template(item)
        elif action == delete_action:
            self.delete_template(item)
        elif action == export_action:
            self.export_template(item)
            
    def _on_template_selected(self):
        """处理模板选择变化"""
        item = self.template_tree.currentItem()
        if not item or not item.parent():  # 忽略分类项
            return
            
        template_name = item.text(0)
        templates = self.config_manager.load_alpha_templates()
        if template_name in templates:
            self.set_settings(templates[template_name])
            
    def delete_template(self, item=None):
        """删除模板"""
        if not item:
            item = self.template_tree.currentItem()
        if not item or not item.parent():  # 忽略分类项
            return
            
        template_name = item.text(0)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模板 '{template_name}' 吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            templates = self.config_manager.load_alpha_templates()
            if template_name in templates:
                del templates[template_name]
                self.config_manager._save_templates(templates)
                self._load_templates()
                self.clear_settings()
                QMessageBox.information(self, "删除成功", f"模板 '{template_name}' 已删除")
                
    def export_template(self, item=None):
        """导出模板"""
        if not item:
            item = self.template_tree.currentItem()
        if not item or not item.parent():  # 忽略分类项
            return
            
        template_name = item.text(0)
        templates = self.config_manager.load_alpha_templates()
        if template_name not in templates:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            f"{template_name}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(templates[template_name], f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", "模板导出成功")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"导出模板时发生错误：{str(e)}")
                
    def clear_settings(self):
        """清空所有设置为默认值"""
        default_settings = {
            'language': 'FASTEXPR',
            'instrument_type': 'EQUITY',
            'region': 'USA',
            'universe': 'TOP3000',
            'delay': 1,
            'neutralization': 'NONE',
            'decay': 0,
            'truncation': 0,
            'pasteurization': 'ON',
            'unit_handling': 'VERIFY',
            'nan_handling': 'ON',
            'alpha_expression': ''
        }
        self.set_settings(default_settings)
        # 清除当前选中的模板
        self.template_tree.clearSelection()
        
    def save_settings(self):
        """保存设置"""
        if not self._validate_settings():
            return
            
        current_text = self.template_tree.currentText()
        if not current_text:  # 如果没有选中模板，提示另存为
            reply = QMessageBox.question(
                self,
                "保存设置",
                "当前没有选中模板，是否要另存为新模板？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_as_template()
            return
            
        try:
            # 从显示文本中提取模板名称
            template_name = current_text.split(" (")[0]
            settings = self.get_settings()
            self.config_manager.save_alpha_template(template_name, settings)
            QMessageBox.information(self, "保存成功", f"模板 '{template_name}' 已更新")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置时发生错误：{str(e)}")
            
    def _select_template_by_name(self, name):
        """根据名称选中模板"""
        for i in range(self.template_tree.topLevelItemCount()):
            item = self.template_tree.topLevelItem(i)
            if item.text(0) == name:
                self.template_tree.setCurrentItem(item)
                return True
        return False
        
    def create_template(self):
        """创建新模板"""
        if not self._validate_settings():
            return
            
        dialog = TemplateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            template_info = dialog.get_template_info()
            name = template_info['name']
            
            if not name:
                QMessageBox.warning(self, "错误", "模板名称不能为空")
                return
                
            # 检查模板名称是否已存在
            templates = self.config_manager.load_alpha_templates()
            if name in templates:
                reply = QMessageBox.question(
                    self,
                    "模板已存在",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
                    
            try:
                settings = self.get_settings()
                settings.update(template_info)
                self.config_manager.save_alpha_template(name, settings)
                self._load_templates()
                
                # 选中新创建的模板
                self._select_template_by_name(name)
                QMessageBox.information(self, "保存成功", f"模板 '{name}' 已创建")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"创建模板时发生错误：{str(e)}")
                
    def edit_template(self, item):
        """编辑模板"""
        template_name = item.text(0)
        templates = self.config_manager.load_alpha_templates()
        if template_name in templates:
            dialog = TemplateDialog(self, templates[template_name])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                template_info = dialog.get_template_info()
                settings = templates[template_name]
                settings.update(template_info)
                
                # 如果名称改变，删除旧模板
                if template_info['name'] != template_name:
                    del templates[template_name]
                    
                templates[template_info['name']] = settings
                self.config_manager._save_templates(templates)
                self._load_templates()
                
    def import_template(self):
        """导入模板"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入模板",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                    
                dialog = TemplateDialog(self, template_data)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    template_info = dialog.get_template_info()
                    template_data.update(template_info)
                    self.config_manager.save_alpha_template(template_info['name'], template_data)
                    self._load_templates()
                    QMessageBox.information(self, "导入成功", "模板导入成功")
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"导入模板时发生错误：{str(e)}")
                
    def save_as_template(self):
        """另存为模板"""
        if not self._validate_settings():
            return
            
        dialog = TemplateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            template_info = dialog.get_template_info()
            name = template_info['name']
            
            if not name:
                QMessageBox.warning(self, "错误", "模板名称不能为空")
                return
                
            try:
                # 检查模板名称是否已存在
                templates = self.config_manager.load_alpha_templates()
                if name in templates:
                    reply = QMessageBox.question(
                        self,
                        "模板已存在",
                        f"模板 '{name}' 已存在，是否覆盖？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return
                        
                # 获取当前设置并添加模板信息
                settings = self.get_settings()
                settings.update(template_info)
                
                # 保存模板
                self.config_manager.save_alpha_template(name, settings)
                self._load_templates()
                
                # 选中新保存的模板
                self._select_template_by_name(name)
                QMessageBox.information(self, "保存成功", f"模板 '{name}' 已保存")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存模板时发生错误：{str(e)}")
        
    def _validate_expression(self):
        """验证Alpha表达式"""
        expression = self.alpha_input.text()
        if expression:
            is_valid = self.alpha_processor.validate_expression(expression)
            if is_valid:
                self.alpha_input.setStyleSheet("QLineEdit { background-color: #e6ffe6; }")
            else:
                self.alpha_input.setStyleSheet("QLineEdit { background-color: #ffe6e6; }")
        else:
            self.alpha_input.setStyleSheet("")
            
    def get_settings(self):
        """获取所有设置参数"""
        # 特殊处理language字段
        language = self.language_combo.currentText()
        if language.upper() == "FAST EXPRESSION":
            language = "FASTEXPR"
        else:
            language = language.upper()
            
        settings = {
            'language': language,
            'instrument_type': self.instrument_combo.currentText().upper(),
            'region': self.region_combo.currentText().upper(),
            'universe': self.universe_combo.currentText().upper(),
            'delay': self.delay_spin.value(),
            'neutralization': self.neutral_combo.currentText().upper(),
            'decay': self.decay_spin.value(),
            'truncation': self.trunc_spin.value(),
            'pasteurization': self.past_combo.currentText().upper(),
            'unit_handling': self.unit_combo.currentText().upper(),
            'nan_handling': self.nan_combo.currentText().upper(),
            'alpha_expression': self.alpha_processor.format_expression(self.alpha_input.text())
        }
        return settings
        
    def set_settings(self, settings):
        """设置参数值"""
        if not settings:
            return
            
        # 特殊处理language字段
        language = settings.get('language', '')
        if language == 'FASTEXPR':
            self.language_combo.setCurrentText('Fast Expression')
        else:
            self.language_combo.setCurrentText(language.title())  # 转换为首字母大写
            
        # 设置其他下拉框值（将存储的大写值转换为首字母大写显示）
        self.instrument_combo.setCurrentText(settings.get('instrument_type', '').title())
        self.region_combo.setCurrentText(settings.get('region', ''))  # 区域保持大写
        self.universe_combo.setCurrentText(settings.get('universe', ''))  # universe保持大写
        
        # 设置数值型控件
        self.delay_spin.setValue(int(settings.get('delay', 0)))
        self.decay_spin.setValue(int(settings.get('decay', 0)))
        self.trunc_spin.setValue(int(settings.get('truncation', 0)))
        
        # 设置其他下拉框（将存储的大写值转换为首字母大写显示）
        neutralization = settings.get('neutralization', 'NONE').title()
        if neutralization == "None":  # 特殊处理None值
            self.neutral_combo.setCurrentText("None")
        else:
            self.neutral_combo.setCurrentText(neutralization)
            
        # On/Off类型的设置
        self.past_combo.setCurrentText(settings.get('pasteurization', 'ON').title())
        self.unit_combo.setCurrentText(settings.get('unit_handling', 'VERIFY').title())
        self.nan_combo.setCurrentText(settings.get('nan_handling', 'ON').title())
        
        # 设置Alpha表达式
        if 'alpha_expression' in settings:
            self.alpha_input.setText(settings['alpha_expression'])
            
        # 触发表达式验证
        self._validate_expression()
        
    def _validate_settings(self):
        """验证当前设置是否有效"""
        if not self.alpha_input.text():
            QMessageBox.warning(self, "验证错误", "Alpha表达式不能为空")
            return False
            
        if not self.alpha_processor.validate_expression(self.alpha_input.text()):
            QMessageBox.warning(self, "验证错误", "Alpha表达式格式不正确，只能包含一个变量，且需要用$括起来")
            return False
            
        return True 