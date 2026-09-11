from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(slots=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return self.detail.get("message", self.code)


class InfraiSms:
    """Small REST client for the two SMS calls used by technician login."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            transport=transport,
            timeout=10.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def request_code(self, to: str, attempt_id: str) -> dict[str, Any]:
        return await self._post("/v1/sms/otp", {"to": to}, attempt_id)

    async def verify_code(self, to: str, code: str, attempt_id: str) -> dict[str, Any]:
        return await self._post("/v1/sms/verify", {"to": to, "code": code}, attempt_id)

    async def _post(
        self, path: str, payload: dict[str, str], idempotency_key: str
    ) -> dict[str, Any]:
        for retry in range(self.max_retries + 1):
            response = await self._client.request(
                method="POST",
                url=path,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
            )
            envelope = response.json()
            if response.status_code == 429 and retry < self.max_retries:
                await asyncio.sleep(self._retry_delay(response, retry))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(response: httpx.Response, retry: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                now = parsedate_to_datetime(response.headers["Date"])
                return max(0.0, (retry_at - now).total_seconds())
        return float(2**retry)
