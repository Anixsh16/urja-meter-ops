"""Reproduce only requests made by the portal's normal login and export UI."""

import asyncio
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

from urja.config import Settings
from urja.errors import ServiceError, protocol_error


class PortalClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.portal_url,
            transport=transport,
            follow_redirects=False,
            timeout=httpx.Timeout(15, connect=5, pool=5),
            limits=httpx.Limits(max_connections=settings.upstream_concurrency),
            headers={"User-Agent": "UrjaMeterAPI/1.0 (read-only integration)"},
        )
        # The portal can carry session state; serialize an entire logical operation,
        # including auth refresh, so cookie/token changes cannot race a signed export.
        self.lock = asyncio.Lock()
        self.authenticated = False
        self.semaphore = asyncio.Semaphore(settings.upstream_concurrency)

    async def close(self):
        await self.http.aclose()

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(2):
            try:
                response = await self.http.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                if method == "GET" and attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise ServiceError(
                    "upstream_timeout", "The portal did not respond in time.", 504
                ) from exc
            except httpx.RequestError as exc:
                if method == "GET" and attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise ServiceError(
                    "upstream_unavailable", "The portal is unreachable.", 503
                ) from exc
            if method == "GET" and response.status_code in {502, 503, 504} and attempt == 0:
                await asyncio.sleep(0.2)
                continue
            return response
        raise AssertionError("unreachable")

    async def _login(self):
        response = await self._send(
            "POST",
            "/login",
            data={
                "email": self.settings.portal_username,
                "password": self.settings.portal_password.get_secret_value(),
            },
            headers={
                "Origin": self.settings.portal_url,
                "Referer": self.settings.portal_url + "/login",
            },
        )
        redirected = (
            response.status_code in {302, 303} and response.headers.get("location") == "/meters"
        )
        try:
            body = response.json()
            redirected |= body.get("type") == "redirect" and body.get("location") == "/meters"
        except (ValueError, AttributeError):
            pass
        if not redirected or not self.http.cookies:
            raise ServiceError(
                "upstream_auth", "Portal authentication failed; check server configuration.", 503
            )
        self.authenticated = True

    @staticmethod
    def _expired(response: httpx.Response) -> bool:
        return (
            response.status_code == 401
            or (
                response.status_code in {302, 303, 307, 308}
                and "/login" in response.headers.get("location", "")
            )
            or (
                "text/html" in response.headers.get("content-type", "")
                and ("Sign in" in response.text or 'name="password"' in response.text)
            )
        )

    async def _json(self, path: str, **kwargs):
        for attempt in range(2):
            response = await self._send("GET", path, **kwargs)
            if self._expired(response):
                self.authenticated = False
                if attempt == 0:
                    await self._login()
                    # Signed calls must rebuild their signature with the new session.
                    if path.startswith("/portal/export"):
                        raise ServiceError("session_changed", "Session changed during export.", 503)
                    continue
                raise ServiceError(
                    "upstream_auth", "The portal session could not be restored.", 503
                )
            if response.status_code == 404:
                raise ServiceError("not_found", "Meter not found.", 404)
            if response.status_code == 429:
                raise ServiceError(
                    "upstream_rate_limit", "The portal is rate limiting requests. Try later.", 503
                )
            if response.status_code >= 500:
                raise ServiceError(
                    "upstream_unavailable", "The portal is temporarily unavailable.", 503
                )
            if response.status_code != 200:
                raise ServiceError("upstream_rejected", "The portal rejected the read request.")
            try:
                value = response.json()
            except ValueError as exc:
                raise protocol_error() from exc
            if not isinstance(value, dict) or "data" not in value:
                raise protocol_error()
            return value
        raise AssertionError("unreachable")

    async def catalog(self) -> list[dict]:
        async with self.semaphore, self.lock:
            if not self.authenticated:
                await self._login()
            for attempt in range(2):
                keys = await self._json("/portal/keys")
                try:
                    secret = keys["data"]["signingSecret"]
                    timestamp = str(int(time.time()))
                    query = urlencode({"page": 1})
                    message = "\n".join(["GET", "/portal/export", query, timestamp])
                    signature = hmac.new(
                        secret.encode(), message.encode(), hashlib.sha256
                    ).hexdigest()
                except (KeyError, TypeError, AttributeError) as exc:
                    raise protocol_error() from exc
                try:
                    result = await self._json(
                        "/portal/export?" + query,
                        headers={"x-timestamp": timestamp, "x-signature": signature},
                    )
                except ServiceError as exc:
                    if exc.code == "session_changed" and attempt == 0:
                        continue
                    raise
                rows = result["data"]
                if not isinstance(rows, list) or result.get("total") != len(rows):
                    raise ServiceError(
                        "incomplete_export",
                        "Portal export is incomplete; refusing partial results.",
                    )
                if not all(isinstance(row, dict) for row in rows):
                    raise protocol_error()
                return rows
        raise AssertionError("unreachable")

    async def energy(self, meter_id: str, from_date=None, to_date=None) -> list[dict]:
        async with self.semaphore, self.lock:
            if not self.authenticated:
                await self._login()
            params = {}
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()
            result = await self._json(f"/portal/meters/{meter_id}/energy", params=params)
            if not isinstance(result["data"], list):
                raise protocol_error()
            return result["data"]
