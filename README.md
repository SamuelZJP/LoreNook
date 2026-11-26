# LoreNook · 炉隅

面向小圈子邀请制内测的 AI 角色对话应用，已部署上线（[lorenook.cryingstray.cn](https://lorenook.cryingstray.cn)，无公开注册，体验链接按需发放）。个人独立开发：需求、后端、前端、模型接入与运维。

![对话页：右侧为结构化状态与生成插图](docs/images/chat.jpg)

## 它解决什么问题

让 AI 长期扮演一个角色，会遇到两个问题：

- **记不住**：几十轮之前发生的事很快被挤出上下文。LoreNook 用**分层记忆**（回合摘要 → 情节摘要，按需召回）应对。
- **不像他**：聊久了，角色的心情、处境、关系对不上前文，不同角色也渐渐说成同一个腔调。LoreNook 用**角色状态变量**应对。

前身是记忆后端原型 [MAAS](https://github.com/SamuelZJP/MAAS)（2026.04 – 07），验证过的设计并入了本项目。

## 功能

- 分层记忆与按需召回
- 角色状态变量：每个角色自定义 Schema，可附状态脚本
- 可编程写作预设：用户编写的 JavaScript 在 QuickJS 沙箱中运行
- 联动 ComfyUI 生成插图，实时显示进度
- 角色状态栏、角色卡导入导出、聊天配置模板
- 内置账号，用户之间数据完全隔离
- 一次性体验链接：限时、限次数，结束后自动清理

## 技术栈

| | |
| --- | --- |
| 后端 | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · SQLite · httpx（读取模型 SSE 流）· websockets（订阅 ComfyUI 进度） |
| 前端 | Vue 3 · TypeScript · Vite · TanStack Query · CodeMirror 6 · openapi-typescript |
| 测试 | pytest（800+ 用例）· 带故障注入的模拟后端 |
| 部署 | Systemd · Caddy · 内网穿透 · 每日自动备份 |

## 工程上的几点

- **依赖方向由测试强制**：后端只允许 `api → workflows → modules → repository / schemas / llm / shared` 单向依赖，违反即测试失败（`backend/tests/test_architecture.py`）。
- **可插拔功能**：插图、记忆召回、体验链接、状态栏都是独立功能包，各自只有一个接入点。
- **前后端类型同步**：前端接口类型由 OpenAPI 自动生成。
- **模型地址防护**：用户填写的模型地址只能指向公网，防止借服务器访问内网。
- **迁移显式执行**：启动时从不自动迁移，数据库结构变化一律走 Alembic。

## 文档

- [`docs/design.md`](docs/design.md)：概念、回合生命周期、归档、记忆与状态规则
- [`docs/deployment.md`](docs/deployment.md)：部署、更新、备份与恢复

（文档为英文。）

## 本地运行

需要 Python ≥ 3.12，Node `^20.19.0 || >=22.12.0`。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m backend.cli user add <name> --admin
LORENOOK_API_DOCS=1 .venv/bin/python -m uvicorn backend.main:app --reload
```

```bash
cd frontend && npm install && npm run dev    # http://localhost:5173，/api 代理到 LORENOOK_BACKEND（默认 http://127.0.0.1:8000）
```

- 没有注册功能，用户用 `python -m backend.cli user add|passwd|disable|enable|list` 管理。
- 会话 Cookie 默认仅限 HTTPS；浏览器对 `http://localhost` 放行。在其他地址用纯 http 时设 `LORENOOK_COOKIE_SECURE=0`。
- 数据库默认 `data/lorenook.db`，可用 `LORENOOK_DATABASE_URL` 指定；上传图片在 `data/media`，生成插图在 `data/images`。启动时不自动迁移，需自己运行 `alembic upgrade head`。
- `LORENOOK_API_DOCS=1` 时开放 Swagger（`/docs`）。前端其他脚本：`npm run build`、`npm run typecheck`、`npm run gen:api`（从运行中的后端重新生成 `src/api/schema.d.ts`）。

### 模拟后端（不需要模型）

用假模型运行真实应用，数据库为 `data/mock.db`，预置了示例角色、身份、预设和模型配置。用 `demo` / `demo-password`（管理员）或 `guest` / `guest-password`（普通用户）登录：

```bash
python frontend/dev/mock_backend.py --port 8765 --reset
LORENOOK_BACKEND=http://127.0.0.1:8765 npm run dev
```

在输入里加标记可以触发特定行为：`[[fail-writing]]`、`[[fail-state_update]]`、`[[fail-round_summary]]`、`[[fail-episode_summary]]`（归档类标记只让第一次尝试失败）、`[[bad-output]]`、`[[newday]]`（推进 `世界.日期`）、`[[slow]]`。

### 测试与迁移

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic check
.venv/bin/python -m alembic revision --autogenerate -m 'describe change'
```

`requirements-dev.lock` 固定了测试过的版本，`pyproject.toml` 声明版本范围。

### 在应用里开始

1. 新建角色。它的 `state_schema` 必须产出合法的 `世界` 对象，可从 `backend/modules/state/examples/basic.py` 开始。
2. 用 `backend/modules/presets/examples/google_tool.js` 新建写作预设。
3. 新建模型配置，并在聊天里分别绑定到 `writing`、`state_update`、`round_summary`、`episode_summary`。
4. 生成、确认，等归档完成后再进行下一轮。

## 目录

```text
backend/
  api/        HTTP 路由             schemas/    请求/响应契约
  workflows/  跨模块流程            modules/    各功能的业务规则
  repository/ 数据表与查询          llm/        模型 API 适配
  migrations/ Alembic               tests/
frontend/src/
  api/        类型化客户端          composables/roundFlow.ts  回合生命周期
  views/      页面                  components/ 面板与编辑器
  lib/        输出解析、引号、偏好、字体
```
