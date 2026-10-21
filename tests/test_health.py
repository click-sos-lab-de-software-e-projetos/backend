from app.main import app, health_check


def test_health_check_returns_ok() -> None:
    health_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/health"
    )
    assert "GET" in health_route.methods
    assert health_check() == {"status": "ok"}