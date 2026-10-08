import asyncio

import httpx

from app.main import app


def test_health_check_returns_ok() -> None:
    async def request_health_check() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get("/health")

    response = asyncio.run(request_health_check())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
