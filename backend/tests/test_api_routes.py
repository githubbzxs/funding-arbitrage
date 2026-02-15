from app.main import app


def _route_paths() -> set[str]:
    return {route.path for route in app.router.routes}


def test_config_credentials_routes_registered() -> None:
    paths = _route_paths()
    assert "/api/config/credentials" in paths
    assert "/api/config/credentials/" in paths
    assert "/api/config/credentials/{exchange}" in paths


def test_legacy_credentials_routes_still_registered() -> None:
    paths = _route_paths()
    assert "/api/credentials" in paths
    assert "/api/credentials/" in paths
    assert "/api/credentials/{exchange}" in paths


def test_terminal_routes_registered() -> None:
    paths = _route_paths()
    assert "/api/templates" in paths
    assert "/api/templates/" in paths
    assert "/api/templates/{template_id}" in paths
    assert "/api/risk-events" in paths
    assert "/api/risk-events/{event_id}/resolve" in paths
