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

    # ── OAuth2 flow ──────────────────────────────────────────────────────────
    st.markdown("### 🔐 Fyers OAuth2 Authentication")

    if not (creds.get("client_id") and creds.get("secret_key")):
        st.warning("⚠️ Save your Fyers Client ID and Secret Key first (Step 1 above).")
    else:
        # ── Method A: Auto (local app only) ──────────────────────────────────
        st.markdown("#### Option A — Auto Login (Recommended for local desktop)")
        st.info(
"Automatically opens your browser, logs you in via Fyers, "
            "and captures the token — no copy-pasting needed.\n\n"
            "This only works when running the app locally on your computer "
            "(not on Render/cloud). Your Fyers app Redirect URL must be set to:\n\n"
            "`http://127.0.0.1:8085/callback`"
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🚀 Auto Login (opens browser)", use_container_width=True, type="primary"):
                with st.spinner("Waiting for Fyers login… (browser should open)"):
                    try:
                        from utils.auth_server import run_local_auth_flow
                        token = run_local_auth_flow(
                            creds["client_id"].strip(),
                            creds["secret_key"].strip(),
                        )
                        if token:
                            st.session_state[SESSION_KEY]["access_token"] = token
                            st.session_state[SESSION_KEY]["fyers_connected"] = True
                            st.success("✅ Access token obtained automatically!")
                            st.rerun()
                        else:
                            st.error("❌ Login timed out or failed. Try Manual Login below.")
                    except Exception as e:
                        st.error(f"❌ Auto login error: {e}")
        with col2:
            st.caption("Timeout: 3 minutes")

        st.markdown("---")

        # ── Method B: Manual (works everywhere including Render) ─────────────
        st.markdown("#### Option B — Manual Login (Works on Render / cloud)")
        st.caption(
            "Use this when deploying on Render or any cloud server. "
            "Set your Fyers app Redirect URL to any URL (e.g. `https://trade.fyers.in`), "
            "log in, then copy the `auth_code` value from the browser address bar."
        )

        col1, col2 = st.columns(2)
        with col1:
            redirect_for_manual = st.text_input(
                "Redirect URL (for manual flow)",
                value=creds.get("redirect_url", "https://trade.fyers.in"),
                key="manual_redirect_url",
                help="Set this same URL in your Fyers API portal",
            )
            if st.button("🔗 Generate Login URL", use_container_width=True):
                from data.fyers_client import FyersClient
                url = FyersClient.generate_auth_url(
                    creds["client_id"], redirect_for_manual, creds["secret_key"]
                )
                st.session_state["manual_auth_url"] = url

            if st.session_state.get("manual_auth_url"):
                url = st.session_state["manual_auth_url"]
                st.markdown(f"**[👉 Click to Open Fyers Login]({url})**")
                st.caption("After login, copy the `auth_code=XXXXXX` from the redirected URL.")

        with col2:
            auth_code = st.text_input(
                "Paste auth_code here",
                placeholder="e.g. eyJ0eXAiOiJKV1QiLCJhbGc...",
                key="auth_code_input",
                help="Copy the value after auth_code= in the browser URL bar after login",
            )
            if st.button("🔄 Exchange for Token", use_container_width=True):
                if auth_code.strip():
                    with st.spinner("Exchanging auth code…"):
                        from data.fyers_client import FyersClient
                        token = FyersClient.exchange_auth_code(
                            creds["client_id"], creds["secret_key"], auth_code.strip()
                        )
                    if token:
                        st.session_state[SESSION_KEY]["access_token"] = token
                        st.session_state[SESSION_KEY]["fyers_connected"] = True
                        st.success("✅ Access token obtained!")
                        st.rerun()
                    else:
                        st.error("❌ Token exchange failed. Check credentials and auth code.")
                else:
                    st.warning("Paste the auth_code first.")

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
