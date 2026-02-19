"""
Fyers headless login — correct v3 API endpoints.

Fyers login flow (verified against fyers-apiv3 SDK source):
  Step 1: POST https://api-t2.fyers.in/vagator/v2/send-login-otp
  Step 2: POST https://api-t2.fyers.in/vagator/v2/verify-otp  (or TOTP)
  Step 3: POST https://api-t2.fyers.in/vagator/v2/verify-pin
  Step 4: POST https://api-t1.fyers.in/api/v3/validate-authcode

Credentials are hardcoded here — never stored in DB or UI inputs.
"""

from __future__ import annotations
import hashlib
import requests
import pyotp
from typing import Tuple
from utils.logger import get_logger

log = get_logger(__name__)

# ─── HARDCODED CREDENTIALS ───────────────────────────────────────────────────
# Fill these once. They never appear in the UI.
FYERS_CLIENT_ID  = "KS5VRSP9RF-100"      # e.g. "AB12345-100"
FYERS_SECRET_KEY = "6NXYPEG7NB"  # App secret from myapi.fyers.in
FYERS_TOTP_KEY   = "HPTQQ5JXYIINM3E32VX2NFLSV4PBFZ5Z"  # Base32 TOTP secret from Fyers 2FA setup
FYERS_PIN        = "2501"              # Your 4-digit Fyers login PIN
# ─────────────────────────────────────────────────────────────────────────────

LOGIN_URL = "https://api-t2.fyers.in/vagator/v2"
TOKEN_URL = "https://api-t1.fyers.in/api/v3"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _post(url: str, payload: dict) -> dict:
    """POST with proper headers, returns parsed JSON or raises with raw text."""
    headers = {
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    raw = resp.text.strip()
    log.debug("POST %s → %d | %s", url, resp.status_code, raw[:200])
    try:
        return resp.json()
    except Exception:
        raise ValueError(f"Non-JSON response from {url}: {raw[:300]}")


def _step1_send_otp(fy_id: str) -> Tuple[bool, str]:
    """Initiate login — Fyers sends OTP or we proceed with TOTP."""
    try:
        # app_id_hash is sha256 of "client_id:secret_key"
        payload = {"fy_id": fy_id, "app_id": "2"}
        data = _post(f"{LOGIN_URL}/send-login-otp", payload)
        log.info("send-login-otp: %s", data)
        if data.get("s") == "ok" or str(data.get("code","")) == "200":
            return True, data.get("request_key", "")
        return False, data.get("message", str(data))
    except Exception as e:
        return False, str(e)


def _step2_verify_totp(request_key: str, totp_secret: str) -> Tuple[bool, str]:
    """Verify using TOTP code generated from secret."""
    try:
        code = pyotp.TOTP(totp_secret.strip().replace(" ", "")).now()
        log.info("Generated TOTP code: %s", code)
        payload = {"request_key": request_key, "otp": code}
        data = _post(f"{LOGIN_URL}/verify-otp", payload)
        log.info("verify-otp (TOTP): %s", data)
        if data.get("s") == "ok" or str(data.get("code","")) == "200":
            return True, data.get("request_key", request_key)
        return False, data.get("message", str(data))
    except Exception as e:
        return False, str(e)


def _step2_verify_sms_otp(request_key: str, otp: str) -> Tuple[bool, str]:
    """Verify SMS/email OTP entered by user."""
    try:
        payload = {"request_key": request_key, "otp": otp.strip()}
        data = _post(f"{LOGIN_URL}/verify-otp", payload)
        log.info("verify-otp (SMS): %s", data)
        if data.get("s") == "ok" or str(data.get("code","")) == "200":
            return True, data.get("request_key", request_key)
        return False, data.get("message", str(data))
    except Exception as e:
        return False, str(e)


def _step3_verify_pin(request_key: str, pin: str) -> Tuple[bool, str]:
    """Verify PIN — returns auth_code."""
    try:
        payload = {
            "request_key":   request_key,
            "identity_type": "pin",
            "identifier":    _sha256(pin.strip()),
        }
        data = _post(f"{LOGIN_URL}/verify-pin", payload)
        log.info("verify-pin: %s", data)
        if data.get("s") == "ok" or str(data.get("code","")) == "200":
            # auth code can be nested in data.data or at top level
            auth = (data.get("data") or {}).get("authorization_code") \
                or data.get("authorization_code", "")
            return True, auth
        return False, data.get("message", str(data))
    except Exception as e:
        return False, str(e)


def _step4_get_token(auth_code: str) -> Tuple[bool, str]:
    """Exchange auth_code for access_token."""
    try:
        app_hash = _sha256(f"{FYERS_CLIENT_ID}:{FYERS_SECRET_KEY}")
        payload = {
            "grant_type": "authorization_code",
            "appIdHash":  app_hash,
            "code":       auth_code,
        }
        data = _post(f"{TOKEN_URL}/validate-authcode", payload)
        log.info("validate-authcode: s=%s", data.get("s"))
        if data.get("s") == "ok" or str(data.get("code","")) == "200":
            return True, data.get("access_token", "")
        return False, data.get("message", str(data))
    except Exception as e:
        return False, str(e)


# ─── PUBLIC ENTRY POINT ──────────────────────────────────────────────────────

def login_with_totp() -> Tuple[bool, str]:
    """
    Full automated login using hardcoded credentials + TOTP.
    Returns (True, access_token) or (False, error_message).
    """
    fy_id = FYERS_CLIENT_ID.split("-")[0]  # strip "-100" suffix

    log.info("Step 1: Initiating login for %s", fy_id)
    ok, rk1 = _step1_send_otp(fy_id)
    if not ok:
        return False, f"Step 1 failed: {rk1}"

    log.info("Step 2: Verifying TOTP")
    ok, rk2 = _step2_verify_totp(rk1, FYERS_TOTP_KEY)
    if not ok:
        return False, f"Step 2 (TOTP) failed: {rk2}"

    log.info("Step 3: Verifying PIN")
    ok, auth_code = _step3_verify_pin(rk2, FYERS_PIN)
    if not ok:
        return False, f"Step 3 (PIN) failed: {auth_code}"
    if not auth_code:
        return False, "Step 3: auth_code empty — PIN may be wrong"

    log.info("Step 4: Getting access token")
    ok, token = _step4_get_token(auth_code)
    if not ok:
        return False, f"Step 4 (token) failed: {token}"
    if not token:
        return False, "Step 4: empty token received"

    log.info("Login successful.")
    return True, token


def login_with_sms_otp(sms_otp: str) -> Tuple[bool, str]:
    """
    Login using SMS OTP (call after send_sms_otp() first).
    Returns (True, access_token) or (False, error_message).
    """
    rk1 = _SESSION_STATE.get("rk1", "")
    if not rk1:
        return False, "No request_key — call send_sms_otp() first"

    ok, rk2 = _step2_verify_sms_otp(rk1, sms_otp)
    if not ok:
        return False, f"OTP verify failed: {rk2}"

    ok, auth_code = _step3_verify_pin(rk2, FYERS_PIN)
    if not ok:
        return False, f"PIN verify failed: {auth_code}"

    ok, token = _step4_get_token(auth_code)
    if not ok:
        return False, f"Token failed: {token}"

    return True, token


def send_sms_otp() -> Tuple[bool, str]:
    """Initiate SMS OTP — stores request_key for login_with_sms_otp()."""
    fy_id = FYERS_CLIENT_ID.split("-")[0]
    ok, rk1 = _step1_send_otp(fy_id)
    if ok:
        _SESSION_STATE["rk1"] = rk1
        return True, "OTP sent to registered mobile"
    return False, rk1


# Simple in-memory state for SMS flow across two calls
_SESSION_STATE: dict = {}
