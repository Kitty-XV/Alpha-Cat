"""
主窗口模块，包含顶部导航栏和主要内容区域
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                           QPushButton, QStackedWidget, QToolBar,
                           QLabel, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt
from .settings_window import SettingsWidget
from .data_fields_window import DataFieldsWidget
from .alpha_settings_window import AlphaSettingsWindow

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WQBrain App")
        self.resize(800, 600)
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 使用垂直布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        main_layout.setSpacing(0)  # 移除间距
        
        # 创建顶部导航栏
        nav_bar = self.create_nav_bar()
        main_layout.addWidget(nav_bar)
        
        # 创建内容区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)  # 添加内容区域边距
        
        # 创建堆叠窗口部件用于切换不同页面
        self.stacked_widget = QStackedWidget()
        
        # 创建并添加各个页面
        self.settings_widget = SettingsWidget()
        self.settings_widget.login_success.connect(self.update_user_info)
        self.settings_widget.logout_success.connect(self.clear_user_info)
        self.stacked_widget.addWidget(self.settings_widget)
        
        self.data_widget = DataFieldsWidget()
        self.stacked_widget.addWidget(self.data_widget)
        
        # 创建Alpha设置界面
        self.alpha_widget = AlphaSettingsWindow()
        self.stacked_widget.addWidget(self.alpha_widget)
        
        self.backtest_widget = QWidget()
        self.backtest_widget.setStyleSheet("background-color: #F5F5F5;")
        self.stacked_widget.addWidget(self.backtest_widget)
        
        self.batch_widget = QWidget()
        self.batch_widget.setStyleSheet("background-color: #F5F5F5;")
        self.stacked_widget.addWidget(self.batch_widget)
        
        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_widget)
        
        # 默认显示设置页面
        self.show_settings()
        self.nav_buttons[0].setChecked(True)
        
    def create_nav_bar(self):
        """创建顶部导航栏"""
        nav_bar = QWidget()
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(10, 0, 10, 0)  # 设置水平边距
        
        # 创建导航按钮
        nav_buttons = [
            ("设置", self.show_settings),
            ("数据字段", self.show_data),
            ("Alpha设置", self.show_alpha),
            ("回测", self.show_backtest),
            ("批量提交", self.show_batch)
        ]
        
        # 存储导航按钮引用
        self.nav_buttons = []
        
        for text, slot in nav_buttons:
            button = QPushButton(text)
            button.setFixedHeight(40)
            button.setStyleSheet("""
                QPushButton {
                    border: none;
                    padding: 5px 15px;
                    background: transparent;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #E5F3FF;
                    border-bottom: 2px solid #0078D4;
                }
                QPushButton:checked {
                    background-color: #CCE4FF;
                    border-bottom: 2px solid #0078D4;
                }
            """)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, b=button, s=slot: self.handle_nav_button_click(b, s))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
            
        # 添加弹性空间
        nav_layout.addStretch()
        
        # 添加用户信息标签
        self.user_label = QLabel()
        self.user_label.setStyleSheet("""
            QLabel {
                color: #0078D4;
                padding: 5px 15px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        nav_layout.addWidget(self.user_label)
        
        # 添加底部边框
        nav_bar.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        
        return nav_bar
    
    def handle_nav_button_click(self, clicked_button, slot):
        """处理导航按钮点击"""
        # 更新按钮状态
        for button in self.nav_buttons:
            if button != clicked_button:
                button.setChecked(False)
        
        # 调用对应的槽函数
        slot()
    
    def update_user_info(self, user_id):
        """更新用户信息显示"""
        if user_id:
            self.user_label.setText(f"用户ID: {user_id}")
            # 设置数据字段页面的session
            self.data_widget.set_session(self.settings_widget.api.session)
            
    def clear_user_info(self):
        """清除用户信息显示"""
        self.user_label.setText("")
        # 清除数据字段页面的session
        self.data_widget.set_session(None)
    
    def show_settings(self):
        """显示设置页面"""
        self.stacked_widget.setCurrentWidget(self.settings_widget)
    
    def show_data(self):
        """显示数据字段页面"""
        self.stacked_widget.setCurrentWidget(self.data_widget)
    
    def show_alpha(self):
        """显示Alpha设置页面"""
        self.stacked_widget.setCurrentWidget(self.alpha_widget)
    
    def show_backtest(self):
        """显示回测页面"""
        self.stacked_widget.setCurrentWidget(self.backtest_widget)
    
    def show_batch(self):
        """显示批量提交页面"""
        self.stacked_widget.setCurrentWidget(self.batch_widget) 