"""
Live Terminal Tab — real-time market overview.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from core.config import PAPER_MODE, IST
from utils.logger import get_logger

if TYPE_CHECKING:
    from core.strategy import GammaStrangleStrategy

log = get_logger(__name__)


def render_live_terminal_tab(strategy: Optional["GammaStrangleStrategy"]) -> None:
    st.markdown("## 📡 Live Market Terminal")

    if PAPER_MODE:
        st.warning("🟡 **PAPER TRADING MODE ACTIVE** — No real orders will be placed")

    if strategy is None:
        st.info("Configure credentials in the **Profile** tab and start the strategy.")
        return

    # ── Key metrics row ──────────────────────────────────────────────────────
    spot = strategy.spot or 0.0
    st_dir = strategy.supertrend_dir
    vwap = strategy.vwap or 0.0
    net_delta = strategy.get_net_delta()
    gamma_score = strategy.get_gamma_risk_score()
    live_mtm = strategy.calculate_mtm()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏷️ NIFTY Spot", f"{spot:,.2f}")
        trend_color = "🟢" if st_dir == "BULLISH" else "🔴" if st_dir == "BEARISH" else "⚪"
        st.metric("📈 Supertrend", f"{trend_color} {st_dir}")
    with col2:
        st.metric("⚡ VWAP", f"{vwap:,.2f}")
        delta_color = "🟡" if abs(net_delta) > 0.1 else "🟢"
        st.metric("Δ Net Delta", f"{delta_color} {net_delta:+.4f}")
    with col3:
        # Gamma risk indicator
        if gamma_score > 70:
            g_label = "🔴 HIGH RISK"
        elif gamma_score > 50:
            g_label = "🟡 MODERATE"
        else:
            g_label = "🟢 LOW RISK"
        st.metric("Γ Gamma Risk", g_label, f"Score: {gamma_score:.1f}")

        mtm_color = "normal" if live_mtm >= 0 else "inverse"
        st.metric("💰 Live MTM", f"₹{live_mtm:+,.0f}", delta_color=mtm_color)

    st.markdown("---")

    # ── Gamma risk progress bar ───────────────────────────────────────────────
    st.markdown("#### Gamma Risk Gauge")
    st.progress(min(gamma_score / 100, 1.0), text=f"Gamma Risk: {gamma_score:.1f} / 100")

    # ── Strategy state ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Strategy State")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status = "🟢 Running" if strategy.is_running else "🔴 Stopped"
        st.info(f"**Status**: {status}")
    with col2:
        st.info(f"**Capital**: ₹{strategy.capital:,.0f}")
    with col3:
        st.info(f"**Daily PnL**: ₹{strategy._daily_pnl:+,.0f}")
    with col4:
        st.info(f"**Trades Today**: {strategy._trades_today}")

    # ── Last update ───────────────────────────────────────────────────────────
    st.caption(f"Last updated: {datetime.now(IST).strftime('%H:%M:%S IST')}")
