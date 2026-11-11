"""
Configurable SMS sender supporting Aliyun SMS and Twilio.

Config via environment variables:
  SMS_PROVIDER: "aliyun" | "twilio"  (default: "aliyun")
  ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, ALIYUN_SIGN_NAME, ALIYUN_TEMPLATE_CODE
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import urllib.parse
import uuid
from datetime import datetime, timezone

from backend.platform.http_client import get_http_client

logger = logging.getLogger(__name__)


async def _send_via_aliyun(to: str, message: str) -> None:
    """Send SMS via Aliyun SMS API using httpx (no SDK dependency)."""
    access_key_id = os.environ["ALIYUN_ACCESS_KEY_ID"]
    access_key_secret = os.environ["ALIYUN_ACCESS_KEY_SECRET"]
    sign_name = os.environ["ALIYUN_SIGN_NAME"]
    template_code = os.environ["ALIYUN_TEMPLATE_CODE"]

    params: dict[str, str] = {
        "AccessKeyId": access_key_id,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": to,
        "RegionId": "cn-hangzhou",
        "SignName": sign_name,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "TemplateCode": template_code,
        "TemplateParam": f'{{"code":"{message}"}}',
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }

    # Build canonical query string (sorted, URL-encoded)
    sorted_params = sorted(params.items())
    query_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted_params
    )
    string_to_sign = "GET&%2F&" + urllib.parse.quote(query_string, safe="")

    # HMAC-SHA1 signature
    key = (access_key_secret + "&").encode("utf-8")
    sig = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    params["Signature"] = base64.b64encode(sig).decode("utf-8")

    async with get_http_client(timeout=10.0) as client:
        resp = await client.get(
            "https://dysmsapi.aliyuncs.com/",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("Code") != "OK":
            raise RuntimeError(f"Aliyun SMS error: {data.get('Message')}")

    logger.info("SMS sent via Aliyun to %s", to)


async def _send_via_twilio(to: str, message: str) -> None:
    """Send SMS via Twilio REST API."""
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_FROM_NUMBER"]

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    credentials = base64.b64encode(
        f"{account_sid}:{auth_token}".encode()
    ).decode()

    async with get_http_client(timeout=10.0) as client:
        resp = await client.post(
            url,
            data={"To": to, "From": from_number, "Body": message},
            headers={"Authorization": f"Basic {credentials}"},
        )
        resp.raise_for_status()

    logger.info("SMS sent via Twilio to %s", to)


async def send_sms(to: str, message: str) -> None:
    """Send an SMS using the configured provider."""
    provider = os.environ.get("SMS_PROVIDER", "aliyun")
    if provider == "twilio":
        await _send_via_twilio(to, message)
    else:
        await _send_via_aliyun(to, message)
