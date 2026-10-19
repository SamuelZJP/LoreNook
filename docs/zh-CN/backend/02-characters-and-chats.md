# LoreNook 角色与聊天模块

[English](../../backend/02-characters-and-chats.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 职责

本模块管理来源角色、用户身份，以及聊天内独立副本；聊天创建 Workflow 负责在一个事务内复制资料、重建配置关联并保存初始状态。

| 位置 | 职责 |
| --- | --- |
| `modules/characters/service.py` | 角色资料、First Message、状态配置及定义列表的管理与复制 |
| `modules/users/service.py` | 用户身份资料及定义列表的管理与复制 |
| `modules/definitions/storage.py` | 按归属读取、整体替换定义；逐条管理与模板解析见定义模块 |
| `modules/chats/service.py` | 聊天列表、详情、配置与删除 |
| `modules/state/initial.py` | 初始状态生成协议及 JSON 结果检查 |
| `workflows/create_chat.py` | 创建事务、复制与关联重建 |
| `api/catalog.py`、`api/chats.py` | HTTP 入口 |

业务模块接收 Repository，参与调用方事务，不自行提交。所有 HTTP 数据库操作在同步入口内完成，事务与 Session 均在同一线程打开并关闭。

## 2. 来源与副本

`chat_id` 为空的角色、身份、预设和模型配置属于来源库。创建聊天只接受来源 ID，不能使用其他聊天的副本作为来源。

创建后所有对象和定义均生成新 ID、重建归属，记录新的创建时间。复制保留原文、顺序、启用标记、模板标记、First Message、状态配置、模型参数与鉴权信息。定义暂不解析，预设暂不执行。

同一来源在不同聊天中形成不同副本。修改或删除来源不影响已有聊天；聊天内修改只作用于当前副本。来源库接口不会读取、编辑或删除聊天内的角色和身份。

First Message 存在聊天内角色的 `first_message` 中，作为第 0 楼材料，不产生 `rounds` 记录。创建完成时只有初始状态快照，尚无正式回合。

## 3. 资料接口

所有接口以 `/api` 为前缀。

| 路径 | 方法 | 行为 |
| --- | --- | --- |
| `/characters` | GET、POST | 列出或创建来源角色 |
| `/characters/{id}` | GET、PATCH、DELETE | 读取、编辑或删除来源角色 |
| `/user-identities` | GET、POST | 列出或创建来源用户身份 |
| `/user-identities/{id}` | GET、PATCH、DELETE | 读取、编辑或删除来源用户身份 |
| `/chats/{id}/character` | GET、PATCH | 读取或编辑聊天内角色 |
| `/chats/{id}/user-identity` | GET、PATCH | 读取或编辑聊天内身份 |

角色写入字段为 `name`、`avatar`、`description`、`first_message`、`state_schema`、`state_reference`、`state_update_rules` 和 `definitions`；身份写入字段为 `name`、`avatar`、`description` 和 `definitions`。创建角色要求非空白名称及能够生成合格初始状态的 `state_schema`，创建身份只要求非空白名称；其余文本默认空字符串，头像默认空值，定义默认空列表。

定义列表每项包含 `order`、`enabled`、`has_template`、`content`，不允许指定 ID 或归属字段。读取返回 ID、实际归属，并按顺序及 ID 排序。

PATCH 只修改显式提供的字段。省略 `definitions` 保留原列表，传入列表时整体替换、生成新定义 ID，空列表表示清空。需要保留 ID 的逐条编辑与排序使用[定义模块接口](03-definition-rendering.md)。显式 `avatar: null` 表示清空头像；非空字段不接受 `null`。未知字段、负顺序及错误类型返回 422。

创建角色及修改 `state_schema` 时，执行默认值生成并检查统一世界字段，失败返回 422，修改整体回滚；仅修改其他资料时不重新校验旧 Schema。编辑聊天内 First Message 或状态配置不重新生成已有状态、摘要或情节。状态 Schema 的执行和状态编辑校验属于状态模块。

## 4. 创建聊天

`POST /api/chats` 接收：

| 字段 | 含义 |
| --- | --- |
| `title` | 非空白聊天名称，必填 |
| `character_id`、`user_identity_id` | 来源角色与身份 ID，必填 |
| `writing_preset_ids` | 需要复制的来源预设列表，默认空列表 |
| `writing_preset_id` | 当前选用的来源预设，可为空；无需重复列入上述列表 |
| `model_config_ids` | 需要复制的来源模型配置列表，默认空列表 |
| `model_bindings` | 用途到来源模型配置 ID 的映射，引用配置会自动加入复制集合 |
| `recent_rounds`、`min_summaries` | 非负整数 X、Y，默认 5、6 |

模型用途限定为 `writing`、`state_update`、`round_summary`、`episode_summary`。预设与模型列表中的重复来源只复制一次；多个用途引用同一来源模型时，绑定同一份聊天内配置。

创建顺序：

1. 开启写事务并创建聊天。
2. 复制来源角色、身份及其全部定义。
3. 复制选定预设，映射新 ID 并设置当前选择。
4. 复制模型配置，映射新 ID 并创建用途关联。
5. 使用复制后的角色状态配置生成初始状态，保存 `round_id` 为空的快照。
6. 提交全部记录并返回聊天详情。

缺失或越界的来源、状态生成失败及数据库保存失败均回滚整个创建事务。不存在只保存了部分副本的正常创建结果。

允许先创建尚未选择预设、尚未绑定模型的聊天。配置管理接口见[写作预设](05-writing-presets.md)与[模型调用](06-model-calls.md)；后续写作及归档流程负责检查所需配置是否齐全。

### 初始状态接入

`InitialStateFactory` 是同步纯计算接口：输入角色的 Schema 源码，输出完成默认值填充、校验与修正的 JSON 对象。可通过 `create_app(..., initial_state_factory=...)` 注入实现，直接调用创建 Workflow 时也可传入。

默认执行器使用 Python/Pydantic 源码中导出的 `Schema` 生成初始状态；空白源码无法生成必需的世界字段，因此初始化失败。源码、默认值或校验失败时返回 422 并回滚。非空源码不作为 JSON 默认值，不通过创建请求体直接指定初始状态。具体表达方式和可注入校验器见[状态模块](08-state-updates.md)。

保存前额外检查顶层为对象、嵌套值是 JSON 值且不含 NaN 或无穷值，并与执行器保留的可变对象断开引用。执行器不应执行模型调用、网络或文件 I/O，保持创建事务简短。

## 5. 聊天读取与配置

| 路径 | 方法 | 行为 |
| --- | --- | --- |
| `/chats` | GET | 按创建时间倒序返回聊天基础信息 |
| `/chats` | POST | 创建完整聊天副本，成功返回 201 |
| `/chats/{id}` | GET | 返回聊天、角色、身份、定义、预设、模型配置、用途关联与最新状态 |
| `/chats/{id}` | PATCH | 修改标题、X、Y、预设选择或模型用途关联 |
| `/chats/{id}` | DELETE | 级联删除该聊天及其副本，成功返回 204 |

PATCH 中的预设与模型 ID 必须是当前聊天内的 ID，不接受来源或其他聊天的配置。`writing_preset_id: null` 清空选择。显式提供 `model_bindings` 时整体替换用途映射，空对象表示清空；未引用的聊天内配置仍保留。

聊天详情返回模型配置的 `has_api_key`，不返回 `api_key`。复制时仍保存鉴权原文，供后续模型调用读取。最新状态按回合序号选择，尚无回合时返回初始状态。

删除聊天不影响来源库和其他聊天。删除来源角色或身份时，同时删除其来源定义，不修改已复制的定义。

## 6. 错误与验证

- 404：记录不存在，或 ID 不属于当前请求的来源库/聊天范围。
- 409：已有聊天缺少必要资料或状态，或数据库关联、唯一性约束冲突。
- 422：请求字段不合法，或状态初始化无法完成。

数据库约束错误响应不回显 SQL 参数，避免包含模型鉴权信息。未知程序异常仍按服务端错误处理，写事务会回滚。

测试覆盖资料增删改查、PATCH 省略与空值行为、请求类型校验、HTTP 错误映射、来源与副本范围、完整复制与共享模型去重、多聊天隔离、来源删除后的独立性、创建中途失败回滚、状态生成接入，以及配置的聊天归属检查。
