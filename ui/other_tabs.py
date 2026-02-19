"""
Remaining UI tabs:
- Open Positions
- Trade Log
- P&L History
- Strategy Control
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
from typing import Optional, TYPE_CHECKING

from data.database import (
    get_open_trades, get_all_trades, get_all_daily_summaries
)
from core.config import IST, PAPER_MODE
from utils.logger import get_logger

if TYPE_CHECKING:
    from core.strategy import GammaStrangleStrategy

log = get_logger(__name__)


# ─── OPEN POSITIONS TAB ──────────────────────────────────────────────────────

def render_positions_tab(strategy: Optional["GammaStrangleStrategy"]) -> None:
    st.markdown("## 📂 Open Positions")

    if strategy is None:
        st.info("No strategy running. Configure credentials in Profile tab.")
        return

    open_trades = get_open_trades()

    if not open_trades:
        st.success("✅ No open positions.")
        return

    rows = []
    for trade in open_trades:
        trade_id = trade["id"]
        positions = strategy.active_positions.get(trade_id, [])

        # Short legs
        for pos in [p for p in positions if p.side == "SELL" and not p.is_hedge]:
            greeks = pos.greeks
            rows.append({
                "Trade ID": trade_id,
                "Strike": pos.strike,
                "Type": pos.option_type,
                "Side": pos.side,
                "Entry ₹": f"{pos.entry_price:.2f}",
                "Current ₹": f"{pos.current_price:.2f}",
                "P&L ₹": f"{pos.pnl:+.0f}",
                "Delta": f"{greeks.get('delta', 0):.3f}",
                "Gamma": f"{greeks.get('gamma', 0):.5f}",
                "Hedge": "No",
            })
        # Hedge legs
        for pos in [p for p in positions if p.is_hedge]:
            greeks = pos.greeks
            rows.append({
                "Trade ID": trade_id,
                "Strike": pos.strike,
                "Type": pos.option_type,
                "Side": "BUY",
                "Entry ₹": f"{pos.entry_price:.2f}",
                "Current ₹": f"{pos.current_price:.2f}",
                "P&L ₹": f"{pos.pnl:+.0f}",
                "Delta": f"{greeks.get('delta', 0):.3f}",
                "Gamma": f"{greeks.get('gamma', 0):.5f}",
                "Hedge": "Yes",
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Aggregate summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        total_pnl = strategy.calculate_mtm()
        net_delta = strategy.get_net_delta()
        gamma_score = strategy.get_gamma_risk_score()
        with col1:
            st.metric("Total Unrealised P&L", f"₹{total_pnl:+,.0f}")
        with col2:
            st.metric("Net Delta", f"{net_delta:+.4f}")
        with col3:
            st.metric("Gamma Risk Score", f"{gamma_score:.1f}/100")


# ─── TRADE LOG TAB ────────────────────────────────────────────────────────────

def render_trade_log_tab() -> None:
    st.markdown("## 📋 Trade Log")

    all_trades = get_all_trades()
    if not all_trades:
        st.info("No trades recorded yet.")
        return

    rows = []
    for t in all_trades:
        from data.database import get_adjustments_for_trade
        adjs = get_adjustments_for_trade(t["id"])
        adj_desc = "; ".join(
            f"L{a['level']}: {a.get('action','')}" for a in adjs
        ) if adjs else "—"

        rows.append({
            "ID":          t["id"],
            "Date":        str(t.get("trade_date", "")),
            "Entry Time":  _fmt_dt(t.get("entry_time")),
            "Exit Time":   _fmt_dt(t.get("exit_time")),
            "CE Strike":   t.get("ce_strike", ""),
            "PE Strike":   t.get("pe_strike", ""),
            "Premium ₹":   f"{t.get('premium_collected', 0):.0f}",
            "Realised P&L ₹": f"{t.get('realized_pnl', 0) or 0:+.0f}",
            "Status":      t.get("status", ""),
            "Close Reason":t.get("close_reason", "—"),
            "Adj Level":   t.get("adjustment_level", 0),
            "Adjustments": adj_desc,
        })

    df = pd.DataFrame(rows)

    # Colour P&L column
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export
    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️ Export Trade Log CSV",
        csv,
        file_name=f"trade_log_{date.today()}.csv",
        mime="text/csv",
    )


# ─── P&L HISTORY TAB ─────────────────────────────────────────────────────────

def render_pnl_history_tab() -> None:
    st.markdown("## 📊 P&L History")

    summaries = get_all_daily_summaries()
    all_trades = get_all_trades()

    if not summaries and not all_trades:
        st.info("No history available yet.")
        return

    # ── Daily summary table ───────────────────────────────────────────────────
    if summaries:
        st.markdown("### Daily Summary")
        df_day = pd.DataFrame(summaries)
        df_day["trade_date"] = pd.to_datetime(df_day["trade_date"])
        df_day = df_day.sort_values("trade_date", ascending=False)
        df_day["net_pnl"] = df_day["net_pnl"].map(lambda x: f"₹{x:+,.0f}")
        df_day["win_rate"] = df_day["win_rate"].map(lambda x: f"{x:.1f}%")
        display_cols = ["trade_date", "total_trades", "winning_trades", "net_pnl", "max_drawdown", "win_rate"]
        st.dataframe(df_day[display_cols], use_container_width=True, hide_index=True)

    # ── Weekly summary ────────────────────────────────────────────────────────
    if all_trades:
        st.markdown("### Weekly Summary")
        df_trades = pd.DataFrame(all_trades)
        df_trades["trade_date"] = pd.to_datetime(df_trades["trade_date"])
        df_trades["week"] = df_trades["trade_date"].dt.isocalendar().week
        df_trades["year"] = df_trades["trade_date"].dt.year

        closed = df_trades[df_trades["status"] == "CLOSED"].copy()
        if not closed.empty:
            closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0)
            weekly = (
                closed.groupby(["year", "week"])
                .agg(
                    trades=("id", "count"),
                    net_pnl=("realized_pnl", "sum"),
                    wins=("realized_pnl", lambda x: (x > 0).sum()),
                )
                .reset_index()
            )
            weekly["win_rate"] = (weekly["wins"] / weekly["trades"] * 100).map(lambda x: f"{x:.0f}%")
            weekly["net_pnl_fmt"] = weekly["net_pnl"].map(lambda x: f"₹{x:+,.0f}")
            st.dataframe(
                weekly[["year", "week", "trades", "net_pnl_fmt", "win_rate"]],
                use_container_width=True, hide_index=True
            )

        # ── Equity curve ──────────────────────────────────────────────────────
        st.markdown("### Equity Curve")
        if not closed.empty:
            closed = closed.sort_values("exit_time")
            closed["cum_pnl"] = closed["realized_pnl"].cumsum()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=closed["exit_time"],
                y=closed["cum_pnl"],
                mode="lines+markers",
                name="Cumulative P&L",
                line=dict(color="#00d4aa", width=2),
                fill="tonexty",
                fillcolor="rgba(0,212,170,0.1)",
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig.update_layout(
                title="Cumulative P&L (Paper Trading)",
                xaxis_title="Date",
                yaxis_title="P&L (₹)",
                template="plotly_dark",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Win/Loss bar chart
            st.markdown("### Daily P&L Bar Chart")
            if summaries:
                df_bar = pd.DataFrame(summaries)
                df_bar["trade_date"] = pd.to_datetime(df_bar["trade_date"])
                df_bar = df_bar.sort_values("trade_date")
                colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in df_bar["net_pnl"]]
                fig2 = go.Figure(go.Bar(
                    x=df_bar["trade_date"],
                    y=df_bar["net_pnl"],
                    marker_color=colors,
                    name="Daily P&L",
                ))
                fig2.update_layout(
                    title="Daily P&L",
                    xaxis_title="Date",
                    yaxis_title="P&L (₹)",
                    template="plotly_dark",
                    height=350,
                )
                st.plotly_chart(fig2, use_container_width=True)


# ─── STRATEGY CONTROL TAB ─────────────────────────────────────────────────────

def render_strategy_control_tab(strategy: Optional["GammaStrangleStrategy"]) -> None:
    st.markdown("## 🎛️ Strategy Control")

    if strategy is None:
        st.error("Strategy not initialised. Complete Profile setup first.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### ▶️ Start")
        if st.button("🟢 Start Strategy", use_container_width=True, type="primary", key="btn_start_strategy"):
            strategy.start()
            st.success("Strategy started!")
            st.rerun()

    with col2:
        st.markdown("### ⏹️ Stop")
        if st.button("🔴 Stop Strategy", use_container_width=True, key="btn_stop_strategy"):
            strategy.stop()
            st.warning("Strategy stopped. Existing positions remain open.")
            st.rerun()

    with col3:
        st.markdown("### 🔁 Reset")
        if st.button("⚠️ Reset Day", use_container_width=True, key="btn_reset_day"):
            if st.session_state.get("confirm_reset"):
                strategy.reset_day()
                st.session_state["confirm_reset"] = False
                st.success("Day reset! All positions closed.")
                st.rerun()
            else:
                st.session_state["confirm_reset"] = True
                st.warning("Click again to confirm reset (closes all positions).")

    st.markdown("---")

    # ── Manual trade controls ─────────────────────────────────────────────────
    st.markdown("### 🖐️ Manual Controls")

    col1, col2 = st.columns(2)
    with col1:
        strategy_type = st.selectbox(
            "Strategy Version",
            ["GAMMA_STRANGLE", "EXPIRY"],
            help="GAMMA_STRANGLE = regular. EXPIRY = after 9:45 ATM+100 version."
        )
        if st.button("📥 Force New Entry", use_container_width=True, key="btn_force_entry"):
            trade_id = strategy.open_position(strategy_type=strategy_type)
            if trade_id:
                st.success(f"✅ Paper trade opened! Trade ID: {trade_id}")
            else:
                st.error("❌ Entry rejected. Check entry conditions.")

    with col2:
        open_trades = get_open_trades()
        if open_trades:
            trade_ids = [str(t["id"]) for t in open_trades]
            selected = st.selectbox("Select Trade to Close", trade_ids)
            close_reason = st.text_input("Close Reason", value="MANUAL")
            if st.button("📤 Force Close Trade", use_container_width=True, key="btn_force_close"):
                pnl = strategy.close_position(int(selected), reason=close_reason)
                st.success(f"Trade {selected} closed. P&L: ₹{pnl:+.0f}")
                st.rerun()
        else:
            st.info("No open positions to close.")

    st.markdown("---")

    # ── Risk parameters display ────────────────────────────────────────────────
    st.markdown("### 📋 Current Risk Parameters")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Capital", f"₹{strategy.capital:,.0f}")
    with col2:
        st.metric("Risk % / Day", f"{strategy.risk_pct:.1f}%")
    with col3:
        max_loss = strategy.capital * strategy.risk_pct / 100
        st.metric("Max Daily Loss", f"₹{max_loss:,.0f}")
    with col4:
        lots = getattr(strategy, "num_lots", 1)
        st.metric("Lots", f"{lots} × 65 = {lots*65} qty")

    st.markdown("---")

    # ── Margin Calculator ─────────────────────────────────────────────────────
    st.markdown("### 💰 Margin Required (Live from Fyers)")
    st.caption(
        "Margin is fetched directly from Fyers API using all 4 legs together "
        "(SELL 20-25Δ CE + SELL 20-25Δ PE + BUY 0.10Δ CE hedge + BUY 0.10Δ PE hedge). "
        "SPAN + Exposure with actual hedge benefit as calculated by the exchange."
    )

    col_refresh, col_lots_info = st.columns([1, 3])
    with col_refresh:
        fetch_margin = st.button("🔄 Fetch Margin from Fyers", use_container_width=True, key="btn_fetch_margin")
    with col_lots_info:
        lots = getattr(strategy, "num_lots", 1)
        qty  = lots * 65
        st.info(f"Lots: **{lots}** | Qty per leg: **{qty}** (1 lot = 65 shares)")

    if fetch_margin or st.session_state.get("margin_data"):
        if fetch_margin:
            with st.spinner("Calling Fyers margin API…"):
                try:
                    m = strategy.calculate_margin_required()
                    st.session_state["margin_data"] = m
                except Exception as e:
                    st.error(f"Error: {e}")
                    m = None
        else:
            m = st.session_state.get("margin_data")

        if m:
            if m.get("error") or m.get("source") == "unavailable":
                st.error(
                    "Could not fetch live margin from Fyers.\n\n"
                    f"Reason: {m.get('error', 'Unknown')}\n\n"
                    "Make sure:\n"
                    "- You have a valid Fyers access token (complete OAuth in Profile tab)\n"
                    "- The strategy is initialised with a live token\n"
                    "- Market hours: margin API works best between 9:00-15:30 IST"
                )
            else:
                total    = m.get("total_required", 0) or 0
                span     = m.get("span_margin",     0) or 0
                exposure = m.get("exposure_margin", 0) or 0
                benefit  = m.get("hedge_benefit",   0) or 0

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 SPAN Margin", f"₹{span:,.0f}",
                              help="Exchange SPAN margin after hedge netting")
                with col2:
                    st.metric("📈 Exposure Margin", f"₹{exposure:,.0f}",
                              help="Broker exposure margin requirement")
                with col3:
                    st.metric("💵 Total Required", f"₹{total:,.0f}",
                              help="SPAN + Exposure as computed by Fyers")

                if benefit > 0:
                    st.success(f"✅ Hedge Benefit Applied by Broker: ₹{benefit:,.0f} saved vs naked position")

                # Leg breakdown
                legs = m.get("legs", [])
                if legs:
                    st.markdown("**Legs sent to margin API:**")
                    leg_rows = []
                    for leg in legs:
                        leg_rows.append({
                            "Symbol": leg["symbol"],
                            "Qty":    leg["qty"],
                            "Side":   "SELL" if leg["side"] == -1 else "BUY",
                        })
                    import pandas as pd
                    st.dataframe(pd.DataFrame(leg_rows), hide_index=True, use_container_width=True)

                # Capital utilisation
                if total > 0 and strategy.capital > 0:
                    cap_util = total / strategy.capital * 100
                    color = "normal" if cap_util < 50 else "inverse"
                    st.progress(
                        min(cap_util / 100, 1.0),
                        text=f"Capital Utilisation: {cap_util:.1f}% of ₹{strategy.capital:,.0f}"
                    )
                    if cap_util > 80:
                        st.warning("⚠️ Margin > 80% of capital. Consider reducing lots.")

                st.caption(f"Source: Fyers API | Spot ref: {m.get('spot', 0):,.0f} | Lots: {m.get('lots',1)} | Qty/leg: {m.get('qty',0)}")
    else:
        st.info("Click **Fetch Margin from Fyers** to get live margin calculation.")


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return str(dt)
