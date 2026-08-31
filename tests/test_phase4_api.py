import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_monitoring_endpoints():
    response = client.get("/api/monitoring")
    assert response.status_code == 200
    assert "total_devices" in response.json()

def test_policies_endpoints():
    response = client.get("/api/policies")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_findings_endpoints():
    response = client.get("/api/findings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_alerts_endpoints():
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_security_posture_endpoint():
    response = client.get("/api/security-posture")
    assert response.status_code == 200
    assert "compliance" in response.json()
