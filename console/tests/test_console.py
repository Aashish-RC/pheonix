"""Unit tests for Phase 5 & Phase 6 Console Web Application."""

from fastapi.testclient import TestClient
from console.server import create_console_app


def test_console_static_routes():
    app = create_console_app()
    client = TestClient(app)

    # Test root HTML
    res = client.get("/")
    assert res.status_code == 200
    assert "Pheonix | Unified Intelligence & Governance Console" in res.text
    assert "id=\"nav-btn-chat\"" in res.text
    assert "id=\"nav-btn-owner\"" in res.text
    assert "id=\"nav-btn-canvas\"" in res.text

    # Test CSS
    css_res = client.get("/styles.css")
    assert css_res.status_code == 200
    assert "--accent-primary" in css_res.text

    # Test JS
    js_res = client.get("/app.js")
    assert js_res.status_code == 200
    assert "switchTab" in js_res.text

    # Test PWA Manifest
    manifest_res = client.get("/manifest.json")
    assert manifest_res.status_code == 200
    data = manifest_res.json()
    assert data["short_name"] == "Pheonix"
    assert data["display"] == "standalone"


def test_console_api_endpoints():
    app = create_console_app()
    client = TestClient(app)

    # Health API
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["modules_passing"] == 36

    # Tenants API
    tenants_res = client.get("/api/tenants")
    assert tenants_res.status_code == 200
    assert len(tenants_res.json()["tenants"]) == 3

    # Prompt Optimizer API
    opt_res = client.post("/api/prompt/optimize", json={"prompt": "Analyze code security", "target_domain": "security"})
    assert opt_res.status_code == 200
    assert "security" in opt_res.json()["optimized_prompt"]
