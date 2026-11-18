import httpx

from app.config import get_settings
from app.main import create_app


async def test_serves_webapp_from_configured_dir(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>mini app</h1>")
    monkeypatch.setattr(get_settings(), "webapp_dist", str(tmp_path))
    app = create_app(background=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")
    assert r.status_code == 200 and "mini app" in r.text
