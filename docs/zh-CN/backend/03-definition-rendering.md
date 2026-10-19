# LoreNook 定义管理与模板解析

[English](../../backend/03-definition-rendering.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 职责与实现

定义模块管理角色定义与用户身份定义，按照保存的顺序提供原文，或结合最新状态解析模板。解析结果只用于当前请求，不覆盖原文。

| 文件 | 职责 |
| --- | --- |
| `schemas/definitions.py` | 编辑、排序和解析结果的数据结构 |
| `modules/definitions/service.py` | 限定归属的逐条管理与整组排序 |
| `modules/definitions/storage.py` | 资料创建和复制时的定义列表保存 |
| `modules/definitions/renderer.py` | Jinja 模板解析，供预览和写作流程调用 |
| `workflows/resolve_definitions.py` | 读取聊天的一致快照，在数据库事务外解析 |
| `api/definitions.py` | 来源库及聊天内定义接口 |

模块不组织模型请求、不执行模型调用。写作流程在定义全部解析成功后，才进入预设包装。

## 2. 定义管理

每条定义包含 `order`、`enabled`、`has_template`、`content`，以及由所属资料确定的 ID 与归属。

- `order` 为非负整数，默认 0；按 `order`、ID 排序，允许相同顺序值。
- `enabled` 默认开启，关闭的条目不参与解析，也不提供给写作预设。
- `has_template` 默认关闭，关闭时不检查或解析 Jinja 语法，原文直接提供。
- `content` 保存原文，可以为空；模板解析为空字符串也属于有效结果。

逐条编辑、启用切换与排序均保留定义 ID。创建和编辑时不预先执行模板，允许保存尚在编辑中的模板；参与请求时再报告解析错误。

来源角色、来源身份、聊天内角色和聊天内身份分别限定归属，不能通过定义 ID 转移或越界操作。聊天复制仍生成新定义 ID。

### HTTP 接口

以下四个集合路径使用相同操作：

| 集合路径 | 归属 |
| --- | --- |
| `/api/characters/{id}/definitions` | 来源角色 |
| `/api/user-identities/{id}/definitions` | 来源用户身份 |
| `/api/chats/{id}/character/definitions` | 当前聊天角色副本 |
| `/api/chats/{id}/user-identity/definitions` | 当前聊天身份副本 |

| 方法与后缀 | 行为 |
| --- | --- |
| `GET` 集合 | 按序返回所有定义，包含禁用项 |
| `POST` 集合 | 创建定义，返回 201 |
| `GET /{definition_id}` | 读取单条定义 |
| `PATCH /{definition_id}` | 只修改显式提供的业务字段 |
| `DELETE /{definition_id}` | 删除单条定义，返回 204 |
| `PUT /reorder` | 使用完整 ID 列表重排本归属的全部定义 |

排序请求示例：

```json
{"definition_ids": ["第二条定义的ID", "第一条定义的ID"]}
```

排序列表必须包含该归属下的全部定义，每条恰好一次，包括禁用项。成功后顺序连续重置为 0、1、2……。重复 ID 返回 422；遗漏、额外或其他归属的 ID 返回 409，原顺序保持不变。空归属可提交空列表。

PATCH 省略字段表示保留，不接受显式 `null`；不得指定 ID 或归属字段。既有资料接口中的 `definitions` 整体替换仍可使用，但会生成新 ID；需要保留 ID 时使用本模块逐条管理接口。

## 3. 模板执行

使用 Jinja2 的 `ImmutableSandboxedEnvironment` 和 `StrictUndefined`。配置与行为参照 [Jinja 沙箱文档](https://jinja.palletsprojects.com/en/stable/sandbox/)和 [Jinja API 文档](https://jinja.palletsprojects.com/en/stable/api/)。

业务上下文仅包含 `state`，其值是当前最新状态的完整 JSON 副本。保留 Jinja 默认辅助函数、过滤器和测试，不向模板传入 Repository、Session、配置或其他应用对象。

```jinja
当前日期：{{ state["世界"]["日期"] }}
{% if state["年龄"] > 10 %}采用较成熟的描述。{% else %}采用年幼的描述。{% endif %}
{% for name in state["在场人物"] %}{{ name }}{% if not loop.last %}、{% endif %}{% endfor %}
```

JSON 嵌套访问建议使用方括号。字典方括号查找缺失键时直接产生未定义值，不回退到字典方法；例如不存在的 `state["items"]` 不会被误当作 `dict.items`。

未处理的缺失变量、缺失嵌套字段、语法错误和运行错误均使该请求失败。模板可显式处理可选字段：

```jinja
{{ state["可选字段"] | default("未设置") }}
{% if state["可选字段"] is defined %}{{ state["可选字段"] }}{% endif %}
```

不进行 HTML 转义，保留 `<content>` 等文本标签。模板保留尾部换行，Jinja 将模板中的行结束符规范为 LF；未标记模板的条目按原文完整保留，包括 CRLF 和模板符号。

沙箱禁止修改 JSON 字典、列表及访问 Python 内部属性。未配置外部模板加载器，不支持从文件加载 `include`、`import` 或继承模板。单条模板使用流式输出，超过 1,000,000 字符时失败，不截断为成功结果。

每次解析创建新的状态副本，不保存渲染结果。所有条目使用同一份状态副本，修改状态的方法调用由不可变沙箱阻止。

## 4. 聊天解析入口

`POST /api/chats/{id}/definitions/resolve` 使用数据库中的最新状态解析定义，不接收客户端指定的替代状态。解析预览和写作流程复用相同的 Renderer。

处理流程：

1. 在一个读事务中取得聊天内角色、身份、定义和最新状态。
2. 记录状态快照 ID，将定义转换为独立的数据对象。
3. 关闭数据库会话。
4. 过滤禁用项，角色与身份定义分别按顺序解析。
5. 全部成功后一次性返回两组结果。

返回字段：

| 字段 | 含义 |
| --- | --- |
| `chat_id` | 当前聊天 |
| `state_snapshot_id` | 本次解析所使用的状态快照 |
| `character_definitions` | 按序组织的角色定义，每项为 ID、顺序、解析文本 |
| `user_definitions` | 按序组织的身份定义，每项为 ID、顺序、解析文本 |

最新状态按照回合序号选择，首回合前使用初始快照。每次请求重新读取，因此状态或定义修改后，下一次解析立即使用新值。

解析预览可在归档过程中使用已经保存的最新状态。写作入口仍须检查上一回合已归档完成；该检查由写作 Workflow 负责。

## 5. 错误与事务

- 404：资料、定义或聊天不存在，或定义不属于请求限定的归属。
- 409：整组排序列表与现有定义不匹配，或聊天缺少必要资料、状态快照。
- 422：请求参数无效，或模板编译、执行失败。

模板错误响应包含失败定义的 ID、错误信息和可定位时的行号：

```json
{
  "detail": {
    "definition_id": "失败定义的ID",
    "message": "缺失字段或模板错误说明",
    "line": 2
  }
}
```

任意一条失败时不返回部分成功结果，不继续处理后续条目。渲染不持有数据库事务、不写入数据库；定义原文、状态快照和归档进度均保持原值。编辑和排序由单个写事务提交，失败时整体回滚。

## 6. 验证

测试覆盖四种归属下的接口、越界拒绝、PATCH 语义、ID 保留、整组排序及失败回滚；同时验证嵌套 JSON、条件和循环、禁用项跳过、普通原文保留、未定义变量、错误定位、沙箱限制、输出长度限制、最新状态读取，以及任一组失败时不返回部分结果。
