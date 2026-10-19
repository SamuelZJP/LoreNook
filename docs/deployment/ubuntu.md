# Ubuntu Deployment and Operations

[中文](../zh-CN/deployment/ubuntu.md) | [Documentation](../README.md)

Updated: 2026-10-20. See [milestone 1](../releases/milestone-1.md) for acceptance results.

## 1. Deployed arrangement

The application runs on Ubuntu 26.04 LTS at `192.168.31.64`, under `/home/samuel/LoreNook`. Commands below use the ordinary account `samuel` in Bash. Code, virtual environment, data, deployment files, and backups stay in that directory; systemd registers the services and the existing Caddyfile gains a route.

```text
Browser https://lorenook.cryingstray.cn
  → Cloud Caddy: HTTPS and Authelia authentication
  → Existing frp TCP tunnel
  → LAN Caddy :8080: Host-based routing
      ├─ Pages and assets → frontend/dist/
      └─ API → Uvicorn 127.0.0.1:18780 → data/lorenook.db
```

LAN and external clients use the same HTTPS hostname. LAN access also traverses the cloud and tunnel; an independent local access path is not configured. The existing frp tunnel is reused.

| Path | Purpose |
| --- | --- |
| `.venv/` | Linux Python virtual environment |
| `frontend/dist/` | Built static frontend |
| `data/lorenook.db` | Production SQLite database, including model credentials |
| `deploy/lorenook.env` | Backend environment variables |
| `deploy/lorenook.service` | Backend service definition |
| `deploy/backup.sh` | Automatic backup script |
| `deploy/lorenook-backup.service`, `deploy/lorenook-backup.timer` | Backup job and schedule |
| `backups/` | Database backups, restore-check copies, configuration backups |
| `/etc/caddy/Caddyfile` | Existing LAN Caddy configuration entry point |

`deploy/` contains machine-local files, not a deployment package supplied by this repository. Deployment files, backups, and runtime data stay out of Git. Service logs use journald.

## 2. First installation or reconstruction

Do not initialize an existing deployment again. To reconstruct it, obtain the accepted code revision in `~/LoreNook`, then install:

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

Python ≥3.12 is required. The current frontend lock requires Node `^20.19.0 || >=22.12.0`. Run tests on Ubuntu's Python 3.14 too. Clock validation explicitly restricts values to `00:00–23:59`, regardless of whether `time.fromisoformat()` accepts `24:00`.

For a Windows migration, stop the Windows backend before copying `data/lorenook.db`. Keep the original database before migration. Do not copy the Windows virtual environment, `node_modules`, or mock database.

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

Relative database paths resolve from the project root. The app neither loads `.env` automatically nor migrates at startup. `LORENOOK_LLM_RECORDING_DIRECTORY` optionally enables complete model request/response records; it is unset in this deployment. Records contain chat content and need a retention policy if enabled. The HTTP client ignores `HTTP_PROXY` and `HTTPS_PROXY`; arrange model connectivity separately if a proxy is required.

## 3. Backend service

Save as `deploy/lorenook.service`. Migrate explicitly before starting. Use one worker without development `--reload`.

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

Register and start once:

```bash
sudo systemctl enable "$HOME/LoreNook/deploy/lorenook.service"
sudo systemctl start lorenook
curl --fail http://127.0.0.1:18780/health
curl --fail http://127.0.0.1:18780/api/chats
```

`/health` only establishes that the process responds; check a business endpoint for database access. After editing a unit, run `sudo systemctl daemon-reload` and restart the service.

## 4. Extend the existing LAN Caddy

Inspect `sudo systemctl cat caddy` for the configuration and service user. This deployment uses `/etc/caddy/Caddyfile`, user `caddy`, without `ProtectHome`. Allow directory traversal and frontend reads:

```bash
sudo setfacl -m u:caddy:--x /home/samuel /home/samuel/LoreNook /home/samuel/LoreNook/frontend
sudo setfacl -R -m u:caddy:r-X /home/samuel/LoreNook/frontend/dist
sudo -u caddy test -r /home/samuel/LoreNook/frontend/dist/index.html
```

Reapply `dist/` permissions after rebuilding. A custom `ProtectHome` setting needs separate namespace configuration.

Back up and edit the existing file:

```bash
sudo cp /etc/caddy/Caddyfile "$HOME/LoreNook/backups/Caddyfile-$(date +%Y%m%d-%H%M%S)"
SUDO_EDITOR=nano sudoedit /etc/caddy/Caddyfile
```

Add inside the existing `:8080` block, alongside other host handlers. Preserve existing sites and the final fallback `handle { abort }`.

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

Keep the `/api` prefix; do not strip it with `handle_path`. Only `dist/` is served. Page paths fall back to `index.html`; API requests and missing `/assets/*` do not. Generation and archiving can take minutes: avoid short response timeouts throughout the proxy chain and automatic retries of model-producing requests.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
# Reload only after validation succeeds:
sudo systemctl reload caddy
curl --fail -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/health
curl --fail -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/api/chats
curl -I -H 'Host: lorenook.cryingstray.cn' http://127.0.0.1:8080/settings
```

## 5. Cloud hostname and authentication

The cloud Caddy already defines `(protected)`. Add or verify this site in its active Caddyfile without duplicating an existing entry:

```caddyfile
lorenook.cryingstray.cn {
    import protected
    reverse_proxy 127.0.0.1:8080
}
```

Back up, validate, and reload on the cloud host. DNS uses the existing wildcard record. Verify that Authelia requires authentication for the hostname under the existing `one_factor` policy, without matching `bypass`. Public traffic must not reach frps TCP 8080 directly; local Caddy still connects through loopback. This is a network access check, not an application permission feature.

LoreNook has no built-in login, state Schemas execute Python, and the administrative API can reveal model keys. Restrict access to trusted users.

## 6. Acceptance and routine commands

Open `https://lorenook.cryingstray.cn` from both LAN and mobile data. Check authentication, migrated chats, generation and confirmation/archive, state and summaries, detail-page refresh, and persistence after a service restart.

```bash
systemctl is-enabled lorenook caddy
sudo systemctl status lorenook --no-pager
sudo journalctl -u lorenook -n 100 --no-pager
sudo journalctl -u lorenook -f
sudo systemctl restart lorenook
```

After an archive failure, continue the latest unfinished archive in the UI rather than confirming the same candidate again. Wait for active generation/archive work before restarting. Unconfirmed candidates live only in browser memory.

## 7. Backup and restoration

Backups contain business data and model credentials. Only same-machine backups are configured; off-machine backups are deferred.

### Manual backup and restore drill

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

Checks should return only `ok`, with migration revision marked `(head)`. The drill uses an independent file and does not replace production.

For an actual restore, stop `lorenook` and `lorenook-backup.timer`, ensure no backup job is running, and retain a consistent backup of the current database. Replace production with a verified backup and set its mode to `600`. Run `alembic upgrade head` and `alembic check`, start the backend and timer, then verify chats through API and UI. When schema versions differ, first use code compatible with the backup, then migrate to the intended version. A code rollback alone cannot make a newer database schema compatible.

### Automatic backup

Current `deploy/backup.sh`:

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

`deploy/lorenook-backup.service`:

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

`deploy/lorenook-backup.timer`:

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

Runs daily at 03:00 Asia/Shanghai and catches up after missed runs. After successful verification, deletes `auto-*.db` files at least 30 days old. Manual backups and restore-check copies are retained. Register once, run a test, and inspect:

```bash
sudo systemctl link "$HOME/LoreNook/deploy/lorenook-backup.service"
sudo systemctl enable --now "$HOME/LoreNook/deploy/lorenook-backup.timer"
sudo systemctl start lorenook-backup.service
sudo journalctl -u lorenook-backup.service -n 20 --no-pager
systemctl list-timers lorenook-backup.timer
```

## 8. Subsequent updates

Normal releases use linear commits and `git pull --ff-only`. Wait for requests to finish, stop the backend and backup schedule, ensure the backup job is no longer running, then back up and update:

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

Execute step by step and resolve failures before proceeding. Ordinary code changes do not require a Caddy reload. Rewriting published commits is exceptional: back up and inspect local edits before aligning history, rather than forcibly deleting changes.
