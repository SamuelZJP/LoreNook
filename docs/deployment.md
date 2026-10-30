# Deployment

Production runs on Ubuntu 26.04 at `192.168.31.64`, in `/home/samuel/LoreNook`, as user `samuel`.

```text
https://lorenook.cryingstray.cn
  → Cloud Caddy (HTTPS + Authelia)
  → frp TCP tunnel
  → LAN Caddy :8080 (host routing)
      ├─ pages/assets → frontend/dist/
      └─ /api, /health, /docs → Uvicorn 127.0.0.1:18780 → data/lorenook.db
```

Machine-local files (not in Git): `deploy/lorenook.env`, `deploy/lorenook.service`, `data/` (database and `data/images/`), `backups/`. Their contents are reproduced below for reconstruction.

## Update

Wait for running generation/archive work to finish first. Illustration jobs still running at shutdown are marked failed on the next start. Uvicorn must run a single worker: the illustration queue is in-process.

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
curl --fail http://127.0.0.1:18780/api/chats
```

Run it step by step and stop on any failure. Code-only changes don't need a Caddy reload.

## Routine

```bash
sudo systemctl status lorenook --no-pager
sudo journalctl -u lorenook -f
sudo systemctl restart lorenook
```

`/health` only shows the process is up; `/api/chats` also checks the database. After an archive failure, use retry in the UI — don't re-confirm the candidate.

## Backup and restore

There is no scheduled backup. Take one manually when needed (the update procedure always snapshots first):

```bash
cd ~/LoreNook && umask 077 && sqlite3 data/lorenook.db ".backup 'backups/manual-$(date +%Y%m%d-%H%M%S).db'"
```

Database backups don't include `data/images/`; copy that folder separately to keep the illustrations.

Backups contain model API keys. They are kept on the same machine only.

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
echo 'LORENOOK_DATABASE_URL=sqlite:///data/lorenook.db' > deploy/lorenook.env && chmod 600 deploy/lorenook.env
set -a; source deploy/lorenook.env; set +a
.venv/bin/python -m alembic upgrade head
```

Node must be `^20.19.0 || >=22.12.0`. The app doesn't load `.env` or migrate on startup.

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

Don't strip `/api` (no `handle_path`). Generation and archiving can take minutes — no short timeouts or automatic retries anywhere in the proxy chain.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && sudo systemctl reload caddy
```

### Cloud Caddy

```caddyfile
lorenook.cryingstray.cn {
    import protected
    reverse_proxy 127.0.0.1:8080
}
```

Make sure Authelia requires login for this host and frps port 8080 isn't publicly reachable.
