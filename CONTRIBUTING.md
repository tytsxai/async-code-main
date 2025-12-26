# 贡献指南

感谢你愿意贡献。

## 开发环境

- Docker / Docker Compose（推荐）
- 或本地：Node.js + Python 3

## 本地启动

### 使用 Docker

```bash
docker compose up --build
```

### 不使用 Docker

```bash
# Frontend
cd async-code-web
npm ci
npm run dev

# Backend
cd ../server
python3 main.py
```

## 提交前自检

```bash
# Backend
python3 -m compileall -q server

# Frontend
npm --prefix async-code-web run lint
npm --prefix async-code-web run build
```

## 注意事项

- 不要提交 `server/local_db.json`、任何 `.env`、以及 `node_modules/`、`.next/` 等构建产物。
- 不要在 issue/PR 里粘贴真实的 Token 或密钥。
