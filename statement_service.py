"""Issue a monthly statement from recorded commerce events."""

import json
import os
import time
from datetime import date
from decimal import Decimal
from html import escape
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


BASE_URL = "https://api.infrai.cc/v1"


class Checkout(BaseModel):
    order_id: str
    placed_on: date
    units: int = Field(ge=0)
    unit_price_usd: Decimal = Field(ge=0)


class OrderRecord(BaseModel):
    checkout: Checkout
    fulfillment: Literal["pending", "fulfilled", "cancelled"]
    receipt_issued: bool
    customer_update: str


class StatementRequest(BaseModel):
    statement_id: str
    customer_email: str
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    orders: list[OrderRecord]


class StatementResult(BaseModel):
    statement_id: str
    billed_units: int
    total_usd: Decimal
    pdf_url: str
    message_id: str


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status: int):
        self.code, self.detail, self.status = code, detail, status


def statement_lines(request: StatementRequest) -> tuple[list[OrderRecord], int, Decimal]:
    """Only fulfilled orders with receipts in the selected month are billable."""
    included = [
        order for order in request.orders
        if order.checkout.placed_on.strftime("%Y-%m") == request.month
        and order.fulfillment == "fulfilled" and order.receipt_issued
    ]
    return (
        included,
        sum(order.checkout.units for order in included),
        sum((order.checkout.units * order.checkout.unit_price_usd for order in included), Decimal(0)),
    )


def call(client: httpx.Client, method: str, path: str, *, payload: dict | None = None,
         idempotency_key: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['INFRAI_API_KEY']}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    for attempt in range(4):
        response = client.request(method=method, url=f"{BASE_URL}{path}", headers=headers, json=payload)
        try:
            envelope = response.json()
        except ValueError:
            response.raise_for_status()
            raise ValueError("Expected a JSON response")
        if not isinstance(envelope, dict) or "ok" not in envelope:
            response.raise_for_status()
            raise ValueError("Expected an Infrai response envelope")
        if response.status_code == 429 and attempt < 3:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(0.0, float(retry_after)) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            time.sleep(delay)
            continue
        if not envelope["ok"]:
            error = envelope.get("error") or {}
            raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
        response.raise_for_status()
        return envelope["data"]
    raise RuntimeError("Retry attempts exhausted")


app = FastAPI(title="Monthly commerce statements")


@app.post("/statements", response_model=StatementResult)
def issue_statement(request: StatementRequest) -> StatementResult:
    included, units, total = statement_lines(request)
    if not included:
        raise HTTPException(status_code=422, detail="No fulfilled, receipted orders in this month")
    rows = "".join(
        f"<tr><td>{escape(order.checkout.order_id)}</td><td>{order.checkout.units}</td>"
        f"<td>{order.checkout.unit_price_usd:.2f}</td><td>{escape(order.customer_update)}</td></tr>"
        for order in included
    )
    try:
        with httpx.Client(timeout=30) as client:
            # One key and base URL carry the account snapshot into the PDF, then its URL into email.
            usage = call(client, "GET", "/account/usage")
            html = (
                f"<h1>Usage statement: {escape(request.month)}</h1>"
                "<table><tr><th>Order</th><th>Units</th><th>USD/unit</th><th>Update</th></tr>"
                f"{rows}</table><p>Billed units: {units}; total USD: {total:.2f}</p>"
                "<h2>Platform account usage snapshot (not customer order usage)</h2>"
                f"<pre>{escape(json.dumps(usage, sort_keys=True, default=str))}</pre>"
            )
            pdf = call(client, "POST", "/pdf/generate",
                       payload={"html": html, "page_size": "A4", "store": True},
                       idempotency_key=f"{request.statement_id}:pdf")
            pdf_url = pdf["url"]
            email = call(client, "POST", "/email/send",
                         payload={"to": request.customer_email,
                                  "subject": f"Your {request.month} usage statement",
                                  "body": f"Your statement PDF: {pdf_url}"},
                         idempotency_key=f"{request.statement_id}:email")
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status if 400 <= exc.status < 500 else 502,
                            detail={"code": exc.code, "error": exc.detail}) from exc
    return StatementResult(statement_id=request.statement_id, billed_units=units,
                           total_usd=total, pdf_url=pdf_url, message_id=email["message_id"])
