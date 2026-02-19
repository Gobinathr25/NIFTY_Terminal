"""
Profile Tab — credential management.
Credentials stored ONLY in st.session_state.
NO database storage of secrets.
"""

from __future__ import annotations
import streamlit as st
import requests
import hashlib
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)

SESSION_KEY = "credentials"


def _init_session() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = {
            "client_id":        "",
            "secret_key":       "",
            "redirect_url":     "",
            "telegram_token":   "",
            "telegram_chat_id": "",
            "access_token":     "",
            "fyers_connected":  False,
            "telegram_active":  False,
        }


def get_credentials() -> dict:
    _init_session()
    return st.session_state[SESSION_KEY]



def _do_full_totp_login(creds: dict) -> None:
    """Complete full login flow using TOTP (no SMS OTP step needed)."""
    import streamlit as st
    from utils.fyers_login import (
        step1_send_login_otp, step2b_verify_totp,
        step3_verify_pin, step4_get_access_token
    )

    fy_id       = st.session_state.get("login_fy_id", "")
    pin         = st.session_state.get("login_pin", "")
    totp_secret = st.session_state.get("login_totp_secret", "")

    # Step 1: initiate login
    ok, request_key = step1_send_login_otp(fy_id, creds["client_id"])
    if not ok:
        st.error(f"❌ Login initiation failed: {request_key}")
        return

    # Step 2: verify TOTP
    ok2, rk2 = step2b_verify_totp(request_key, totp_secret)
    if not ok2:
        st.error(f"❌ TOTP verification failed: {rk2}")
        return

    # Step 3: verify PIN
    ok3, auth_code = step3_verify_pin(rk2, pin)
    if not ok3:
        st.error(f"❌ PIN verification failed: {auth_code}")
        return

    # Step 4: get token
    ok4, token = step4_get_access_token(creds["client_id"], creds["secret_key"], auth_code)
    if ok4 and token:
        st.session_state[SESSION_KEY]["access_token"] = token
        st.session_state[SESSION_KEY]["fyers_connected"] = True
        st.session_state["login_step"] = 1
        st.success("✅ TOTP Login successful! Access token obtained.")
        st.info("Click **⚡ Initialise Strategy** below to start.")
        st.rerun()
    else:
        st.error(f"❌ Token generation failed: {token}")


def render_profile_tab() -> None:
    _init_session()
    creds = st.session_state[SESSION_KEY]

    st.markdown("## ⚙️ API Profile Configuration")
    st.info(
        "Credentials are stored **only in your browser session** (RAM). "
        "They are never saved to disk or database. Refreshing the page will clear them."
    )

    # ── Status indicators ────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        fyers_status = "🟢 Connected" if creds["fyers_connected"] else "🔴 Not Connected"
        st.metric("Fyers API Status", fyers_status)
    with col2:
        tg_status = "🟢 Active" if creds["telegram_active"] else "🔴 Not Active"
        st.metric("Telegram Status", tg_status)

    st.markdown("---")

    # ── Fyers credentials ────────────────────────────────────────────────────
    st.markdown("### 🔑 Fyers API Credentials")
    with st.form("credentials_form", clear_on_submit=False):
        client_id = st.text_input(
            "Fyers Client ID",
            value=creds.get("client_id", ""),
            placeholder="e.g. XYZ123-100",
            help="Your Fyers App ID from https://myapi.fyers.in",
        )
        secret_key = st.text_input(
            "Fyers Secret Key",
            value=creds.get("secret_key", ""),
            type="password",
            placeholder="App secret key",
        )
        redirect_url = st.text_input(
            "Redirect URL",
            value=creds.get("redirect_url", ""),
            placeholder="https://yourapp.com/callback",
            help="Must match the URL registered in Fyers API portal",
        )

        st.markdown("---")
        st.markdown("### 📱 Telegram Alerts")
        tg_token = st.text_input(
            "Telegram Bot Token",
            value=creds.get("telegram_token", ""),
            type="password",
            placeholder="1234567890:AABBccDDeeFF...",
            help="Get from @BotFather on Telegram",
        )
        tg_chat_id = st.text_input(
            "Telegram Chat ID",
            value=creds.get("telegram_chat_id", ""),
            placeholder="-100xxxxxxxxxx or @channelname",
            help="Your personal chat ID or group/channel ID",
        )

        submitted = st.form_submit_button("💾 Save to Session", type="primary", use_container_width=True)
        if submitted:
            st.session_state[SESSION_KEY].update({
                "client_id":        client_id.strip(),
                "secret_key":       secret_key.strip(),
                "redirect_url":     redirect_url.strip(),
                "telegram_token":   tg_token.strip(),
                "telegram_chat_id": tg_chat_id.strip(),
            })
            st.success("✅ Credentials saved to session state.")
            log.info("Credentials updated in session state.")

    st.markdown("---")

    # ── Headless Login Flow ───────────────────────────────────────────────────
    st.markdown("### 🔐 Fyers Login")
    st.info(
        "Enter your Fyers credentials below. The app will handle the full login "
        "automatically — no browser redirect or copy-pasting needed. "
        "Works on both local and Render deployments."
    )

    if not (creds.get("client_id") and creds.get("secret_key")):
        st.warning("⚠️ Save your Fyers Client ID and Secret Key first (Step 1 above).")
    else:
        # ── Login form ────────────────────────────────────────────────────────
        login_step = st.session_state.get("login_step", 1)

        # ── Step 1: Fyers ID + PIN + OTP method ──────────────────────────────
        if login_step == 1:
            st.markdown("#### Step 1 — Enter Credentials")
            with st.form("fyers_login_form"):
                fy_id    = st.text_input("Fyers Client ID / User ID",
                                          value=creds.get("client_id",""),
                                          help="Your Fyers login ID e.g. XY12345")
                pin      = st.text_input("4-digit PIN", type="password",
                                          placeholder="Your Fyers trading PIN",
                                          help="The 4-digit PIN you use to log in to Fyers")
                otp_mode = st.radio("OTP Method", ["SMS / Email OTP", "TOTP (Google Authenticator)"],
                                     horizontal=True)
                totp_secret = ""
                if otp_mode == "TOTP (Google Authenticator)":
                    totp_secret = st.text_input(
                        "TOTP Secret Key",
                        type="password",
                        placeholder="Base32 secret from Fyers 2FA setup",
                        help="Found in Fyers app → Security → 2FA setup → show secret key",
                    )

                send_otp = st.form_submit_button("📲 Send OTP & Continue", type="primary",
                                                  use_container_width=True)

            if send_otp:
                if not fy_id or not pin:
                    st.error("❌ Fyers User ID and PIN are required.")
                else:
                    # Store for later steps
                    st.session_state["login_fy_id"]      = fy_id.strip()
                    st.session_state["login_pin"]        = pin.strip()
                    st.session_state["login_otp_mode"]   = otp_mode
                    st.session_state["login_totp_secret"]= totp_secret.strip()

                    if otp_mode == "TOTP (Google Authenticator)":
                        if not totp_secret:
                            st.error("❌ TOTP secret is required for authenticator login.")
                        else:
                            # With TOTP we can complete the whole flow now
                            with st.spinner("Logging in with TOTP…"):
                                _do_full_totp_login(creds)
                    else:
                        # SMS OTP — send it first
                        with st.spinner("Sending OTP to your registered mobile…"):
                            from utils.fyers_login import step1_send_login_otp
                            ok, result = step1_send_login_otp(
                                fy_id.strip(), creds["client_id"].strip()
                            )
                        if ok:
                            st.session_state["login_request_key"] = result
                            st.session_state["login_step"] = 2
                            st.success("✅ OTP sent to your registered mobile/email!")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to send OTP: {result}")

        # ── Step 2: Enter OTP ─────────────────────────────────────────────────
        elif login_step == 2:
            st.markdown("#### Step 2 — Enter OTP")
            st.info("OTP sent to your registered mobile/email. Enter it below.")
            with st.form("otp_form"):
                otp = st.text_input("Enter OTP", placeholder="6-digit OTP",
                                     max_chars=6)
                verify = st.form_submit_button("✅ Verify OTP & Login", type="primary",
                                               use_container_width=True)
                back   = st.form_submit_button("← Back")

            if back:
                st.session_state["login_step"] = 1
                st.rerun()

            if verify:
                if not otp.strip():
                    st.error("Enter the OTP.")
                else:
                    request_key = st.session_state.get("login_request_key","")
                    pin         = st.session_state.get("login_pin","")
                    with st.spinner("Verifying OTP…"):
                        from utils.fyers_login import step2_verify_otp, step3_verify_pin, step4_get_access_token
                        ok, rk2 = step2_verify_otp(request_key, otp.strip())
                    if not ok:
                        st.error(f"❌ OTP verification failed: {rk2}")
                    else:
                        with st.spinner("Verifying PIN…"):
                            ok2, auth_code = step3_verify_pin(rk2, pin)
                        if not ok2:
                            st.error(f"❌ PIN verification failed: {auth_code}")
                        else:
                            with st.spinner("Getting access token…"):
                                ok3, token = step4_get_access_token(
                                    creds["client_id"], creds["secret_key"], auth_code
                                )
                            if ok3 and token:
                                st.session_state[SESSION_KEY]["access_token"] = token
                                st.session_state[SESSION_KEY]["fyers_connected"] = True
                                st.session_state["login_step"] = 1
                                st.success("✅ Login successful! Access token obtained.")
                                st.info("Click **⚡ Initialise Strategy** below to start.")
                                st.rerun()
                            else:
                                st.error(f"❌ Token generation failed: {token}")

    st.markdown("---")

    # ── Validate / Test buttons ───────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔌 Test Fyers Connection", use_container_width=True):
            _test_fyers_connection()

    with col2:
        if st.button("📤 Test Telegram Alert", use_container_width=True):
            _test_telegram()

    # ── Access token display (masked) ────────────────────────────────────────
    if creds.get("access_token"):
        token = creds["access_token"]
        masked = token[:6] + "*" * (len(token) - 10) + token[-4:]
        st.markdown("---")
        st.markdown(f"**Active Access Token:** `{masked}`")
        st.caption("Token is stored in session state only — never persisted.")


def _test_fyers_connection() -> None:
    creds = get_credentials()
    if not creds.get("access_token") or not creds.get("client_id"):
        st.error("❌ No access token. Complete OAuth2 flow first.")
        return

    with st.spinner("Testing Fyers API…"):
        try:
            from data.fyers_client import FyersClient
            client = FyersClient(creds["client_id"], creds["access_token"])
            ok = client.validate_token()
            if ok:
                st.session_state[SESSION_KEY]["fyers_connected"] = True
                st.success("✅ Fyers API Connected!")
            else:
                st.session_state[SESSION_KEY]["fyers_connected"] = False
                st.error("❌ Fyers API validation failed. Token may be expired.")
        except Exception as e:
            st.session_state[SESSION_KEY]["fyers_connected"] = False
            st.error(f"❌ Connection error: {e}")


def _test_telegram() -> None:
    creds = get_credentials()
    if not creds.get("telegram_token") or not creds.get("telegram_chat_id"):
        st.error("❌ Telegram Bot Token and Chat ID required.")
        return

    with st.spinner("Sending test message…"):
        try:
            from alerts.telegram import TelegramNotifier
            notifier = TelegramNotifier(creds["telegram_token"], creds["telegram_chat_id"])
            ok = notifier.test()
            if ok:
                st.session_state[SESSION_KEY]["telegram_active"] = True
                st.success("✅ Telegram alert sent successfully!")
            else:
                st.session_state[SESSION_KEY]["telegram_active"] = False
                st.error("❌ Telegram send failed. Check bot token and chat ID.")
        except Exception as e:
            st.session_state[SESSION_KEY]["telegram_active"] = False
            st.error(f"❌ Telegram error: {e}")
