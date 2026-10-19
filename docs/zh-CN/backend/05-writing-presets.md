# LoreNook 写作预设模块

[English](../../backend/05-writing-presets.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 职责与实现

写作预设是保存在 `writing_presets.source` 中的一份 JavaScript 源码，负责把结构化材料转换为目标接口请求，并从接口 JSON 响应中提取、校验完整 AI 输出。预设不执行模型调用，不访问数据库，不控制归档或前端展示。

| 文件 | 职责 |
| --- | --- |
| `schemas/presets.py` | 预设管理、写作材料、请求与解析结果的数据契约 |
| `modules/presets/service.py` | 来源库及聊天内预设的增删改查与归属检查 |
| `modules/presets/runtime.py` | 独立 QuickJS 上下文、执行限制及结果校验 |
| `modules/presets/examples/google_tool.js` | 可编辑的 Google 工具输出示例 |
| `workflows/writing_materials.py`、`preview_writing.py` | 与写作生成共用快照收集和材料解析，预览在事务外包装 |
| `api/presets.py` | 管理、单独试运行及聊天预览接口 |

复用现有表与聊天副本复制逻辑，无新增数据库迁移。新增依赖为 `quickjs-ng` 与 `PyYAML`，验证版本见依赖锁定文件。执行 API 参考 [QuickJS Python 封装](https://github.com/genotrance/quickjs-ng)。

## 2. 预设源码与材料

源码使用普通 JavaScript，定义两个同步入口，不使用 `export`、`import` 或 CommonJS：

```javascript
function build(materials) {
    return {
        api_type: 'example',
        body: {messages: [{role: 'user', content: materials.user_input}]}
    };
}

function parse(response) {
    if (typeof response.text !== 'string') throw new Error('缺少回复文本');
    return response.text;
}
```

`build` 的输入为：

| 字段 | 内容 |
| --- | --- |
| `character_name`、`user_identity_name` | 聊天内角色与用户身份名称 |
| `character_definitions`、`user_definitions` | 各自按序组织的已启用定义，条目为 `id`、`order`、解析后的 `content` |
| `first_message` | 第 0 楼原文，始终提供 |
| `history` | `total_rounds`、X/Y、按时间排列的 `items` 和 `uses_compressed_history`，见[记忆装配](04-memory-assembly.md) |
| `user_input` | 当前用户输入，独立于历史 |
| `state` | 当前最新状态的 JSON 对象 |
| `state_yaml` | 由同一份 `state` 生成的 YAML 文本，保留中文、字段顺序及 JSON 值类型 |

`state_yaml` 和 `history.uses_compressed_history` 为应用计算的只读派生字段。HTTP 单独试运行时不填写这两个字段，不能提交与状态或历史矛盾的替代值。

`build` 必须返回恰好包含 `api_type` 和 `body` 的对象，前者为非空白字符串，后者为 JSON 对象。请求体内部允许任意目标接口字段；通用运行时不限定消息角色、工具参数或标签。预设自行编排内容，例如把用户输入并入 `model` 消息、把用户消息换成固定填充。

`parse` 直接接收模型接口的完整 JSON 对象，返回非空白字符串。模块对外封装为 `{"ai_output": "..."}`。通用运行时只校验返回类型，具体工具选择、候选选择、标签提取和格式检查由预设源码负责；失败时抛出 JavaScript `Error`。不修剪成功字符串，不自动剥离标签。

材料中的数据库文本在进入预设之前保留原文；定义仅进行已约定的模板解析，状态额外提供 YAML 表示。预设允许改变本次请求或接收结果，但不会改写数据库原文。

## 3. 执行环境

每次 `build` 或 `parse` 创建全新的 QuickJS Context，源码重新执行，两个入口都必须存在；不保留前一次调用的全局变量或闭包。完整写作流程为一次请求保留同一份源码快照，分别执行发送前包装和接收后解析。

环境仅有 JavaScript 内置能力，不注册 Python 回调、网络、文件、数据库或模型接口，不提供 `fetch`、`require`、`process`、`std`、`os`。入口必须同步返回，不支持 Promise 或异步任务调度。

默认限制：

| 项目 | 限制 |
| --- | --- |
| 源码求值、入口执行 | 每次 QuickJS 执行最多 0.5 秒 CPU 时间 |
| Context 内存 | 32 MiB |
| JavaScript 栈 | 512 KiB |
| 源码、序列化输入、序列化输出 | 各不超过 2,000,000 字符；输入按 JSON ASCII 转义后的长度计数 |

仅通过 JSON 交换输入输出，阻断输入对象与数据库、调用方可变对象之间的引用。循环引用、`undefined`、函数、Symbol、BigInt、NaN、Infinity 等不能作为成功结果。未设置的可选请求字段直接省略，不填写 `undefined`。输入及输出整数必须处于 JavaScript 安全整数范围；更大的整数使用字符串，避免转换时静默改变数值。

源码、类型、运行、资源限制或结果校验失败统一成为预设执行错误，不返回部分结果，也不保存待确认回合。

## 4. 管理与试运行接口

以下两个集合提供同一套操作：

- `/api/writing-presets`：来源预设库。
- `/api/chats/{chat_id}/writing-presets`：当前聊天的独立预设。

| 方法与后缀 | 行为 |
| --- | --- |
| `GET` 集合 | 返回该归属下的全部预设 |
| `POST` 集合 | 提交 `name`、`source`，创建并返回 201 |
| `GET /{preset_id}` | 返回 ID、归属、名称、完整源码和创建时间 |
| `PATCH /{preset_id}` | 按显式字段修改名称或源码，保留 ID |
| `DELETE /{preset_id}` | 删除，成功返回 204 |
| `POST /{preset_id}/build` | 请求体为写作材料；返回 `{api_type, body}` |
| `POST /{preset_id}/parse` | 请求体为 `{"response": {...}}`；返回 `{ai_output}` |

名称必须非空白。源码可为空或尚未完成；保存时不执行预设，试运行时才报告错误。PATCH 省略字段保留原值，不接受显式 `null`、ID、归属或未知字段。

来源、当前聊天和其他聊天之间不能越界读取、编辑、删除或试运行。复制后的源码和 ID 相互独立，后续修改或删除来源不影响聊天副本。删除聊天当前选用的预设前，应通过聊天 PATCH 切换或清空 `writing_preset_id`，否则返回 409。

单独试运行使用请求中提供的材料或响应，不代表真实发送，也不改变聊天、原文或归档步骤。数据库会话关闭后才执行预设。

## 5. 聊天请求预览

`POST /api/chats/{chat_id}/writing-preview` 接收 `{"user_input": "当前输入"}`，使用当前聊天选中的预设：

1. 在一个读事务中检查当前回合已归档完成、聊天已选择预设。
2. 读取预设源码、聊天内资料、定义、最新状态及按当前 X/Y 装配的历史，转换为独立对象。
3. 关闭数据库会话。
4. 使用这份状态解析已启用定义；任一失败时停止。
5. 计算状态 YAML，执行 `build` 并校验结果。
6. 返回 `chat_id`、`preset_id`、`state_snapshot_id` 和 `request: {api_type, body}`。

预览不要求已绑定模型，不执行模型调用，不补充模型默认参数，也不检查目标接口与模型配置的兼容性；完整发送由[写作流程](07-writing-workflow.md)串联[模型调用](06-model-calls.md)。预览入口不会创建正式回合。

## 6. 工具输出示例

`modules/presets/examples/google_tool.js` 是可直接保存为预设 `source` 的完整示例。文件顶部 `fixed` 对象集中放置可手动修改的固定内容；源码随安装包分发，不自动写入用户数据库。

示例行为：

- 以 `google_generate_content` 作为目标接口标识，构造原生请求体。字段形状依据 [Google GenerateContent API](https://ai.google.dev/api/generate-content)，实际发送由调用模块执行。
- 没有采用摘要或情节时包含 First Message；开始采用压缩历史后不再包含。
- 历史情节和回合摘要进入第一段历史文本；最近回合的用户输入加前后缀放入 `model` 消息，`user` 消息使用固定填充；上一次 AI 输出与下一次用户输入合并。
- 重发完整 AI 输出，保留 `<report_nya~>` 与 `<content>`；定义进入系统指令，状态以 YAML 进入单独消息。
- 声明 `game_content(content: string)`，使用 `ANY` 并限定该工具，要求模型把回复交到工具参数中。工具只承载文本，不实际执行函数，也不追加第二次模型调用。
- 解析时要求恰好一个候选且 `finishReason=STOP`，并且恰好一个 `game_content` 调用；从 `args.content` 提取两个必需标签。
- 两个标签各出现一次、正确闭合、内容非空白，不能嵌套或交叉。保留各区段原文和标签，按原出现顺序以换行连接；区段外文本被丢弃。

这些工具名、参数、标签和解析限制仅属于示例，可在源码中修改，不是其他预设必须遵守的全局格式。

## 7. 错误与验证

- 404：聊天或预设不存在，或预设不属于当前集合。
- 409：当前归档未完成、尚未选用预设、缺少聊天资料或状态、记忆范围冲突，或试图删除当前选用预设。
- 422：请求结构不合法、定义模板失败，或预设编译、执行和结果校验失败。

预设错误响应为 `{"detail": {"stage": "build或parse", "message": "错误说明"}}`；说明最多保留 2,000 字符。定义模板失败仍返回定义 ID 与可定位的行号。数据库约束冲突沿用现有错误映射，不回显 SQL 参数。

覆盖源码管理、PATCH、跨归属拒绝、副本独立、当前预设删除保护、OpenAPI 路径契约、同步执行与类型校验、环境隔离、CPU/内存/栈/长度限制、JSON 数值边界、草案消息重排、YAML、First Message 条件、工具回复与标签异常、当前状态读取、归档门槛及失败不创建回合。
