"""
回测窗口模块
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QPushButton, QGroupBox, QTextEdit,
                           QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from core.config_manager import ConfigManager
import pandas as pd
from pathlib import Path
import json
import requests
import time
import re

class BacktestThread(QThread):
    """回测线程"""
    progress_signal = pyqtSignal(str)  # 进度信号
    progress_value_signal = pyqtSignal(int)  # 进度值信号
    finished_signal = pyqtSignal(dict)  # 完成信号，传递回测结果
    error_signal = pyqtSignal(str)  # 错误信号
    field_progress_signal = pyqtSignal(int, int)  # 字段进度信号 (当前索引, 总数)

    def __init__(self, alpha_template, data_field, session=None):
        super().__init__()
        self.alpha_template = alpha_template
        self.data_field = data_field
        self.config_manager = ConfigManager()
        self.session = session
        self._is_running = True  # 添加运行状态标志
        
    def stop(self):
        """停止回测"""
        self._is_running = False
        
    def run(self):
        try:
            if not self.session:
                raise Exception("未登录，请先登录后再进行回测")

            # 获取模板数据
            templates = self.config_manager.load_alpha_templates()
            template_data = templates.get(self.alpha_template, {})
            if not template_data:
                raise Exception(f"找不到模板: {self.alpha_template}")
                
            self.progress_signal.emit("\n=== 模板信息 ===")
            self.progress_signal.emit(f"模板名称: {self.alpha_template}")
            self.progress_signal.emit(f"原始表达式: {template_data['alpha_expression']}")
            self.progress_signal.emit(f"模板参数: {json.dumps(template_data, ensure_ascii=False, indent=2)}")

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
                
            # 显示总体信息
            self.progress_signal.emit("\n=== 回测信息 ===")
            self.progress_signal.emit(f"模板名称: {self.alpha_template}")
            self.progress_signal.emit(f"原始表达式: {template_data['alpha_expression']}")
            self.progress_signal.emit(f"字段总数: {len(field_ids)}")
            
            # 依次测试每个字段
            for i, field_id in enumerate(field_ids):
                if not self._is_running:
                    self.progress_signal.emit("\n回测已停止")
                    return  # 直接返回，不抛出异常
                    
                self.progress_signal.emit(f"\n\n=== 测试字段 [{i+1}/{len(field_ids)}] ===")
                self.progress_signal.emit(f"字段ID: {field_id}")
                self.field_progress_signal.emit(i + 1, len(field_ids))
                
                # 检查字段ID是否包含vector
                if "vector" in field_id.lower():
                    self.progress_signal.emit(f"跳过vector字段: {field_id}")
                    continue
                
                # 构建alpha表达式
                alpha_expression = template_data['alpha_expression']
                if "{data}" in alpha_expression:
                    alpha_expression = alpha_expression.replace("{data}", field_id)
                else:
                    alpha_expression = re.sub(r'\{[^}]+\}', field_id, alpha_expression)
                
                self.progress_signal.emit(f"表达式: {alpha_expression}")
                
                # 检查表达式格式
                if not alpha_expression:
                    raise Exception("Alpha表达式为空")
                
                # 处理truncation参数，将百分比转换为小数
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
                        'truncation': truncation,  # 使用转换后的小数值
                        'pasteurization': template_data.get('pasteurization', 'ON'),
                        'unitHandling': template_data.get('unit_handling', 'VERIFY'),
                        'nanHandling': template_data.get('nan_handling', 'ON'),
                        'language': template_data.get('language', 'FASTEXPR'),
                        'visualization': False,
                    },
                    'regular': alpha_expression
                }

                # 打印请求信息
                self.progress_signal.emit("\n=== 请求信息 ===")
                self.progress_signal.emit(f"请求URL: https://api.worldquantbrain.com/simulations")
                self.progress_signal.emit(f"请求数据:\n{json.dumps(simulation_data, ensure_ascii=False, indent=2)}")

                # 发送回测请求
                self.progress_signal.emit("\n正在发送回测请求...")
                try:
                    sim_resp = self.session.post(
                        'https://api.worldquantbrain.com/simulations',
                        json=simulation_data,
                        timeout=30,  # 添加超时设置
                        verify=True
                    )
                except requests.exceptions.SSLError:
                    raise Exception("网络连接错误：请检查您的网络连接或代理设置")
                except requests.exceptions.Timeout:
                    raise Exception("连接超时：服务器响应时间过长，请稍后重试")
                except requests.exceptions.ConnectionError:
                    raise Exception("连接失败：无法连接到服务器，请检查网络设置")
                except requests.exceptions.RequestException as e:
                    if "Failed to resolve" in str(e):
                        raise Exception("DNS解析失败：无法解析服务器地址，请检查网络连接或DNS设置")
                    raise Exception(f"网络请求错误：{str(e)}")
                
                # 打印响应信息
                self.progress_signal.emit("\n=== 响应信息 ===")
                self.progress_signal.emit(f"状态码: {sim_resp.status_code}")
                self.progress_signal.emit(f"响应头: {json.dumps(dict(sim_resp.headers), ensure_ascii=False, indent=2)}")
                self.progress_signal.emit(f"响应内容: {sim_resp.text}")
                
                if sim_resp.status_code != 200 and sim_resp.status_code != 201:
                    error_text = sim_resp.text
                    try:
                        error_json = sim_resp.json()
                        if isinstance(error_json, dict):
                            error_text = json.dumps(error_json, ensure_ascii=False, indent=2)
                    except:
                        pass
                    raise Exception(f"回测请求失败: {error_text}")
                    
                if 'Location' not in sim_resp.headers:
                    raise Exception("回测请求失败，未返回进度URL")
                    
                sim_progress_url = sim_resp.headers['Location']
                self.progress_signal.emit(f"\n进度URL: {sim_progress_url}")
                
                # 轮询回测进度
                while self._is_running:
                    try:
                        sim_progress_resp = self.session.get(
                            sim_progress_url,
                            timeout=10,
                            verify=True
                        )
                    except requests.exceptions.SSLError:
                        raise Exception("网络连接错误：请检查您的网络连接或代理设置")
                    except requests.exceptions.Timeout:
                        raise Exception("获取进度超时：服务器响应时间过长，请稍后重试")
                    except requests.exceptions.ConnectionError:
                        raise Exception("连接失败：无法连接到服务器，请检查网络设置")
                    except requests.exceptions.RequestException as e:
                        if "Failed to resolve" in str(e):
                            raise Exception("DNS解析失败：无法解析服务器地址，请检查网络连接或DNS设置")
                        raise Exception(f"获取进度时发生错误：{str(e)}")
                    
                    if sim_progress_resp.status_code != 200:
                        raise Exception(f"获取回测进度失败: {sim_progress_resp.text}")
                        
                    progress_data = sim_progress_resp.json()
                    progress = progress_data.get('progress', 0)
                    if isinstance(progress, float):
                        # 发送进度值
                        self.progress_value_signal.emit(int(progress * 100))
                    
                    retry_after_sec = float(sim_progress_resp.headers.get("Retry-After", 0))
                    
                    if retry_after_sec == 0:  # 回测完成
                        if progress_data.get('status') == 'ERROR':
                            raise Exception(f"回测失败: {progress_data.get('message', '未知错误')}")
                        
                        # 获取alpha结果
                        alpha_id = progress_data.get('alpha')
                        if not alpha_id:
                            raise Exception(f"回测结果格式错误: {progress_data}")
                            
                        # 获取详细结果
                        self.progress_signal.emit("\n正在获取详细结果...")
                        result_resp = self.session.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}')
                        
                        if result_resp.status_code != 200:
                            raise Exception(f"获取回测结果失败: {result_resp.text}")
                            
                        result = result_resp.json()
                        
                        # 发送完整的API响应结果
                        self.finished_signal.emit(result)
                        
                        # 显示基本信息
                        self.progress_signal.emit("\n=== 回测结果 ===")
                        self.progress_signal.emit(f"Alpha ID: {result.get('id', '')}")
                        self.progress_signal.emit(f"创建时间: {result.get('dateCreated', '')}")
                        self.progress_signal.emit(f"表达式: {result.get('regular', {}).get('code', '')}")
                        
                        # 显示检查结果
                        checks = result.get('is', {}).get('checks', [])
                        self.progress_signal.emit("\n检查项结果：")
                        for check in checks:
                            name = check.get('name')
                            result_val = check.get('result')
                            value = check.get('value', 'N/A')
                            self.progress_signal.emit(f"{name}: {result_val} (值: {value})")
                        
                        # 等待一秒再继续下一个字段
                        time.sleep(1)
                        
                        break
                        
                    self.progress_signal.emit(f"回测进行中，等待 {retry_after_sec} 秒...")
                    
                    # 分段休眠，以便能够及时响应停止请求
                    for _ in range(2):
                        if not self._is_running:
                            self.progress_signal.emit("\n回测已停止")
                            return  # 直接返回，不抛出异常
                        time.sleep(0.5)

            if self._is_running:  # 只有在正常完成时才发送完成消息
                self.progress_signal.emit("\n全部字段测试完成！")
                
        except Exception as e:
            if self._is_running:  # 只有在非停止状态下才发送错误
                self.error_signal.emit(str(e))

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
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 创建选择区域
        selection_group = QGroupBox("回测设置")
        selection_layout = QVBoxLayout()
        
        # Alpha模板选择
        template_layout = QHBoxLayout()
        template_label = QLabel("Alpha模板:")
        self.template_combo = QComboBox()
        template_layout.addWidget(template_label)
        template_layout.addWidget(self.template_combo)
        selection_layout.addLayout(template_layout)
        
        # 数据字段选择
        field_layout = QHBoxLayout()
        field_label = QLabel("数据字段:")
        self.field_combo = QComboBox()
        field_layout.addWidget(field_label)
        field_layout.addWidget(self.field_combo)
        selection_layout.addLayout(field_layout)
        
        selection_group.setLayout(selection_layout)
        main_layout.addWidget(selection_group)

        # 创建进度显示区域
        progress_group = QGroupBox("回测进度")
        progress_layout = QVBoxLayout()
        
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMinimumHeight(150)
        progress_layout.addWidget(self.progress_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)  # 显示百分比
        self.progress_bar.setFormat("%p%")  # 设置进度条格式为百分比
        progress_layout.addWidget(self.progress_bar)
        
        # 添加字段进度标签
        self.field_progress_label = QLabel("字段进度: 0/0")
        progress_layout.addWidget(self.field_progress_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # 创建按钮区域
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始回测")
        self.stop_button = QPushButton("停止回测")  # 添加停止按钮
        self.stop_button.setEnabled(False)  # 初始状态禁用
        self.start_button.clicked.connect(self.start_backtest)
        self.stop_button.clicked.connect(self.stop_backtest)  # 连接停止信号
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)  # 添加到布局
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        self.setLayout(main_layout)
        
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
            
    def showEvent(self, event):
        """窗口显示时触发"""
        super().showEvent(event)
        self.update_timer.start()  # 启动定时器
        self.load_templates_and_fields()  # 立即加载一次
        
        # 如果回测正在运行，更新UI状态
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
    def hideEvent(self, event):
        """窗口隐藏时触发"""
        super().hideEvent(event)
        self.update_timer.stop()  # 只停止定时器，不停止回测
        
    def closeEvent(self, event):
        """窗口关闭时触发"""
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.backtest_thread.stop()
            self.backtest_thread.wait()  # 等待线程结束
        super().closeEvent(event)
        
    def append_progress(self, text):
        """添加进度信息"""
        self.progress_text.append(text)
        # 滚动到底部
        self.progress_text.verticalScrollBar().setValue(
            self.progress_text.verticalScrollBar().maximum()
        )
        
    def set_session(self, session):
        """设置session"""
        self.session = session
        
    def start_backtest(self):
        """开始回测"""
        if not self.session:
            QMessageBox.warning(self, "错误", "请先登录")
            return
            
        if not self.template_combo.currentText() or not self.field_combo.currentText():
            QMessageBox.warning(self, "错误", "请选择Alpha模板和数据字段")
            return
            
        # 禁用开始按钮，启用停止按钮
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_text.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)
        
        # 创建并启动回测线程
        self.backtest_thread = BacktestThread(
            self.template_combo.currentText(),
            self.field_combo.currentText(),
            self.session
        )
        self.backtest_thread.progress_signal.connect(self.append_progress)
        self.backtest_thread.progress_value_signal.connect(self.progress_bar.setValue)  # 连接进度值信号
        self.backtest_thread.finished_signal.connect(self.handle_backtest_finished)
        self.backtest_thread.error_signal.connect(self.handle_backtest_error)
        self.backtest_thread.field_progress_signal.connect(self.update_field_progress)
        self.backtest_thread.start()
        
    def stop_backtest(self):
        """停止回测"""
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.backtest_thread.stop()
            self.append_progress("\n正在停止回测...")
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(True)
            self.progress_bar.setValue(0)  # 重置进度条
        
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
        
        # 只有当回测线程已经结束时才启用开始按钮
        if not self.backtest_thread or not self.backtest_thread.isRunning():
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setValue(100)
        
    def handle_backtest_error(self, error_msg):
        """处理回测错误"""
        self.progress_bar.setValue(0)  # 重置进度条
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_progress(f"\n错误: {error_msg}")
        QMessageBox.critical(self, "回测失败", f"回测过程中发生错误：{error_msg}")
        
    def update_field_progress(self, current, total):
        """更新字段进度"""
        self.field_progress_label.setText(f"字段进度: {current}/{total}")
        # 更新总体进度条
        total_progress = int((current - 1) / total * 100)
        self.progress_bar.setValue(total_progress) 