# ChatGPT 账号菜单新增 CodexManager 上传入口设计

## 背景
当前 ChatGPT 账号列表的“更多菜单”已支持上传 CPA / Team Manager，但缺少 CodexManager 上传入口。注册弹框已支持选择 CodexManager 自动上传。

## 目标
- 在 ChatGPT 账号菜单中新增“上传 CodexManager”。
- 行为与注册弹框选择 CodexManager 一致：无需输入参数，自动解析配置/环境变量/Token 文件。
- 仅影响 ChatGPT 平台。

## 非目标
- 不新增其它平台的 CodexManager 操作。
- 不添加手动填写 RPC URL/Token 的弹窗。

## 方案
### 行为
- 菜单新增 action：`upload_codexmanager`（无参数）。
- 点击后立即执行上传，结果以 UI toast 展示。

### 数据流
1. 前端通过 `/api/actions/chatgpt` 获取 action 列表。
2. 选择 `upload_codexmanager` 后调用 `/api/actions/chatgpt/{account_id}/upload_codexmanager`。
3. 后端执行 `platforms.chatgpt.codexmanager_upload.upload_to_codexmanager(account)`。
4. 上传成功/失败返回 `ok` 与 `data`，前端展示消息。

### 配置来源
- `codexmanager_rpc_url` / `codexmanager_rpc_token` / `codexmanager_rpc_token_file`（配置）
- 环境变量或默认 token 文件路径
- 与注册弹框的 CodexManager 上传一致

## 错误处理
- 上传失败仅返回错误，不影响账号状态。
- 缺少 token / url 时返回明确错误消息。

## 测试
- 单测：为 `execute_action` 新增 `upload_codexmanager` 分支测试（可选）。
- 手动：点击菜单项确认请求与提示正确。
