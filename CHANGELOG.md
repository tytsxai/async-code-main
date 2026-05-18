# Changelog

## [0.1.0] - 2026-05-19

First tagged release of `async-code-main` — a self-hosted platform for running multiple AI coding agents in parallel.

### Included

- **Parallel agent execution** — Claude Code + Codex CLI (extensible), each in isolated Docker containers
- **Codex-style UI** — task list, real-time status polling, log streaming
- **File-level diff viewer** — git diff + before/after per file
- **One-click PR** — clones repo, applies saved patch on new branch, pushes, opens PR via user's GitHub token
- **Two storage modes** — Supabase (multi-user persistent) or local JSON (single machine, no signup)
- **Optional host `~/.codex` mount** for inheriting Codex CLI credentials
- **`CODEX_PRIVILEGED` opt-in** for compat mode (off by default)
- **Stack** — Next.js + TypeScript frontend, Flask backend, Docker Compose orchestration
- **Discovery** — bilingual README + `llms.txt`

### Notes

Behavior matches the most recent `main` commit before tagging. This freezes v0.1.0 so downstream forks/integrations can pin a baseline.
