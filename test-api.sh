#!/bin/bash

echo "🧪 正在测试 Claude Code Automation API..."

API_BASE="http://localhost:5000"

# 测试健康检查
echo "📋 测试健康检查..."
curl -s "$API_BASE/ping" | jq . || echo "❌ 健康检查失败"

# 测试根端点
echo "📋 测试根端点..."
curl -s "$API_BASE/" | jq . || echo "❌ 根端点失败"

echo ""
echo "✅ 基础 API 测试完成"
echo "💡 若需完整测试，你需要："
echo "  1. 在 server/.env 中配置 Anthropic API Key"
echo "  2. 用于创建任务的 GitHub 令牌"
echo "  3. 目标仓库 URL"
