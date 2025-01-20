from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                           QPushButton, QLabel, QLineEdit, QMessageBox, QProgressBar,
                           QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
import pandas as pd
from pathlib import Path
import datetime
import time
import json

class SubmitThread(QThread):
    """提交线程"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str, bool)  # alpha_id, success

    def __init__(self, session, alpha_id):
        """
        @param session: API会话
        @param alpha_id: Alpha ID
        """
        super().__init__()
        self.session = session
        self.alpha_id = alpha_id
        
    def run(self):
        """执行提交任务"""
        submit_url = f"https://api.worldquantbrain.com/alphas/{self.alpha_id}/submit"
        
        # 第一轮提交
        attempts = 0
        while attempts < 5:
            attempts += 1
            self.progress_signal.emit(f"正在尝试提交 {self.alpha_id} (第{attempts}次)")
            
            res = self.session.post(submit_url)
            if res.status_code == 201:
                self.progress_signal.emit(f"Alpha {self.alpha_id} 开始提交...")
                break
            elif res.status_code == 400:
                self.progress_signal.emit(f"Alpha {self.alpha_id} 已经提交过")
                self.finished_signal.emit(self.alpha_id, False)
                return
            elif res.status_code == 403:
                self.progress_signal.emit(f"Alpha {self.alpha_id} 提交被拒绝")
                self.finished_signal.emit(self.alpha_id, False)
                return
            
            time.sleep(3)
            
        # 第二轮提交
        count = 0
        start_time = datetime.datetime.now()
        while True:
            res = self.session.get(submit_url)
            if res.status_code == 200:
                retry = res.headers.get('Retry-After', 0)
                if retry:
                    count += 1
                    time.sleep(float(retry))
                    if count % 75 == 0:
                        elapsed = datetime.datetime.now() - start_time
                        self.progress_signal.emit(f"Alpha {self.alpha_id} 等待中... {elapsed}")
                else:
                    self.progress_signal.emit(f"Alpha {self.alpha_id} 提交成功!")
                    self.finished_signal.emit(self.alpha_id, True)
                    return
            else:
                self.progress_signal.emit(f"Alpha {self.alpha_id} 提交失败")
                self.finished_signal.emit(self.alpha_id, False)
                return

class BatchSubmitWindow(QWidget):
    """批量提交窗口"""
    
    def __init__(self, session):
        """
        @param session: API会话对象
        """
        super().__init__()
        self.session = session
        self.results_file = Path("data/processed/backtest_results.csv")
        self.last_modified_time = None
        self.setup_ui()
        
        # 创建文件监视定时器
        self.file_watcher = QTimer()
        self.file_watcher.timeout.connect(self.check_file_changes)
        self.file_watcher.start(1000)  # 每秒检查一次
        
        # 初始加载数据
        self.load_data()
        
    def setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 添加标题标签
        title_label = QLabel("通过回测的Alpha列表")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333;
                padding: 5px 0;
            }
        """)
        layout.addWidget(title_label)
        
        # 添加说明标签
        desc_label = QLabel("以下Alpha已通过回测检验，可以提交到平台")
        desc_label.setStyleSheet("""
            QLabel {
                color: #666;
                padding-bottom: 10px;
            }
        """)
        layout.addWidget(desc_label)
        
        # 结果显示区域 - 使用表格
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)  # 设置隔行变色
        # 禁用编辑
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # 整行选择
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # 设置样式
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #F8F8F8;
                gridline-color: #E0E0E0;
                border: 1px solid #D0D0D0;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #F0F0F0;
                padding: 6px;
                border: none;
                border-right: 1px solid #D0D0D0;
                border-bottom: 1px solid #D0D0D0;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 6px;
                border: none;
            }
        """)
        layout.addWidget(self.results_table)
        
        # 单独提交区域
        submit_layout = QHBoxLayout()
        self.alpha_input = QLineEdit()
        self.alpha_input.setPlaceholderText("输入Alpha ID")
        submit_btn = QPushButton("提交")
        submit_btn.clicked.connect(self.submit_single)
        submit_layout.addWidget(QLabel("Alpha ID:"))
        submit_layout.addWidget(self.alpha_input)
        submit_layout.addWidget(submit_btn)
        layout.addLayout(submit_layout)
        
        # 批量提交按钮
        batch_btn = QPushButton("批量提交")
        batch_btn.clicked.connect(self.submit_batch)
        layout.addWidget(batch_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态显示
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        layout.addWidget(self.status_text)
        
    def check_file_changes(self):
        """检查CSV文件是否发生变化"""
        if not self.results_file.exists():
            return
            
        current_mtime = self.results_file.stat().st_mtime
        if self.last_modified_time is None or current_mtime > self.last_modified_time:
            self.last_modified_time = current_mtime
            self.load_data()
            
    def load_data(self):
        """加载回测结果到表格"""
        try:
            if not self.results_file.exists():
                self.status_text.setText("未找到回测结果文件")
                return
                
            df = pd.read_csv(self.results_file)
            
            # 只选择需要显示的列并设置更友好的显示名称
            columns_to_show = ['alpha_id', 'LOW_SHARPE', 'LOW_FITNESS', 
                             'LOW_TURNOVER', 'HIGH_TURNOVER', 'LOW_SUB_UNIVERSE_SHARPE']
            column_labels = ['Alpha ID', '夏普比率', '适应度', 
                           '最低换手率', '最高换手率', '子域夏普比率']
            
            df = df[columns_to_show]
            
            # 设置表格列数和标题
            self.results_table.setColumnCount(len(columns_to_show))
            self.results_table.setHorizontalHeaderLabels(column_labels)  # 使用中文标签
            
            # 设置表格行数
            self.results_table.setRowCount(len(df))
            
            # 填充数据
            for row in range(len(df)):
                for col in range(len(columns_to_show)):
                    value = str(df.iloc[row, col])
                    item = QTableWidgetItem(value)
                    # 设置对齐方式
                    if columns_to_show[col] == 'alpha_id':
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    else:
                        # 数值列右对齐
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.results_table.setItem(row, col, item)
            
            # 调整列宽
            self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # alpha_id列
            
            # 对于数值列，设置固定宽度
            for col in range(1, self.results_table.columnCount()):
                self.results_table.setColumnWidth(col, 100)
            
            # 设置表格高度
            header_height = self.results_table.horizontalHeader().height()
            content_height = sum(self.results_table.rowHeight(row) for row in range(self.results_table.rowCount()))
            total_height = header_height + content_height + 2
            self.results_table.setMinimumHeight(min(400, total_height))
            
        except Exception as e:
            self.status_text.setText(f"加载结果失败: {str(e)}")
            
    def submit_single(self):
        """提交单个Alpha"""
        alpha_id = self.alpha_input.text().strip()
        if not alpha_id:
            QMessageBox.warning(self, "提示", "请输入Alpha ID")
            return
            
        self.status_text.clear()
        self.submit_thread = SubmitThread(self.session, alpha_id)
        self.submit_thread.progress_signal.connect(self.update_status)
        self.submit_thread.finished_signal.connect(self.on_submit_finished)
        self.submit_thread.start()
        
    def submit_batch(self):
        """批量提交Alpha"""
        try:
            df = pd.read_csv(self.results_file)
            # 过滤出未提交的Alpha
            unsubmitted = df[df['submitted'].fillna(False) == False]
            
            if len(unsubmitted) == 0:
                QMessageBox.information(self, "提示", "没有待提交的Alpha")
                return
                
            self.status_text.clear()
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(unsubmitted))
            self.progress_bar.setValue(0)
            
            # 开始提交第一个
            self.current_batch_index = 0
            self.batch_alphas = unsubmitted['alpha_id'].tolist()
            self.submit_next_batch()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量提交失败: {str(e)}")
            
    def submit_next_batch(self):
        """提交下一个批次的Alpha"""
        if self.current_batch_index >= len(self.batch_alphas):
            self.progress_bar.setVisible(False)
            QMessageBox.information(self, "完成", "批量提交完成")
            return
            
        alpha_id = self.batch_alphas[self.current_batch_index]
        self.submit_thread = SubmitThread(self.session, alpha_id)
        self.submit_thread.progress_signal.connect(self.update_status)
        self.submit_thread.finished_signal.connect(self.on_batch_submit_finished)
        self.submit_thread.start()
        
    def update_status(self, message):
        """更新状态信息"""
        self.status_text.append(message)
        
    def on_submit_finished(self, alpha_id, success):
        """单个提交完成回调"""
        if success:
            self.mark_as_submitted(alpha_id)
            
    def on_batch_submit_finished(self, alpha_id, success):
        """批量提交完成回调"""
        if success:
            self.mark_as_submitted(alpha_id)
        
        self.current_batch_index += 1
        self.progress_bar.setValue(self.current_batch_index)
        self.submit_next_batch()
        
    def mark_as_submitted(self, alpha_id):
        """标记Alpha为已提交"""
        try:
            df = pd.read_csv(self.results_file)
            df.loc[df['alpha_id'] == alpha_id, 'submitted'] = True
            
            # 将已提交的移到最后
            submitted = df[df['submitted'] == True]
            unsubmitted = df[df['submitted'] != True]
            df = pd.concat([unsubmitted, submitted])
            
            # 保存更新后的CSV
            df.to_csv(self.results_file, index=False)
            
            # 刷新表格显示
            self.load_data()
            
        except Exception as e:
            self.update_status(f"标记提交状态失败: {str(e)}")

    def showEvent(self, event):
        """窗口显示时触发"""
        super().showEvent(event)
        self.file_watcher.start()
        self.load_data()
        
    def hideEvent(self, event):
        """窗口隐藏时触发"""
        super().hideEvent(event)
        self.file_watcher.stop() 