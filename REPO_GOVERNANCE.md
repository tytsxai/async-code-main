# REPO_GOVERNANCE

更新时间：2026-04-12
仓库：`async-code-main`

## 仓库定位
并行代码代理自托管平台，包含 Web UI、后端服务、Docker 与 CI，属于正式项目，不是垃圾目录。

## 当前判断
- 本地状态：目录保留
- 云端状态：`tytsxai/async-code-main`，public，未归档
- 当前分类：继续维护 / 可继续公开
- 风险级别：中（P1 已完成，仍建议继续做 P2 文档与说明复核）

## 已确认事实
- `README.md:1` 将项目定义为 Async Code Agent
- 目录包含前端、后端、Docker、CI、License 等完整项目要素
- 已存在开源许可证：`LICENSE:1` 为 Apache-2.0
- 已提供安全说明：`SECURITY.md:1`
- 已提供环境变量模板：`server/.env.example:1`
- `.gitignore` 已忽略 `.env` 与 `server/local_db.json`
- 前端 GitHub Token 现仅保存在 `sessionStorage`，并会清理遗留 `localStorage` 键：`async-code-web/app/settings/page.tsx:26`
- 首页与任务页已同步改为 session-only token 读取：`async-code-web/app/page.tsx:59`、`async-code-web/app/tasks/[id]/page.tsx:55`
- 本地导出链路会移除 `user.github_token`：`server/database.py:317`
- 后端导出/重置测试已覆盖未鉴权、正常导出、导出脱敏、reset：`server/tests/test_local_db_endpoints.py:22`
- 不应再放入“垃圾候选”

## 建议动作
### 本地
- 保留目录
- 继续维护

### 云端
- 当前 public 状态可以继续保留
- 已完成本轮 P1 安全加固，可继续公开
- 下一步重点转为 P2 文档/说明一致性复核，而不是立即转私有

## 公开安全加固清单
### P1（优先处理）
- [x] 移除 GitHub Token 的 `localStorage` 持久化，仅保留 `sessionStorage`
- [x] 复核前端设置页、任务页与后端日志，确认当前 P1 范围内未新增 token 持久化路径，且保留现有后端 `_redact()` 遮罩基线
- [x] 复核本地导出链路，确认导出的本地数据不包含 `github_token`，并补充后端测试覆盖

### P2（建议处理）
- [x] 在 README 或 SECURITY 中补一段公开使用风险说明：该系统会运行代码代理、克隆仓库、处理 GitHub Token
- [x] 审查测试/示例脚本，避免让用户误以为可以把真实 token 直接写入脚本或日志
- [x] 复核 `GUIDE.md`、`RELEASE.md`、`db/README.md` 等文档中的敏感信息处理说明是否一致

### 公开判断
- 当前仓库可以继续保持 public
- P1 已完成；在继续推进 P2 前，无需因这轮问题转私有
- 如后续扩大传播范围，优先完成 README / GUIDE / RELEASE / db 文档一致性复核

## 待办
- [x] 核实 git remote 与云端仓库状态
- [ ] 判断是否仍在活跃使用
- [x] 做一轮公开仓库安全加固审查
- [x] 完成 P1 公开安全加固项
- [x] 如继续长期公开，补齐公开使用风险说明
- 2026-04-12：从“垃圾候选”中移除，标记为正式项目
- 2026-04-12：完成公开仓库初审，确认许可证、README、SECURITY、环境模板齐备
- 2026-04-12：识别出 GitHub Token 可持久化到 `localStorage` 的安全加固项（旧行为位于 `async-code-web/app/settings/page.tsx`）
- 2026-04-12：完成 P1 安全加固：设置页/首页/任务页统一改为 session-only token，移除本地导出中的 `github_token`，并通过容器内后端测试验证
- 2026-04-12：完成 P2 文档一致性复核：补充 SECURITY 风险提示、更新 RELEASE 检查项，并统一 db/README 对 token 与导出行为的说明
