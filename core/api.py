"""
API处理模块，处理与WorldQuant Brain的API交互
"""
import os
import json
import requests
from os.path import join, dirname, abspath
from requests.auth import HTTPBasicAuth

class WQBrainAPI:
    """WorldQuant Brain API处理类"""
    def __init__(self):
        self.base_url = "https://api.worldquantbrain.com"
        self.session = requests.Session()
        
    def get_project_root(self):
        """获取项目根目录"""
        return dirname(dirname(abspath(__file__)))
        
    def login(self):
        """
        登录WorldQuant Brain并保存凭证
        返回: (bool, str, str) 登录是否成功、错误信息、用户ID
        """
        try:
            project_root = self.get_project_root()
            credentials_path = join(project_root, 'config', 'credentials.json')
            token_path = join(project_root, 'config', 'token.json')
            
            # 读取凭证
            with open(credentials_path, 'r') as f:
                credentials = json.load(f)
            username, password = credentials
            
            # 创建session并认证
            self.session.auth = HTTPBasicAuth(username, password)
            
            # 发送认证请求
            try:
                response = self.session.post(f'{self.base_url}/authentication', verify=True, timeout=10)
            except requests.exceptions.SSLError as e:
                return False, "网络连接错误：请检查您的网络连接或代理设置", ""
            except requests.exceptions.Timeout:
                return False, "连接超时：服务器响应时间过长，请稍后重试", ""
            except requests.exceptions.ConnectionError:
                return False, "连接失败：无法连接到服务器，请检查网络设置", ""
            except Exception as e:
                return False, f"网络请求错误：{str(e)}", ""
                
            if response.status_code == 401:
                return False, "用户名或密码不正确", ""
            elif response.status_code not in [200, 201]:
                return False, f"认证失败 (HTTP {response.status_code})", ""
                
            # 获取认证信息
            auth_info = response.json()
            
            if not auth_info.get('permissions') or not auth_info['permissions']:
                return False, "账号权限不足", ""
                
            # 保存token信息
            token_data = {
                'user_id': auth_info['user']['id'],
                'token': auth_info['permissions'][0],
                'expiry': auth_info['token']['expiry']
            }
            
            os.makedirs(dirname(token_path), exist_ok=True)
            with open(token_path, 'w') as f:
                json.dump(token_data, f, indent=2)
                
            return True, "", auth_info['user']['id']  # 返回用户ID
            
        except FileNotFoundError:
            return False, "找不到凭证文件，请重新输入用户名密码", ""
        except json.JSONDecodeError:
            return False, "凭证文件格式错误，请重新输入用户名密码", ""
        except KeyError as e:
            return False, "服务器响应格式错误", ""
        except Exception as e:
            return False, f"登录过程出错: {str(e)}", ""

    def clear_cache(self):
        """
        清理缓存和认证信息
        """
        project_root = self.get_project_root()
        credentials_path = join(project_root, 'config', 'credentials.json')
        token_path = join(project_root, 'config', 'token.json')
        
        # 清理认证信息
        try:
            if os.path.exists(credentials_path):
                os.remove(credentials_path)
            if os.path.exists(token_path):
                os.remove(token_path)
            return True
        except Exception as e:
            print(f"清理缓存失败: {str(e)}")
            return False
            
    def logout(self):
        """
        退出登录，只清理session
        """
        try:
            # 清理session
            self.session = requests.Session()
            return True
        except Exception as e:
            print(f"退出登录失败: {str(e)}")
            return False 