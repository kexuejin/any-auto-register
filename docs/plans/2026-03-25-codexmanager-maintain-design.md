# CodexManager 定时维护（封禁清理 + 自动补量）设计

## 背景
当前 any-auto-register 已支持 CodexManager 导入，但缺少定时维护：
- 需要定期清理 CodexManager 中“封禁”账号（并同步删除本地记录）。
- 需要按阈值自动补充账号数量（不足则触发 ChatGPT 注册任务并自动导入）。

## 目标
- 每 2 小时巡检一次（可配置）。
- 清理 CodexManager 中“封禁”账号，并在本地数据库中直接删除对应 ChatGPT 账号。
- 统计“可用账号数”，若低于阈值，触发注册任务补量（仅 ChatGPT）。
- 新增全局配置项，提供 UI 控制。

## 非目标
- 不实现完整的 CodexManager 巡检/重登逻辑（仅“封禁”清理）。
- 不改变 CodexManager RPC 服务本身。

## 方案概述
新增 `CodexManagerMaintainer` 后台线程，随服务启动，按间隔执行：
1. 通过 RPC 拉取“封禁”列表并删除。
2. 同步删除本地 ChatGPT 账号。
3. 统计“可用账号数”。
4. 不足阈值则触发注册任务补量，并自动导入 CodexManager。

## 关键设计

### 1) 定时器/生命周期
- 在 `main.py` 的 `lifespan` 中启动/停止维护线程。
- 线程内部避免并发执行（若上一次未结束则跳过）。

### 2) RPC 调用封装
- 复用 `platforms/chatgpt/codexmanager_upload.py` 中的 RPC URL/Token 解析逻辑。
- 新增轻量 RPC helper：
  - `account/list`（支持 filter 参数）
  - `account/delete`

### 3) “封禁”清理
- 使用配置 `codexmanager_banned_filter`（默认 `banned`）调用 `account/list`。
- 对返回的账号逐个 `account/delete`。
- 本地数据库按 `email`（优先 item.email，其次 item.label）匹配 `platform=chatgpt` 账号并直接删除。

### 4) 可用账号统计
- 使用配置 `codexmanager_available_filter`（默认 `active`）。
- 支持逗号分隔多个过滤值，分别调用 `account/list` 并按 `id` 去重计数。
- 统计口径仅用于补量，按需求 **新导入但未刷新额度的账号也算可用**。

### 5) 自动补量
- 配置：
  - `codexmanager_min_available`（默认 50）
  - `codexmanager_fill_count`（默认 0；为 0 表示补到阈值）
- 当 `available < min_available` 时触发：
  - `need = fill_count > 0 ? fill_count : (min_available - available)`
  - 触发 ChatGPT 注册任务，强制 `auto_upload_target = codexmanager`。

### 6) 配置与 UI
新增全局配置项（ChatGPT → CodexManager 卡片）：
- `codexmanager_maintain_enabled`（默认 true）
- `codexmanager_maintain_interval_secs`（默认 7200）
- `codexmanager_min_available`（默认 50）
- `codexmanager_fill_count`（默认 0）
- `codexmanager_banned_filter`（默认 `banned`）
- `codexmanager_available_filter`（默认 `active`）

### 7) 失败与容错
- RPC 不可达、Token 缺失、返回异常等情况，仅记录日志并跳过本轮。
- 不影响主服务其它功能。

## 需要修改的模块
- `core/` 新增维护线程实现（例如 `core/codexmanager_maintainer.py`）。
- `main.py`：在 `lifespan` 中启动/停止。
- `api/config.py`：新增配置 key。
- `frontend/src/pages/Settings.tsx`：CodexManager 配置卡片新增字段。
- `tests/`：新增单测覆盖 RPC 调用与补量触发逻辑。

## 测试计划
- 单测：
  - 维护线程逻辑：封禁账号清理、available 统计与补量计算。
  - 过滤值多段合并计数。
  - RPC 失败/空返回容错。
- UI：设置页字段展示与保存。
