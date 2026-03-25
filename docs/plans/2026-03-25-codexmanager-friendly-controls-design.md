# CodexManager 配置控件友好化设计

## 背景
当前设置页 CodexManager 配置全部为文本输入，自动补号开关需要手动输入 true/false，整体体验不友好。

## 目标
- 将 CodexManager 配置改为更友好的控件（开关、数字输入、分组提示）。
- 高级参数默认折叠，减少日常配置干扰。
- 保持后端配置 key 与行为不变。

## 非目标
- 不改动后端配置结构与 RPC 逻辑。
- 不引入新的配置项。

## 方案概述
在 Settings 页面为 CodexManager 增加控件类型与分组：
- 基础区：连接设置 + 自动补号。
- 高级区：过滤值与补号细节，默认折叠。
- `自动补号开关` 使用 Toggle；数值类使用 `<input type="number">`。

## UI 设计
### 分组
- 连接设置：RPC URL、RPC Token、RPC Token File。
- 自动补号：开关、检查间隔、最低可用数。
- 高级设置（折叠）：每次补号数量、封禁过滤值、可用过滤值。

### 控件
- `codexmanager_maintain_enabled`：Toggle（启用/禁用）。
- `codexmanager_maintain_interval_secs`：数字输入（min 60，step 60）。
- `codexmanager_min_available`：数字输入（min 1）。
- `codexmanager_fill_count`：数字输入（min 0，提示 0=补到阈值）。
- `codexmanager_banned_filter`：文本输入（提示默认 banned）。
- `codexmanager_available_filter`：文本输入（提示默认 active）。

### 文案/提示
为关键字段增加简短说明（help 文案），弱化对 placeholder 的依赖。

## 数据绑定
- 继续通过 `/api/config` 读写现有 key。
- Toggle 写入 `"true"/"false"` 字符串，保持后端兼容。

## 实现范围
- 主要修改 `frontend/src/pages/Settings.tsx`：
  - 扩展 Field 渲染，支持 `type: 'toggle' | 'number'`。
  - 添加高级设置折叠区。
  - CodexManager items 增加 `type/min/step/help`。
- 前端构建更新 `static/` 产物。

## 测试
- 手动验证 Settings 页面：控件显示、折叠逻辑、保存配置生效。
