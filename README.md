# WQ App

一个基于 PyQt6 的量化数据分析应用。

## 功能特点

- 数据采集和处理
- Alpha 回测
- 可视化分析
- 结果导出

## 环境要求

- Python 3.9+
- PyQt6
- pandas
- requests

## 安装

1. 克隆仓库
```bash
git clone https://github.com/your-username/WQ_app.git
cd WQ_app
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行程序
```bash
python main.py
```

## 项目结构

```
wq_app/
├── main.py           # 程序入口
├── gui/             # 界面相关
├── core/            # 核心功能
├── resources/       # 资源文件
└── config/          # 配置文件
```

## 配置说明

1. 在 `config/` 目录下创建 `credentials.json` 文件
2. 配置相应的 API 密钥和其他设置

## 使用说明

1. 启动程序后，使用账号密码登录
2. 在主界面选择数据和模板
3. 设置回测参数
4. 运行回测并查看结果

## License

MIT 