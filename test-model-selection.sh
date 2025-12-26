#!/bin/bash

echo "正在测试模型选择 API..."

# 测试 Claude 模型
echo "正在测试 Claude Code 模型..."
curl -X POST http://localhost:5000/start-task \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "在 README 中添加一条测试注释",
    "repo_url": "https://github.com/test/repo",
    "branch": "main",
    "github_token": "test_token",
    "model": "claude"
  }'

echo -e "\n\n正在测试 Codex CLI 模型..."
curl -X POST http://localhost:5000/start-task \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "在 README 中添加一条测试注释",
    "repo_url": "https://github.com/test/repo",
    "branch": "main", 
    "github_token": "test_token",
    "model": "codex"
  }'

echo -e "\n\n正在测试无效模型..."
curl -X POST http://localhost:5000/start-task \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "在 README 中添加一条测试注释",
    "repo_url": "https://github.com/test/repo",
    "branch": "main",
    "github_token": "test_token",
    "model": "invalid_model"
  }'
