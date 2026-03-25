# 账号列表按创建时间倒序设计

## 背景
当前 `/api/accounts` 列表未指定排序，导致返回顺序不稳定。需求是账号列表按创建时间倒序展示（最新在前）。

## 目标
- `/api/accounts` 默认按 `created_at` 倒序返回。
- 分页逻辑保持不变。
- `/accounts/export` 不调整排序。

## 非目标
- 不改变导出 CSV 的顺序。
- 不增加前端排序逻辑。

## 方案
- 在 `api/accounts.py::list_accounts` 的查询中追加 `order_by(AccountModel.created_at.desc())`。
- 保持过滤条件、分页参数和返回结构不变。

## 测试
- 新增单测：构造两条不同 `created_at` 的账号记录，验证列表返回顺序为最新在前。
