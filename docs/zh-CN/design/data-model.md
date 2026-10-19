# LoreNook 数据模型

[English](../../design/data-model.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

本文定义逻辑数据模型；SQLite 物理类型、额外归属字段与约束见[数据访问](../backend/01-data-access.md)。`id` 为记录标识，`*_id` 为关联字段。

## 1. 聊天 `chats`

| 字段 | 含义 |
| --- | --- |
| `id` | 聊天 ID |
| `title` | 聊天名称 |
| `writing_preset_id` | 当前使用的聊天内写作预设 |
| `recent_rounds` | 最近完整回合数 X |
| `min_summaries` | 最少保留回合摘要数 Y |
| `created_at` | 创建时间 |

## 2. 角色 `characters`

| 字段 | 含义 |
| --- | --- |
| `id` | 角色 ID |
| `chat_id` | 所属聊天；为空表示角色库中的来源角色 |
| `name` | 角色名称 |
| `avatar` | 头像引用 |
| `description` | 元数据描述 |
| `first_message` | 第 0 楼内容 |
| `state_schema` | 状态结构、默认值、校验与修正规则源码 |
| `state_reference` | 状态更新参考信息 |
| `state_update_rules` | 状态更新规则文本 |
| `created_at` | 创建时间 |

每个聊天拥有一份独立角色记录。

## 3. 用户身份 `user_identities`

| 字段 | 含义 |
| --- | --- |
| `id` | 用户身份 ID |
| `chat_id` | 所属聊天；为空表示身份库中的来源身份 |
| `name` | 名称 |
| `avatar` | 头像引用 |
| `description` | 元数据描述 |
| `created_at` | 创建时间 |

用户身份指角色扮演身份。每个聊天拥有一份独立用户身份记录。

## 4. 定义 `definitions`

| 字段 | 含义 |
| --- | --- |
| `id` | 定义 ID |
| `character_id` | 所属角色；用户定义时为空 |
| `user_identity_id` | 所属用户身份；角色定义时为空 |
| `order` | 排列顺序 |
| `enabled` | 是否启用 |
| `has_template` | 是否包含模板 |
| `content` | 定义原文 |

`character_id` 与 `user_identity_id` 必须且只能填写一个。模板在发送时解析，结果仅用于本次请求。

## 5. 写作预设 `writing_presets`

| 字段 | 含义 |
| --- | --- |
| `id` | 预设 ID |
| `chat_id` | 所属聊天；为空表示预设库中的来源预设 |
| `name` | 预设名称 |
| `source` | 完整预设源码，包含请求包装、目标接口声明和返回解析逻辑 |
| `created_at` | 创建时间 |

## 6. 模型配置与用途

### 模型配置 `model_configs`

| 字段 | 含义 |
| --- | --- |
| `id` | 配置 ID |
| `chat_id` | 所属聊天；为空表示配置库中的来源配置 |
| `name` | 配置名称 |
| `api_type` | 接口类型 |
| `base_url` | 接口地址 |
| `api_key` | 鉴权信息 |
| `model` | 模型名称 |
| `default_parameters` | 默认请求参数，JSON |

### 用途关联 `chat_model_bindings`

| 字段 | 含义 |
| --- | --- |
| `chat_id` | 所属聊天 |
| `purpose` | `writing`、`state_update`、`round_summary`、`episode_summary` |
| `model_config_id` | 使用的聊天内模型配置 |

`chat_id + purpose` 唯一。同一聊天的多个用途可以使用同一份配置。第一版情节判定不使用模型。

## 7. 状态快照 `state_snapshots`

| 字段 | 含义 |
| --- | --- |
| `id` | 状态快照 ID |
| `character_id` | 所属聊天内角色 |
| `round_id` | 所属回合；初始状态为空 |
| `content` | 完整状态 JSON |
| `created_at` | 保存时间 |

创建聊天时，由角色 Schema 默认值生成初始快照。每个回合状态更新成功后保存对应快照。最新状态取最新回合已保存的状态，无回合状态时取初始快照。

物理表额外保存 `chat_id`，用于约束角色、回合与聊天的归属一致性。

## 8. 回合 `rounds`

| 字段 | 含义 |
| --- | --- |
| `id` | 回合 ID |
| `chat_id` | 所属聊天 |
| `round_no` | 聊天内回合序号，从 1 开始 |
| `user_input` | 用户确认的输入 |
| `ai_output` | 预设认可的完整 AI 输出，保留标签 |
| `summary` | 回合摘要；生成前为空 |
| `archive_step` | 当前归档步骤 |
| `archive_error` | 当前步骤错误；无错误时为空 |
| `episode_required` | 是否需要情节；尚未判定时为空 |
| `episode_start_round_id` | 判定选定的起始回合 |
| `episode_end_round_id` | 判定选定的截止回合 |
| `created_at` | 正文保存时间 |

`chat_id + round_no` 唯一。点击归档时创建记录，归档模块只读取 `ai_output` 的 `<content>` 正文。

归档步骤：

```text
state_update → round_summary → episode_decision → episode_summary → complete
```

无需情节时，判定后直接完成。每步结果保存成功后推进；失败留在当前步骤，仅重试该步。情节摘要重试使用已保存的判定范围。

## 9. 情节 `episodes`

| 字段 | 含义 |
| --- | --- |
| `id` | 情节 ID |
| `chat_id` | 所属聊天 |
| `start_round_id` | 覆盖的起始回合 |
| `end_round_id` | 覆盖的截止回合 |
| `title` | 情节标题，新生成时非空且不超过20字；旧情节默认为空字符串 |
| `summary` | 情节摘要原文 |
| `created_by_round_id` | 产生该情节的归档回合 |
| `created_at` | 保存时间 |

例如第 6 回合生成覆盖第 1—5 回合的情节，起止回合为 1 和 5，产生回合为 6。`created_by_round_id` 用于找到最新归档可编辑的情节。

情节保存成功后，其覆盖回合视为已归纳；处理边界由情节记录确定。

## 10. 创建与修改

创建聊天时复制角色、用户身份、定义、写作预设和模型配置，生成新 ID，并将关联字段指向聊天内副本。First Message 与状态配置随角色复制，初始状态由复制后的 Schema 生成。

不同聊天的数据独立。聊天面板仅操作最新回合；归档成功后只允许编辑摘要、状态和本次情节。数据修改页面可修改数据库任何部分。

数据修改入口支持在同一批中调整主键、归属、情节范围及其关联记录，整体提交或回滚。最终数据仍须满足引用、连续回合编号、归档结果齐全和情节覆盖一致性。历史状态按 JSON 原文保存，写入时检查统一世界字段，不执行角色 Schema 或自动重算其他结果；未修改的旧状态可继续读取。
