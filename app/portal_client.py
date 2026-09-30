"""Read-only HTTP client for the observed Urja Meter Ops portal protocol."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote, urlencode

import httpx

from app.config import PORTAL_BASE_URL, PORTAL_PASSWORD, PORTAL_TIMEOUT_SECONDS, PORTAL_USERNAME


class PortalError(RuntimeError):
    """Safe-to-display portal error without response bodies or credentials."""


class PortalClient:
    """Owns an authenticated cookie session and signs the portal's bulk export."""

    def __init__(self) -> None:
        if not PORTAL_USERNAME or not PORTAL_PASSWORD:
            raise PortalError("Set PORTAL_USERNAME and PORTAL_PASSWORD before syncing portal data.")
        self._client = httpx.Client(
            base_url=PORTAL_BASE_URL,
            timeout=httpx.Timeout(PORTAL_TIMEOUT_SECONDS),
            follow_redirects=True,
            headers={"User-Agent": "FlockMeterAPI/1.0 (read-only integration)"},
        )
        self._signing_secret: str | None = None

    def close(self) -> None:
        self._client.close()

    def _login(self) -> None:
        """Use the same SvelteKit form action used by the portal sign-in page."""
        try:
            self._client.get("/login")
            response = self._client.post(
                "/login",
                data={"email": PORTAL_USERNAME, "password": PORTAL_PASSWORD},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": PORTAL_BASE_URL,
                    "Referer": f"{PORTAL_BASE_URL}/login",
                    "x-sveltekit-action": "true",
                },
            )
            if response.status_code >= 400:
                raise PortalError(f"Portal sign-in failed with HTTP {response.status_code}.")
            # SvelteKit actions return a JSON action result rather than a normal redirect.
            # A second 401 check against /portal/keys confirms whether the action succeeded.
            self._signing_secret = None
        except httpx.HTTPError as error:
            raise PortalError("Portal sign-in request failed; check network access and portal availability.") from error

    def _keys(self, *, allow_login: bool = True) -> dict:
        try:
            response = self._client.get("/portal/keys")
            if response.status_code == 401 and allow_login:
                self._login()
                response = self._client.get("/portal/keys")
            if response.status_code == 401:
                raise PortalError("Portal session was not accepted after sign-in.")
            if response.status_code >= 400:
                raise PortalError(f"Portal key endpoint returned HTTP {response.status_code}.")
            payload = response.json()
            secret = payload.get("data", {}).get("signingSecret")
            if not isinstance(secret, str) or not secret:
                raise PortalError("Portal key response did not contain a signing secret.")
            return payload
        except httpx.HTTPError as error:
            raise PortalError("Could not establish a portal session.") from error
        except ValueError as error:
            raise PortalError("Portal key endpoint returned invalid JSON.") from error

    def _signed_get(self, path: str, query: str) -> dict:
        if self._signing_secret is None:
            self._signing_secret = self._keys()["data"]["signingSecret"]
        timestamp = str(int(time.time()))
        message = "\n".join(["GET", path, query, timestamp]).encode("utf-8")
        signature = hmac.new(self._signing_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        try:
            response = self._client.get(
                f"{path}?{query}",
                headers={"x-timestamp": timestamp, "x-signature": signature},
            )
            if response.status_code == 401:
                self._signing_secret = None
                self._login()
                self._signing_secret = self._keys(allow_login=False)["data"]["signingSecret"]
                timestamp = str(int(time.time()))
                message = "\n".join(["GET", path, query, timestamp]).encode("utf-8")
                signature = hmac.new(self._signing_secret.encode(), message, hashlib.sha256).hexdigest()
                response = self._client.get(path + "?" + query, headers={"x-timestamp": timestamp, "x-signature": signature})
            if response.status_code >= 400:
                raise PortalError(f"Portal read endpoint returned HTTP {response.status_code}.")
            return response.json()
        except httpx.HTTPError as error:
            raise PortalError("Portal read request failed; check network access and portal availability.") from error
        except ValueError as error:
            raise PortalError("Portal read endpoint returned invalid JSON.") from error

    def _get_json(self, path: str) -> dict:
        try:
            response = self._client.get(path)
            if response.status_code == 401:
                self._login()
                response = self._client.get(path)
            if response.status_code >= 400:
                raise PortalError(f"Portal read endpoint returned HTTP {response.status_code}.")
            return response.json()
        except httpx.HTTPError as error:
            raise PortalError("Portal read request failed; check network access and portal availability.") from error
        except ValueError as error:
            raise PortalError("Portal read endpoint returned invalid JSON.") from error

    def export_meters(self) -> list[dict]:
        """Fetch the portal's signed bulk export; it contains every meter, not one UI page."""
        payload = self._signed_get("/portal/export", urlencode({"page": 1}))
        items = payload.get("data")
        if not isinstance(items, list):
            raise PortalError("Portal export response did not contain a meter list.")
        return items

    def list_transformers(self) -> list[dict]:
        """Read every 20-item page from the distribution-transformer listing."""
        first = self._get_json("/portal/dts?page=1")
        items = first.get("data")
        total = first.get("total")
        if not isinstance(items, list) or not isinstance(total, int):
            raise PortalError("Transformer response is missing its data or total fields.")
        page_size = 20
        pages = (total + page_size - 1) // page_size
        if pages > 100:
            raise PortalError("Portal reported an unexpectedly large transformer page count.")
        for page in range(2, pages + 1):
            payload = self._get_json(f"/portal/dts?page={page}")
            page_items = payload.get("data")
            if not isinstance(page_items, list):
                raise PortalError("Transformer page response did not contain a data list.")
            items.extend(page_items)
        return items

    def meter_energy(self, meter_id: str) -> list[dict]:
        """Fetch the meter detail page's recent half-hourly register observations."""
        payload = self._get_json(f"/portal/meters/{quote(meter_id, safe='')}/energy")
        items = payload.get("data")
        if not isinstance(items, list):
            raise PortalError("Energy response did not contain a readings list.")
        return items
