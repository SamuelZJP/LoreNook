# LoreNook 数据访问模块

[English](../../backend/01-data-access.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 职责与入口

数据访问模块负责存储模型、数据库连接、查询与保存。业务模块及 Workflow 决定何时调用，事务由调用方控制。Repository 内只执行查询、写入及 `flush`，不执行 `commit`、模型调用、定义解析或状态 Schema 校验。

| 文件 | 内容 |
| --- | --- |
| `backend/config.py` | SQLite 地址和连接超时配置 |
| `backend/repository/models.py` | 物理表与约束 |
| `backend/repository/database.py` | 连接、读会话、写事务 |
| `backend/repository/queries.py` | 基础读写与范围查询 |
| `backend/repository/archive.py` | 归档步骤结果保存 |
| `backend/migrations/` | Alembic 结构版本 |

## 2. 存储类型

- 普通记录 ID 为应用生成的 UUID 字符串，SQLite 类型为 `VARCHAR(36)`。
- 文本与源码使用 `TEXT`；头像可为空，空描述使用空字符串。
- 序号和数量使用 `INTEGER`；布尔值使用带 0/1 检查的 SQLite 布尔列。
- 时间按 UTC 保存为 `DATETIME`，读取时恢复 UTC 时区；应用写入的时间必须带时区。
- 状态与模型默认参数使用 JSON 列，数据库检查 JSON 合法且顶层为对象，保留嵌套值类型。
- `state_schema` 保存 Python/Pydantic 源码；结构、默认值与校验见[状态模块](08-state-updates.md)。

JSON 修改采用整体赋值：在副本上修改后重新赋给字段。原地修改嵌套字典不会自动触发 ORM 更新。

## 3. 表与约束

业务字段沿用[数据模型](../design/data-model.md)。物理结构补充如下：

| 表 | 物理约束与索引 |
| --- | --- |
| `chats` | X、Y 非负；默认 X=5、Y=6，可修改；选中的预设必须属于当前聊天 |
| `characters` | 非空 `chat_id` 唯一，每个聊天至多一份角色；空值允许多份来源角色 |
| `user_identities` | 非空 `chat_id` 唯一，每个聊天至多一份身份；空值允许多份来源身份 |
| `definitions` | 角色与身份必须且只能填写一个；顺序非负；按归属建索引，允许相同顺序并以 ID 稳定排序 |
| `writing_presets` | 按 `chat_id` 建索引；`id + chat_id` 唯一，供同聊天复合外键引用 |
| `model_configs` | 按 `chat_id` 建索引；`id + chat_id` 唯一；默认参数必须为 JSON 对象 |
| `chat_model_bindings` | `chat_id + purpose` 为联合主键；用途限定为四种已定义值；配置必须属于当前聊天 |
| `rounds` | 聊天内回合序号唯一且从 1 开始；部分唯一索引限制每个聊天只有一个未完成归档回合 |
| `state_snapshots` | 额外保存非空 `chat_id`；复合外键保证角色、回合与聊天一致；每回合至多一份快照；部分唯一索引限制每角色至多一份初始快照 |
| `episodes` | 起止回合与产生回合必须属于当前聊天；每个产生回合至多一份情节；摘要非空 |

回合归档步骤限定为 `state_update`、`round_summary`、`episode_decision`、`episode_summary`、`complete`。数据库同时检查摘要进度、情节判定字段的组合形状，以及完成回合不能保留错误。尚未判定使用空值，无需情节使用 `false`，需要情节使用 `true` 并保存两个端点。

数据库约束负责引用、唯一性和单行字段一致性。创建聊天时角色、身份、初始状态及必要配置是否齐全，由创建流程负责；正常状态操作的 Schema 校验由状态模块负责；回合状态与情节保存是否齐全，通过归档保存接口保证。情节范围的先后、连续性和不重复覆盖由范围查询与归档保存接口检查。[数据管理模块](13-data-management.md)独立校验最终跨行规则，其历史状态修改按原文保存，不执行 Schema。

## 4. 查询与修改

`Repository` 提供：

| 接口 | 行为 |
| --- | --- |
| `get(model, key)` | 按主键读取，缺失抛出 `NotFoundError`；用途关联使用联合主键 |
| `add(record)` / `delete(record)` | 写入或删除并 `flush`，提交由外层负责 |
| `list_chats()` | 按创建时间倒序读取聊天 |
| `list_owned(model, chat_id)` | 读取某聊天的副本；传入空值时读取来源库 |
| `definitions(...)` | 按角色或身份读取定义，支持只读取启用项，按顺序及 ID 排序 |
| `rounds(chat_id, completed_only=...)` | 按回合序号读取，支持只读取已归档回合 |
| `latest_round(chat_id)` | 最新回合，无记录时为空 |
| `round_header(chat_id, round_id)` / `latest_round_header(chat_id)` | 限定聊天读取回合 ID、序号和步骤，不读取正文 |
| `latest_state(character_id)` | 优先读取最大回合序号的已保存快照，其次读取初始快照 |
| `state_for_round(chat_id, round_id)` | 精确读取同聊天中指定回合的状态，不回退到其他快照 |
| `states_for_rounds(chat_id, round_ids)` | 批量读取同聊天中指定回合的状态，不回退到其他快照 |
| `round_summaries_in_range(chat_id, start_no, end_no)` | 按序投影读取范围内回合 ID、序号和摘要，不加载正文 |
| `round_dates(chat_id, round_ids)` | 投影读取指定回合的 `世界.日期`，缺少快照不返回该 ID |
| `summaries_before(chat_id, round_no, limit)` | 取指定回合之前最近若干个已归档回合，按序返回，供生成模块读取摘要 |
| `episodes(chat_id)` | 按覆盖范围的起始回合排序 |
| `episode_for_round(chat_id, round_id)` | 读取指定产生回合的情节，无结果时为空 |
| `unrepresented_rounds(chat_id)` | 排除所有已保存情节覆盖的回合，按回合序号返回 |
| `unrepresented_round_headers(chat_id)` | 使用相同覆盖筛选，只返回回合元数据，供情节判定与范围校验使用 |

最新状态不按保存时间判断：编辑旧快照不应使其成为最新状态。未完成归档回合已经保存的状态也参与最新状态查询；下一次发送仍需由流程检查归档完成。

修改现有记录时，在写事务内读取对象、赋值字段并提交；JSON 字段整体赋值。当前基础 Repository 为内部接口，不直接作为数据管理 HTTP API。

数据管理使用独立 `AdminRepository`，通过固定业务表注册与参数化 SQL 处理全量快照和批量修改。在同一写事务内暂缓外键检查，执行操作后统一核对引用及最终数据一致性；数据库唯一性、非空和单行检查仍即时生效。读取和编辑不包含 Alembic 版本表或 SQLite 内部表。

## 5. 事务边界

所有连接启用外键，锁等待默认 5 秒。SQLAlchemy 显式发出 `BEGIN`，使 DDL、查询与保存遵守相同事务规则。连接策略依据 [SQLAlchemy SQLite 文档](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)。

`Database.read()` 提供用后关闭、退出不提交的会话。`Database.transaction()` 使用 `BEGIN IMMEDIATE`，先取得写锁再查询，正常退出统一提交，异常时统一回滚。第一版采用同步数据库访问；FastAPI 的数据库入口使用同步函数，后续异步 Workflow 应将完整短事务放在线程中执行，Session 不跨线程共享。

```python
with database.transaction() as session:
    repository = Repository(session)
    chat = repository.add(Chat(title="新的聊天"))
    repository.add(Character(chat_id=chat.id, name="角色"))
    # 创建流程还需在同一事务中复制其余数据并保存初始状态。
```

| 操作 | 事务边界 |
| --- | --- |
| 创建聊天 | 聊天、各副本、定义、关联及初始快照共用一个事务 |
| 点击归档 | 单独保存确认后的正文，产生 `state_update` 回合 |
| 每步归档结果 | 本步结果与 `archive_step` 推进共用一个事务 |
| 记录归档失败 | 结果事务回滚后，另开事务记录当前步骤错误 |
| 手动编辑 | 一次编辑共用一个事务，成功后立即生效 |

模型调用和生成处理在数据库事务外执行。模型返回后重新开启写事务，核对当前步骤，再保存结果。多个写入请求会串行取得 SQLite 写锁，唯一约束作为最终保护；锁超时错误由调用方处理。

## 6. 归档保存接口

`ArchiveRepository` 是归档 Workflow 的存储接口，每次调用放在新的写事务中。已完成或过期步骤的结果抛出 `ConflictError`，不重复写入。

| 接口 | 保存与推进 |
| --- | --- |
| `create_round` | 检查上一回合已完成，分配下一序号，保存确认正文 |
| `save_state` | 保存完整状态快照，推进到回合摘要 |
| `save_summary` | 保存非空回合摘要，推进到情节判定 |
| `save_decision` | 两端为空表示无需情节并完成；否则保存范围并推进到情节摘要 |
| `pending_episode_range` | 检查待生成步骤，校验并读取已保存范围的回合元数据 |
| `save_episode` | 再次校验已保存范围，创建情节并标记完成 |
| `save_error` | 核对当前步骤，保存错误并保留步骤 |

判定范围必须从最早未归纳回合开始，覆盖连续、已完成的回合，且截止于当前归档回合之前。具体是否触发情节、如何选择截止回合，由情节判定模块决定。

情节摘要失败后只保留判定范围，不新增情节，已归纳边界不移动；重试时直接使用原范围。完成步骤后清空错误。进程在提交前中断时结果整体回滚，提交后的成功步骤不会因后续失败而撤销。

## 7. 删除与迁移

删除聊天会级联删除其角色、身份、定义、预设、模型配置、用途关联、回合、状态与情节，来源库不受影响。删除来源角色或身份会级联删除其定义。

已选预设及被范围引用的回合使用延迟外键，在事务提交时检查，因此可在同一事务中重建关联。删除已选预设须先切换或清空聊天选择；删除被情节引用的回合须同步调整相关情节与判定范围。直接删除模型配置会一并删除其用途关联。

数据库结构只由 Alembic 管理。首版迁移固定表、约束和索引，不依赖运行时 ORM 建表。应用启动不自动迁移；迁移命令、验证命令见 [README](../README.md)。

迁移 `d49c370021ae` 为 `episodes` 增加 `title TEXT NOT NULL DEFAULT ''`。已有情节仅补入空标题，不改写摘要、正文、状态、覆盖范围或时间。新生成情节的非空标题与摘要在同一事务中保存；数据管理快照和写作记忆中的情节项均包含标题。升级已有数据库前保留备份，再执行 `alembic upgrade head`。

## 8. 验证范围

测试使用实际临时 SQLite 文件，并从 Alembic 迁移建库，覆盖：外键与归属、定义排序、JSON 类型、状态唯一性、最新状态选取、事务回滚、归档错误和重试、情节边界、重复提交、并发创建、聊天级联删除、迁移结构一致性与带数据降级重建、应用生命周期及健康接口。
