import base64
import asyncio
import importlib
import json


def test_rem_status_payload_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.api_server as api_server
    api = importlib.reload(api_server)
    status = api._load_rem_status()
    assert {"enabled", "interval_s", "max_turns", "prompt", "last_run", "events_buffered", "last_audit_preview", "running"} <= set(status)


def test_rem_control_sanitizes_dream_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.api_server as api_server
    api = importlib.reload(api_server)
    api._rem_control_path().write_text(json.dumps({"enabled": True, "interval_seconds": 3, "max_turns": 99, "prompt": "dream"}), encoding="utf-8")
    control = api._load_rem_control()
    assert control["enabled"] is True
    assert control["interval_seconds"] == 10
    assert control["max_turns"] == 10
    assert control["prompt"] == "dream"


def test_api_mutation_auth_middleware(monkeypatch):
    monkeypatch.setenv("MAXWELL_ADMIN_USER", "admin")
    monkeypatch.setenv("MAXWELL_ADMIN_PASSWORD", "pw")
    import api.api_server as api_server
    api = importlib.reload(api_server)

    class Req:
        method = "POST"
        path = "/api/rem/run"
        headers = {}

    async def handler(request):
        return "ok"

    async def run():
        mw = await api._auth_middleware_unless_login(None, handler)
        res = await mw(Req())
        assert res.status == 401
        token = base64.b64encode(b"admin:pw").decode()
        Req.headers = {"Authorization": f"Basic {token}"}
        assert await mw(Req()) == "ok"
    asyncio.run(run())
