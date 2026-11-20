import pytest
import app as app_module
from config import Config
from database import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_monitoring.db")
    monkeypatch.setattr(Config, "DB_PATH", test_db)
    monkeypatch.setattr(Config, "API_KEY", "test-key")
    monkeypatch.setattr(Config, "RAM_THRESHOLD", 90.0)
    monkeypatch.setattr(Config, "CPU_THRESHOLD", 85.0)
    monkeypatch.setattr(Config, "DISK_THRESHOLD", 90.0)
    monkeypatch.setattr(
        app_module,
        "collect_system_metrics",
        lambda: {
            "ram_percent": 45.0,
            "cpu_percent": 20.0,
            "disk_percent": 50.0,
            "uptime_seconds": 120.0,
        },
    )
    app_module.system_state["is_healthy"] = True
    app_module.system_state["failure_reason"] = ""
    init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def test_dashboard_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Cloud Monitoring Node" in response.data


def test_api_status_returns_ok(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "OK"


def test_health_check_ok_and_persists_metric(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "OK"
    assert "response_time_ms" in data

    history = client.get("/api/history").get_json()
    assert len(history["items"]) == 1
    assert history["items"][0]["http_code"] == 200


def test_health_check_fails_when_ram_exceeds_threshold(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "collect_system_metrics",
        lambda: {
            "ram_percent": 95.5,
            "cpu_percent": 20.0,
            "disk_percent": 50.0,
            "uptime_seconds": 125.0,
        },
    )
    response = client.get("/health")
    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "ERROR"
    assert "RAM" in data["message"]


def test_break_requires_valid_api_key(client):
    no_key = client.post("/break", json={"reason": "Test"})
    assert no_key.status_code == 401

    wrong_key = client.post(
        "/break",
        headers={"X-API-Key": "wrong-key"},
        json={"reason": "Test"},
    )
    assert wrong_key.status_code == 401


def test_incident_lifecycle_break_and_fix(client):
    headers = {"X-API-Key": "test-key"}

    break_res = client.post(
        "/break",
        headers=headers,
        json={"reason": "Awaria testowa"},
    )
    assert break_res.status_code == 200

    health_err = client.get("/health")
    assert health_err.status_code == 500
    assert health_err.get_json()["status"] == "ERROR"

    incidents_open = client.get("/api/incidents").get_json()["items"]
    assert len(incidents_open) == 1
    assert incidents_open[0]["status"] == "OPEN"

    fix_res = client.post("/fix", headers=headers)
    assert fix_res.status_code == 200

    health_ok = client.get("/health")
    assert health_ok.status_code == 200

    incidents_closed = client.get("/api/incidents").get_json()["items"]
    assert incidents_closed[0]["status"] == "RESOLVED"
    assert incidents_closed[0]["duration_seconds"] is not None


def test_stats_endpoint_calculates_availability(client):
    headers = {"X-API-Key": "test-key"}
    client.get("/health")
    client.post("/break", headers=headers, json={"reason": "Test SLA"})
    client.get("/health")
    client.post("/fix", headers=headers)

    stats = client.get("/api/stats").get_json()
    assert stats["total_checks"] == 2
    assert stats["successful_checks"] == 1
    assert stats["availability_percent"] == 50.0
    assert stats["total_incidents"] == 1