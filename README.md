# Maxwell

Maxwell is a Discord self-client experiment with an OpenAI-compatible/Ollama-style model backend, tools, temporary site generation, and a small web dashboard/admin API.

## Security Notes

This project can store Discord message content, user IDs, generated sites, prompts, and admin data. Fresh defaults are conservative, but you must explicitly review settings before deploying.

- Do not commit `.env`, `data/`, logs, PM2 dumps, generated `public/bot/` sites, or real Caddy basic-auth hashes.
- Set `MAXWELL_ADMIN_USER` and `MAXWELL_ADMIN_PASSWORD`; the API does not bootstrap or persist admin credentials.
- Serve generated `/bot/*` sites on a separate sandbox origin if possible. Arbitrary generated HTML on the same origin as admin pages can steal browser-local credentials.
- `discord.py-self` and `self_bot=True` may violate Discord Terms of Service. Use at your own risk or refactor to a normal bot account before public deployment.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, then run:

```bash
python bot.py
python api/api_server.py
```

With PM2:

```bash
pm2 start ecosystem.config.js
```

## Web

Static dashboard files live in `web/`. A deployment can copy `web/index.html` and `web/admin/index.html` to a web root, then reverse proxy `/api/*` and `/data/*` to `MAXWELL_API_HOST:MAXWELL_API_PORT`.

See `examples/Caddyfile.example` for a sanitized reverse proxy example.

## License

MIT. See `LICENSE`.
