# LoreNook 文档索引

[English](../README.md) | [项目说明](README.md)

英文为主文档，中文按相同主题结构提供对照。现行文档描述项目规则与后端契约，历史草稿单独归档。

## 建议阅读顺序

1. [项目说明](README.md)：启动、迁移与可用接口。
2. [产品设计](design/product-design.md)：目标、界面、回合生命周期与记忆规则。
3. [数据模型](design/data-model.md)：逻辑实体、字段与归属。
4. [项目结构](architecture/project-layout.md)：文档与代码目录分工。
5. [后端总览](backend/README.md)：技术选型、分层与流程。
6. 按需阅读下方模块说明。

产品设计描述产品行为与范围；数据模型描述逻辑业务数据，物理约束由数据访问文档补充；各模块说明描述已实现的后端接口。前端和首次个人部署已完成验收，具体验证范围见里程碑记录。

## 部署与版本

- [Ubuntu 部署与运维](deployment/ubuntu.md)：现有 Caddy 分流、systemd、数据库迁移、更新、备份与恢复。
- [里程碑一](releases/milestone-1.md)：交付范围、验收证据、Python 3.14 兼容修复与当前边界。
- [前端实现说明](../../frontend/README.md)：命令、结构、渲染与浏览器本地偏好。

## 后端模块

| 文档 | 内容 |
| --- | --- |
| [01 数据访问](backend/01-data-access.md) | 存储、约束、查询、事务与迁移 |
| [02 角色与聊天](backend/02-characters-and-chats.md) | 来源资料、独立副本、创建与配置 |
| [03 定义解析](backend/03-definition-rendering.md) | 条目管理、排序与 Jinja2 模板 |
| [04 记忆装配](backend/04-memory-assembly.md) | X/Y 选取与历史表示 |
| [05 写作预设](backend/05-writing-presets.md) | JavaScript、试运行与请求预览 |
| [06 模型调用](backend/06-model-calls.md) | 配置、参数合并、适配与错误 |
| [07 写作流程](backend/07-writing-workflow.md) | 快照、单次调用与待确认回复 |
| [08 状态更新](backend/08-state-updates.md) | Python/Pydantic、JSON Patch 与编辑 |
| [09 回合摘要](backend/09-round-summaries.md) | 使用本回合已保存状态生成摘要 |
| [10 情节判定](backend/10-episode-decisions.md) | 跨日规则、候选与范围保存 |
| [11 情节摘要](backend/11-episode-summaries.md) | 选定范围的摘要生成与编辑 |
| [12 归档流程](backend/12-archiving-workflow.md) | 确认、顺序保存、进度与恢复 |
| [13 数据管理](backend/13-data-management.md) | 全量读取、版本、原子修改与一致性 |

## 术语

| 中文 | 英文 |
| --- | --- |
| 聊天 | Chat |
| 用户身份 | User identity |
| 定义 | Definition |
| 回合 | Round |
| 回合摘要 | Round summary |
| 情节 | Episode |
| 状态快照 | State snapshot |
| 写作预设 | Writing preset |
| 归档 | Archiving |
| 开场消息 / 第 0 楼 | First Message |

接口、字段、路径、标签和可执行示例键名保留原拼写，尤其是跨日判定使用的 `世界.日期`，英文文档也不改写该键名。

## 历史资料

[最早项目概览](../archive/initial-project-outline.zh-CN.md)保留原始中文正文并标明历史状态，不作为现行规范，也不维护完整英文译本。

[前端功能交接](../archive/frontend-handoff.temporary.md)和[前端测试交接](../archive/frontend-test-handoff.temporary.md)保留实现阶段的需求与冒烟检查清单。其中待办描述属于历史状态；当前进度以前端说明和里程碑记录为准。
