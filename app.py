"""
NIFTY Options Paper Trading Terminal
Main Streamlit Application Entry Point

PAPER_MODE = True | No real orders are ever placed.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.config import PAPER_MODE
from data.database import init_db
from utils.logger import get_logger

log = get_logger("app")

st.set_page_config(
    page_title="NIFTY Paper Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

if PAPER_MODE:
    st.markdown(
        """<div style="background-color:#ff9900;padding:8px 16px;border-radius:6px;
                    text-align:center;font-weight:bold;color:#000;font-size:16px;margin-bottom:8px;">
            ⚠️ PAPER TRADING MODE ACTIVE — All orders are simulated. No real trades placed.
        </div>""",
        unsafe_allow_html=True,
    )

init_db()

for _k, _v in [("strategy", None), ("scheduler", None), ("capital", 500_000), ("risk_pct", 2.0), ("max_trades_day", 2), ("num_lots", 1)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _build_strategy():
    from ui.profile_tab import get_credentials
    creds = get_credentials()

    if not creds.get("client_id", "").strip():
        return None, "❌ Fyers Client ID is missing. Fill in the Profile tab and click Save."

    try:
        from data.fyers_client import FyersClient
        from alerts.telegram import TelegramNotifier
        from core.strategy import GammaStrangleStrategy
        from core.scheduler import TradingScheduler

        access_token = creds.get("access_token", "").strip() or "PAPER_DUMMY_TOKEN"
        client = FyersClient(creds["client_id"].strip(), access_token)

        notifier = TelegramNotifier(
            creds.get("telegram_token", ""),
            creds.get("telegram_chat_id", ""),
        )

        strategy = GammaStrangleStrategy(
            fyers=client,
            capital=st.session_state["capital"],
            risk_pct=st.session_state["risk_pct"],
            num_lots=st.session_state.get("num_lots", 1),
            telegram_fn=notifier.send,
        )

        if st.session_state["scheduler"] is None:
            scheduler = TradingScheduler()
            scheduler.setup(
                on_market_open=strategy.start,
                on_no_new_trades=strategy.stop,
                on_force_close=lambda: strategy.close_all_positions("FORCE_CLOSE"),
                on_eod_report=_make_eod_fn(strategy, notifier),
                on_monitor=strategy.monitor_positions,
            )
            scheduler.start()
            st.session_state["scheduler"] = scheduler

        return strategy, "✅ Strategy initialised successfully!"

    except Exception as e:
        log.error("Strategy build error: %s", e, exc_info=True)
        return None, f"❌ Error: {e}"


def _make_eod_fn(strategy, notifier):
    def _fn():
        summary = strategy.generate_eod_summary()
        notifier.send_eod_report(
            total_trades=summary["total_trades"],
            net_pnl=summary["net_pnl"],
            max_dd=summary["max_drawdown"],
            win_rate=summary["win_rate"],
        )
    return _fn


with st.sidebar:
    st.markdown("## ⚙️ Trading Parameters")
    st.markdown("---")

    capital = st.number_input("💰 Capital (₹)", min_value=100_000, max_value=10_000_000,
                               value=int(st.session_state["capital"]), step=50_000, format="%d")
    st.session_state["capital"] = capital

    risk_pct = st.slider("⚠️ Risk % per Day", min_value=0.5, max_value=5.0,
                          value=float(st.session_state["risk_pct"]), step=0.25)
    st.session_state["risk_pct"] = risk_pct

    max_trades = st.number_input("🔢 Max Trades / Day", min_value=1, max_value=5,
                                  value=int(st.session_state["max_trades_day"]))
    st.session_state["max_trades_day"] = max_trades

    num_lots = st.number_input("📦 Number of Lots", min_value=1, max_value=50,
                                value=int(st.session_state["num_lots"]),
                                help="1 lot = 75 NIFTY shares. More lots = more margin required.")
    st.session_state["num_lots"] = num_lots

    st.markdown("---")
    st.metric("Max Daily Loss", f"₹{capital * risk_pct / 100:,.0f}")
    st.markdown("---")

    if st.session_state["strategy"] is not None:
        s = st.session_state["strategy"]
        running = getattr(s, "is_running", False)
        st.success(f"🟢 Strategy Ready\nRunning: {running}")
    else:
        st.warning("🔴 Not initialised\nGo to Profile tab ↓")

    st.markdown("---")
    if st.button("🔄 Reinitialise Strategy", use_container_width=True):
        st.session_state["strategy"] = None
        strat, msg = _build_strategy()
        if strat:
            strat.capital = capital
            strat.risk_pct = risk_pct
            st.session_state["strategy"] = strat
            st.success(msg)
        else:
            st.error(msg)
        st.rerun()

    st.markdown("---")
    st.caption("Paper Trading Terminal v1.0")
    st.caption("Powered by Fyers API v3")


if st.session_state["strategy"] is not None:
    st.session_state["strategy"].capital = capital
    st.session_state["strategy"].risk_pct = risk_pct
    st.session_state["strategy"].num_lots = num_lots

st.markdown(
    """<h1 style='text-align:center;color:#00d4aa;margin-bottom:0'>
        📊 NIFTY Options Paper Trading Terminal
    </h1>
    <p style='text-align:center;color:#888;margin-top:2px;font-size:13px'>
        Supertrend Gamma Strangle · Weekly NIFTY Options · Paper Mode
    </p>""",
    unsafe_allow_html=True,
)
st.markdown("---")

tab_profile, tab_live, tab_positions, tab_log, tab_pnl, tab_control = st.tabs([
    "⚙️ Profile", "📡 Live Terminal", "📂 Open Positions",
    "📋 Trade Log", "📊 P&L History", "🎛️ Strategy Control",
])

with tab_profile:
    from ui.profile_tab import render_profile_tab
    render_profile_tab()

    st.markdown("---")
    st.markdown("### 🚀 Step 2 — Initialise Strategy Engine")
    st.caption("After saving credentials above, click this button to start the engine.")

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("⚡ Initialise Strategy", type="primary", use_container_width=True):
            with st.spinner("Building strategy engine…"):
                strat, msg = _build_strategy()
            if strat:
                strat.capital = st.session_state["capital"]
                strat.risk_pct = st.session_state["risk_pct"]
                st.session_state["strategy"] = strat
                st.success(msg)
                st.info("✅ Now go to **🎛️ Strategy Control** tab → click **Start Strategy**.")
            else:
                st.error(msg)
    with col2:
        if st.session_state["strategy"] is not None:
            st.success("✅ Ready")
        else:
            st.warning("⚠️ Not init")

with tab_live:
    from ui.live_terminal_tab import render_live_terminal_tab
    render_live_terminal_tab(st.session_state["strategy"])

with tab_positions:
    from ui.other_tabs import render_positions_tab
    render_positions_tab(st.session_state["strategy"])

with tab_log:
    from ui.other_tabs import render_trade_log_tab
    render_trade_log_tab()

with tab_pnl:
    from ui.other_tabs import render_pnl_history_tab
    render_pnl_history_tab()

with tab_control:
    from ui.other_tabs import render_strategy_control_tab
    render_strategy_control_tab(st.session_state["strategy"])

if st.session_state.get("strategy") and getattr(st.session_state["strategy"], "is_running", False):
    st.markdown(
        "<script>setTimeout(function(){window.location.reload();}, 30000);</script>",
        unsafe_allow_html=True,
    )
