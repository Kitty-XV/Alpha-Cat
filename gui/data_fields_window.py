"""
数据字段页面模块
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                           QLineEdit, QPushButton, QGroupBox, QComboBox,
                           QSpinBox, QTextEdit, QMessageBox, QTableWidget,
                           QTableWidgetItem, QHeaderView, QFormLayout, QProgressDialog,
                           QTreeWidget, QTreeWidgetItem, QDialog, QMenu, QInputDialog)
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QDateTime
from urllib.parse import urlparse, parse_qs
import requests
import json
import pandas as pd
from pathlib import Path
import logging
import shutil

class DataFetcherThread(QThread):
    """数据获取线程"""
    progress_updated = pyqtSignal(int, str)  # 进度更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    data_fetched = pyqtSignal(list, list)  # 数据获取完成信号
    
    def __init__(self, session, api_url):
        super().__init__()
        self.session = session
        self.api_url = api_url
        self.is_running = True
        
    def run(self):
        try:
            # 认证
            self.progress_updated.emit(10, "正在认证...")
            auth_response = self.session.post('https://api.worldquantbrain.com/authentication')
            
            if auth_response.status_code == 401:
                self.error_occurred.emit("认证失败：用户名或密码错误")
                return
            elif auth_response.status_code not in [200, 201]:
                self.error_occurred.emit(f"认证失败：服务器返回状态码 {auth_response.status_code}")
                return
                
            # 获取数据
            self.progress_updated.emit(20, "开始获取数据...")
            
            # 先获取总数据量
            response = self.session.get(self.api_url)
            if response.status_code == 200:
                data = response.json()
                total_count = data.get('count', 0)
                if total_count == 0:
                    self.error_occurred.emit("未找到数据")
                    return
                    
                self.progress_updated.emit(30, f"找到 {total_count} 条数据，开始获取...")
            else:
                self.error_occurred.emit(f"获取数据总量失败：HTTP {response.status_code}")
                return
            
            all_fields = []
            first_page_fields = []
            offset = 0
            limit = 50
            
            while self.is_running:
                try:
                    current_url = f"{self.api_url}&offset={offset}"
                    response = self.session.get(current_url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'results' in data:
                            results = data['results']
                            if not results:
                                break
                                
                            for field in results:
                                field_info = {
                                    'id': field.get('id', ''),
                                    'name': field.get('name', '')
                                }
                                
                                all_fields.append(field_info)
                                if offset == 0:
                                    first_page_fields.append(f"{field_info['id']} - {field_info['name']}")
                                    
                            offset += limit
                            
                            # 计算实际进度百分比
                            progress = min(95, 30 + (len(all_fields) * 65 // total_count))
                            self.progress_updated.emit(
                                progress,
                                f"已获取 {len(all_fields)}/{total_count} 个字段..."
                            )
                        else:
                            break
                    else:
                        self.error_occurred.emit(f"请求失败：HTTP {response.status_code}")
                        return
                        
                except Exception as e:
                    self.error_occurred.emit(f"获取数据出错：{str(e)}")
                    return
                    
            if all_fields:
                self.progress_updated.emit(100, "数据获取完成！")
                self.data_fetched.emit(all_fields, first_page_fields)
                
        except Exception as e:
            self.error_occurred.emit(f"发生错误：{str(e)}")
            
    def stop(self):
        """停止线程"""
        self.is_running = False

class DataFieldDialog(QDialog):
    """数据字段信息对话框"""
    def __init__(self, parent=None, field_info=None):
        super().__init__(parent)
        self.setWindowTitle("数据字段信息")
        self.setMinimumWidth(400)
        self.setup_ui(field_info)
        
    def setup_ui(self, field_info=None):
        layout = QVBoxLayout(self)
        
        # 名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("名称:"))
        self.name_edit = QLineEdit()
        if field_info and 'name' in field_info:
            self.name_edit.setText(field_info['name'])
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # 描述
        layout.addWidget(QLabel("描述:"))
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("请输入数据字段描述...")
        if field_info and 'description' in field_info:
            self.description_edit.setText(field_info['description'])
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
        
    def get_field_info(self):
        """获取字段信息"""
        return {
            'name': self.name_edit.text(),
            'description': self.description_edit.toPlainText(),
            'created_time': QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
        }

class DataFieldsWidget(QWidget):
    """数据字段页面类"""
    
    # 定义信号
    url_converted = pyqtSignal(str)
    data_fetched = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.session = None
        self.fetcher_thread = None
        # 设置项目根目录
        self.project_root = Path(__file__).parent.parent
        # 确保data目录及其子目录存在
        self.data_dir = self.project_root / "data"
        self.raw_data_dir = self.data_dir / "raw"
        self.processed_data_dir = self.data_dir / "processed"
        self.data_dir.mkdir(exist_ok=True)
        self.raw_data_dir.mkdir(exist_ok=True)
        self.processed_data_dir.mkdir(exist_ok=True)
        # fields_info.json 现在存放在raw目录下
        self.fields_info_file = self.raw_data_dir / "fields_info.json"
        
        # 初始化时自动加载已有的数据字段
        self._load_existing_fields()
        
    def setup_ui(self):
        """初始化UI"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # URL转换组
        url_group = QGroupBox("URL转换")
        url_layout = QVBoxLayout()
        url_layout.setSpacing(12)
        url_layout.setContentsMargins(15, 20, 15, 15)
        
        # 平台URL输入
        platform_url_layout = QHBoxLayout()
        platform_url_layout.setSpacing(10)
        
        platform_url_label = QLabel("平台URL:")
        self.platform_url_input = QLineEdit()
        self.platform_url_input.setPlaceholderText("输入platform.worldquantbrain.com的URL...")
        self.platform_url_input.setMinimumWidth(400)
        
        convert_button = QPushButton("转换")
        convert_button.setFixedWidth(100)
        convert_button.clicked.connect(self.convert_url)
        
        platform_url_layout.addWidget(platform_url_label)
        platform_url_layout.addWidget(self.platform_url_input)
        platform_url_layout.addWidget(convert_button)
        
        # API URL显示
        api_url_layout = QHBoxLayout()
        api_url_layout.setSpacing(10)
        
        api_url_label = QLabel("API URL:")
        self.api_url_display = QLineEdit()
        self.api_url_display.setReadOnly(True)
        
        api_url_layout.addWidget(api_url_label)
        api_url_layout.addWidget(self.api_url_display)
        
        # 添加到URL组布局
        url_layout.addLayout(platform_url_layout)
        url_layout.addLayout(api_url_layout)
        url_group.setLayout(url_layout)
        
        # 获取数据按钮
        fetch_button = QPushButton("获取数据字段")
        fetch_button.setFixedWidth(200)
        fetch_button.clicked.connect(self.fetch_data_fields)
        
        # 创建水平布局来居中放置获取按钮
        fetch_button_layout = QHBoxLayout()
        fetch_button_layout.addStretch()
        fetch_button_layout.addWidget(fetch_button)
        fetch_button_layout.addStretch()
        
        # 添加URL组和获取按钮到主布局
        main_layout.addWidget(url_group)
        main_layout.addLayout(fetch_button_layout)
        
        # 创建水平分割布局用于左右面板
        split_layout = QHBoxLayout()
        split_layout.setSpacing(20)
        
        # 左侧：数据字段管理区域
        fields_group = QGroupBox("数据字段管理")
        fields_layout = QVBoxLayout()
        fields_layout.setContentsMargins(15, 20, 15, 15)
        
        # 字段列表
        self.fields_tree = QTreeWidget()
        self.fields_tree.setHeaderLabels(["名称", "描述", "创建时间"])
        self.fields_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fields_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.fields_tree.itemSelectionChanged.connect(self._on_field_selected)
        fields_layout.addWidget(self.fields_tree)
        
        fields_group.setLayout(fields_layout)
        
        # 右侧：数据预览区域
        display_group = QGroupBox("数据预览")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(15, 20, 15, 15)
        
        # 添加预览控制
        preview_control_layout = QHBoxLayout()
        preview_label = QLabel("选择预览字段:")
        self.preview_combo = QComboBox()
        self.preview_combo.currentTextChanged.connect(self._update_preview)
        preview_control_layout.addWidget(preview_label)
        preview_control_layout.addWidget(self.preview_combo)
        preview_control_layout.addStretch()
        display_layout.addLayout(preview_control_layout)
        
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.data_display.setMinimumHeight(300)
        display_layout.addWidget(self.data_display)
        display_group.setLayout(display_layout)
        
        # 添加左右面板到分割布局
        split_layout.addWidget(fields_group, 1)  # 比例1
        split_layout.addWidget(display_group, 1)  # 比例1
        
        # 添加分割布局到主布局
        main_layout.addLayout(split_layout)
        
    def set_session(self, session):
        """设置API会话"""
        self.session = session
        
    def convert_url(self):
        """转换平台URL为API URL"""
        platform_url = self.platform_url_input.text()
        try:
            # 解析URL
            parsed_url = urlparse(platform_url)
            params = parse_qs(parsed_url.query)
            
            # 从路径中提取dataset_id
            path_parts = parsed_url.path.split('/')
            dataset_id = ''
            if 'data-sets' in path_parts:
                try:
                    dataset_index = path_parts.index('data-sets')
                    if len(path_parts) > dataset_index + 1:
                        dataset_id = path_parts[dataset_index + 1]
                except ValueError:
                    pass
            
            # 构建新的API URL
            api_params = {
                'delay': params.get('delay', ['1'])[0],
                'instrumentType': params.get('instrumentType', ['EQUITY'])[0],
                'limit': '50',  # 固定使用最大limit值50
                'offset': params.get('offset', ['0'])[0],
                'region': params.get('region', ['USA'])[0],
                'search': params.get('search', [''])[0],
                'universe': params.get('universe', ['TOP3000'])[0]
            }
            
            # 如果有dataset_id，添加到参数中
            if dataset_id:
                api_params['dataset_id'] = dataset_id
            
            # 构建查询字符串
            query_string = '&'.join([f"{k}={v}" for k, v in api_params.items() if v])
            
            # 构建最终的API URL
            api_url = f"https://api.worldquantbrain.com/data-fields?{query_string}"
            
            self.api_url_display.setText(api_url)
            logging.info(f"URL转换成功: {api_url}")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"URL转换失败: {str(e)}")
            logging.error(f"URL转换失败: {str(e)}")
            
    def fetch_data_fields(self):
        """获取数据字段"""
        if not self.session:
            QMessageBox.warning(self, "错误", "请先在设置页面完成API认证")
            return
            
        api_url = self.api_url_display.text()
        if not api_url:
            QMessageBox.warning(self, "错误", "请先输入平台URL并点击转换按钮")
            return
            
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("准备获取数据...", "取消", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_fetch)
        
        # 设置进度条样式
        self.progress_dialog.setStyleSheet("""
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                text-align: center;
                background-color: #F5F5F5;
            }
            QProgressBar::chunk {
                background-color: #0078D4;
                width: 1px;
            }
        """)
        
        self.progress_dialog.show()
        
        # 创建并启动数据获取线程
        self.fetcher_thread = DataFetcherThread(self.session, api_url)
        self.fetcher_thread.progress_updated.connect(self.update_progress)
        self.fetcher_thread.error_occurred.connect(self.handle_error)
        self.fetcher_thread.data_fetched.connect(self.save_data)
        self.fetcher_thread.start()
        
    def cancel_fetch(self):
        """取消数据获取"""
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            self.fetcher_thread.stop()
            self.fetcher_thread.wait()
            
    def update_progress(self, value, message):
        """更新进度对话框"""
        if self.progress_dialog:
            self.progress_dialog.setValue(value)
            self.progress_dialog.setLabelText(message)
            
    def handle_error(self, error_message):
        """处理错误"""
        QMessageBox.critical(self, "错误", error_message)
        self.progress_dialog.close()
        
    def _check_file_exists(self, name):
        """检查文件名是否已存在"""
        csv_file = self.raw_data_dir / f"{name}.csv"
        fields_info = self._load_fields_info()
        return csv_file.exists() or name in fields_info
        
    def save_data(self, all_fields, first_page_fields):
        """保存数据"""
        try:
            # 更新显示
            self.data_display.setText('\n'.join(first_page_fields))
            
            while True:
                # 弹出保存对话框
                dialog = DataFieldDialog(self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    field_info = dialog.get_field_info()
                    field_name = field_info['name']
                    
                    if not field_name:
                        QMessageBox.warning(self, "错误", "字段名称不能为空")
                        continue
                        
                    # 检查文件名是否已存在
                    if self._check_file_exists(field_name):
                        reply = QMessageBox.question(
                            self,
                            "文件已存在",
                            f"数据字段 '{field_name}' 已存在，是否覆盖？",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.No:
                            continue
                            
                    # 保存原始CSV文件到raw目录
                    raw_csv_file = self.raw_data_dir / f"{field_name}.csv"
                    
                    # 只提取字段ID
                    field_ids = [field['id'] for field in all_fields]
                    df = pd.DataFrame({'field_id': field_ids})
                    df.to_csv(raw_csv_file, index=False, encoding='utf-8')
                    
                    # 保存字段信息
                    fields_info = self._load_fields_info()
                    fields_info[field_name] = field_info
                    self._save_fields_info(fields_info)
                    
                    # 更新预览下拉框
                    current_index = self.preview_combo.findText(field_name)
                    if current_index == -1:
                        self.preview_combo.addItem(field_name)
                    self.preview_combo.setCurrentText(field_name)
                    
                    # 重新加载字段列表
                    self._load_fields_info()
                    
                    if raw_csv_file.exists():
                        file_size = raw_csv_file.stat().st_size
                        logging.info(f"已保存 {len(field_ids)} 个字段ID到: {raw_csv_file} (文件大小: {file_size} 字节)")
                        QMessageBox.information(
                            self,
                            "保存成功",
                            f"已保存全部 {len(field_ids)} 个字段ID到:\n{raw_csv_file}\n(界面仅显示前50条)"
                        )
                    else:
                        raise Exception("文件保存失败：文件不存在")
                    break  # 保存成功，退出循环
                else:
                    # 用户取消保存
                    break
                    
        except Exception as e:
            error_msg = f"保存数据失败: {str(e)}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.warning(self, "保存失败", f"保存数据时出错：\n{str(e)}")
        finally:
            self.progress_dialog.close()
            
    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.fields_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        
        action = menu.exec(self.fields_tree.viewport().mapToGlobal(position))
        if action == edit_action:
            self.edit_field(item)
        elif action == delete_action:
            self.delete_field(item)
            
    def edit_field(self, item):
        """编辑字段信息"""
        field_name = item.text(0)
        fields_info = self._load_fields_info()
        
        if field_name in fields_info:
            dialog = DataFieldDialog(self, fields_info[field_name])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_info = dialog.get_field_info()
                
                # 如果名称改变，重命名文件
                if new_info['name'] != field_name:
                    old_path = self.raw_data_dir / f"{field_name}.csv"
                    new_path = self.raw_data_dir / f"{new_info['name']}.csv"
                    if old_path.exists():
                        shutil.move(old_path, new_path)
                    del fields_info[field_name]
                    
                fields_info[new_info['name']] = new_info
                self._save_fields_info(fields_info)
                self._load_fields_info()
                
    def delete_field(self, item):
        """删除字段"""
        field_name = item.text(0)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除数据字段 '{field_name}' 吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 只删除raw目录中的CSV文件
            csv_path = self.raw_data_dir / f"{field_name}.csv"
            if csv_path.exists():
                csv_path.unlink()
                
            # 删除信息记录
            fields_info = self._load_fields_info()
            if field_name in fields_info:
                del fields_info[field_name]
                self._save_fields_info(fields_info)
                self._load_fields_info()
                QMessageBox.information(self, "删除成功", f"数据字段 '{field_name}' 已删除")
                
    def _update_preview(self, field_name):
        """更新预览内容"""
        if not field_name:
            self.data_display.clear()
            return
            
        try:
            # 只从raw目录读取数据
            csv_file = self.raw_data_dir / f"{field_name}.csv"
            
            if csv_file.exists():
                df = pd.read_csv(csv_file)
                preview = df['field_id'].head(50).tolist()
                self.data_display.setText('\n'.join(map(str, preview)))
            else:
                self.data_display.clear()
        except Exception as e:
            logging.error(f"更新预览时发生错误: {str(e)}")
            self.data_display.clear()
            
    def _on_field_selected(self):
        """处理字段选择变化"""
        item = self.fields_tree.currentItem()
        if item:
            field_name = item.text(0)
            current_index = self.preview_combo.findText(field_name)
            if current_index != -1:
                self.preview_combo.setCurrentIndex(current_index)
                
    def _load_existing_fields(self):
        """加载已有的数据字段"""
        try:
            # 加载字段信息
            fields_info = self._load_fields_info()
            
            # 更新预览下拉框
            self.preview_combo.clear()
            field_names = []
            
            # 只检查raw目录中的CSV文件
            for field_name in list(fields_info.keys()):
                csv_file = self.raw_data_dir / f"{field_name}.csv"
                if not csv_file.exists():
                    # 如果CSV文件不存在，从信息记录中删除
                    del fields_info[field_name]
                    self._save_fields_info(fields_info)
                else:
                    field_names.append(field_name)
                    
            # 添加字段到预览下拉框
            if field_names:
                # 添加一个空选项作为默认值
                self.preview_combo.addItem("")
                self.preview_combo.addItems(field_names)
                # 默认选择空选项
                self.preview_combo.setCurrentIndex(0)
            
            # 清空预览区域
            self.data_display.clear()
            
            # 更新树形视图
            self._load_fields_info()
            
        except Exception as e:
            logging.error(f"加载数据字段时发生错误: {str(e)}")
            
    def _load_fields_info(self):
        """加载字段信息"""
        if not self.fields_info_file.exists():
            return {}
            
        try:
            with open(self.fields_info_file, 'r', encoding='utf-8') as f:
                fields_info = json.load(f)
                
            # 更新树形视图
            self.fields_tree.clear()
            for name, info in fields_info.items():
                item = QTreeWidgetItem([
                    name,
                    info.get('description', ''),
                    info.get('created_time', '')
                ])
                self.fields_tree.addTopLevelItem(item)
                
            return fields_info
        except Exception:
            return {}
            
    def _save_fields_info(self, fields_info):
        """保存字段信息"""
        with open(self.fields_info_file, 'w', encoding='utf-8') as f:
            json.dump(fields_info, f, ensure_ascii=False, indent=2) 