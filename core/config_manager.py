"""
配置管理模块
"""
import os
import json
from pathlib import Path

class ConfigManager:
    """配置管理类"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.config_dir = Path("config")
        self.alpha_templates_file = self.config_dir / "alpha_templates.json"
        self._ensure_config_dir()
        
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_dir.mkdir(exist_ok=True)
        if not self.alpha_templates_file.exists():
            self._save_templates({})
            
    def save_alpha_template(self, name: str, settings: dict):
        """
        保存Alpha模板
        
        Args:
            name: 模板名称
            settings: 模板设置
        """
        templates = self.load_alpha_templates()
        templates[name] = settings
        self._save_templates(templates)
        
    def load_alpha_templates(self) -> dict:
        """
        加载所有Alpha模板
        
        Returns:
            dict: 模板字典
        """
        if not self.alpha_templates_file.exists():
            return {}
            
        try:
            with open(self.alpha_templates_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
            
    def _save_templates(self, templates: dict):
        """
        保存模板到文件
        
        Args:
            templates: 模板字典
        """
        with open(self.alpha_templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2) 