# Async Code Agent

一个用于“并行跑代码代理”的自托管平台：通过 Web UI 同时运行 Claude Code 与 Codex CLI（或其它代理），统一收集执行日志与代码变更，并支持一键创建 Pull Request。

![async-code-ui](https://github.com/user-attachments/assets/e490c605-681a-4abb-a440-323e15f1a90d)

![async-code-review](https://github.com/user-attachments/assets/bbf71c82-636c-487b-bb51-6ad0b393c2ef)

## 你会用它做什么

- 让多个代理并行修改同一个仓库，然后在 UI 里对比差异
- 将代理输出转换成可审查的 git patch/diff，再创建 PR
- 在隔离容器里执行（便于控制依赖、减少环境污染）

## 主要特性

- 多代理并行：Claude Code + Codex CLI（可扩展）
- Codex 风格 UI：任务列表、状态轮询、日志查看
- 变更对比：展示 git diff + 文件级 before/after
- PR 创建：基于保存的 patch 克隆仓库、应用补丁并推送分支，再创建 PR
- 两种存储模式：
  - Supabase（多用户、持久化、鉴权）
  - 本地 JSON（单机快速体验）

## 架构概览

- 前端：Next.js + TypeScript
- 后端：Flask API
- 执行：Docker 容器（每个任务一个隔离环境）

## 快速开始（推荐：Docker）

1. 准备环境文件

```bash
cp server/.env.example server/.env
```

2. 启动

```bash
docker compose up --build
```

3. 打开

- Web UI：`http://localhost:3000`
- API：`http://localhost:5000`

## 运行模式与鉴权

### Supabase 模式（推荐）

- 前端通过 Supabase 登录获取 `access_token`
- 前端调用后端 API 时会自动带 `Authorization: Bearer <token>`

前端需要：

```bash
# async-code-web 环境变量（例如通过容器/部署平台注入）
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

后端需要：

```bash
# server/.env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

### 本地模式（快速体验）

- 不使用 Supabase
- 前端会使用本地用户（`X-User-ID`）调用后端
- 任务/项目存储在 `server/local_db.json`（该文件不应提交到仓库）

可通过以下环境变量禁用 Supabase：

```bash
SUPABASE_DISABLED=true
NEXT_PUBLIC_SUPABASE_DISABLED=true
```

## Codex / Claude 的执行配置

### Claude Code

- 需要在 `server/.env` 提供 `ANTHROPIC_API_KEY`

### Codex CLI

- Codex 任务会在独立容器里运行，需要提供 OpenAI Key 等环境变量（在 Web「设置」页里配置）
- 如需让容器读取你本机的 `~/.codex`（例如 `auth.json`、`config.toml`），设置：

```bash
HOST_CODEX_DIR=/path/to/your/.codex
```

安全提示：Codex 兼容性“特权模式”默认关闭。如确有需要再显式开启：

```bash
CODEX_PRIVILEGED=true
```

## GitHub Token

- Web「设置」页用于配置 GitHub Token（用于 clone/push/创建 PR）
- GitHub Token 仅保存在当前会话（`sessionStorage`），不会持久化到 `localStorage`
- 本地模式导出的数据不会包含 GitHub Token 或其他凭据字段

## 目录结构

```text
async-code-main/
  async-code-web/     # Next.js 前端
  server/             # Flask 后端
  db/                 # Supabase 初始化 SQL
  docker-compose.yml  # 一键启动
```

## 开发（不使用 Docker）

```bash
# Frontend
cd async-code-web
npm ci
npm run dev

# Backend
cd ../server
python3 main.py
```

## 贡献

见 `CONTRIBUTING.md`。

## 许可证

本项目使用 Apache-2.0，详见 `LICENSE`。
