# LoreNook 项目结构

[English](../../architecture/project-layout.md) | [中文文档索引](../index.md)

更新日期：2026-10-19

## 1. 文档目录

```text
LoreNook/
├─ README.md                       # 英文项目介绍与启动方法
├─ AGENTS.md                       # 协作规则
└─ docs/
   ├─ README.md                    # 英文文档索引
   ├─ design/
   │  ├─ product-design.md         # 产品规则与范围
   │  └─ data-model.md             # 逻辑数据模型
   ├─ architecture/
   │  └─ project-layout.md         # 项目结构
   ├─ backend/
   │  ├─ README.md                 # 技术、分层与流程
   │  └─ 01-… 至 13-…              # 模块说明
   ├─ zh-CN/
   │  ├─ README.md                 # 中文项目介绍
   │  ├─ index.md                  # 中文文档索引
   │  ├─ design/
   │  ├─ architecture/
   │  └─ backend/
   └─ archive/
      └─ initial-project-outline.zh-CN.md
```

各模块的完整导航见[后端总览](../backend/README.md)。中英文主题文档采用对应目录，历史草稿独立归档，由索引提供入口。

## 2. 后端目录

以下说明当前主要目录分工，具体文件见各模块文档，不作为逐文件清单。

```text
backend/
├─ main.py                    # 应用入口与生命周期
├─ config.py                  # 运行设置
├─ api/                       # HTTP 路由、参数校验与响应
├─ schemas/                   # 接口与模块间数据契约
├─ workflows/                 # 跨模块流程编排
├─ modules/
│  ├─ characters/             # 角色资料与副本
│  ├─ users/                  # 用户身份资料与副本
│  ├─ chats/                  # 聊天读取与配置
│  ├─ definitions/            # 定义管理与 Jinja2 解析
│  ├─ memory/                 # X/Y 历史选取
│  ├─ presets/                # JavaScript 预设与 QuickJS
│  ├─ models/                 # 模型配置与用途绑定
│  ├─ state/                  # Schema、状态快照与 JSON Patch
│  ├─ round_summary/          # 回合摘要
│  ├─ episode_decision/       # 判定方法分发与跨日规则
│  ├─ episode_summary/        # 范围归纳与情节编辑
│  └─ admin/                  # 全量数据与一致性检查
├─ llm/                       # HTTP、参数、接口适配与文本提取
├─ repository/                # 模型、会话、查询与归档/数据管理写入
├─ shared/                    # 正文提取与公共错误
├─ migrations/                # Alembic 版本与环境
└─ tests/                     # 模块、接口、存储与流程测试
```

当前普通查询集中在 `repository/queries.py`，归档写入位于 `repository/archive.py`，数据管理位于 `repository/admin.py`，不再按每个实体各列一份 Repository 文件。HTTP 资料与模型接口分别使用 `api/catalog.py`、`api/models.py` 等实际分组；原生接口适配位于 `llm/google.py`、`llm/deepseek.py`，三个归档生成模块通过 `llm/generation.py` 共用文本请求构建。

### 前端

```text
frontend/
├─ src/
│  ├─ api/                    # 生成的 OpenAPI 类型、请求客户端、接口函数
│  ├─ lib/                    # 输出区段、偏好、Markdown、数据管理暂存
│  ├─ composables/            # 回合生命周期、布局状态、提示
│  ├─ components/             # 外壳、聊天时间线、侧边面板、资源编辑器
│  └─ views/                  # 首页、聊天、资源库、数据管理、设置
└─ dev/mock_backend.py        # 使用模拟模型调用的真实后端，用于开发与测试
```

前端是 Vue 3 单页应用，调用后端 `/api` 接口；浏览器中只保存未确认的候选回复和本地显示偏好。见 [`frontend/README.md`](../../../frontend/README.md)。

## 3. 调用与事务

```text
API → Service                         # 查询与编辑
API → Workflow → Services             # 聊天创建、写作与归档
Service / Workflow → Repository       # 数据库操作
Workflow / 生成模块 → LLM              # 模型请求
```

API 负责传输，Workflow 控制顺序与保存时机，模块实现业务行为，Repository 执行读写但不自行提交，模型请求集中在 LLM 层。

创建聊天在同一事务中复制资源并生成初始状态。写作先读取一致快照、关闭会话，再执行定义解析、预设与模型调用。归档先保存正文，各步结果与步骤推进分别原子提交；网络调用不持有数据库事务。

## 4. 运行数据与配置

- `data/`：默认 SQLite 数据库位置。
- `alembic.ini` 与 `backend/migrations/`：迁移配置及版本。
- `pyproject.toml`：包配置、兼容依赖与测试设置。
- `requirements-dev.lock`：验证环境的固定依赖。

虚拟环境、缓存、生成的包元数据与临时内容不属于维护文档目录。部署打包仍待设计。
