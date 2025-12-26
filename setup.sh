#!/bin/bash

# setup.sh - Sandbox 环境初始化脚本
echo "🚀 开始初始化 Sandbox 环境..."

# 如未设置，默认使用开发环境
export NODE_ENV=${NODE_ENV:-development}

# 如有需要安装额外依赖
echo "📦 安装依赖..."
npm install

# 在此执行数据库迁移或初始化命令
# 示例：
# npm run db:migrate
# npm run db:seed

# 需要时构建应用
echo "🔨 构建应用..."
npm run build 2>/dev/null || echo "⚠️  未找到 build 脚本，已跳过构建"

# 启动开发服务器
echo "🌟 启动开发服务器..."
echo "🎉 Sandbox 环境已就绪！"

# 启动应用（根据 package.json 脚本自动选择）
if npm run dev >/dev/null 2>&1; then
    npm run dev
elif npm start >/dev/null 2>&1; then
    npm start
else
    echo "⚠️  package.json 中未找到 dev 或 start 脚本"
    echo "🔧 尝试直接启动 Node.js..."
    node server.js 2>/dev/null || node index.js 2>/dev/null || echo "❌ 未找到入口文件"
fi
