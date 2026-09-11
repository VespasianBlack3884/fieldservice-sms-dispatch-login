from __future__ import annotations

import asyncio

import pytest

from fieldservice_login.dispatch_service import DispatchLoginService, DispatchStatus, WorkOrder


class RecordingSms:
    def __init__(self) -> None:
        self.verified: list[tuple[str, str, str]] = []

    async def request_code(self, to: str, attempt_id: str) -> dict:
        return {"accepted": True}

    async def verify_code(self, to: str, code: str, attempt_id: str) -> dict:
        self.verified.append((to, code, attempt_id))
        return {"verified": True}


def test_matching_technician_confirmation_acknowledges_dispatch() -> None:
    order = WorkOrder(
        work_order_id="WO-1042",
        technician_id="tech-17",
        technician_phone="+15551234567",
    )
    sms = RecordingSms()
    login = DispatchLoginService(sms, {order.work_order_id: order})

    confirmed = asyncio.run(
        login.confirm_login("WO-1042", "tech-17", "attempt-42", "381204")
    )

    assert confirmed.status is DispatchStatus.TECHNICIAN_CONFIRMED
    assert sms.verified == [("+15551234567", "381204", "verify:attempt-42")]


def test_other_technician_cannot_acknowledge_dispatch() -> None:
    order = WorkOrder(
        work_order_id="WO-1042",
        technician_id="tech-17",
        technician_phone="+15551234567",
    )
    login = DispatchLoginService(RecordingSms(), {order.work_order_id: order})

    with pytest.raises(PermissionError):
        asyncio.run(
            login.confirm_login("WO-1042", "tech-99", "attempt-43", "381204")
        )

    assert order.status is DispatchStatus.DISPATCHED
