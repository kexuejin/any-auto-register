# CodexManager 立即检查（手动触发完整维护流程）设计

## 背景
已支持 CodexManager 定时维护（封禁清理 + 可用统计 + 自动补号），但缺少手动“立即检查”入口，导致调试与运维不便。

## 目标
- 在 Settings -> ChatGPT -> CodexManager 增加“立即检查”按钮。
- 点击后立即触发一次完整维护流程（清理封禁 + 统计可用 + 不足补号）。
- **忽略自动补号开关**：即便 `codexmanager_maintain_enabled=false` 也强制执行一次。
- 并发控制：若维护线程正在执行，手动触发直接返回“执行中/忙”，不重复触发。

## 非目标
- 不新增复杂的任务队列/排队机制。
- 不提供历史报告列表（只返回本次结果）。

## 方案概述
- 新增后端 API：`POST /api/codexmanager/maintain/run`
- 后端调用 `CodexManagerMaintainer.run_once(force=True)` 并返回 report。
- 前端 Settings 页面在 CodexManager 卡片中新增按钮，调用该 API 并 toast 展示结果。

## API 设计
### Endpoint
- `POST /api/codexmanager/maintain/run`

### Responses
- 成功：
  - `{ ok: true, forced: true, report: { deleted: number, available: number, fill: number } }`
- 忙（锁被占用）：
  - `{ ok: false, error: "busy" }`
- 失败：
  - `{ ok: false, error: string }`

## 并发控制
- 复用 `CodexManagerMaintainer` 内部 `_lock`。
- 手动触发时 `blocking=False` 获取锁；获取失败直接返回 busy。

## 前端交互
- 按钮：`立即检查`
- loading：`检查中...` 并禁用按钮。
- toast：
  - 成功：`清理封禁 X，可用 Y，补号 Z`
  - busy：`执行中/忙`
  - 失败：显示错误文本

## 测试
- 后端：新增单测验证 `force=True` 时即使 enabled=false 仍执行（且 busy 返回）。
- 前端：补充一条单测验证按钮存在并能触发 API（若现有测试框架允许）。
