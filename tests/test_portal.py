import asyncio
import hashlib
import hmac

import httpx
import pytest

from tests.fakes import row, settings
from urja.errors import ServiceError
from urja.portal import PortalClient


def login_response():
    return httpx.Response(
        200,
        json={"type": "redirect", "status": 303, "location": "/meters"},
        headers={"set-cookie": "session=test; Path=/; Secure; HttpOnly"},
    )


async def test_real_protocol_shape_origin_cookie_and_signed_export():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/login":
            assert request.headers["origin"] == "https://urja-ops.flockenergy.tech"
            assert b"email=test%40example.invalid" in request.content
            return login_response()
        assert "session=test" in request.headers["cookie"]
        if request.url.path == "/portal/keys":
            return httpx.Response(200, json={"data": {"signingSecret": "fixture-secret"}})
        assert request.url.query == b"page=1"
        message = "\n".join(["GET", "/portal/export", "page=1", request.headers["x-timestamp"]])
        expected = hmac.new(b"fixture-secret", message.encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(request.headers["x-signature"], expected)
        return httpx.Response(200, json={"data": [row()], "total": 1})

    client = PortalClient(settings(), httpx.MockTransport(handler))
    assert len(await client.catalog()) == 1
    assert calls == ["/login", "/portal/keys", "/portal/export"]
    await client.close()


async def test_concurrent_calls_share_login_and_expired_cookie_restored_once():
    logins = [0]
    expired = [False]

    def handler(request):
        if request.url.path == "/login":
            logins[0] += 1
            return login_response()
        if expired[0]:
            expired[0] = False
            return httpx.Response(302, headers={"location": "/login"})
        return httpx.Response(200, json={"data": []})

    client = PortalClient(settings(), httpx.MockTransport(handler))
    await asyncio.gather(*(client.energy("T001") for _ in range(5)))
    assert logins[0] == 1
    expired[0] = True
    assert await client.energy("T001") == []
    assert logins[0] == 2
    await client.close()


async def test_expiry_during_signed_export_rebuilds_signature():
    exports = [0]
    logins = [0]

    def handler(request):
        if request.url.path == "/login":
            logins[0] += 1
            return login_response()
        if request.url.path == "/portal/keys":
            return httpx.Response(200, json={"data": {"signingSecret": f"key-{logins[0]}"}})
        exports[0] += 1
        if exports[0] == 1:
            return httpx.Response(401, json={"error": "expired"})
        message = "\n".join(["GET", "/portal/export", "page=1", request.headers["x-timestamp"]])
        assert (
            request.headers["x-signature"]
            == hmac.new(b"key-2", message.encode(), hashlib.sha256).hexdigest()
        )
        return httpx.Response(200, json={"data": [row()], "total": 1})

    client = PortalClient(settings(), httpx.MockTransport(handler))
    assert len(await client.catalog()) == 1
    assert logins[0] == 2
    await client.close()


@pytest.mark.parametrize(
    "response,code,status",
    [
        (httpx.Response(404, json={"error": "not_found"}), "not_found", 404),
        (httpx.Response(429), "upstream_rate_limit", 503),
        (httpx.Response(503), "upstream_unavailable", 503),
        (httpx.Response(200, text="garbled"), "upstream_protocol", 502),
        (httpx.Response(200, json=[]), "upstream_protocol", 502),
        (httpx.Response(403), "upstream_rejected", 502),
    ],
)
async def test_portal_failures_are_bounded_and_translated(response, code, status):
    calls = []

    def handler(request):
        if request.url.path == "/login":
            return login_response()
        calls.append(request)
        return response

    client = PortalClient(settings(), httpx.MockTransport(handler))
    with pytest.raises(ServiceError) as error:
        await client.energy("T001")
    assert error.value.code == code and error.value.status == status
    assert len(calls) <= 2
    await client.close()


async def test_timeout_retried_once_and_auth_failure_not_looped():
    calls = [0]

    def handler(request):
        if request.url.path == "/login":
            return login_response()
        calls[0] += 1
        raise httpx.ReadTimeout("fixture timeout")

    client = PortalClient(settings(), httpx.MockTransport(handler))
    with pytest.raises(ServiceError, match="did not respond") as error:
        await client.energy("T001")
    assert error.value.status == 504 and calls[0] == 2
    await client.close()
    calls[0] = 0

    def failed_login(request):
        calls[0] += 1
        return httpx.Response(403, text="Forbidden")

    client = PortalClient(settings(), httpx.MockTransport(failed_login))
    with pytest.raises(ServiceError) as error:
        await client.energy("T001")
    assert error.value.code == "upstream_auth" and calls[0] == 1
    await client.close()


async def test_incomplete_export_fails_instead_of_silently_truncating():
    def handler(request):
        if request.url.path == "/login":
            return login_response()
        if request.url.path == "/portal/keys":
            return httpx.Response(200, json={"data": {"signingSecret": "fixture"}})
        return httpx.Response(200, json={"data": [row()], "total": 2})

    client = PortalClient(settings(), httpx.MockTransport(handler))
    with pytest.raises(ServiceError) as error:
        await client.catalog()
    assert error.value.code == "incomplete_export"
    await client.close()
