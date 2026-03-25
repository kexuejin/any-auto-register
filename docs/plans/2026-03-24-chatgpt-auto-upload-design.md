# ChatGPT 注册后自动导入（CPA / Team Manager / CodexManager）设计

## 背景
当前 ChatGPT 注册成功后会自动上传 CPA（若配置了 `cpa_api_url`），Team Manager 仅支持手动上传，CodexManager 无对接。需要在注册弹框中增加“注册成功后自动导入”的选择，并新增 CodexManager 支持。

## 目标
- 仅在 ChatGPT 注册弹框提供“自动导入”选择。
- 支持自动上传到三类目标：CPA、Team Manager、CodexManager。
- 默认选项跟随已配置目标（优先级：CPA → Team Manager → CodexManager），否则为“不自动上传”。
- 上传失败不影响注册流程，仅记录日志。

## 非目标
- 不为其它平台注册流程增加自动导入。
- 不改变现有账号列表中的手动“上传 Team Manager/CPA”行为。
- 不新增跨平台批量同步逻辑。

## 方案与权衡
采用“混合配置”方案：
- UI 可配置 CodexManager RPC URL / Token。
- 若未配置，仍按环境变量与 token 文件自动探测（与 `api-register-py` 行为一致）。
优点是易用与兼容性兼顾，缺点是后端逻辑稍复杂。

## UX 设计
- `frontend/src/pages/Accounts.tsx` 的 `RegisterModal` 增加下拉框：
  - 不自动上传
  - CPA
  - Team Manager
  - CodexManager
- 仅当 `platform === "chatgpt"` 显示该下拉框。
- 打开弹框时请求 `/config`，根据已配置项自动设置默认值：
  - 若配置了 `cpa_api_url`，默认 CPA。
  - 否则若配置了 `team_manager_url`，默认 Team Manager。
  - 否则若配置了 `codexmanager_rpc_url` 或可探测到 token，默认 CodexManager。
  - 否则默认不自动上传。

## 配置设计
新增配置项（持久化在 ConfigStore）：
- `codexmanager_rpc_url`
- `codexmanager_rpc_token`
- `codexmanager_rpc_token_file`

`Settings` 页面新增 “CodexManager” 小节显示以上配置。

## 后端行为
注册成功后执行以下流程：
1. 读取用户选择的 `auto_upload_target`。
2. 根据选择调用对应上传函数：
   - CPA：沿用 `platforms/chatgpt/cpa_upload.py::upload_to_cpa`。
   - Team Manager：沿用 `platforms/chatgpt/cpa_upload.py::upload_to_team_manager`。
   - CodexManager：新增 `platforms/chatgpt/codexmanager_upload.py`（或复用现有模块）实现 JSON-RPC 调用。
3. 失败仅记录日志，不阻断注册。

## CodexManager 对接细节
- RPC URL 选择优先级：
  - `codexmanager_rpc_url`（UI 配置）
  - 环境变量 `CODEXMANAGER_RPC_URL`
  - 默认 `http://127.0.0.1:48760/rpc`
  - 同时尝试候选列表：`localhost:48760/rpc`、`127.0.0.1:48761/api/rpc`、`localhost:48761/api/rpc`
- RPC Token 选择优先级：
  - `codexmanager_rpc_token`（UI 配置）
  - 环境变量 `CODEXMANAGER_RPC_TOKEN`
  - `codexmanager_rpc_token_file`（UI 配置）
  - 环境变量 `CODEXMANAGER_RPC_TOKEN_FILE`
  - `CODEXMANAGER_DB_PATH` 推导到同目录 `codexmanager.rpc-token`
  - macOS 默认路径（与 `api-register-py` 一致）
- 请求方式：HTTP POST JSON-RPC `account/import`
  - Header: `Content-Type: application/json`, `X-CodexManager-Rpc-Token`（若有）
  - Body:
    ```json
    {"id":123,"method":"account/import","params":{"content":"[ ... ]"}}
    ```
- 导入 payload 字段：
  - `email`, `label`, `access_token`, `refresh_token`, `id_token`, `workspace_id`, `account_id`
  - 若 `access_token` 为空则不导入。
- 成功后可尝试调用 `account/usage/refresh`（失败忽略）。

## 日志与错误处理
- 统一日志前缀：`[CPA]`、`[TM]`、`[CodexManager]`。
- 失败仅记录日志，不影响注册成功状态。

## 测试计划
- 手动：
  - ChatGPT 注册弹框显示下拉框，其他平台注册弹框不显示。
  - 配置不同目标时默认选项正确。
  - 选择不同目标后注册成功触发对应上传。
- 单元：
  - CodexManager 上传函数在无 token / 无 access_token 时返回明确错误。

## 兼容性
- 现有 CPA 自动上传行为将改为“默认选择 CPA”，当用户明确选择“不自动上传”时不再触发。
