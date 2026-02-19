"""
Fyers headless login utility.
Automates the full OAuth2 flow using Fyers' login API endpoints directly.
The user provides username, password, PAN/DOB, and TOTP/OTP — 
the app handles everything and returns an access token.

Flow (mirrors what the Fyers web app does internally):
  Step 1: POST /api/v3/...send-login-otp   → sends OTP to registered mobile
  Step 2: POST /api/v3/...verify-otp       → verifies OTP, returns login_token
  Step 3: POST /api/v3/...verify-pin       → verifies PIN, returns auth_code  
  Step 4: POST /api/v3/...validate-authcode → exchanges auth_code for access_token

Note: Fyers also supports TOTP (Google Authenticator) instead of SMS OTP.
"""

from __future__ import annotations
import hashlib
import requests
import pyotp
from typing import Optional, Tuple
from utils.logger import get_logger

log = get_logger(__name__)

FYERS_LOGIN_URL = "https://api-t2.fyers.in/vagator/v2"
FYERS_TOKEN_URL = "https://api-t1.fyers.in/api/v3"

SESSION = requests.Session()
SESSION.headers.update({
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
})


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def step1_send_login_otp(fy_id: str, app_id: str) -> Tuple[bool, str]:
    """
    Step 1 — Send OTP to user's registered mobile/email.
    fy_id: Fyers Client ID (e.g. XY12345)
    app_id: First part of App ID before the dash (e.g. 'XY12345' from 'XY12345-100')
    Returns (success, request_key or error_message)
    """
    try:
        payload = {
            "fy_id":  fy_id,
            "app_id": app_id.split("-")[0] if "-" in app_id else app_id,
        }
        resp = SESSION.post(f"{FYERS_LOGIN_URL}/send-login-otp", json=payload, timeout=15)
        data = resp.json()
        log.info("send-login-otp response: %s", data)

        if data.get("s") == "ok" or data.get("code") == 200:
            request_key = data.get("request_key", "")
            return True, request_key
        else:
            return False, data.get("message", str(data))
    except Exception as e:
        log.error("send-login-otp error: %s", e)
        return False, str(e)


def step2_verify_otp(request_key: str, otp: str) -> Tuple[bool, str]:
    """
    Step 2 — Verify OTP entered by user.
    Returns (success, request_key_for_next_step or error)
    """
    try:
        payload = {
            "request_key": request_key,
            "otp":         otp.strip(),
        }
        resp = SESSION.post(f"{FYERS_LOGIN_URL}/verify-otp", json=payload, timeout=15)
        data = resp.json()
        log.info("verify-otp response: %s", data)

        if data.get("s") == "ok" or data.get("code") == 200:
            return True, data.get("request_key", request_key)
        else:
            return False, data.get("message", str(data))
    except Exception as e:
        log.error("verify-otp error: %s", e)
        return False, str(e)


def step2b_verify_totp(request_key: str, totp_secret: str) -> Tuple[bool, str]:
    """
    Step 2 (TOTP variant) — Use Google Authenticator TOTP instead of SMS OTP.
    totp_secret: the base32 secret from Fyers 2FA setup page.
    """
    try:
        totp = pyotp.TOTP(totp_secret.strip().replace(" ", ""))
        current_otp = totp.now()
        log.info("Generated TOTP: %s", current_otp)
        return step2_verify_otp(request_key, current_otp)
    except Exception as e:
        log.error("TOTP generation error: %s", e)
        return False, str(e)


def step3_verify_pin(request_key: str, pin: str) -> Tuple[bool, str]:
    """
    Step 3 — Verify 4-digit PIN (trading PIN).
    Returns (success, auth_code or error)
    """
    try:
        payload = {
            "request_key": request_key,
            "identity_type": "pin",
            "identifier":    _sha256(pin.strip()),
        }
        resp = SESSION.post(f"{FYERS_LOGIN_URL}/verify-pin", json=payload, timeout=15)
        data = resp.json()
        log.info("verify-pin response: %s", data)

        if data.get("s") == "ok" or data.get("code") == 200:
            auth_code = data.get("data", {}).get("authorization_code", "")
            if not auth_code:
                auth_code = data.get("authorization_code", "")
            return True, auth_code
        else:
            return False, data.get("message", str(data))
    except Exception as e:
        log.error("verify-pin error: %s", e)
        return False, str(e)


def step4_get_access_token(
    client_id: str, secret_key: str, auth_code: str
) -> Tuple[bool, str]:
    """
    Step 4 — Exchange auth_code for access_token.
    Returns (success, access_token or error)
    """
    try:
        app_id_hash = _sha256(f"{client_id}:{secret_key}")
        payload = {
            "grant_type": "authorization_code",
            "appIdHash":  app_id_hash,
            "code":       auth_code,
        }
        resp = SESSION.post(f"{FYERS_TOKEN_URL}/validate-authcode", json=payload, timeout=15)
        data = resp.json()
        log.info("validate-authcode response code: %s", data.get("s") or data.get("code"))

        if data.get("s") == "ok" or data.get("code") == 200:
            token = data.get("access_token", "")
            return True, token
        else:
            return False, data.get("message", str(data))
    except Exception as e:
        log.error("validate-authcode error: %s", e)
        return False, str(e)
