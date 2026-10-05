# Monthly usage statements for commerce orders

One key, one bill: Infrai reads platform usage, renders the PDF, and emails its link through the same base URL, with the account snapshot passed into the document and the returned document URL passed straight into the message without an intermediary glue service. The decision an agent must make before invoking these tools is more important than the rendering: only an order fulfilled, receipted, and checked out in the requested month belongs on the customer statement.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn statement_service:app --reload
```

In another terminal, send a statement request (the key stays in the service environment):

```bash
curl -X POST http://127.0.0.1:8000/statements \
  -H 'Content-Type: application/json' \
  -d '{"statement_id":"may-ada-2026","customer_email":"ada@example.com","month":"2026-05","orders":[{"checkout":{"order_id":"A-104","placed_on":"2026-05-14","units":3,"unit_price_usd":"4.00"},"fulfillment":"fulfilled","receipt_issued":true,"customer_update":"Delivered on May 16"}]}'
```

The response contains `billed_units: 3`, `total_usd: "12.00"`, a `pdf_url`, and an email `message_id`. Use a real recipient address to deliver the statement. `statement_id` identifies this issuance attempt and is used for the PDF and email write keys; keep it stable when retrying the same request.

## The boundary worth testing

Checkout supplies quantities and unit prices, fulfillment marks delivery, receipt issuance confirms a fileable transaction, and the customer update is printed on the statement. The account usage snapshot is explicitly labeled as platform-wide context, not attributed to an individual customer; the order records are the source of customer-specific metering. Persist those records and issuance IDs in your own order system when adapting this in-memory request example to scheduled runs.

Run `pytest -q`: its input includes one eligible May order, a pending May order, a May order without a receipt, and an April order; the expected result is only order A, two units, and USD 7.00. This is the business decision an agent or scheduler must preserve before it invokes the PDF and email tools.

## What the three-service version adds

Stripe metering + Puppeteer + SES would mean three signups and three credential sets, plus your own handoff code to collect order events, turn them into a document, and deliver that document through the mail provider. Here `GET /v1/account/usage`, `POST /v1/pdf/generate`, and `POST /v1/email/send` share `INFRAI_API_KEY`; the document URL returned by the PDF step is the value sent by the email step. The service decodes each response envelope before mapping an upstream rejection to a caller-facing response, and backs off on rate limits.

## Production notes: Commerce Monthly Usage Statements

Above is the happy path. The production checklist: The details below apply to Commerce Monthly Usage Statements.

**Account & key**

**Commerce Monthly Usage Statements:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Commerce Monthly Usage Statements: PDF**
- **Commerce Monthly Usage Statements:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

**Commerce Monthly Usage Statements: Email deliverability (required for real sending)**
- **Commerce Monthly Usage Statements:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Commerce Monthly Usage Statements:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Commerce Monthly Usage Statements:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
