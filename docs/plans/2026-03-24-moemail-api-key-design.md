# MoeMail API Key Support Design

## Goal
当配置了 `moemail_api_key` 时，优先使用 MoeMail API Key 模式创建邮箱并拉取邮件；未配置时保持现有“注册 + Turnstile”流程不变。

## Non-Goals
- 不新增独立的 `moemail_api` provider。
- 不做 API 失败自动回退注册（避免隐藏配置问题）。
- 不新增自动化测试（暂无 MoeMail 测试桩/伪造服务）。

## API 约定（来自用户提供文档）
- Base URL 复用 `moemail_api_url`（例如 `https://auroramedia.icu`）。
- 认证头：`X-API-Key: <key>`
- 关键接口：
  - `GET /api/config` 获取域名列表
  - `POST /api/emails/generate` 创建邮箱（含 `name`, `domain`, `expiryTime`）
  - `GET /api/emails/{emailId}` 拉取邮件列表/内容

## Architecture
1. 在 `MoeMailMailbox` 增加 `api_key` 参数。
2. `get_email()`：
   - 若 `api_key` 存在：走 API Key 流程（`/api/config` → `/api/emails/generate`）。
   - 否则：走现有注册流程（含 Turnstile）。
3. `get_current_ids()` / `wait_for_code()`：
   - API Key 模式下直接用带 `X-API-Key` 的请求，不依赖 session-token。
   - 注册模式保持现有逻辑。

## Config & UI
- 新增全局配置项 `moemail_api_key`（secret）。
- MoeMail 配置面板新增 “API Key” 字段（Register + Settings 都支持）。
- 保持 `moemail_api_url` 复用为 API Base。

## Error Handling
- API Key 模式：
  - 非 2xx 或返回缺失 `email/id` → 明确报错（提示 API Key/域名配置问题）。
  - `/api/config` 失败 → 明确报错（提示 API Key 无效或权限不足）。
- 注册模式保持现有错误处理。

## Testing
- 无新增测试；依赖现有 `pytest` 基线与手动验证 API Key 模式。
