"""
设置页面模块，包含认证设置和外观设置
"""
import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, 
                           QFormLayout, QLineEdit, QPushButton,
                           QComboBox, QLabel, QHBoxLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from core.api import WQBrainAPI

class LoginThread(QThread):
    """登录线程类"""
    # 定义信号
    finished = pyqtSignal(bool, str)  # 登录结果信号
    user_info = pyqtSignal(str)       # 用户信息信号
    
    def __init__(self, api, username, password):
        super().__init__()
        self.api = api
        self.username = username
        self.password = password
        
    def run(self):
        """线程执行函数"""
        try:
            # 保存认证信息
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            with open(os.path.join(config_dir, 'credentials.json'), 'w') as f:
                json.dump([self.username, self.password], f)
                
            # 调用API登录
            success, error_msg = self.api.login()
            if success:
                # 读取token文件获取用户ID
                token_path = os.path.join(config_dir, 'token.json')
                if os.path.exists(token_path):
                    with open(token_path, 'r') as f:
                        token_data = json.load(f)
                        user_id = token_data.get('user_id')
                        if user_id:
                            self.user_info.emit(user_id)
            
            self.finished.emit(success, error_msg)
            
        except Exception as e:
            self.finished.emit(False, str(e))

class AutoHideMessage(QLabel):
    """自动隐藏的消息提示框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置样式
        self.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 默认隐藏
        self.hide()
        
    def showMessage(self, text, duration=2000):
        """显示消息，duration为显示时长(毫秒)"""
        self.setText(text)
        self.show()
        # 创建定时器自动隐藏
        QTimer.singleShot(duration, self.hide)

class SettingsWidget(QWidget):
    """设置页面类"""
    
    # 定义信号
    login_success = pyqtSignal(str)  # 登录成功信号，传递用户ID
    logout_success = pyqtSignal()    # 登出成功信号
    
    def __init__(self):
        super().__init__()
        self.api = WQBrainAPI()
        self.login_thread = None
        
        # 创建主布局
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 添加认证设置组
        auth_group = self.create_auth_group()
        layout.addWidget(auth_group)
        
        # 添加外观设置组
        appearance_group = self.create_appearance_group()
        layout.addWidget(appearance_group)
        
        self.setLayout(layout)
        
        # 加载保存的设置
        self.load_settings()
        
    def create_auth_group(self):
        """创建认证设置组"""
        group_box = QGroupBox("认证设置")
        layout = QFormLayout()
        
        # 用户名输入框
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入邮箱")
        layout.addRow("用户名:", self.username_input)
        
        # 密码输入框
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入密码")
        layout.addRow("密码:", self.password_input)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        
        # 登录按钮
        self.login_button = QPushButton("登录")
        self.login_button.setStyleSheet(
            "background-color: #0078D4; color: white; padding: 5px 15px;"
        )
        self.login_button.clicked.connect(self.handle_login)
        button_layout.addWidget(self.login_button)
        
        # 退出登录按钮
        self.logout_button = QPushButton("退出登录")
        self.logout_button.setStyleSheet(
            "background-color: #E81123; color: white; padding: 5px 15px;"
        )
        self.logout_button.clicked.connect(self.handle_logout)
        self.logout_button.setEnabled(False)  # 初始状态禁用
        button_layout.addWidget(self.logout_button)
        
        layout.addRow("", button_layout)
        
        # 添加清理缓存按钮
        clear_button = QPushButton("清理所有缓存")
        clear_button.setStyleSheet(
            "background-color: #666666; color: white; padding: 5px 15px;"
        )
        clear_button.clicked.connect(self.handle_clear_cache)
        layout.addRow("", clear_button)
        
        group_box.setLayout(layout)
        return group_box
        
    def create_appearance_group(self):
        """创建外观设置组"""
        group_box = QGroupBox("外观设置")
        layout = QFormLayout()
        
        # 主题选择下拉框
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["商务蓝", "暗黑模式", "浅色模式"])
        self.theme_combo.currentTextChanged.connect(self.handle_theme_change)
        layout.addRow("主题:", self.theme_combo)
        
        group_box.setLayout(layout)
        return group_box
    
    def handle_logout(self):
        """处理退出登录请求"""
        try:
            if self.api.logout():
                self.login_button.setText("登录")
                self.login_button.setEnabled(True)
                self.logout_button.setEnabled(False)
                self.logout_success.emit()  # 发送登出成功信号
                print("已成功退出登录")
            else:
                print("退出登录失败")
                QMessageBox.warning(self, "警告", "退出登录失败，请查看日志")
        except Exception as e:
            print(f"退出登录时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"退出登录时出错: {str(e)}")
            
    def handle_login(self):
        """处理登录"""
        success, error_msg, user_id = self.api.login()
        if success:
            # 更新UI状态
            self.update_login_status(True)
            # 显示自动消失的成功提示
            if not hasattr(self, 'message_label'):
                self.message_label = AutoHideMessage(self)
                # 将提示框添加到布局
                self.layout().insertWidget(0, self.message_label)
            self.message_label.showMessage(f"登录成功！欢迎回来，{user_id}")
            # 发送登录成功信号
            self.login_success.emit(user_id)
        else:
            # 显示错误消息
            QMessageBox.critical(self, "登录失败", error_msg)
            self.update_login_status(False)
    
    def handle_theme_change(self, theme):
        """处理主题更改"""
        # TODO: 实现主题切换逻辑
        pass
    
    def handle_clear_cache(self):
        """处理清理缓存请求"""
        try:
            # 显示确认对话框
            reply = QMessageBox.question(
                self, 
                "确认清理", 
                "确定要清理所有缓存数据吗？\n这将清除所有登录信息和配置数据。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # 默认选择"否"
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.api.clear_cache():
                    self.username_input.clear()
                    self.password_input.clear()
                    self.login_button.setText("登录")
                    self.login_button.setEnabled(True)
                    self.logout_button.setEnabled(False)
                    print("缓存清理成功")
                    # 弹出提示框
                    QMessageBox.information(self, "提示", "所有缓存数据已清理完成")
                else:
                    print("缓存清理失败")
                    QMessageBox.warning(self, "警告", "缓存清理失败，请查看日志")
        except Exception as e:
            print(f"清理缓存时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"清理缓存时出错: {str(e)}")
    
    def load_settings(self):
        """加载保存的设置"""
        # 尝试加载保存的认证信息
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        credentials_path = os.path.join(config_dir, 'credentials.json')
        
        if os.path.exists(credentials_path):
            with open(credentials_path, 'r') as f:
                credentials = json.load(f)
                if len(credentials) == 2:
                    self.username_input.setText(credentials[0])
                    # 不加载密码，出于安全考虑 

    def update_login_status(self, is_logged_in):
        """更新登录状态UI"""
        if is_logged_in:
            self.login_button.setText("已登录")
            self.login_button.setEnabled(False)
            self.logout_button.setEnabled(True)
            # 清空密码输入框
            self.password_input.clear()
        else:
            self.login_button.setText("登录")
            self.login_button.setEnabled(True)
            self.logout_button.setEnabled(False) 