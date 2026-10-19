# Ubuntu 部署与运维

[English](../../deployment/ubuntu.md) | [中文文档索引](../index.md)

更新日期：2026-10-20。首次部署及验收记录见[里程碑一](../releases/milestone-1.md)。

## 1. 已部署方案

应用位于团团（Ubuntu 26.04 LTS，`192.168.31.64`）的 `/home/samuel/LoreNook`，以下命令使用普通用户 `samuel` 的 Bash 终端。代码、虚拟环境、数据库、部署文件和备份均在该目录中；systemd 注册服务，现有 Caddyfile 增加分流。

```text
浏览器 https://lorenook.cryingstray.cn
  → 云云 Caddy：HTTPS 与 Authelia 认证
  → 现有 frp TCP 隧道
  → 团团 Caddy :8080：按 Host 分流
      ├─ 网页与静态资源 → frontend/dist/
      └─ API → Uvicorn 127.0.0.1:18780 → data/lorenook.db
```

局域网与公网使用同一 HTTPS 域名，局域网访问同样经过云端入口和隧道；没有配置断网时可用的内网直连入口。沿用现有 frp 隧道，无需新建代理。

| 路径 | 用途 |
| --- | --- |
| `.venv/` | Linux Python 虚拟环境 |
| `frontend/dist/` | 静态网页构建结果 |
| `data/lorenook.db` | 正式 SQLite 数据库，含模型配置和密钥 |
| `deploy/lorenook.env` | 后端环境变量 |
| `deploy/lorenook.service` | 后端服务定义 |
| `deploy/backup.sh` | 自动备份脚本 |
| `deploy/lorenook-backup.service`、`deploy/lorenook-backup.timer` | 备份任务与定时器 |
| `backups/` | 数据库备份、恢复检查副本、配置备份 |
| `/etc/caddy/Caddyfile` | 团团已使用的 Caddy 配置入口 |

`deploy/` 是每台机器的本地配置，不是仓库提供的部署包；`deploy/`、`backups/` 和运行数据不提交到 Git。服务日志由 journald 保存。

## 2. 首次安装或重建

现有部署无需重复初始化。重建时先取得已验收版本的代码，进入 `~/LoreNook`，安装依赖：

```bash
sudo apt update
sudo apt install -y git curl build-essential python3 python3-venv python3-dev nodejs npm acl sqlite3
cd ~/LoreNook
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
cd frontend
npm ci
npm run build
cd ..
mkdir -p deploy data backups
chmod 700 data backups
```

Python 要求 ≥3.12；当前前端锁定依赖要求 Node `^20.19.0 || >=22.12.0`。Ubuntu 的 Python 3.14 上也须通过测试。时间校验显式限制为 `00:00–23:59`，不依赖 `time.fromisoformat()` 是否接受 `24:00`。

导入 Windows 数据时，停止 Windows 后端后复制 `data/lorenook.db`。不复制 Windows 虚拟环境、`node_modules` 或模拟数据库。首次迁移前保留原数据库副本。

```bash
cat > deploy/lorenook.env <<'EOF'
LORENOOK_DATABASE_URL=sqlite:///data/lorenook.db
EOF
chmod 600 deploy/lorenook.env
set -a
source deploy/lorenook.env
set +a
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
```

数据库相对路径按项目根目录解析。应用不自动加载 `.env`，也不在启动时执行迁移。`LORENOOK_LLM_RECORDING_DIRECTORY` 可选择开启完整模型请求/响应记录，当前部署未启用；记录包含聊天内容，应设置保留周期。HTTP 客户端不读取 `HTTP_PROXY`、`HTTPS_PROXY`，需要代理时须另行配置连接方案。

## 3. 后端服务

`deploy/lorenook.service` 内容如下。迁移在服务启动前显式执行；单进程运行，不使用开发模式的 `--reload`。

```ini
[Unit]
Description=LoreNook backend
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=samuel
WorkingDirectory=/home/samuel/LoreNook
EnvironmentFile=/home/samuel/LoreNook/deploy/lorenook.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/samuel/LoreNook/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 18780 --workers 1 --timeout-graceful-shutdown 420
Restart=on-failure
RestartSec=5
TimeoutStopSec=450
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

首次注册与启动：

```bash
sudo systemctl enable "$HOME/LoreNook/deploy/lorenook.service"
sudo systemctl start lorenook
curl --fail http://127.0.0.1:18780/health
curl --fail http://127.0.0.1:18780/api/chats
```

`/health` 只说明进程能够响应，数据库可用性还须通过业务接口确认。服务文件修改后执行 `sudo systemctl daemon-reload`，再重启服务。

## 4. 团团现有 Caddy 的增量配置

`sudo systemctl cat caddy` 可确认实际配置入口和运行用户。本次使用 `/etc/caddy/Caddyfile`、用户 `caddy`，未启用 `ProtectHome`。授予父目录穿行权限及前端读取权限：

```bash
sudo setfacl -m u:caddy:--x /home/samuel /home/samuel/LoreNook /home/samuel/LoreNook/frontend
sudo setfacl -R -m u:caddy:r-X /home/samuel/LoreNook/frontend/dist
sudo -u caddy test -r /home/samuel/LoreNook/frontend/dist/index.html
```

每次重新构建后重新授予 `dist/` 权限。若自行开启 `ProtectHome`，须另外处理服务的目录隔离。

先备份 Caddyfile，再编辑原文件：

```bash
sudo cp /etc/caddy/Caddyfile "$HOME/LoreNook/backups/Caddyfile-$(date +%Y%m%d-%H%M%S)"
SUDO_EDITOR=nano sudoedit /etc/caddy/Caddyfile
```

在现有 `:8080` 块内添加以下内容，与其他域名的 `handle` 同层，保留已有站点和末尾兜底 `handle { abort }`：

```caddyfile
@lorenook host lorenook.cryingstray.cn
handle @lorenook {
    encode gzip
    @lorenook_backend path /api /api/* /health /docs /docs/* /openapi.json /redoc
    handle @lorenook_backend {
        reverse_proxy 127.0.0.1:18780
    }
    handle /assets/* {
        root * /home/samuel/LoreNook/frontend/dist
        file_server
    }
    handle {
        root * /home/samuel/LoreNook/frontend/dist
        try_files {path} /index.html
        header Cache-Control "no-cache"
        file_server
    }
}
```

API 保留完整 `/api` 前缀，不用 `handle_path` 剥离。静态文件根目录只指向 `dist/`。前端页面路径回退到 `index.html`，API 与缺失的 `/assets/*` 不回退成首页。生成和归档可能持续数分钟，代理链不能设置过短的响应超时，也不自动重试产生模型调用的请求。

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
# 只在验证成功后执行：
sudo systemctl reload caddy
curl --fail -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/health
curl --fail -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/api/chats
curl -I -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/settings
```

## 5. 云端域名与认证入口

云云已有认证片段 `(protected)`；在其实际 Caddyfile 中加入或核对以下站点，不重复创建：

```caddyfile
lorenook.cryingstray.cn {
    import protected
    reverse_proxy 127.0.0.1:8080
}
```

在云云上备份原配置，执行 Caddy 验证后重载。新域名解析沿用现有通配记录。确认 Authelia 对该域名要求认证；沿用 `one_factor` 策略，检查没有匹配到 `bypass`。公网不得直接访问 frps 的 TCP 8080 入口，本机 Caddy 仍通过回环地址连接；这是网络接入检查项，不是应用中的权限控制。

LoreNook 本身没有用户登录，状态 Schema 会执行 Python 源码，管理接口支持密钥读取，因此访问入口只提供给可信使用者。

## 6. 验收与日常命令

局域网和手机移动网络分别访问 `https://lorenook.cryingstray.cn`，检查认证、迁移后的聊天、生成与确认归档、状态和摘要、详情页刷新、重启后数据保留。

```bash
systemctl is-enabled lorenook caddy
sudo systemctl status lorenook --no-pager
sudo journalctl -u lorenook -n 100 --no-pager
sudo journalctl -u lorenook -f
sudo systemctl restart lorenook
```

模型或配置导致归档失败时，在网页继续最新未完成归档；不重新确认同一候选。重启前等待当前生成或归档结束，未确认候选只保存在浏览器内存。

## 7. 备份与恢复

备份包含业务数据和模型密钥。当前仅配置同机备份，异机备份暂不启用。

### 手动备份与恢复演练

```bash
cd ~/LoreNook
umask 077
snapshot="$HOME/LoreNook/backups/lorenook-$(date +%Y%m%d-%H%M%S).db"
sqlite3 -cmd '.timeout 10000' data/lorenook.db ".backup '$snapshot'"
restored="$HOME/LoreNook/backups/restore-check-$(date +%Y%m%d-%H%M%S).db"
cp "$snapshot" "$restored"
sqlite3 "$restored" 'PRAGMA integrity_check; PRAGMA foreign_key_check;'
LORENOOK_DATABASE_URL="sqlite:///$restored" .venv/bin/python -m alembic current
```

检查只输出 `ok`，迁移版本标记为 `(head)`。演练使用独立文件，不覆盖正式库。

实际恢复时，先停止 `lorenook` 和 `lorenook-backup.timer`，确认备份任务不在执行；保留当前数据库的一致性备份，再用已校验的备份替换正式库并设为 `600`。运行 `alembic upgrade head` 与 `alembic check` 后启动后端和定时器，验证聊天接口与页面。数据库结构变化时应使用与备份匹配的代码，再按目标版本迁移；不能只回退代码并继续使用更高版本数据库。

### 自动备份

当前 `deploy/backup.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
umask 077
project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="$project/backups"
database="$project/data/lorenook.db"
mkdir -p "$backup_dir"
test -f "$database"
backup="$backup_dir/auto-$(date +%Y%m%d-%H%M%S).db"
sqlite3 -cmd '.timeout 10000' "$database" ".backup '$backup'"
result="$(sqlite3 "$backup" 'PRAGMA integrity_check; PRAGMA foreign_key_check;')"
if [[ "$result" != "ok" ]]; then
    echo "备份校验失败：$backup" >&2
    echo "$result" >&2
    exit 1
fi
find "$backup_dir" -maxdepth 1 -type f -name 'auto-*.db' -mtime +29 -delete
echo "备份完成：$backup"
```

`deploy/lorenook-backup.service`：

```ini
[Unit]
Description=Back up LoreNook database

[Service]
Type=oneshot
User=samuel
WorkingDirectory=/home/samuel/LoreNook
ExecStart=/bin/bash /home/samuel/LoreNook/deploy/backup.sh
UMask=0077
```

`deploy/lorenook-backup.timer`：

```ini
[Unit]
Description=Daily LoreNook database backup

[Timer]
OnCalendar=*-*-* 03:00:00 Asia/Shanghai
Persistent=true
Unit=lorenook-backup.service

[Install]
WantedBy=timers.target
```

每天北京时间 03:00 运行，关机错过后补执行；校验成功后删除满 30 天的 `auto-*.db`，不清理手动备份和恢复检查副本。首次注册、试运行和日常检查：

```bash
sudo systemctl link "$HOME/LoreNook/deploy/lorenook-backup.service"
sudo systemctl enable --now "$HOME/LoreNook/deploy/lorenook-backup.timer"
sudo systemctl start lorenook-backup.service
sudo journalctl -u lorenook-backup.service -n 20 --no-pager
systemctl list-timers lorenook-backup.timer
```

## 8. 后续更新

正常发布采用线性提交，使用 `git pull --ff-only`。等待当前请求结束后停止后端和备份定时器，确认备份服务没有运行，再备份并更新：

```bash
cd ~/LoreNook
sudo systemctl stop lorenook-backup.timer
sudo systemctl stop lorenook-backup.service
sudo systemctl stop lorenook
umask 077
snapshot="$HOME/LoreNook/backups/pre-update-$(date +%Y%m%d-%H%M%S).db"
sqlite3 data/lorenook.db ".backup '$snapshot'"
git rev-parse HEAD > "${snapshot%.db}.commit"
git pull --ff-only
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
cd frontend
npm ci
npm run build
cd ..
sudo setfacl -R -m u:caddy:r-X frontend/dist
set -a
source deploy/lorenook.env
set +a
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
sudo systemctl start lorenook
curl --fail http://127.0.0.1:18780/health
curl --fail http://127.0.0.1:18780/api/chats
sudo systemctl start lorenook-backup.timer
```

逐步执行，失败时先处理错误，再继续。普通代码更新不用重载 Caddy。改写已经发布的提交属于例外，需要先备份并核对本地修改后对齐历史，不使用强制清理代替冲突处理。
