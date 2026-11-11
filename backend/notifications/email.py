"""
Configurable email sender supporting SendGrid, AWS SES, and SMTP.

Config via environment variables:
  EMAIL_PROVIDER: "sendgrid" | "ses" | "smtp"  (default: "smtp")
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
  SENDGRID_API_KEY, SENDGRID_FROM
  AWS_SES_REGION, AWS_SES_FROM
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from platform.http_client import get_http_client

logger = logging.getLogger(__name__)

_PROVIDER = os.environ.get("EMAIL_PROVIDER", "smtp")


async def _send_via_smtp(to: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        if port != 25:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [to], msg.as_string())

    logger.info("Email sent via SMTP to %s", to)


async def _send_via_sendgrid(to: str, subject: str, body: str) -> None:
    api_key = os.environ["SENDGRID_API_KEY"]
    from_addr = os.environ.get("SENDGRID_FROM", "noreply@example.com")

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }

    async with get_http_client(timeout=10.0) as client:
        resp = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()

    logger.info("Email sent via SendGrid to %s", to)


async def _send_via_ses(to: str, subject: str, body: str) -> None:
    import boto3

    region = os.environ.get("AWS_SES_REGION", "us-east-1")
    from_addr = os.environ.get("AWS_SES_FROM", "noreply@example.com")

    client = boto3.client("ses", region_name=region)
    client.send_email(
        Source=from_addr,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
    logger.info("Email sent via AWS SES to %s", to)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send an email using the configured provider."""
    provider = os.environ.get("EMAIL_PROVIDER", _PROVIDER).lower()
    if provider in ("console", "log", "dev"):
        logger.info(
            "DEV email to=%s subject=%s body=%s",
            to,
            subject,
            body.replace("\n", " | "),
        )
        print(f"[DEV EMAIL] to={to} subject={subject}\n{body}", flush=True)
        return
    if provider == "sendgrid":
        await _send_via_sendgrid(to, subject, body)
    elif provider == "ses":
        await _send_via_ses(to, subject, body)
    else:
        await _send_via_smtp(to, subject, body)
