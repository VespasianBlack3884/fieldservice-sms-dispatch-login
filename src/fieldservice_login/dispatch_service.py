from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

class DispatchStatus(StrEnum):
    DISPATCHED = "dispatched"
    TECHNICIAN_CONFIRMED = "technician_confirmed"


@dataclass
class WorkOrderPhoto:
    object_key: str
    caption: str


@dataclass
class TechnicianFollowUp:
    required: bool = False
    note: str | None = None


@dataclass
class WorkOrder:
    work_order_id: str
    technician_id: str
    technician_phone: str
    status: DispatchStatus = DispatchStatus.DISPATCHED
    photos: list[WorkOrderPhoto] = field(default_factory=list)
    follow_up: TechnicianFollowUp = field(default_factory=TechnicianFollowUp)


class SmsGateway(Protocol):
    async def request_code(self, to: str, attempt_id: str) -> dict: ...

    async def verify_code(self, to: str, code: str, attempt_id: str) -> dict: ...


@dataclass
class DispatchLoginService:
    sms: SmsGateway
    work_orders: dict[str, WorkOrder]

    async def start_login(
        self, work_order_id: str, technician_id: str, attempt_id: str
    ) -> WorkOrder:
        order = self._assigned_order(work_order_id, technician_id)
        await self.sms.request_code(order.technician_phone, f"otp:{attempt_id}")
        return order

    async def confirm_login(
        self, work_order_id: str, technician_id: str, attempt_id: str, code: str
    ) -> WorkOrder:
        order = self._assigned_order(work_order_id, technician_id)
        await self.sms.verify_code(
            order.technician_phone, code, f"verify:{attempt_id}"
        )
        order.status = DispatchStatus.TECHNICIAN_CONFIRMED
        return order

    def _assigned_order(self, work_order_id: str, technician_id: str) -> WorkOrder:
        order = self.work_orders.get(work_order_id)
        if order is None:
            raise LookupError("work order was not found")
        if order.technician_id != technician_id:
            raise PermissionError("work order belongs to another technician")
        return order
