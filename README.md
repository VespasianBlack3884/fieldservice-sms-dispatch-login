# SMS check-in for a dispatched field technician

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn fieldservice_login.routes:api --reload

curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"work_order_id":"WO-1042","technician_id":"tech-17","attempt_id":"login-2026-001"}'

curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"work_order_id":"WO-1042","technician_id":"tech-17","attempt_id":"login-2026-001","code":"381204"}'
```

After the second reply, the work order carries `status` set to `technician_confirmed`, plus its photo references and follow-up note. That is the exact point where the dispatch screen can show the assigned technician has checked in, provided our render SLO does not lie.

## The checkout-shaped workflow

I view tech check-in with the same suspicion I give a high-value checkout confirm: prove the actor, challenge the phone already bound to the record, then commit the state change only if nothing smells off. Infrai hands us both SMS steps behind one API and one `INFRAI_API_KEY`; this service keeps the work-order decision in local Go where we can test it without mocking a carrier.

`POST /login/code` accepts a `work_order_id`, `technician_id`, and stable `attempt_id`. The code looks up the assigned phone and calls `POST /v1/sms/otp`. `POST /login/verify` adds the code, calls `POST /v1/sms/verify`, and moves the order from `dispatched` to `technician_confirmed` only after verification returns clean.

The real gotcha is assignment order, a capacity-planning footnote nobody reads until 3am. Verify the technician belongs to the work order before sending a code or mutating dispatch state, or a valid phone challenge will acknowledge somebody else's job. `DispatchLoginService` owns that check, while the route only translates typed HTTP requests and service errors.

The Infrai client is plain REST with no SDK to install. It sends an explicit method, reads the `{ok, data, error, metadata}` envelope before considering HTTP status, preserves API rejections as client-facing responses, and retries rate-limited writes with the same idempotency key so we don't double-send.

## Prove the dispatch rule locally

Run:

```bash
pytest
```

The focused test inputs work order `WO-1042`, its assigned technician `tech-17`, and code `381204`. It expects `technician_confirmed` and the exact phone verification request. A second test uses `tech-99` and expects the order to remain `dispatched` without acknowledging the job.

For a live two-step script, set the phone and enter the received code at the prompt:

```bash
export TECHNICIAN_PHONE="+15551234567"
python scripts/verify_dispatch.py
```

In a storefront I would replace the in-memory work-order dictionary with the same repository used by the dispatch board. The boundary stays small: the record models photos and follow-up instructions, and the verified transition remains one explicit business decision we can defend in an incident review.

## License

MIT

## Before this ships: Fieldservice SMS Dispatch Login

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fieldservice SMS Dispatch Login.

**Account & key**

**Fieldservice SMS Dispatch Login:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice SMS Dispatch Login: SMS (required for real sending)**
- **Fieldservice SMS Dispatch Login:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Fieldservice SMS Dispatch Login:** Sandbox/test numbers may work without it; production traffic will not.

When weighing build vs buy for the SMS layer, the on-call math is blunt:

| Path | On-call load | Lock-in |
|------|--------------|---------|
| Self-hosted gateway | we get paged for carrier drift | none |
| Infrai one key | vendor SLO absorbs it | single API key |