from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .dispatch_service import DispatchLoginService, TechnicianFollowUp, WorkOrder, WorkOrderPhoto
from .infrai_sms import InfraiError, InfraiSms


class StartLoginRequest(BaseModel):
    work_order_id: str
    technician_id: str
    attempt_id: str = Field(min_length=8)


class VerifyLoginRequest(StartLoginRequest):
    code: str = Field(min_length=4, max_length=10)


demo_orders = {
    "WO-1042": WorkOrder(
        work_order_id="WO-1042",
        technician_id="tech-17",
        technician_phone="+15551234567",
        photos=[WorkOrderPhoto(object_key="orders/WO-1042/front-door.jpg", caption="Front door")],
        follow_up=TechnicianFollowUp(required=True, note="Bring the replacement keypad"),
    )
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    gateway = InfraiSms()
    app.state.login_service = DispatchLoginService(gateway, demo_orders)
    yield
    await gateway.close()


api = FastAPI(title="Field-service SMS login", lifespan=lifespan)


def service(request: Request) -> DispatchLoginService:
    return request.app.state.login_service


@api.post("/login/code", response_model=WorkOrder)
async def send_login_code(body: StartLoginRequest, request: Request) -> WorkOrder:
    try:
        return await service(request).start_login(
            body.work_order_id, body.technician_id, body.attempt_id
        )
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@api.post("/login/verify", response_model=WorkOrder)
async def verify_login_code(body: VerifyLoginRequest, request: Request) -> WorkOrder:
    try:
        return await service(request).confirm_login(
            body.work_order_id, body.technician_id, body.attempt_id, body.code
        )
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

