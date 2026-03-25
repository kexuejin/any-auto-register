# CodexManager 导入对齐（openai-auto-register）设计

## 背景
当前 any-auto-register 已有 CodexManager 导入能力，但与 openai-auto-register 的 RPC 调用与 payload 约定不完全一致，导致默认选择、错误分类、RPC 地址/Token 解析等行为存在偏差。同时 Settings 中 CodexManager RPC URL 的提示值不准确。

## 目标
- 导入实现与 openai-auto-register 对齐（payload、RPC 调用、错误分类与返回信息）。
- UI 配置提示值准确，减少误配置。
- 默认自动上传目标在“未配置 URL 但可解析到 Token”时仍可选择 CodexManager。

## 非目标
- 不引入跨仓库共享模块。
- 不改变 CodexManager RPC 服务本身。
- 不新增 UI 页面，仅修正现有配置入口。

## 设计概述
对 `platforms/chatgpt/codexmanager_upload.py` 进行行为对齐：
- 统一 RPC URL fallback 列表与尝试顺序。
- 统一 RPC Token 解析策略（仍保留 ConfigStore 优先级）。
- payload 字段与必填校验与 openai-auto-register 一致。
- 错误分类与返回信息对齐。

同时：
- `api/tasks.py` 默认选择逻辑支持“有 token 但 URL 为空”时选中 CodexManager。
- `frontend/src/pages/Settings.tsx` 的 CodexManager RPC URL placeholder 改为 `http://127.0.0.1:48760/rpc`。

## 具体改动点
### 1) 导入 payload 与校验
- 生成 payload 字段：`email`, `label`, `access_token`, `refresh_token`, `id_token`, `workspace_id`, `account_id`。
- 当 `access_token` / `refresh_token` / `id_token` 任一缺失时，拒绝导入并返回明确错误。

### 2) RPC URL 解析与 fallback
- 主 URL 解析优先级：
  1. `codexmanager_rpc_url`（ConfigStore）
  2. `CODEXMANAGER_RPC_URL`
  3. 默认 `http://127.0.0.1:48760/rpc`
- fallback 列表（顺序与 openai-auto-register 一致）：
  - `http://127.0.0.1:48760/rpc`
  - `http://localhost:48760/rpc`
  - `http://127.0.0.1:48761/api/rpc`
  - `http://localhost:48761/api/rpc`

### 3) RPC Token 解析
- 解析优先级：
  1. `codexmanager_rpc_token`（ConfigStore）
  2. `CODEXMANAGER_RPC_TOKEN`
  3. `codexmanager_rpc_token_file`（ConfigStore）
  4. `CODEXMANAGER_RPC_TOKEN_FILE`
  5. `CODEXMANAGER_DB_PATH` 同目录 `codexmanager.rpc-token`
  6. macOS 默认路径 `~/Library/Application Support/com.codexmanager.desktop/codexmanager.rpc-token` / `~/Library/Application Support/codexmanager/codexmanager.rpc-token`

### 4) 错误分类与返回
- 对齐 openai-auto-register 的错误分类：
  - `rpc_http_401`, `rpc_http_502`, `rpc_connection_refused`, `rpc_timeout`, `rpc_invalid_json`, `rpc_unreachable`
- 返回值保持 `ok: bool` + `msg` 文本，日志输出使用 `[CodexManager]` 前缀。

### 5) 默认自动上传目标
- `pick_auto_upload_target` 允许在 `codexmanager_rpc_url` 为空、但可解析到 token 时选择 CodexManager。

### 6) UI 配置提示
- `Settings -> ChatGPT -> CodexManager` 的 RPC URL placeholder 改为 `http://127.0.0.1:48760/rpc`。

## 数据流（导入）
1. 账号注册或手动触发菜单上传。
2. 组装 payload，进行 token 必填校验。
3. 解析 RPC URL + token。
4. 依次尝试 RPC URL fallback；成功即返回 `created/updated/failed` 结果。
5. 失败返回分类错误并记录日志。

## 测试计划
- 单元测试：
  - payload 校验缺失 token 返回明确错误。
  - RPC URL fallback 顺序与去重。
  - 错误分类（401/502/connection refused/timeout/invalid json/unreachable）。
- 行为测试：
  - `codexmanager_rpc_url` 为空但 token 可解析时，注册默认选中 CodexManager。
  - Settings placeholder 展示正确默认值。

## 风险与缓解
- **风险**：改动错误分类后可能影响前端展示。
  - **缓解**：保持返回结构不变，仅优化错误文本。
- **风险**：URL fallback 变更导致连接目标不同。
  - **缓解**：主 URL 优先级不变，fallback 保持 openai-auto-register 的顺序。

## 迁移/兼容性
- 旧配置无需变更。
- 若用户使用 Docker，需显式配置 `codexmanager_rpc_url` 为可达地址（例如 `http://host.docker.internal:48760/rpc`）。
