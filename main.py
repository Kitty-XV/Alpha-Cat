"""
主程序入口模块
"""
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    """主程序入口函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 