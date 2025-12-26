# Async Code 操作指南

这份文档面向“使用者/自部署者”，按步骤说明如何启动、配置、创建任务与排查常见问题。

## 1. 启动与停止

### 启动（Docker）

```bash
docker compose up --build
```

访问地址：

- 前端界面：`http://localhost:3000`
- 后端 API：`http://localhost:5000`

### 停止

```bash
docker compose down
```

## 2. 基本使用

### 创建任务

1. 选择项目/仓库（默认会自动选择最近使用的）
2. 选择分支（默认 `main`）
3. 选择模型（Codex 或 Claude）
4. 输入任务描述（提示词）
5. 点击发送

### 任务状态

| 状态 | 说明 |
| --- | --- |
| `pending` | 等待执行 |
| `running` | 正在执行 |
| `completed` | 执行成功 |
| `failed` | 执行失败 |

### 任务归档

- 已完成/失败任务可归档
- 归档信息保存在浏览器本地存储（仅影响当前浏览器）

## 3. 模型与凭据配置

### Claude Code

在 `server/.env` 配置：

```bash
ANTHROPIC_API_KEY=your_key
```

### Codex CLI

Codex 的 Key/环境变量建议在 Web「设置」页配置（这些值会注入任务容器中）。

如果你希望任务容器读取你宿主机的 `~/.codex`（例如 `auth.json` / `config.toml`），可设置：

```bash
HOST_CODEX_DIR=/path/to/your/.codex
```

安全提示：Codex “特权模式”默认关闭；只有在确实遇到 sandbox/系统调用限制时再开启：

```bash
CODEX_PRIVILEGED=true
```

## 4. GitHub Token（创建 PR）

- 在 Web「设置」页配置 GitHub Token
- 默认仅保存在当前会话（`sessionStorage`）；勾选“记住”才会写入 `localStorage`
- Token 用于：克隆仓库、推送分支、创建 PR

## 5. 常见问题

### 容器启动失败

```bash
docker ps
docker compose logs -f
```

### 前端修改不生效

开发模式用 `npm run dev`；如果使用 Docker 运行生产构建，需要重新 build 镜像。

### 如何查看某个任务的容器日志

后端日志里会记录容器名称/ID；也可以查看后端服务日志：

```bash
docker compose logs -f backend
```

## 6. 端口说明

| 端口 | 服务 |
| --- | --- |
| 3000 | 前端（Next.js） |
| 5000 | 后端（Flask API） |
