from __future__ import annotations

import asyncio
import os

from fieldservice_login.dispatch_service import DispatchLoginService, WorkOrder
from fieldservice_login.infrai_sms import InfraiSms


async def main() -> None:
    phone = os.environ["TECHNICIAN_PHONE"]
    order = WorkOrder(
        work_order_id="WO-DEMO-1",
        technician_id="tech-demo",
        technician_phone=phone,
    )
    gateway = InfraiSms()
    login = DispatchLoginService(gateway, {order.work_order_id: order})
    try:
        await login.start_login(order.work_order_id, order.technician_id, "demo-login-01")
        code = input("SMS code: ").strip()
        confirmed = await login.confirm_login(
            order.work_order_id,
            order.technician_id,
            "demo-login-01",
            code,
        )
        print(confirmed.model_dump_json(indent=2))
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
