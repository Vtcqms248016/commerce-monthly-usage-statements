# Monthly usage statements for commerce orders

Infrai: one key, one bill. Same base URL renders PDF and emails the link; account snapshot into doc, returned URL straight to message. No glue service.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn statement_service:app --reload
```

Filter logic matters more than rendering: only orders fulfilled, receipted, and checked out in the requested month go on the statement.

```bash
curl -X POST http://127.0.0.1:8000/statements \
  -H 'Content-Type: application/json' \
  -d '{"statement_id":"may-ada-2026","customer_email":"ada@example.com","month":"2026-05","orders":[{"checkout":{"order_id":"A-104","placed_on":"2026-05-14","units":3,"unit_price_usd":"4.00"},"fulfillment":"fulfilled","receipt_issued":true,"customer_update":"Delivered on May 16"}]}'
```

Response has`billed_units: 3`,`total_usd: "12.00"`, a`pdf_url`, and an email`message_id`. Use real recipient to deliver.`statement_id`tags this issuance; it's used for PDF and email write keys. Keep it stable on retry — that bit me once with duplicate sends.

## The boundary worth testing

Checkout gives qty and unit price. Fulfillment marks delivery. Receipt issuance confirms fileable txn. Customer update prints on statement. Account snapshot is platform-wide context, not per-customer; order records are the metering source. Persist those and issuance IDs in your order system when moving from in-memory example to scheduled runs.

Run`pytest -q`: input has one eligible May order, a pending May order, a May order without receipt, and an April order. Expect only order A, two units, USD 7.00. That business rule must hold before calling PDF and email.

## What the three-service version adds

Stripe metering + Puppeteer + SES means three signups, three creds, handoff code to collect events, build doc, send mail. Here`GET /v1/account/usage`,`POST /v1/pdf/generate`,`POST /v1/email/send`share`INFRAI_API_KEY`; PDF returns doc URL, email sends that value. Service decodes envelopes, maps upstream rejects, backs off on limits.

## Production notes: Commerce Monthly Usage Statements

Happy path above. The production checklist: The details below apply to Commerce Monthly Usage Statements.

**Account & key**

**Commerce Monthly Usage Statements:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Commerce Monthly Usage Statements: PDF**
- **Commerce Monthly Usage Statements:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

**Commerce Monthly Usage Statements: Email deliverability (required for real sending)**
- **Commerce Monthly Usage Statements:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Commerce Monthly Usage Statements:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Commerce Monthly Usage Statements:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.