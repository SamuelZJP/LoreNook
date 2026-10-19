# LoreNook

[English](../../README.md) | [中文文档索引](index.md)

个人使用的 AI 角色扮演工具。当前后端已实现资料与聊天管理、定义解析、分层记忆、写作预设、模型调用、完整写作生成、状态管理与更新、回合摘要、情节判定、情节摘要、确认归档流程与数据管理；Vue 网页前端覆盖聊天流程、资源编辑、数据管理与偏好设置。

里程碑一已在 Ubuntu 26.04 LTS 部署并验收。现有 Caddy 入口、systemd 服务、更新与备份见[部署与运维](deployment/ubuntu.md)，验收结果见[里程碑一](releases/milestone-1.md)。

## 本地开发

需要 Python 3.12 或更高版本。在项目根目录执行（PowerShell）：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

健康检查：`GET /health`；接口文档：[本地 API 文档](http://127.0.0.1:8000/docs)。

默认数据库为项目根目录下的 `data/lorenook.db`。通过环境变量 `LORENOOK_DATABASE_URL` 指定其他 SQLite 地址；相对文件路径始终基于项目根目录。应用启动不自动建表或迁移。

```powershell
$env:LORENOOK_DATABASE_URL = 'sqlite:///data/development.db'
.venv\Scripts\python.exe -m alembic upgrade head
```

## 前端

网页前端位于 `frontend/`（Vue 3、TypeScript、Vite）。后端在 8000 端口运行时：

```powershell
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173。构建、类型生成与模拟后端见 [frontend/README.md](../../frontend/README.md)。

从已提交的锁定文件重复安装时使用 `npm ci`。正式部署由 Caddy 托管 `frontend/dist/`；Vite 开发与预览服务用于本地工作。

## 验证与迁移

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m alembic revision --autogenerate -m 'describe change'
```

`requirements-dev.lock` 固定本次验证使用的依赖版本；`pyproject.toml` 声明兼容范围。调整依赖后应重新验证并更新锁定文件。

## 文档与实现

完整导航见[文档索引](index.md)，产品规则见[产品设计](design/product-design.md)，逻辑字段见[数据模型](design/data-model.md)，目录分工见[项目结构](architecture/project-layout.md)。

- [后端总览](backend/README.md)：技术栈与分层。
- [数据访问模块](backend/01-data-access.md)：物理结构、约束、接口和事务边界。
- [角色与聊天](backend/02-characters-and-chats.md)：资料管理、聊天副本、创建流程与 HTTP 接口。
- [定义管理与模板解析](backend/03-definition-rendering.md)：逐条管理、排序、状态模板与解析错误。
- [记忆装配](backend/04-memory-assembly.md)：按 X/Y 选择历史表示、按时间组织及只读预览。
- [写作预设](backend/05-writing-presets.md)：JavaScript 预设、请求包装、回复解析与聊天预览。
- [模型调用](backend/06-model-calls.md)：模型配置、默认参数、Google GenerateContent 适配与错误处理。
- [写作流程](backend/07-writing-workflow.md)：材料收集、预设包装、单次调用与待确认回复。
- [状态更新](backend/08-state-updates.md)：Python/Pydantic Schema、状态编辑、JSON Patch 与步骤保存。
- [回合摘要](backend/09-round-summaries.md)：使用本回合状态生成摘要、保存与重试、读取及编辑。
- [情节判定](backend/10-episode-decisions.md)：跨日与回合数规则、候选范围、判定保存和步骤推进。
- [情节摘要](backend/11-episode-summaries.md)：选定范围的分层归纳、失败重试、情节读取与编辑。
- [归档流程](backend/12-archiving-workflow.md)：确认保存、顺序执行、失败恢复与回合查询。
- [数据管理](backend/13-data-management.md)：全量读取、历史数据原子批改、版本与关联校验。
- `backend/repository/models.py`：10 张业务表；另由 Alembic 维护迁移版本表。
- `backend/repository/database.py`：连接与事务。
- `backend/repository/queries.py`：基础读写与业务查询。
- `backend/repository/archive.py`：归档结果与步骤的原子保存。
- `backend/migrations/`：版本化结构迁移。

## 当前可用接口

- `/api/characters`、`/api/user-identities`：来源资料的创建与列表；按 ID 读取、编辑和删除。
- `/api/chats`：创建与列表；按 ID 读取详情、编辑配置和删除。
- `/api/chats/{id}/character`、`/api/chats/{id}/user-identity`：读取和编辑聊天内副本。
- 在角色、身份及聊天内副本路径后追加 `/definitions`：定义列表与逐条管理；`PUT /reorder` 按完整 ID 列表排序。
- `POST /api/chats/{id}/definitions/resolve`：使用最新状态解析已启用定义，返回本次文本，不改写原文。
- `GET /api/chats/{id}/memory`：使用当前 X/Y 配置装配已归档历史，返回情节、回合摘要和最近完整回合。
- `/api/writing-presets`、`/api/chats/{id}/writing-presets`：来源库及聊天内预设管理；按预设 ID 追加 `/build`、`/parse` 可单独试运行。
- `POST /api/chats/{id}/writing-preview`：接收 `user_input`，从数据库收集材料并返回当前预设包装的请求，不调用模型。
- `/api/model-configs`、`/api/chats/{id}/model-configs`：来源库及聊天内模型配置管理，读取只返回 `has_api_key`；按配置 ID 追加 `POST /invoke` 可执行单次调用。
- `POST /api/chats/{id}/writing`：接收 `user_input`，通过当前预设与 `writing` 模型生成待确认回复；重新生成使用同一入口，不保存候选回合。
- `GET/PUT /api/chats/{id}/state`：读取或校验后编辑最新可编辑状态。
- `POST /api/chats/{id}/rounds/{round_id}/state-update`：为已保存且处于状态更新步骤的最新回合生成状态，成功后推进到回合摘要。
- `POST /api/chats/{id}/rounds/{round_id}/round-summary`：使用本回合已保存状态生成摘要，成功后推进到情节判定。
- `GET/PUT /api/chats/{id}/rounds/{round_id}/summary`：读取摘要或编辑最新已归档回合的摘要。
- `POST /api/chats/{id}/rounds/{round_id}/episode-decision`：按跨日和回合数规则判定，无需情节则完成归档，否则保存范围并等待情节摘要；不调用模型。
- `POST /api/chats/{id}/rounds/{round_id}/episode-summary`：沿用已保存范围生成情节，保存成功后完成归档。
- `GET /api/chats/{id}/episodes`、`GET/PUT /api/chats/{id}/episodes/{episode_id}`：按序读取情节；编辑仅限最新已归档回合产生的情节摘要。
- `POST /api/chats/{id}/archive`：提交确认的 `user_input`、`ai_output` 和 `based_on_round_id`，保存正式回合并自动执行归档。
- `GET /api/chats/{id}/archive`：查询最新正式回合及归档进度，尚无回合时返回 `null`。
- `POST /api/chats/{id}/rounds/{round_id}/archive/retry`：提交当前 `expected_step`，从该步恢复并继续后续流程。
- `GET /api/chats/{id}/rounds`、`GET /api/chats/{id}/rounds/{round_id}`：按序读取正式回合，或查询指定回合的结果和进度。
- `GET /api/admin/schema`、`GET /api/admin/data`：读取业务表契约和全量快照；显式 `include_secrets=true` 包含模型密钥原文。
- `POST /api/admin/data`：携带 `expected_revision` 和 `operations`，原子执行增删改并校验最终一致性；历史状态按原文保存，不执行 Schema。

`state_schema` 使用 Python/Pydantic 源码，定义 `Schema` 模型，由默认值生成初始状态并执行校验修正。创建角色和修改 Schema 时必须验证初始状态包含 `世界` 对象及日期、星期、时间、地点四个字符串字段。日期严格采用有效的 `YYYY-MM-DD`，星期只能为星期一至星期六或星期日，时间为 24 小时制 `HH:mm`，地点允许为空。正常状态保存先执行 Schema，再检查统一世界字段；数据修改入口只检查统一约束，不执行 Schema。默认执行器无法用空白 Schema 创建角色或聊天。旧状态不自动迁移，仍可读取，再次保存时须符合新约定。可编辑示例位于 `backend/modules/state/examples/basic.py`。详细请求与响应可在本地 API 文档中查看。

草案对应的可编辑示例位于 `backend/modules/presets/examples/google_tool.js`；将文件内容作为 `source` 保存即可使用，固定文本集中在顶部 `fixed` 对象中。

模型调用支持 `google_generate_content` 和 `deepseek_chat_completions`。`base_url` 填写包含所需版本路径的接口根地址；Google 默认参数放在 `generationConfig` 下，DeepSeek 使用 `temperature`、`max_tokens`、`thinking` 等顶层原生字段。聊天选定预设并绑定 `writing` 模型后即可调用写作入口；确认后使用归档入口，分别读取 `state_update`、`round_summary` 和必要的 `episode_summary` 模型绑定。三个归档用途可以共用同一份 DeepSeek 配置。详见[模型调用](backend/06-model-calls.md)。

后端主要业务模块已完成，可进入前端对接与联调。
