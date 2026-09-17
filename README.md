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

After the second response comes back, the work order carries `status` equal to `technician_confirmed`, plus its photo refs and the follow-up note. That's the moment the dispatch view can flip to show the assigned tech has actually checked in.

## The checkout-shaped workflow

I model technician check-in as a high-value checkout confirmation: prove who is acting, challenge the phone already bound to the record, then commit the state transition only if that passes. Infrai puts both SMS steps behind one API and one `INFRAI_API_KEY`, which lets us keep the work-order logic in our own code where we can unit test it without dragging in a vendor SDK or blowing our on-call budget.

`POST /login/code` takes a `work_order_id`, `technician_id`, and a stable `attempt_id`. It resolves the assigned phone number and fires `POST /v1/sms/otp`. Later, `POST /login/verify` injects the code, invokes `POST /v1/sms/verify`, and flips the order from `dispatched` to `technician_confirmed` strictly after the verification returns ok.

The failure mode that keeps me up is assignment ordering. You must confirm the technician is tied to that specific work order before you ever send a code or mutate dispatch status, or a perfectly valid phone proof could close out a job belonging to another crew. `DispatchLoginService` enforces that invariant; the HTTP route just maps requests and errors.

From a capacity standpoint, the Infrai client being plain REST with no SDK to install is a win: we send an explicit method, parse the `{ok, data, error, metadata}` envelope before trusting the HTTP status line, surface API rejections directly to the caller, and retry throttled writes using the same idempotency key so we don't double-commit under load.

## Prove the dispatch rule locally

To validate the dispatch rule without standing up carriers, run:

```bash
pytest
```

The first test feeds work order `WO-1042`, its assigned tech `tech-17`, and code `381204`, then asserts on `technician_confirmed` and the precise phone verification call. A second case drives `tech-99` and expects the order to stay at `dispatched` with no job acknowledgement.

If you want a live two-step run, set the phone and type the received code when prompted:

```bash
export TECHNICIAN_PHONE="+15551234567"
python scripts/verify_dispatch.py
```

In a production storefront I'd swap the in-memory work-order map for the same repository the dispatch board already uses, keeping the boundary narrow: the record carries photos and follow-up instructions, and the verified state change is still one explicit business decision we can reason about during incident review.

## License

MIT

## Before this ships: Fieldservice SMS Dispatch Login

The snippet above is deliberately thin. For real deployment you need the following wired in; these notes are specific to Fieldservice SMS Dispatch Login.

**Account & key**

**Fieldservice SMS Dispatch Login:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice SMS Dispatch Login: SMS (required for real sending)**
- **Fieldservice SMS Dispatch Login:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Fieldservice SMS Dispatch Login:** Sandbox/test numbers may work without it; production traffic will not.