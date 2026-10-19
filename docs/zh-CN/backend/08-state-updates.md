# LoreNook 状态更新模块

[English](../../backend/08-state-updates.md) | [中文文档索引](../index.md)

更新日期：2026-10-20

## 1. 职责与实现

状态模块负责角色 Schema 执行、初始状态生成、最新状态读取与编辑，以及已保存回合的状态更新步骤。状态以完整 JSON 对象保存；更新使用模型生成的增量指令，不使用写作预设。

| 文件 | 职责 |
| --- | --- |
| `modules/state/world.py` | 统一世界字段检查及严格日期解析 |
| `modules/state/schema.py` | Python/Pydantic Schema、默认值、校验修正与 JSON 结果检查 |
| `modules/state/initial.py` | 可注入的初始状态工厂协议与结果检查 |
| `modules/state/patch.py` | add/replace/remove 修改指令执行 |
| `modules/state/prompts.py` | 内置系统提示词、上下文模板与一次性占位符替换 |
| `modules/state/update.py` | 原生模型请求、标签回复解析与状态更新 |
| `modules/state/service.py` | 最新状态查询、编辑范围及保存 |
| `modules/state/examples/basic.py` | 可编辑的 Schema 示例 |
| `workflows/state_update.py` | 读取输入、事务外生成、保存结果与步骤推进、错误重试 |
| `workflows/edit_state.py` | 事务外校验手动输入，核对版本后保存 |
| `shared/content.py` | 从完整 AI 输出中提取唯一 `<content>` 正文 |
| `api/state.py`、`schemas/state.py` | HTTP 入口及模块契约 |

复用状态快照、角色和回合表，无新增迁移或依赖。完整流程由[确认归档](12-archiving-workflow.md)串联；本模块的更新入口处理已经保存且位于 `state_update` 步骤的回合，成功后停在 `round_summary`。

## 2. Schema 源码

`characters.state_schema` 保存普通 Python 源码，必须导出一个名为 `Schema` 的 Pydantic `BaseModel` 子类。可定义嵌套模型、字段默认值、`Field(default_factory=...)`、字段校验器及模型校验器。Schema 是可执行的应用 Python 代码，不使用写作预设的 JavaScript 沙箱。

完整示例见 `modules/state/examples/basic.py`，将文件全文保存到角色 `state_schema` 即可使用。角色自定义字段可自行调整，但必须保留统一世界字段。简化示例：

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)
    世界: dict = Field(default_factory=lambda: {"日期": "2026-10-19", "星期": "星期一", "时间": "08:00", "地点": ""})
    好感度: int = 0

    @field_validator("好感度")
    @classmethod
    def clamp(cls, value):
        return max(0, min(100, value))
```

源码在每次执行时加载到独立临时模块，支持前向引用；执行结束移除模块注册，不跨聊天缓存可变模型实例。类型转换、额外字段处理及默认值校验由 Schema 的 Pydantic 配置决定，建议明确配置 `extra` 与 `validate_default`。结果以 JSON 模式和字段别名导出，并检查顶层为对象、值合法、不含非有限数值或无效 Unicode，断开可变引用。

空白源码不执行角色 Schema，但最终状态仍须满足统一世界字段。以空对象生成初始值时会失败，因此默认执行器不接受空白 Schema 创建角色或聊天。非空源码不作为 JSON 默认值解释。

统一世界字段是应用约束，由 `modules/state/world.py` 检查，不受角色 Schema 配置影响。顶级 `世界` 必须为对象，包含四个字符串字段，允许其他字段：

| 字段 | 约束 |
| --- | --- |
| `世界.日期` | 严格 `YYYY-MM-DD`，四位年份 0001—9999，并通过真实日历校验 |
| `世界.星期` | 仅 `星期一`、`星期二`、`星期三`、`星期四`、`星期五`、`星期六`、`星期日` |
| `世界.时间` | 严格 24 小时制 `HH:mm`，范围 `00:00`—`23:59` |
| `世界.地点` | 字符串，允许为空，不限制内容 |

日期和时间使用 ASCII 数字，不接受首尾空白、不补零、不猜测格式。星期只检查枚举，不与日期联动校验或自动修正。正常状态先执行角色 Schema，再检查统一约束；缺失或错误不会由应用自动补齐。自定义工厂和校验器的最终输出也必须通过统一检查。

已有数据不自动迁移，仍可读取；再次保存状态时必须符合新约定。数据修改入口仅对本次创建或更新的状态检查统一约束，不执行角色 Schema；未修改的旧快照不阻止其他记录的修改。

创建聊天默认使用 `python_initial_state`，以空对象触发 Schema 默认值生成、校验和修正；失败则回滚整个聊天创建。角色参考信息与更新规则继续独立保存在 `state_reference`、`state_update_rules`，不从 Schema 文件的其他常量读取。

保留 `create_app(initial_state_factory=...)` 的注入方式；校验执行器可通过 `create_app(..., state_validator=...)` 注入，协议为 `(source, content) -> JSON对象`。自定义执行器应保持纯计算，不执行模型、网络或文件 I/O。创建流程和后续更新使用同一种自定义 Schema 时，应同时提供相应工厂与校验器。

## 3. 状态更新输入

在一个读事务中收集：

- 当前聊天内角色、用户身份名称及状态配置。
- 最新且处于 `state_update` 的目标回合，其已确认用户输入和完整 AI 输出。
- 该角色最新已保存状态；首回合使用初始快照。若已有当前回合状态却仍处于本步骤，判定为存储冲突。
- `state_update` 用途绑定及其聊天内模型配置。
- 当前回合之前最近若干个已归档回合的摘要，按回合序号排列。

摘要查询使用 `Repository.summaries_before(chat_id, round_no, limit)`，不受情节覆盖范围影响，不包含当前回合。默认取最近 3 个，通过 `Settings.state_recent_summaries` 配置；非正数表示不提供摘要。摘要只帮助理解情境，更新依据仍为本回合对话。

AI 输出必须具有唯一、闭合且非空白的 `<content>` 区段。仅提取区段内部原文，不把报告、其他标签或模型原生思考内容提供给状态更新。数据库中的完整 AI 输出不被修改。

## 4. 模型生成与 Patch

状态模型负责把过去状态推进到本回合对话结束后的时间点，逐项检查变量，结算时间流逝、地点转移及其他变化。它在正文确认后运行，下一回合写作使用结算后的状态。用户不必逐项指定新值或报时；没有明确时长时，根据本回合行为和变量更新规则合理估计。计划、邀请和愿望不等于已经执行，角色台词和猜测不自动等于客观事实；不能凭空补出重要剧情或重复结算过去摘要。跨日时提示模型同步更新日期、星期和时间，程序仍只做既有格式及 Schema 校验，不自动校准星期。

完整提示词见 [`modules/state/prompts.py`](../../../backend/modules/state/prompts.py)。系统消息定义状态结算职责，单条 `user` 消息按以下章节装配：

1. **特别强调**：说明 `<user>`、主角和“我”对应的用户身份名称。
2. **上下文**：`<Reference_Info>` 中的 `state_reference`。
3. **过去状态**：完整旧状态 YAML。
4. **最近剧情回顾**：默认最近三回合摘要，仅用于理解情境。
5. **本回合对话**：用户输入原文与 AI 的 `<content>` 正文。
6. **变量更新规则**：`<Variable_Update_Rules>` 中的 `state_update_rules`。
7. **世界状态约定**：时间推进、行动是否发生及统一世界字段约束。
8. **输出格式**：结算结论及 JSON Patch 的标签结构。

模板仅替换自身占位符，不再次渲染插入材料中的模板语法。全部角色与身份定义、写作预设、情节汇总、完整历史和 Schema 源码不自动进入请求；角色专属依据由参考信息与更新规则提供，已有角色规则不会被自动改写。

读会话关闭后，根据绑定配置发送 `google_generate_content` 或 `deepseek_chat_completions` 原生请求。Google 固定一个候选和 `responseMimeType: text/plain`；DeepSeek 按系统、用户顺序发送相同提示词，固定非流式与 `response_format: {"type": "text"}`。其余默认参数由模型调用层补齐。返回必须恰好一个正常完成的候选（Google 为 `finishReason=STOP`，DeepSeek 为 `finish_reason=stop`），拒绝工具调用、显式拒绝和截断结果；DeepSeek 仅读取 `message.content`，原生思考仅保留在完整调用日志中。可见文本结构为：

```xml
<UpdateVariable>
<Analysis>本轮短暂交谈，时间推进两分钟；地点及其余变量不变。</Analysis>
<JSONPatch>
[{"op":"replace","path":"/世界/时间","value":"08:02"}]
</JSONPatch>
</UpdateVariable>
```

`Analysis` 提供时间、是否允许较大幅度变化及逐变量检查的简短结算结论，不要求详细推理、特定语言或字数；程序仅要求说明非空，不保存或返回它。三个标签必须各出现一次、正确闭合并按上述顺序排列，结构外仅允许空白；拒绝 Markdown 围栏、额外文本和缺失或重复标签。`JSONPatch` 内必须是完整且数值有限的 JSON 数组，无变化时为 `[]`，不接受旧的裸数组格式。忽略标记为 `thought` 的文本部分，拒绝工具调用，不从任意文本中搜索数组。

提示词要求以下划线开头的字段只读；这是模型指令，Patch 执行器不按字段名前缀拦截，硬性变量约束应由角色 Schema 实现。

只支持 `add`、`replace`、`remove`。路径采用 [JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901)，单条操作遵循 [JSON Patch](https://www.rfc-editor.org/rfc/rfc6902) 的对应语义：

- 字典 add 可增加或替换键，父路径必须存在；replace/remove 的目标必须存在。
- 数组 add 为插入，可在数组长度位置或 `-` 处追加；replace 为替换，remove 为删除。
- 数组下标是无前导零的 ASCII 非负整数，不接受负数、越界下标或将 `-` 用于替换/删除。
- `~0` 与 `~1` 分别表达键名中的 `~` 与 `/`；非法转义被拒绝。
- 空路径可整体 add/replace 为对象，不能删除根或改为非对象；`/` 则指向空字符串键。
- add/replace 必须提供 `value`，无关额外字段不影响操作。

操作按顺序应用到旧状态副本。单条结构无效、类型不合要求或路径执行失败时跳过该条，继续后续指令；返回 `skipped_operations` 表示跳过数量。这是本模块的容错规则，不采用整批遇错即中止的处理方式。

全部指令执行完后，对完整结果执行 Schema 校验与修正，再检查统一世界字段。将最终完整 JSON 与更新前状态比较，忽略对象键顺序，区分值类型并保留数组顺序。最终完全相同时返回 422，包括空数组、全部指令跳过、写回原值、操作相互抵消及 Schema 修正恢复原值；不保存快照，停留在 `state_update` 并记录错误，重试仍执行本步骤。提示词明确该失败规则，仅允许基于事实和变量规则更新，禁止为通过检查编造时间推进或其他变化。整体解析、模型或最终校验失败同样不保存新快照。

## 5. 保存、重试与并发

生成与 Schema 校验均在数据库事务外进行。保存前开启写事务，重新读取当前回合步骤及全部输入，与本次使用的输入快照比较。正文、旧状态、Schema、提示词资料、摘要或模型配置发生变化时，返回 409，不保存过期结果；整数与布尔值等 JSON 类型变化也会被识别。

输入未变化时，`ArchiveRepository.save_state` 在同一事务内保存本回合完整状态并推进到 `round_summary`，同时清空旧错误。重复或过期调用在模型请求之前被步骤检查拒绝；并发完成的结果也会在保存时被重新核对。保存或提交失败时事务整体回滚，不留下只保存快照而未推进的结果。

模型、解析、正文或校验失败时，重新核对输入和步骤，在独立短写事务内保存当前步骤错误，再返回原错误。若输入或步骤已变化，不覆盖新的结果或错误。失败后仍停在 `state_update`，重试只重新执行本步骤；已经保存的回合正文保留。

## 6. 读取与手动编辑

`GET /api/chats/{chat_id}/state` 返回最新状态及其 ID、角色、回合关联和保存时间。最新状态仍按回合序号判断，尚无回合状态时返回初始快照；归档中已保存的状态也可读取。

`PUT /api/chats/{chat_id}/state` 接收 `{"content": {...}}`，整体替换当前可编辑状态。尚无回合时允许编辑初始快照；有回合时只允许编辑最新已完成归档回合对应的状态，归档过程中禁止手动编辑。

Schema 校验修正与统一世界字段检查通过后，重新核对 Schema、状态内容和回合范围，再更新原快照，保留其 ID 和回合关联。类型变化会实际写入，例如数字 `1` 改成布尔值 `true`。失败保持原文，不自动重算摘要或情节；新的状态立即成为下一次定义解析与写作使用的值。

## 7. HTTP 更新入口与错误

`POST /api/chats/{chat_id}/rounds/{round_id}/state-update` 从数据库读取本回合正文和配置，不需要客户端提供替代状态或模型响应。成功返回：

```json
{
  "chat_id": "聊天ID",
  "round_id": "回合ID",
  "archive_step": "round_summary",
  "state": {"id": "状态ID", "character_id": "角色ID", "round_id": "回合ID", "content": {}, "created_at": "UTC时间"},
  "skipped_operations": 0
}
```

- 404：聊天或回合不存在，或回合不属于本聊天。
- 409：非最新回合、步骤不符、缺少资料/上一状态/模型绑定、输入过期，或手动编辑范围不符。
- 422：字段、正文、Schema、整体 Patch 响应或模型配置无效。
- 502/504：沿用模型调用的上游错误与超时映射，不回显模型 Key 和上游错误正文。

## 8. 验证

另覆盖上下文章节顺序、插入材料的模板语法原样保留、标签结构、非有限数值及异常回复拒绝。自动测试不判定真实模型的剧情结算质量。

依赖检查通过。覆盖 Schema 默认值、前向引用、嵌套结构、修正规则、JSON 类型与模块清理；Patch 的字典/数组/转义/根路径与逐条跳过；创建初始化、状态读取、手动编辑和范围限制；正文隔离、最近摘要与情节覆盖、更新保存与步骤推进、失败重试与清错、跨聊天拒绝、事务回滚及过期输入检查。模型调用全部使用模拟传输。
