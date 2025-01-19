"""
Alpha表达式处理模块
"""
import re

class AlphaProcessor:
    """Alpha表达式处理类"""
    
    @staticmethod
    def format_expression(expression: str) -> str:
        """
        格式化Alpha表达式，将$包围的变量替换为正确的格式
        
        Args:
            expression: 原始Alpha表达式
            
        Returns:
            格式化后的表达式
        """
        # 使用正则表达式匹配$之间的内容
        pattern = r'\$(.*?)\$'
        
        def replace_var(match):
            """替换变量"""
            var = match.group(1).strip()
            return f"{{{var}}}"
            
        # 替换所有匹配项
        formatted = re.sub(pattern, replace_var, expression)
        return formatted
        
    @staticmethod
    def validate_expression(expression: str) -> bool:
        """
        验证Alpha表达式格式是否正确
        
        Args:
            expression: Alpha表达式
            
        Returns:
            bool: 表达式是否有效
        """
        if not expression:
            return False
            
        # 检查$符号配对
        count = expression.count('$')
        if count != 2:  # 只允许一对$符号，表示一个变量
            return False
            
        # 检查括号匹配
        brackets = []
        for char in expression:
            if char in '({[':
                brackets.append(char)
            elif char in ')}]':
                if not brackets:
                    return False
                if char == ')' and brackets[-1] != '(':
                    return False
                if char == '}' and brackets[-1] != '{':
                    return False
                if char == ']' and brackets[-1] != '[':
                    return False
                brackets.pop()
                
        return len(brackets) == 0
        
    @staticmethod
    def extract_variables(expression: str) -> list:
        """
        提取表达式中的变量
        
        Args:
            expression: Alpha表达式
            
        Returns:
            list: 变量列表
        """
        pattern = r'\$(.*?)\$'
        matches = re.findall(pattern, expression)
        return [var.strip() for var in matches] 