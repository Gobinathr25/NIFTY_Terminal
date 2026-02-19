"""
Profile Tab.
- Credentials (Client ID, Secret, TOTP, PIN) are hardcoded in utils/fyers_login.py
- UI only shows: Initiate Session button, connection status, Telegram config
- No credential input fields for broker — they are never in the UI
"""

from __future__ import annotations
import streamlit as st
from utils.logger import get_logger

log = get_logger(__name__)

SESSION_KEY = "credentials"


def _init_session() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = {
            "access_token":     "",
            "fyers_connected":  False,
            "telegram_token":   "",
            "telegram_chat_id": "",
            "telegram_active":  False,
        }


def get_credentials() -> dict:
    _init_session()
    # Inject all hardcoded credentials — nothing comes from UI inputs
    from utils.fyers_login import (
        FYERS_CLIENT_ID, FYERS_SECRET_KEY,
        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    )
    creds = st.session_state[SESSION_KEY]
    creds["client_id"]        = FYERS_CLIENT_ID
    creds["secret_key"]       = FYERS_SECRET_KEY
    creds["telegram_token"]   = TELEGRAM_BOT_TOKEN
    creds["telegram_chat_id"] = TELEGRAM_CHAT_ID
    # Mark telegram active if credentials are set
    if TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("X"):
        creds["telegram_active"] = True
    return creds


def render_profile_tab() -> None:
    _init_session()
    creds = get_credentials()

    st.markdown("## ⚙️ Session & Alerts Configuration")

    # ── Status banner ─────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if creds["fyers_connected"] and creds["access_token"]:
            st.success("🟢 Fyers API — Connected")
        else:
            st.error("🔴 Fyers API — Not Connected")
    with col2:
        if creds["telegram_active"]:
            st.success("🟢 Telegram — Active")
        else:
            st.warning("🟡 Telegram — Not Configured")

    st.markdown("---")

    # ── Broker session ────────────────────────────────────────────────────────
    st.markdown("### 🔐 Broker Session")
    st.caption(
        "Credentials are securely stored in the application. "
        "Click below to authenticate with Fyers and start your session."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        otp_mode = st.radio(
            "Login Method",
            ["TOTP (Automatic)", "SMS OTP (Manual)"],
            horizontal=True,
            help="TOTP is fully automatic. SMS requires you to enter the OTP sent to your phone.",
        )

    with col2:
        st.caption(" ")  # spacer

    # ── TOTP — fully automatic ────────────────────────────────────────────────
    if otp_mode == "TOTP (Automatic)":
        st.info("🔄 Click the button — the app will log in automatically using your authenticator.")
        if st.button("⚡ Initiate Session", type="primary", use_container_width=True, key="btn_initiate_session"):
            with st.spinner("Connecting to Fyers… (TOTP login, ~5 seconds)"):
                try:
                    from utils.fyers_login import login_with_totp
                    ok, result = login_with_totp()
                except Exception as e:
                    ok, result = False, str(e)

            if ok and result:
                st.session_state[SESSION_KEY]["access_token"]    = result
                st.session_state[SESSION_KEY]["fyers_connected"] = True
                st.success("✅ Session initiated! Fyers API connected.")
                st.info("Now click **⚡ Initialise Strategy** below to start the engine.")
                log.info("Fyers login successful via TOTP.")
                st.rerun()
            else:
                st.error(f"❌ Login failed: {result}")
                st.caption(
                    "Common reasons: wrong TOTP secret, wrong PIN, "
                    "credentials not updated in utils/fyers_login.py, "
                    "or Fyers API is temporarily down."
                )

    # ── SMS OTP — two-step ────────────────────────────────────────────────────
    else:
        sms_step = st.session_state.get("sms_step", 1)

        if sms_step == 1:
            if st.button("📲 Send OTP to Registered Mobile", type="primary", use_container_width=True, key="btn_send_sms_otp"):
                with st.spinner("Sending OTP…"):
                    try:
                        from utils.fyers_login import send_sms_otp
                        ok, msg = send_sms_otp()
                    except Exception as e:
                        ok, msg = False, str(e)
                if ok:
                    st.session_state["sms_step"] = 2
                    st.success("✅ OTP request sent!")
                    st.warning(
                        "⚠️ **Did not receive OTP?** Fyers headless API may not deliver SMS "
                        "for all account types. If OTP doesn't arrive within 30 seconds, "
                        "use **TOTP (Automatic)** method instead — it works without any SMS."
                    )
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
        else:
            st.success("✅ OTP sent to your registered mobile.")
            with st.form("sms_otp_form"):
                otp = st.text_input("Enter OTP", placeholder="6-digit OTP", max_chars=6)
                submitted = st.form_submit_button("✅ Verify & Connect", type="primary",
                                                   use_container_width=True)
                reset = st.form_submit_button("← Resend OTP")

            if reset:
                st.session_state["sms_step"] = 1
                st.rerun()

            if submitted:
                if not otp.strip():
                    st.error("Enter the OTP.")
                else:
                    with st.spinner("Verifying OTP and connecting…"):
                        try:
                            from utils.fyers_login import login_with_sms_otp
                            ok, result = login_with_sms_otp(otp.strip())
                        except Exception as e:
                            ok, result = False, str(e)

                    if ok and result:
                        st.session_state[SESSION_KEY]["access_token"]    = result
                        st.session_state[SESSION_KEY]["fyers_connected"] = True
                        st.session_state["sms_step"] = 1
                        st.success("✅ Session initiated! Fyers API connected.")
                        st.info("Now click **⚡ Initialise Strategy** below.")
                        st.rerun()
                    else:
                        st.error(f"❌ Login failed: {result}")

    # ── Token status ──────────────────────────────────────────────────────────
    if creds.get("access_token"):
        token = creds["access_token"]
        masked = token[:8] + "•" * 20 + token[-4:]
        st.caption(f"Active token: `{masked}`")

    st.markdown("---")

    # ── Telegram status ───────────────────────────────────────────────────────
    st.markdown("### 📱 Telegram Alerts")
    from utils.fyers_login import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("X"):
        st.success(f"✅ Telegram configured. Chat ID: `{TELEGRAM_CHAT_ID}`")
        if st.button("📤 Test Telegram Alert", use_container_width=True, key="btn_test_telegram"):
            _test_telegram()
    else:
        st.warning("⚠️ Telegram not configured. Update TELEGRAM_BOT_TOKEN in utils/fyers_login.py")

    st.markdown("---")

    # ── Initialise strategy button ────────────────────────────────────────────
    st.markdown("### 🚀 Step 2 — Initialise Strategy Engine")
    st.caption("Connect to Fyers first (above), then click this to start the engine.")

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("⚡ Initialise Strategy", type="primary", use_container_width=True, key="btn_init_strategy_profile"):
            if not creds.get("access_token"):
                st.error("❌ Initiate Fyers session first.")
            else:
                with st.spinner("Building strategy engine…"):
                    try:
                        from data.fyers_client import FyersClient
                        from alerts.telegram import TelegramNotifier
                        from core.strategy import GammaStrangleStrategy
                        from core.scheduler import TradingScheduler
                        from utils.fyers_login import FYERS_CLIENT_ID, FYERS_SECRET_KEY

                        client   = FyersClient(FYERS_CLIENT_ID, creds["access_token"])
                        notifier = TelegramNotifier(
                            creds.get("telegram_token", ""),
                            creds.get("telegram_chat_id", ""),
                        )
                        strategy = GammaStrangleStrategy(
                            fyers=client,
                            capital=st.session_state.get("capital", 500_000),
                            risk_pct=st.session_state.get("risk_pct", 2.0),
                            num_lots=st.session_state.get("num_lots", 1),
                            telegram_fn=notifier.send,
                        )

                        if st.session_state.get("scheduler") is None:
                            from core.scheduler import TradingScheduler
                            scheduler = TradingScheduler()
                            def _eod():
                                s = strategy.generate_eod_summary()
                                notifier.send_eod_report(s["total_trades"], s["net_pnl"],
                                                         s["max_drawdown"], s["win_rate"])
                            scheduler.setup(
                                on_market_open   = strategy.start,
                                on_no_new_trades = strategy.stop,
                                on_force_close   = lambda: strategy.close_all_positions("FORCE_CLOSE"),
                                on_eod_report    = _eod,
                                on_monitor       = strategy.monitor_positions,
                            )
                            scheduler.start()
                            st.session_state["scheduler"] = scheduler

                        st.session_state["strategy"] = strategy
                        st.success("✅ Strategy engine ready!")
                        st.info("Go to **🎛️ Strategy Control** → click **Start Strategy**.")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        log.error("Strategy init error: %s", e, exc_info=True)

    with col2:
        if st.session_state.get("strategy") is not None:
            st.success("✅ Ready")
        else:
            st.warning("⚠️ Not init")


def _test_telegram() -> None:
    creds = get_credentials()
    if not creds.get("telegram_token") or not creds.get("telegram_chat_id"):
        st.error("❌ Save Telegram settings first.")
        return
    with st.spinner("Sending test message…"):
        try:
            from alerts.telegram import TelegramNotifier
            ok = TelegramNotifier(creds["telegram_token"], creds["telegram_chat_id"]).test()
            if ok:
                st.session_state[SESSION_KEY]["telegram_active"] = True
                st.success("✅ Telegram alert sent!")
            else:
                st.error("❌ Failed. Check bot token and chat ID.")
        except Exception as e:
            st.error(f"❌ {e}")
