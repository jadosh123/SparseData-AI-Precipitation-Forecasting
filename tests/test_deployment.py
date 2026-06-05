"""
Deployment smoke tests — validate the app is correctly configured for AWS.
These run against the actual app and DB; they need the environment set up
(DB exists, demo snapshot loaded, static files present).
"""
import pytest
from fastapi.testclient import TestClient

from weather_engine.api import app

client = TestClient(app, raise_server_exceptions=True)


def test_homepage_loads():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "map-section" in r.text


def test_demo_map_loads():
    """Demo endpoint must work without a live DB — it uses the bundled snapshot."""
    r = client.get("/demo")
    assert r.status_code == 200
    assert "map-section" in r.text


def test_demo_navigation():
    r_right = client.get("/demo?direction=right&horizon=precipitation_t1&idx=0")
    assert r_right.status_code == 200

    r_left = client.get("/demo?direction=left&horizon=precipitation_t1&idx=1")
    assert r_left.status_code == 200


def test_all_demo_horizons():
    for horizon in ["precipitation_t1", "precipitation_t3", "precipitation_t6", "precipitation_t12"]:
        r = client.get(f"/demo?horizon={horizon}")
        assert r.status_code == 200, f"Failed for horizon: {horizon}"


def test_static_title_gif():
    r = client.get("/static/title.gif")
    assert r.status_code == 200


def test_static_ims_logo():
    r = client.get("/static/ims_logo.png")
    assert r.status_code == 200


def test_inference_pipeline_imports():
    """All inference dependencies must be importable — catches missing packages on deploy."""
    import weather_engine.inference_pipeline  # noqa: F401
