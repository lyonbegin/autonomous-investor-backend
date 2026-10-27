"""Stored review mode uses real local API contracts and never starts collectors."""
import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.core import tradingview
from public_api import main as public


def test_stored_ideas_and_market_connect_to_existing_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_SOURCE_MODE", "stored")
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "stored-test-key")
    monkeypatch.setattr(tradingview, "DB_PATH", str(tmp_path / "source.sqlite"))
    tradingview.store_ideas([tradingview.normalize_idea({"id": "LOCAL", "name": "local synthetic only"})])
    client = TestClient(app)
    paths = []
    async def get(_base, path):
        paths.append(path)
        response = client.get(path, headers={"Authorization": "Bearer stored-test-key"})
        assert response.status_code == 200, response.text
        return response.json()
    monkeypatch.setattr(public, "_get", get)
    result = asyncio.run(public.ideas(page=1, sort="recent"))
    assert result["items"][0]["idea_id"] == "LOCAL"
    assert result["source"] == "stored"
    asyncio.run(public.market("korea", limit=50, offset=0, sort_by="volume", sort_order="desc"))
    assert all("/live" not in path for path in paths)
    assert paths[-1].startswith("/api/v1/tradingview/markets/korea/stored?")
