# Deployment

Production runs on Ubuntu 26.04 at `192.168.31.64`, in `/home/samuel/LoreNook`, as user `samuel`.

```text
https://lorenook.cryingstray.cn
  → Cloud Caddy (HTTPS)
  → frp TCP tunnel
  → LAN Caddy :8080 (host routing)
      ├─ pages/assets → frontend/dist/
      └─ /api, /health → Uvicorn 127.0.0.1:18780 → data/lorenook.db
```

The app does its own sign-in; there is no external authentication in front of it. `/` is the public home page.

Machine-local files (not in Git): `deploy/lorenook.env`, `deploy/lorenook.service`, `data/` (database, `data/images/`, `data/media/`), `backups/`. Their contents are reproduced below for reconstruction.

## Update

Wait for running generation/archive work to finish first. Illustration jobs still running at shutdown are marked failed on the next start. Uvicorn must run a single worker: the illustration queue and its live progress are in-process.

ComfyUI: `SaveImage` writes the whole workflow into each PNG, including the story text in `{{prompt}}`; start ComfyUI with `--disable-metadata` to keep it out. The render timeout (`comfyui_timeout_seconds`, 600 s) also has to cover any LLM nodes in the workflow, including their retries.

```bash
cd ~/LoreNook
sudo systemctl stop lorenook
umask 077
snap="backups/pre-update-$(date +%Y%m%d-%H%M%S).db"
sqlite3 data/lorenook.db ".backup '$snap'" && git rev-parse HEAD > "${snap%.db}.commit"
git pull --ff-only
.venv/bin/python -m pip install -r requirements-dev.lock && .venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
(cd frontend && npm ci && npm run build)
sudo setfacl -R -m u:caddy:r-X frontend/dist
set -a; source deploy/lorenook.env; set +a
.venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic check
sudo systemctl start lorenook
curl --fail http://127.0.0.1:18780/api/public/home && .venv/bin/python -m backend.cli user list
```

Run it step by step and stop on any failure. Code-only changes don't need a Caddy reload.

## Upgrading to v3 (once)

v3 adds users. It is the Update procedure with an administrator for the migration, who will own all existing data:

```bash
cd ~/LoreNook
sudo systemctl stop lorenook
umask 077
snap="backups/pre-v3-$(date +%Y%m%d-%H%M%S).db"
sqlite3 data/lorenook.db ".backup '$snap'" && git rev-parse HEAD > "${snap%.db}.commit"
git pull --ff-only
.venv/bin/python -m pip install -r requirements-dev.lock && .venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
(cd frontend && npm ci && npm run build)
sudo setfacl -R -m u:caddy:r-X frontend/dist
set -a; source deploy/lorenook.env; set +a
read -r LORENOOK_ADMIN_USERNAME && read -rs LORENOOK_ADMIN_PASSWORD && export LORENOOK_ADMIN_USERNAME LORENOOK_ADMIN_PASSWORD
.venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic check
unset LORENOOK_ADMIN_USERNAME LORENOOK_ADMIN_PASSWORD
```

`LORENOOK_MEDIA_DIRECTORY` must point at the real uploads when migrating (the default `data/media` does), so existing images are registered to the administrator.

Add the new settings to `deploy/lorenook.env` (see its table below: at least `LORENOOK_ICP_NUMBER`, and `LORENOOK_MODEL_EXTRA_NETWORKS` if `getent ahosts api.deepseek.com` answers `198.18.x.x`; never the admin password), then:

```bash
sudo systemctl start lorenook
curl --fail http://127.0.0.1:18780/api/public/home
set -a; source deploy/lorenook.env; set +a; .venv/bin/python -m backend.cli user list
```

Then update the LAN Caddy (no `/docs` routes, `trusted_proxies`; see LAN Caddy below), validate and reload it.

Cut over in two steps: first keep Authelia in front (`import protected` in the Cloud Caddy block) and check sign-in, sign-out, and that a second test user sees none of the administrator's data. Then remove `import protected` and reload the cloud Caddy.

## Users

No sign-up. Manage users on the server, with the env file sourced:

```bash
.venv/bin/python -m backend.cli user add <name> [--admin]   # asks for the password
.venv/bin/python -m backend.cli user passwd <name>          # also signs them out everywhere
.venv/bin/python -m backend.cli user disable <name>         # or enable
.venv/bin/python -m backend.cli user list
```

## Routine

```bash
sudo systemctl status lorenook --no-pager
sudo journalctl -u lorenook -f
sudo systemctl restart lorenook
```

`/health` only shows the process is up; `python -m backend.cli user list` (with the env file sourced) checks the database. After an archive failure, use retry in the UI — don't re-confirm the candidate.

## Backup and restore

A systemd timer backs up nightly (below). Take one manually when needed (the update procedure always snapshots first):

```bash
cd ~/LoreNook && umask 077 && sqlite3 data/lorenook.db ".backup 'backups/manual-$(date +%Y%m%d-%H%M%S).db'"
```

Database backups don't include `data/images/` (illustrations) or `data/media/` (uploaded avatars and reference images); copy those folders separately. Keep Caddy's request size limit, if any, above 16 MB so uploads pass.

Backups contain every user's model API keys. Keep them on this machine, or copy them only somewhere as private.

Check a backup without touching production:

```bash
cp backups/<file>.db backups/restore-check.db
sqlite3 backups/restore-check.db 'PRAGMA integrity_check; PRAGMA foreign_key_check;'   # expect "ok"
LORENOOK_DATABASE_URL=sqlite:///backups/restore-check.db .venv/bin/python -m alembic current  # expect (head)
```

To restore: stop `lorenook`, back up the current DB, copy the verified backup to `data/lorenook.db` (mode 600), run `alembic upgrade head`, start it again. If the backup is from a newer schema than the code, check out compatible code first.

## Reconstruct from scratch

```bash
sudo apt install -y git curl build-essential python3 python3-venv python3-dev nodejs npm acl sqlite3
cd ~/LoreNook
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock && .venv/bin/python -m pip install --no-deps -e .
(cd frontend && npm ci && npm run build)
mkdir -p deploy data backups && chmod 700 data backups
printf '%s\n' 'LORENOOK_DATABASE_URL=sqlite:///data/lorenook.db' 'LORENOOK_ICP_NUMBER=<备案号>' > deploy/lorenook.env && chmod 600 deploy/lorenook.env
set -a; source deploy/lorenook.env; set +a
.venv/bin/python -m alembic upgrade head
```

Node must be `^20.19.0 || >=22.12.0`. The app doesn't load `.env` or migrate on startup. On a new empty database, create the first administrator with `backend.cli user add <name> --admin`.

### `deploy/lorenook.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `LORENOOK_DATABASE_URL` | `sqlite:///data/lorenook.db` | Database |
| `LORENOOK_MEDIA_DIRECTORY` / `LORENOOK_IMAGE_DIRECTORY` | `data/media` / `data/images` | Uploads and illustrations |
| `LORENOOK_ICP_NUMBER` | empty | ICP filing number in the home page footer |
| `LORENOOK_MODEL_EXTRA_NETWORKS` | empty | Comma-separated networks users' model addresses may resolve to besides public ones. Set `198.18.0.0/15` if the server's DNS answers with a proxy's fake IPs, or every user's model call is refused. In that setup the proxy, not LoreNook, decides where a name finally goes. |
| `LORENOOK_COOKIE_SECURE` | `1` | Session cookie only over HTTPS. `0` only for plain-http testing on a LAN address. |
| `LORENOOK_API_DOCS` | `0` | `1` serves `/docs` and `/openapi.json` (development) |

`LORENOOK_ADMIN_USERNAME` and `LORENOOK_ADMIN_PASSWORD` are read only by the v3 migration; don't keep them in the file.

### `deploy/lorenook.service`

One worker, no `--reload`. The long graceful shutdown lets in-flight model calls finish.

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

```bash
sudo systemctl enable --now "$HOME/LoreNook/deploy/lorenook.service"
```

### LAN Caddy

Let the `caddy` user read the build:

```bash
sudo setfacl -m u:caddy:--x /home/samuel /home/samuel/LoreNook /home/samuel/LoreNook/frontend
sudo setfacl -R -m u:caddy:r-X /home/samuel/LoreNook/frontend/dist
```

Add inside the existing `:8080` block in `/etc/caddy/Caddyfile` (keep the final `handle { abort }`):

```caddyfile
@lorenook host lorenook.cryingstray.cn
handle @lorenook {
    encode gzip
    @lorenook_backend path /api /api/* /health
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

Login throttling uses the visitor's address from `X-Forwarded-For`. The cloud Caddy sets it; let the LAN Caddy keep it by trusting the tunnel, in the global options block:

```caddyfile
{
    servers {
        trusted_proxies static 127.0.0.1/32 ::1/128
    }
}
```

Without it every visitor looks like `127.0.0.1` and throttling falls back to per-username only.

Don't strip `/api` (no `handle_path`). Generation and archiving can take minutes — no short timeouts or automatic retries anywhere in the proxy chain. Illustration progress is a server-sent event stream (`/api/chats/{id}/illustrations/progress`) and must not be buffered; it sends `Cache-Control: no-transform` so `encode` leaves it alone.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && sudo systemctl reload caddy
```

### Cloud Caddy

```caddyfile
lorenook.cryingstray.cn {
    reverse_proxy 127.0.0.1:8080
}
```

Make sure frps port 8080 isn't publicly reachable.

### Nightly backup

`deploy/lorenook-backup.sh` (mode 700) keeps 14 days of database snapshots and uploaded images:

```bash
#!/bin/sh
set -eu
cd /home/samuel/LoreNook
umask 077
stamp=$(date +%Y%m%d-%H%M%S)
sqlite3 data/lorenook.db ".backup 'backups/nightly-$stamp.db'"
tar -czf "backups/nightly-$stamp-files.tar.gz" -C data images media
find backups -maxdepth 1 -name 'nightly-*' -mtime +14 -delete
```

`deploy/lorenook-backup.service`:

```ini
[Unit]
Description=LoreNook nightly backup

[Service]
Type=oneshot
User=samuel
ExecStart=/home/samuel/LoreNook/deploy/lorenook-backup.sh
```

`deploy/lorenook-backup.timer`:

```ini
[Unit]
Description=LoreNook nightly backup

[Timer]
OnCalendar=*-*-* 04:30
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl link "$HOME/LoreNook/deploy/lorenook-backup.service"
sudo systemctl enable --now "$HOME/LoreNook/deploy/lorenook-backup.timer"
systemctl list-timers lorenook-backup.timer
```
