# Flask Web 应用

一个带有 ping API 与 CORS 支持的简单 Flask Web 应用。

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 启动应用：
```bash
python main.py
```

应用默认运行在 `http://localhost:5000`

## API 端点

- **GET /**：根端点，返回应用信息
- **GET /ping**：健康检查端点，返回 "pong"

## 功能

- 所有路由开启 CORS
- JSON 响应
- 健康检查端点
- 支持 Debug 模式的开发服务器
