#!/bin/bash

echo "🚀 正在构建 Claude Code Automation MVP..."

# 如果 .env 不存在则创建
if [ ! -f server/.env ]; then
    echo "📝 从示例创建 .env 文件..."
    cp server/.env.example server/.env
    echo "⚠️  请在 server/.env 中填写你的 API 密钥"
fi

# 先构建 Claude Code automation 镜像
echo "🔨 正在构建 Claude Code automation 镜像..."
docker build -f Dockerfile.claude-automation -t claude-code-automation:latest .

# 构建并启动所有服务
echo "🔨 正在构建并启动所有服务..."
docker-compose up --build -d

echo "✅ 构建完成！"
echo ""
echo "🌐 前端：http://localhost:3000"
echo "🔧 后端 API：http://localhost:5000"
echo ""
echo "⚠️  别忘了："
echo "1. 在 server/.env 中设置 ANTHROPIC_API_KEY"
echo "2. 为前端准备一个 GitHub 个人访问令牌"
echo ""
echo "📖 查看日志：docker-compose logs -f"
