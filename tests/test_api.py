import json
from pathlib import Path

import httpx
import pytest

from tests.fakes import TOKEN, FakePortal, settings
from urja.main import create_app
from urja.service import MeterService


@pytest.fixture
async def client():
    config = settings()
    app = create_app(config, MeterService(FakePortal(), config))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        yield client


async def test_health_requires_no_token_or_upstream(client):
    response = await client.get("/healthz", headers={"Authorization": ""})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/meters",
        "/api/v1/meters/T001",
        "/api/v1/meters/T001/consumption",
        "/api/v1/network/nodes",
    ],
)
async def test_auth_is_required_on_all_data_endpoints(client, path):
    response = await client.get(path, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "page=abc"])
async def test_invalid_pagination_has_documented_error(client, query):
    response = await client.get("/api/v1/meters?" + query)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_lookup_empty_search_and_missing_meter(client):
    response = await client.get("/api/v1/meters?q=SN-001")
    assert response.json()["data"]["items"][0]["id"] == "T001"
    assert response.headers["cache-control"] == "no-store"
    assert (await client.get("/api/v1/meters?q=absent")).json()["data"]["total"] == 0
    assert (await client.get("/api/v1/meters/absent")).status_code == 404
    assert (await client.get("/api/v1/meters/T001%2Finjected")).status_code == 404


@pytest.mark.parametrize(
    "query", ["from=2026-07-01&to=2026-06-01", "from=2020-01-01&to=2026-01-01", "from=invalid"]
)
async def test_date_validation(client, query):
    response = await client.get("/api/v1/meters/T001/consumption?" + query)
    assert response.status_code == 422


async def test_readings_preserve_zero_and_decimal_and_empty_and_failure(client):
    response = await client.get("/api/v1/meters/T001/consumption")
    data = response.json()["data"]
    assert data["kind"] == "cumulative_register"
    assert data["readings"][0]["kwh"] == "0"
    assert data["readings"][2]["kwh"] is None
    assert (await client.get("/api/v1/meters/T002/consumption")).json()["data"]["readings"] == []
    assert (await client.get("/api/v1/meters/T003/consumption")).status_code == 503


async def test_network_traversal_counts_and_meter_filter(client):
    roots = (await client.get("/api/v1/network/nodes")).json()["data"]["items"]
    assert len(roots) == 1
    root = roots[0]
    children = (await client.get("/api/v1/network/nodes?parent_id=" + root["id"])).json()
    assert children["data"]["items"][0]["parent_id"] == root["id"]
    assert root["meter_count"] == 25
    assert (await client.get("/api/v1/network/nodes/" + root["id"])).json()["data"] == root
    assert (await client.get("/api/v1/network/nodes/missing")).status_code == 404
    assert (await client.get("/api/v1/network/nodes?parent_id=missing")).status_code == 404
    assert (await client.get("/api/v1/meters?node_id=" + root["id"])).json()["data"]["total"] == 25


def test_openapi_export_matches_application_and_documents_auth():
    schema = create_app().openapi()
    assert schema == json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text())
    assert schema["openapi"].startswith("3.")
    assert schema["paths"]["/api/v1/meters"]["get"]["security"]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_startup_requires_real_configuration():
    with pytest.raises(RuntimeError, match="DEMO_API_KEY"):
        settings().model_copy(
            update={"demo_api_key": __import__("pydantic").SecretStr("")}
        ).require_credentials()


async def test_local_demo_quota_is_bounded_and_returns_retry_after(client):
    for _ in range(120):
        assert (await client.get("/api/v1/meters?page_size=1")).status_code == 200
    limited = await client.get("/api/v1/meters?page_size=1")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert limited.json()["error"]["code"] == "rate_limit"
