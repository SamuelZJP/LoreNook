# LoreNook 模型调用模块

[English](../../backend/06-model-calls.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 职责与实现

本模块管理来源库及聊天内模型配置，读取聊天用途绑定，并执行一次模型 HTTP 请求。调用前核对接口兼容性、合并默认参数、构造地址与鉴权；成功后返回完整 JSON 对象供写作预设或归档生成模块解析。

| 文件 | 职责 |
| --- | --- |
| `schemas/models.py` | 配置编辑、公开读取、内部连接快照与响应契约 |
| `modules/models/service.py` | 归属检查、配置管理、按用途读取连接快照 |
| `llm/parameters.py` | 默认参数的递归补齐 |
| `llm/google.py` | Google GenerateContent 地址、模型与鉴权适配 |
| `llm/client.py` | HTTPX 调用、超时、响应限制与错误分类 |
| `api/models.py` | 配置管理与单次调用接口 |

当前支持 `google_generate_content` 和 `deepseek_chat_completions`。其他接口需增加独立适配器；不把不兼容的预设隐式转换成当前接口。复用现有数据库表，无新增迁移。

本模块不解析预设、不提取工具参数、不执行工具、不保存回合或推进归档。聊天请求预览只包装请求；完整的收集材料、调用、回复解析由[写作 Workflow](07-writing-workflow.md)串联。

## 2. 配置与归属

配置字段沿用 `model_configs`：`name`、`api_type`、`base_url`、`api_key`、`model`、`default_parameters`。新增时除 Key 与默认参数外均必填，名称、接口类型、模型名称必须非空白。Key 默认空字符串，默认参数默认为空对象。

- `base_url` 是 HTTP(S) 接口根地址，包含所需版本路径；例如 `https://generativelanguage.googleapis.com/v1beta`。不包含模型路径、操作名、URL 鉴权、查询参数或片段。
- 允许保存尚未接入的非空 `api_type`，便于编辑配置；调用前会明确拒绝尚无适配器的类型。
- 默认参数采用接口原生请求体字段组织；Google 生成参数放在 `generationConfig` 下，例如 `{"generationConfig": {"temperature": 0.8}}`。
- API Key 存入独立字段，内部使用 `SecretStr` 传递，公开配置仅返回 `has_api_key`。PATCH 省略保留原值，空字符串清空，不接受 `null`。

来源、聊天内副本和其他聊天之间不能越界操作。创建聊天仍按原有流程复制模型配置并重建用途绑定；多个用途引用同一来源时只复制一次。修改或删除来源不影响副本，编辑一个聊天不影响另一个聊天。

删除聊天内模型配置时，数据库级联删除引用它的用途关联；未绑定该用途时，后续调用方会得到明确的缺失配置错误。

## 3. 查询与事务

`ModelService(repository, chat_id).connection(config_id)` 返回独立的内部连接对象，包含接口类型、地址、Key、模型名与默认参数，不包含 ORM 实例。

`for_purpose(purpose)` 通过 `Repository.model_binding` 读取 `chat_id + purpose` 的关联，再核对模型属于当前聊天。用途包括 `writing`、`state_update`、`round_summary`、`episode_summary`。此入口只用于聊天，缺失绑定返回冲突错误。

调用方在一个短读事务中取得配置快照，关闭数据库会话后执行 `ModelClient.invoke(connection, built_request)`。网络期间不持有数据库事务；调用期间对配置的编辑在下一次读取生效。配置编辑仍由单个写事务提交，模块不自行提交。

## 4. 参数合并与接口检查

调用请求沿用写作预设的 `{api_type, body}` 契约。请求的 `api_type` 必须与配置完全一致，且已存在适配器；任一不满足时不发送网络请求。

默认参数作为基础，递归补齐预设未提供的字段：

- 两侧同为对象时按键递归合并。
- 显式标量、数组、`false`、`0`、空字符串和 `null` 优先，数组整体替换。
- 显式空对象仍可从默认对象补齐缺失键；不等同于清空整个对象。
- 所有结果使用副本，原配置、预设请求及数据库原文不变。

例：

```text
默认参数：{"generationConfig": {"temperature": 0.8, "topP": 0.9}}
预设请求：{"generationConfig": {"temperature": 1, "seed": null}, "contents": [...]}
合并结果：{"generationConfig": {"temperature": 1, "topP": 0.9, "seed": null}, "contents": [...]}
```

合并后必须可序列化为有效 JSON，不接受 NaN、Infinity。除接口适配必需的结构检查外，不维护一份模型能力或参数白名单；模型是否支持某参数由目标接口验证并返回错误。

## 5. Google GenerateContent

适配依据 [Google GenerateContent REST 文档](https://ai.google.dev/api/generate-content)：

- POST 到 `{base_url}/models/{model}:generateContent`，不使用流式方法。
- 模型默认取配置的 `model`；若合并后的请求体显式包含 `model`，优先取该值，并从实际 HTTP 请求体中移除。名称允许 `models/` 前缀，去除前缀后仅允许字母、数字、点、下划线和连字符，不能改变请求路径层级。
- 非空 Key 放入 `x-goog-api-key` 请求头，不放进 URL；空 Key 不发送此头，允许使用无需此头的自定义兼容服务。Key 必须为无空格、无换行的可见 ASCII 字符。
- 请求使用 `Content-Type: application/json`，必须有非空 `contents` 数组；其余原生字段按合并结果发送。
- 返回整个响应对象，不筛选候选、区段、工具参数或用量字段。`promptFeedback` 等对象也保留，由预设决定其是否可接受；顶层 `error` 作为接口错误处理。

此层不会执行工具，也不会追加第二次模型请求。

### DeepSeek Chat Completions

`llm/deepseek.py` 实现接口类型 `deepseek_chat_completions`，原生契约见 [DeepSeek API](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/)。

- POST 到 `{base_url}/chat/completions`。配置地址包含所需版本路径，例如 `http://gateway:3000/v1`；客户端不猜测或重试其他地址。
- 请求体保留 `model`，默认取配置模型，显式请求值优先；要求非空 `messages` 数组。网关可以按模型名路由，LoreNook 仍按 `api_type` 构造原生请求，不根据名称猜测协议。
- 非空 Key 使用 `Authorization: Bearer ...`，沿用现有地址与 Key 格式检查。空 Key 不发送鉴权头。
- 缺省补入 `stream=false`，拒绝开启流式。完整返回全部 `choices`、工具调用、`reasoning_content`、用量和其他字段；顶层 `error` 沿用上游错误分类。
- 默认参数采用顶层原生字段，例如 `{"temperature": 0.2, "max_tokens": 4096, "stream": false, "thinking": {"type": "disabled"}}`，不混入 Google 参数。具体参数支持由上游模型及网关确认。

状态更新、回合摘要、情节摘要共用 `llm/generation.py` 构建原生请求，`llm/text.py` 提取可见文本。DeepSeek 按系统、用户顺序发送提示词，固定非流式；状态更新和回合摘要使用 `response_format: {"type": "text"}`，情节摘要使用 `{"type":"json_object"}`；Google 分别使用 `text/plain` 和 `application/json`。要求恰好一个正常完成的 assistant 文本回复，拒绝工具调用、显式拒绝及截断结果；情节生成器随后解析并校验标题与摘要对象。`reasoning_content` 不进入状态或摘要，完整原始回复仍记录。

三个归档用途可以共享同一份聊天内 DeepSeek 配置；写作用途可以使用另一份配置。来源与聊天副本独立管理，修改来源不会自动同步已有聊天。日志模型名读取适配后请求体中的 `model`，Google 则读取适配后地址中的模型名；不保存鉴权头或 URL。

## 6. HTTP 执行

每个应用生命周期创建一个同步 `ModelClient`，退出时关闭 HTTPX Client。同步 API 在工作线程内调用；测试可通过 `create_app(..., llm_transport=...)` 注入传输实现，不访问真实模型。

默认连接超时 10 秒、写入超时 30 秒、连接池等待 5 秒、响应读取超时 120 秒。读取超时可通过 `Settings.llm_timeout_seconds` 设置，是各网络读取操作的等待上限，不是整个生成过程的总时限。行为参照 [HTTPX 超时文档](https://www.python-httpx.org/advanced/timeouts/)。

不自动重试，不跟随重定向，不读取环境代理设置。一次 `invoke` 至多发送一次 POST，失败由调用方决定是否重新发起。

成功状态要求 2xx。响应以流读取，解码后的内容默认最多 8 MiB，通过 `Settings.llm_max_response_bytes` 调整；超限立即失败并关闭响应。响应必须是有效 JSON 对象，拒绝数组、空响应、无效文本、非有限数字以及不能作为 UTF-8 输出的字符串。

## 7. HTTP 接口与错误

以下两个集合提供相同操作：

- `/api/model-configs`：来源库。
- `/api/chats/{chat_id}/model-configs`：聊天内副本。

| 方法与后缀 | 行为 |
| --- | --- |
| `GET` 集合 | 列出配置，隐藏 Key 原文 |
| `POST` 集合 | 创建配置，返回 201 |
| `GET /{config_id}` | 读取配置及 `has_api_key` |
| `PATCH /{config_id}` | 按显式提供的字段修改，保留 ID；不接受非空字段的 `null`、ID、归属或未知字段 |
| `DELETE /{config_id}` | 删除配置及其用途关联，返回 204 |
| `POST /{config_id}/invoke` | 提交 `{api_type, body}`，执行一次实际调用，返回 `{"response": {...}}` |

`invoke` 是直接调用入口，来源库和聊天内配置均可使用。它不执行写作预设、不检查归档门槛，不代表一次完整的聊天发送，也不会创建回合；写作 Workflow 另行负责这些业务规则。

- 404：聊天或配置不存在，或配置不在当前归属。
- 409：用途绑定缺失，或数据库关联与唯一性约束冲突。
- 422：字段无效、默认参数不是有效 JSON、接口不匹配、接口未接入、地址/模型/鉴权格式不合要求，或请求缺少必要结构。
- 504：网络超时，`kind=timeout`。
- 502：连接/传输失败（`network`）、非成功 HTTP 状态（`http`）、响应不是有效 JSON 对象（`invalid_response`）、响应过大（`response_too_large`），或顶层接口错误对象（`provider`）。

调用错误响应为 `{"detail": {"kind": "...", "message": "固定错误说明", "upstream_status": 429或null}}`。不回显异常中的 URL、鉴权、请求体和上游错误正文。请求字段校验错误保留定位与说明，省略原始 `input`，避免模型级校验把 Key 随整个请求体返回。

## 8. 验证

使用 HTTPX MockTransport 验证实际构造出的请求，不访问真实模型或消耗额度。

DeepSeek 验证另覆盖 Bearer 鉴权、原生顶层参数、模型覆盖、非流式限制、完整回复及日志、思考字段隔离、工具/拒绝/截断结果拒绝，以及状态更新、回合摘要、情节摘要的完整归档和各步骤失败恢复。

### 可选完整调用记录

设置 `Settings.llm_recording_directory` 或环境变量 `LORENOOK_LLM_RECORDING_DIRECTORY` 后，模型客户端在实际发送位置保存每次尝试。默认不启用。

- `request.json`：默认参数合并、接口适配后实际发送的完整请求字节。
- `response.raw`：响应解析前收到的原始内容字节（HTTP 内容解码后），保留全部候选、工具调用、其他字段及错误正文；有效 JSON 另存为便于阅读的 `response.json`。
- `metadata.json`：调用编号、聊天、回合序号/ID、用途、尝试次数、时间、耗时、HTTP 状态和结果。写作候选尚无正式回合 ID，使用聊天与下一回合序号关联。
- `index.jsonl`：追加事件索引，同一调用编号最后一条事件表示最新状态；重试创建新编号和目录。

不记录请求头或 URL。网络中断保存已收到的内容，标记 `response_complete=false`；未返回内容时仍保留请求和失败元数据。记录启用时，超长响应完整写入磁盘，仍按原长度上限拒绝处理。

写作、状态更新、回合摘要、情节摘要 Workflow 分别关联用途，并在解析或保存失败时更新 `workflow_result` 和错误类型。`result=success` 只表示传输及接口 JSON 检查通过，不代表后续解析或归档完成。记录不增加模型调用，不更改请求或模型回复。

覆盖递归合并与显式值优先、模型覆盖、原文与对象独立性、URL 和鉴权头、接口兼容检查、无 Key 调用、完整 JSON 保留、HTTP/网络/超时分类、重定向与重试关闭、响应 JSON 与长度校验、错误不泄露 Key、配置 CRUD 与 PATCH、来源及跨聊天归属、创建副本与共享用途、来源删除独立性、用途删除级联，以及网络期间数据库仍可写入。
