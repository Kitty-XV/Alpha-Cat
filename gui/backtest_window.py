"""
回测窗口模块
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QPushButton, QGroupBox, QTextEdit,
                           QMessageBox, QProgressBar, QListView, QAbstractItemView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from core.config_manager import ConfigManager
import pandas as pd
from pathlib import Path
import json
import requests
import time
import re
from typing import Dict, Tuple

class ProgressManager:
    """进度管理器，用于管理多个alpha的进度"""
    def __init__(self):
        self.alpha_progress: Dict[str, Tuple[float, str]] = {}  # {alpha_id: (progress, status)}
        
    def update_progress(self, alpha_id: str, progress: float, status: str = "运行中") -> None:
        """更新某个alpha的进度"""
        self.alpha_progress[alpha_id] = (progress, status)
        
    def remove_alpha(self, alpha_id: str) -> None:
        """移除某个alpha的进度"""
        if alpha_id in self.alpha_progress:
            del self.alpha_progress[alpha_id]
            
    def get_overall_progress(self) -> float:
        """获取总体进度"""
        if not self.alpha_progress:
            return 0.0
        total_progress = sum(progress for progress, _ in self.alpha_progress.values())
        return total_progress / len(self.alpha_progress)
        
    def get_status_text(self) -> str:
        """获取所有alpha的状态文本"""
        status_text = []
        for alpha_id, (progress, status) in self.alpha_progress.items():
            status_text.append(f"Alpha {alpha_id}: {progress:.1%} - {status}")
        return "\n".join(status_text)

class BacktestThread(QThread):
    """回测线程"""
    progress_signal = pyqtSignal(str)  # 用于显示单个alpha的回测进度
    progress_update = pyqtSignal(int, str)  # 用于更新总进度条 (总进度百分比, alpha信息)
    finished_signal = pyqtSignal(dict)  # 回测完成信号
    error_signal = pyqtSignal(str)  # 错误信号
    field_progress_signal = pyqtSignal(int, int)  # 字段进度信号 (当前索引, 总数)

    def __init__(self, session, alpha_template, data_field):
        super().__init__()
        self.session = session
        self.alpha_template = alpha_template
        self.data_field = data_field
        self.config_manager = ConfigManager()
        self.total_alphas = 373  # 总共需要回测的alpha数量
        self.current_alpha = 0
        self._is_running = True  # 添加运行状态标志
        self.progress_manager = ProgressManager()
        self.active_requests = {}  # {alpha_id: (sim_progress_url, alpha_expression, field_id)}
        self.max_concurrent = 3  # 默认并发数，会被外部设置
        
    def calculate_overall_progress(self, current_idx: int, total_fields: int) -> int:
        """计算总体进度"""
        # 基础进度：已完成的字段
        base_progress = (current_idx / total_fields) * 100
        
        # 当前运行的alpha的进度贡献
        if self.active_requests:
            active_progress = sum(self.progress_manager.alpha_progress.get(str(idx), (0.0, ''))[0] 
                                for idx in self.active_requests.keys())
            active_contribution = (active_progress / len(self.active_requests)) * (100 / total_fields)
            return int(base_progress + active_contribution)
        
        return int(base_progress)
        
    def get_running_simulations(self) -> int:
        """获取当前正在运行的模拟数量"""
        try:
            response = self.session.get('https://api.worldquantbrain.com/simulations')
            if response.status_code == 200:
                data = response.json()
                running_sims = [sim for sim in data if sim.get('status') == 'RUNNING']
                self.progress_signal.emit(f"\n当前运行中的模拟数量: {len(running_sims)}")
                return len(running_sims)
            return 0
        except Exception as e:
            self.progress_signal.emit(f"\n获取运行中模拟数量失败: {str(e)}")
            return 0
            
    def send_simulation_request(self, alpha_expression, template_data):
        """发送模拟请求"""
        # 处理truncation参数
        truncation = float(template_data.get('truncation', 0)) / 100.0
        
        # 构建回测参数
        simulation_data = {
            'type': 'REGULAR',
            'settings': {
                'instrumentType': template_data.get('instrument_type', 'EQUITY'),
                'region': template_data.get('region', 'USA'),
                'universe': template_data.get('universe', 'TOP3000'),
                'delay': int(template_data.get('delay', 1)),
                'decay': int(template_data.get('decay', 0)),
                'neutralization': template_data.get('neutralization', 'NONE'),
                'truncation': truncation,
                'pasteurization': template_data.get('pasteurization', 'ON'),
                'unitHandling': template_data.get('unit_handling', 'VERIFY'),
                'nanHandling': template_data.get('nan_handling', 'ON'),
                'language': template_data.get('language', 'FASTEXPR'),
                'visualization': False,
            },
            'regular': alpha_expression
        }
        
        response = self.session.post(
            'https://api.worldquantbrain.com/simulations',
            json=simulation_data,
            timeout=30
        )
        
        if response.status_code in (200, 201):
            return response.headers.get('Location')
        elif response.status_code == 429:  # Rate limit
            raise Exception("API请求频率限制，等待30秒后重试")
        else:
            raise Exception(f"回测请求失败: {response.text}")
            
    def check_simulation_progress(self, sim_progress_url):
        """检查模拟进度"""
        response = self.session.get(sim_progress_url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"获取回测进度失败: {response.text}")
            
        progress_data = response.json()
        # 添加详细的进度信息
        if 'status' in progress_data:
            self.progress_signal.emit(f"\n状态: {progress_data['status']}")
        if 'message' in progress_data:
            self.progress_signal.emit(f"消息: {progress_data['message']}")
        if 'stage' in progress_data:
            self.progress_signal.emit(f"阶段: {progress_data['stage']}")
            
        return progress_data
        
    def run(self):
        try:
            if not self.session:
                raise Exception("未登录，请先登录后再进行回测")

            # 获取模板数据
            templates = self.config_manager.load_alpha_templates()
            template_data = templates.get(self.alpha_template, {})
            if not template_data:
                raise Exception(f"找不到模板: {self.alpha_template}")
                
            # 读取CSV文件中的所有字段ID
            fields_file = Path(f"data/raw/{self.data_field}.csv")
            if not fields_file.exists():
                raise Exception(f"找不到字段CSV文件: {fields_file}")
                
            try:
                df = pd.read_csv(fields_file)
                if 'field_id' not in df.columns:
                    raise Exception("CSV文件缺少field_id列")
                field_ids = df['field_id'].tolist()
            except Exception as e:
                raise Exception(f"读取字段ID失败: {str(e)}")
                
            self.progress_signal.emit("\n=== 开始并行回测 ===")
            self.progress_signal.emit(f"总字段数: {len(field_ids)}")
            self.progress_signal.emit(f"并发数: {self.max_concurrent}")
            
            current_idx = 0
            total_fields = len(field_ids)
            
            while (current_idx < total_fields or self.active_requests) and self._is_running:
                # 检查当前运行数量
                running_count = self.get_running_simulations()
                
                # 如果达到并发限制，等待30秒
                if running_count >= self.max_concurrent:
                    self.progress_signal.emit("\n等待其他回测完成...")
                    time.sleep(30)
                    continue
                    
                # 填充活跃请求直到达到并发限制
                while len(self.active_requests) + running_count < self.max_concurrent and current_idx < total_fields and self._is_running:
                    field_id = field_ids[current_idx]
                    
                    # 检查字段ID是否包含vector
                    if "vector" in field_id.lower():
                        self.progress_signal.emit(f"\n跳过vector字段: {field_id}")
                        current_idx += 1
                        continue
                        
                    # 构建alpha表达式
                    alpha_expression = template_data['alpha_expression']
                    if "{data}" in alpha_expression:
                        alpha_expression = alpha_expression.replace("{data}", field_id)
                    else:
                        alpha_expression = re.sub(r'\{[^}]+\}', field_id, alpha_expression)
                        
                    try:
                        # 发送新的模拟请求
                        sim_progress_url = self.send_simulation_request(alpha_expression, template_data)
                        if sim_progress_url:
                            self.active_requests[current_idx] = (sim_progress_url, alpha_expression, field_id)
                            self.progress_signal.emit(f"\n开始回测字段 [{current_idx + 1}/{total_fields}]: {field_id}")
                            self.progress_manager.update_progress(str(current_idx), 0.0)
                    except Exception as e:
                        self.progress_signal.emit(f"\n字段 {field_id} 回测失败: {str(e)}")
                        
                    current_idx += 1
                    
                # 检查所有活跃请求的状态
                completed_requests = []
                for idx, (sim_progress_url, alpha_expression, field_id) in list(self.active_requests.items()):
                    try:
                        progress_data = self.check_simulation_progress(sim_progress_url)
                        progress = progress_data.get('progress', 0)
                        
                        if isinstance(progress, float):
                            self.progress_manager.update_progress(str(idx), progress)
                            self.progress_signal.emit(f"Alpha {idx} ({field_id}) 进度: {progress:.1%}")
                            
                        status = progress_data.get('status', '')
                        if status == 'ERROR':
                            self.progress_signal.emit(f"\nAlpha {idx} ({field_id}) 回测失败: {progress_data.get('message', '未知错误')}")
                            completed_requests.append(idx)
                            continue
                            
                        # 检查是否完成
                        if status == 'COMPLETE' or progress == 1.0:
                            alpha_id = progress_data.get('alpha')
                            if alpha_id:
                                # 获取详细结果
                                result_resp = self.session.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}')
                                if result_resp.status_code == 200:
                                    result = result_resp.json()
                                    self.finished_signal.emit(result)
                                    self.progress_signal.emit(f"\nAlpha {idx} ({field_id}) 回测完成!")
                                    
                            completed_requests.append(idx)
                            
                    except Exception as e:
                        self.progress_signal.emit(f"\nAlpha {idx} ({field_id}) 检查进度失败: {str(e)}")
                        if "404 Client Error" in str(e):  # 如果模拟已经不存在
                            completed_requests.append(idx)
                            
                # 移除已完成的请求
                for idx in completed_requests:
                    del self.active_requests[idx]
                    self.progress_manager.remove_alpha(str(idx))
                    
                # 更新总体进度
                overall_progress = self.calculate_overall_progress(current_idx - len(self.active_requests), total_fields)
                self.progress_update.emit(overall_progress, f"[{current_idx}/{total_fields}]")
                
                # 避免过度请求
                time.sleep(5)
                
            if self._is_running:
                self.progress_signal.emit("\n全部字段测试完成！")
                
        except Exception as e:
            if self._is_running:
                self.error_signal.emit(str(e))
                
    def stop(self):
        """停止回测"""
        self._is_running = False

class BacktestWindow(QWidget):
    """回测窗口类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.backtest_thread = None
        self.session = None
        self.setup_ui()
        
        # 创建文件监视定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.load_templates_and_fields)
        self.update_timer.start(1000)  # 每秒检查一次
        
        # 初始加载
        self.load_templates_and_fields()
        
    def setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 创建选择区域
        selection_group = QGroupBox("回测设置")
        selection_layout = QVBoxLayout()
        
        # Alpha模板选择
        template_layout = QHBoxLayout()
        template_label = QLabel("Alpha模板:")
        self.template_combo = QComboBox()
        # 设置下拉列表始终从第一项开始显示
        self.template_combo.setView(QListView())
        self.template_combo.view().setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        template_layout.addWidget(template_label)
        template_layout.addWidget(self.template_combo)
        selection_layout.addLayout(template_layout)
        
        # 数据字段选择
        field_layout = QHBoxLayout()
        field_label = QLabel("数据字段:")
        self.field_combo = QComboBox()
        # 设置下拉列表始终从第一项开始显示
        self.field_combo.setView(QListView())
        self.field_combo.view().setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        field_layout.addWidget(field_label)
        field_layout.addWidget(self.field_combo)
        selection_layout.addLayout(field_layout)
        
        # 并发数选择
        concurrency_layout = QHBoxLayout()
        concurrency_label = QLabel("并发数:")
        self.concurrency_combo = QComboBox()
        # 设置下拉列表始终从第一项开始显示
        self.concurrency_combo.setView(QListView())
        self.concurrency_combo.view().setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.concurrency_combo.addItems(['1', '2', '3', '4', '5'])
        self.concurrency_combo.setCurrentText('3')  # 默认值为3
        # 添加并发数变化响应
        self.concurrency_combo.currentTextChanged.connect(self.on_concurrency_changed)
        concurrency_layout.addWidget(concurrency_label)
        concurrency_layout.addWidget(self.concurrency_combo)
        selection_layout.addLayout(concurrency_layout)
        
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        # 进度显示区域
        progress_group = QGroupBox("回测进度")
        progress_layout = QVBoxLayout()
        
        # 总体进度
        total_progress_layout = QHBoxLayout()
        total_progress_layout.addWidget(QLabel("总体进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0078D4;
            }
        """)
        total_progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(total_progress_layout)
        
        # 当前运行的Alpha进度
        self.alpha_progress_group = QGroupBox("当前运行的Alpha")
        self.alpha_progress_layout = QVBoxLayout()  # 改为实例变量
        
        # 创建5个进度条用于显示并行的Alpha进度（最大支持5个并发）
        self.alpha_progress_bars = []
        self.alpha_labels = []
        for i in range(5):
            alpha_layout = QHBoxLayout()
            label = QLabel(f"Alpha {i+1}:")
            progress_bar = QProgressBar()
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    text-align: center;
                    height: 15px;
                }
                QProgressBar::chunk {
                    background-color: #00B294;
                }
            """)
            alpha_layout.addWidget(label)
            alpha_layout.addWidget(progress_bar)
            self.alpha_progress_layout.addLayout(alpha_layout)
            self.alpha_progress_bars.append(progress_bar)
            self.alpha_labels.append(label)
            
            # 默认隐藏所有进度条
            label.setVisible(False)
            progress_bar.setVisible(False)
            
        self.alpha_progress_group.setLayout(self.alpha_progress_layout)
        progress_layout.addWidget(self.alpha_progress_group)
        
        # 显示默认数量的进度条
        self.update_progress_bars_visibility(int(self.concurrency_combo.currentText()))
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 状态显示
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        layout.addWidget(self.status_text)

        # 创建按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始回测")
        self.stop_button = QPushButton("停止回测")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_backtest)
        self.stop_button.clicked.connect(self.stop_backtest)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
    def on_concurrency_changed(self, value):
        """并发数变化时的响应"""
        concurrency = int(value)
        self.update_progress_bars_visibility(concurrency)
        
    def update_progress_bars_visibility(self, concurrency):
        """更新进度条的可见性"""
        for i in range(5):
            visible = i < concurrency
            self.alpha_labels[i].setVisible(visible)
            self.alpha_progress_bars[i].setVisible(visible)
            if visible:
                self.alpha_labels[i].setText(f"Alpha {i+1}:")
                self.alpha_progress_bars[i].setValue(0)
                self.alpha_progress_bars[i].setFormat("")
                
    def update_alpha_progress(self, alpha_id, progress, status="运行中"):
        """更新单个Alpha的进度"""
        try:
            concurrency = int(self.concurrency_combo.currentText())
            idx = int(alpha_id) % concurrency  # 使用当前并发数取模
            if idx < len(self.alpha_labels) and self.alpha_labels[idx].isVisible():
                self.alpha_labels[idx].setText(f"Alpha {alpha_id}:")
                self.alpha_progress_bars[idx].setValue(int(progress * 100))
                self.alpha_progress_bars[idx].setFormat(f"{progress:.1%} - {status}")
        except (ValueError, IndexError):
            pass
            
    def clear_alpha_progress(self, alpha_id):
        """清除单个Alpha的进度显示"""
        try:
            concurrency = int(self.concurrency_combo.currentText())
            idx = int(alpha_id) % concurrency
            if idx < len(self.alpha_labels) and self.alpha_labels[idx].isVisible():
                self.alpha_labels[idx].setText(f"Alpha {idx+1}:")
                self.alpha_progress_bars[idx].setValue(0)
                self.alpha_progress_bars[idx].setFormat("")
        except (ValueError, IndexError):
            pass
            
    def update_status(self, status_text):
        """更新状态文本"""
        self.status_text.append(status_text)
        # 滚动到底部
        self.status_text.verticalScrollBar().setValue(
            self.status_text.verticalScrollBar().maximum()
        )
        
        # 解析进度信息
        if "Alpha" in status_text and "进度" in status_text:
            try:
                alpha_id = status_text.split("Alpha")[1].split()[0]
                progress = float(status_text.split(":")[1].strip().replace("%", "")) / 100
                self.update_alpha_progress(alpha_id, progress)
            except:
                pass
                
    def update_progress(self, progress, alpha_info):
        """更新总体进度"""
        self.progress_bar.setValue(progress)
        
    def set_session(self, session):
        """设置session"""
        self.session = session
        
    def start_backtest(self):
        """开始回测"""
        if not self.session:
            QMessageBox.warning(self, "提示", "请先登录")
            return
            
        self.status_text.clear()
        self.progress_bar.setValue(0)
        
        # 获取选择的并发数
        concurrency = int(self.concurrency_combo.currentText())
        
        # 更新进度条显示
        self.update_progress_bars_visibility(concurrency)
        
        # 创建并启动回测线程
        self.backtest_thread = BacktestThread(self.session, 
                                            self.template_combo.currentText(),
                                            self.field_combo.currentText())
        # 设置并发数
        self.backtest_thread.max_concurrent = concurrency
        
        self.backtest_thread.progress_signal.connect(self.update_status)
        self.backtest_thread.progress_update.connect(self.update_progress)
        self.backtest_thread.finished_signal.connect(self.handle_backtest_finished)
        self.backtest_thread.error_signal.connect(self.handle_backtest_error)
        
        # 更新按钮状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        self.backtest_thread.start()
        
    def stop_backtest(self):
        """停止回测"""
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.backtest_thread.stop()
            self.append_progress("\n正在停止回测...")
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(True)
            self.progress_bar.setValue(0)
            
            # 清除所有Alpha进度显示
            for i in range(5):  # 修改为5，匹配最大并发数
                self.alpha_labels[i].setText(f"Alpha {i+1}:")
                self.alpha_progress_bars[i].setValue(0)
                self.alpha_progress_bars[i].setFormat("")
        
    def handle_backtest_finished(self, result):
        """处理回测完成"""
        try:
            # 保存回测结果
            results_file = Path("data/processed/backtest_results.csv")
            results_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 从结果中提取检查项的值
            checks = result.get('is', {}).get('checks', [])
            check_values = {}
            for check in checks:
                name = check.get('name')
                if name in ['LOW_SHARPE', 'LOW_FITNESS', 'LOW_TURNOVER', 
                          'HIGH_TURNOVER', 'LOW_SUB_UNIVERSE_SHARPE']:
                    check_values[name] = check.get('value', 0)
            
            # 构建结果数据
            result_data = {
                'alpha_id': result.get('id', ''),
                'creation_time': result.get('dateCreated', ''),
                'formula': result.get('regular', {}).get('code', ''),
                'LOW_SHARPE': check_values.get('LOW_SHARPE', 0),
                'LOW_FITNESS': check_values.get('LOW_FITNESS', 0),
                'LOW_TURNOVER': check_values.get('LOW_TURNOVER', 0),
                'HIGH_TURNOVER': check_values.get('HIGH_TURNOVER', 0),
                'LOW_SUB_UNIVERSE_SHARPE': check_values.get('LOW_SUB_UNIVERSE_SHARPE', 0)
            }
            
            # 读取现有结果或创建新的DataFrame
            if results_file.exists():
                try:
                    df = pd.read_csv(results_file)
                except pd.errors.EmptyDataError:
                    df = pd.DataFrame(columns=list(result_data.keys()))
                except Exception:
                    df = pd.DataFrame(columns=list(result_data.keys()))
            else:
                df = pd.DataFrame(columns=list(result_data.keys()))
            
            # 检查所有检查项是否都通过
            all_passed = True
            for check in checks:
                if check.get('name') in check_values and check.get('result') != 'PASS':
                    all_passed = False
                    break
            
            # 只有当所有检查项都通过时才保存
            if all_passed:
                # 添加新结果
                df = pd.concat([df, pd.DataFrame([result_data])], ignore_index=True)
                # 移除重复的行
                df = df.drop_duplicates(subset=['alpha_id', 'formula'], keep='last')
                df.to_csv(results_file, index=False, encoding='utf-8')
                self.append_progress("\n回测完成！结果已通过所有检查并保存。")
            else:
                self.append_progress("\n回测完成，但未通过所有检查项，结果未保存。")
            
        except Exception as e:
            self.append_progress(f"\n保存结果时出错: {str(e)}")
            QMessageBox.critical(self, "保存失败", f"保存回测结果时发生错误：{str(e)}")
        
    def handle_backtest_error(self, error_msg):
        """处理回测错误"""
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_progress(f"\n错误: {error_msg}")
        QMessageBox.critical(self, "回测失败", f"回测过程中发生错误：{error_msg}")
        
    def append_progress(self, text):
        """添加进度信息"""
        self.status_text.append(text)
        # 滚动到底部
        self.status_text.verticalScrollBar().setValue(
            self.status_text.verticalScrollBar().maximum()
        )
        
    def showEvent(self, event):
        """窗口显示时触发"""
        super().showEvent(event)
        self.update_timer.start()
        self.load_templates_and_fields()
        
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
    def hideEvent(self, event):
        """窗口隐藏时触发"""
        super().hideEvent(event)
        self.update_timer.stop()
        
    def closeEvent(self, event):
        """窗口关闭时触发"""
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.backtest_thread.stop()
            self.backtest_thread.wait()
        super().closeEvent(event)
        
    def load_templates_and_fields(self):
        """加载Alpha模板和数据字段"""
        # 保存当前选择
        current_template = self.template_combo.currentText()
        current_field = self.field_combo.currentText()
        
        # 加载Alpha模板
        templates = self.config_manager.load_alpha_templates()
        self.template_combo.clear()
        self.template_combo.addItems(templates.keys())
        
        # 恢复之前的选择（如果还存在）
        index = self.template_combo.findText(current_template)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)
            
        # 加载数据字段
        try:
            # 获取raw目录下所有的csv文件
            raw_dir = Path("data/raw")
            if raw_dir.exists():
                csv_files = [f.stem for f in raw_dir.glob("*.csv") if f.is_file()]
                self.field_combo.clear()
                self.field_combo.addItems(csv_files)
                
                # 恢复之前的选择（如果还存在）
                index = self.field_combo.findText(current_field)
                if index >= 0:
                    self.field_combo.setCurrentIndex(index)
                    
        except Exception as e:
            print(f"加载数据字段时出错: {str(e)}")  # 只打印错误，不弹窗 