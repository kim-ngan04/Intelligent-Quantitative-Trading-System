"""
Live Trading Module
===================

Functions for the Live Trading tab in FinRL Trading Dashboard.
Handles portfolio management, order placement, strategy execution, and performance monitoring.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


def show_live_trading():
    """Show live trading interface."""
    from trading.alpaca_manager import create_alpaca_account_from_env
    
    st.header("Live Trading")

    # Check if trading is configured
    try:
        if not create_alpaca_account_from_env:
            st.error("Alpaca trading module not available")
            return
            
        account = create_alpaca_account_from_env()
        st.success(f"Connected to Alpaca account (Paper: {account.is_paper})")

        tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "⚠️ Emergency Orders", "Strategy Execution", "Performance Monitoring"])

        with tab1:
            st.subheader("Current Portfolio")
            
            # Initialize variables OUTSIDE if block to avoid NameError
            from trading.alpaca_manager import AlpacaManager
            manager = AlpacaManager([account])
            positions_df = pd.DataFrame()
            
            # Auto-refresh option
            col_refresh1, col_refresh2 = st.columns([2, 1])
            with col_refresh1:
                auto_refresh = st.checkbox("Refresh portfolio data", value=False, help="Check and click button to load")
            with col_refresh2:
                manual_refresh = st.button("🔄 Refresh Now", use_container_width=True)
            
            if manual_refresh or auto_refresh:
                with st.spinner("Loading portfolio..."):
                    try:
                        # Get account info
                        account_info = manager.get_account_info()
                        positions = manager.get_positions()

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Portfolio Value", f"${float(account_info.get('portfolio_value', 0)):,.2f}")
                        with col2:
                            st.metric("Cash", f"${float(account_info.get('cash', 0)):,.2f}")
                        with col3:
                            st.metric("Buying Power", f"${float(account_info.get('buying_power', 0)):,.2f}")

                        # Positions table with close button
                        if positions:
                            positions_df = pd.DataFrame(positions)
                            st.markdown("#### Open Positions")
                            st.dataframe(
                                positions_df[['symbol', 'qty', 'avg_entry_price', 'market_value', 'unrealized_pl']], 
                                width='stretch',
                                height=250
                            )
                            
                            # Quick close position section
                            st.markdown("#### Close Position")
                            col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
                            with col_c1:
                                position_to_close = st.selectbox(
                                    "Select position to close",
                                    options=positions_df['symbol'].tolist() if len(positions_df) > 0 else [],
                                    key="close_position"
                                )
                            with col_c2:
                                close_pct = st.slider("Close %", 0, 100, 100, 10, key="close_pct", help="100% = sell all")
                            with col_c3:
                                st.write("")  # Spacer
                                # ✅ FIX: Disable button when no positions
                                if st.button("📤 Close", use_container_width=True, disabled=len(positions_df) == 0):
                                    if position_to_close and position_to_close != "":
                                        with st.spinner("Closing position..."):
                                            try:
                                                pos_row = positions_df[positions_df['symbol'] == position_to_close].iloc[0]
                                                qty_to_sell = int(float(pos_row['qty']) * (close_pct / 100))
                                                
                                                from trading.alpaca_manager import OrderRequest
                                                order = OrderRequest(
                                                    symbol=position_to_close,
                                                    quantity=qty_to_sell,
                                                    side='sell',
                                                    order_type='market'
                                                )
                                                response = manager.place_order(order)
                                                st.success(f"✅ Close order placed: {position_to_close} x{qty_to_sell} (ID: {response.order_id})")
                                            except Exception as e:
                                                st.error(f"❌ Failed: {e}")
                            
                            # Last trading day's orders
                            st.divider()
                            st.markdown("#### Orders from Last Trading Day")
                            try:
                                # Get all orders
                                all_orders = manager.get_orders(limit=500, direction='desc')
                                
                                if all_orders:
                                    # Find the most recent trading date
                                    last_trading_date = None
                                    for order in all_orders:
                                        order_date_str = order.get('created_at', '')
                                        if order_date_str:
                                            try:
                                                order_date = pd.to_datetime(order_date_str).date()
                                                if last_trading_date is None or order_date > last_trading_date:
                                                    last_trading_date = order_date
                                            except:
                                                pass
                                    
                                    # Filter orders from last trading date
                                    recent_orders = []
                                    if last_trading_date:
                                        for order in all_orders:
                                            order_date_str = order.get('created_at', '')
                                            if order_date_str:
                                                try:
                                                    order_date = pd.to_datetime(order_date_str).date()
                                                    if order_date == last_trading_date:
                                                        recent_orders.append(order)
                                                except:
                                                    pass
                                        st.caption(f"Showing all orders from {last_trading_date}")
                                    
                                    if recent_orders:
                                        orders_display = []
                                        for order in recent_orders:
                                            try:
                                                # Safely parse submitted_at with fallback
                                                submitted_time = order.get('submitted_at', '')
                                                if submitted_time:
                                                    time_str = pd.to_datetime(submitted_time).strftime('%Y-%m-%d %H:%M:%S')
                                                else:
                                                    time_str = 'N/A'
                                                
                                                # Safely parse filled price
                                                filled_price = order.get('filled_avg_price')
                                                if filled_price and float(filled_price) > 0:
                                                    price_str = f"${float(filled_price):.2f}"
                                                else:
                                                    price_str = '-'
                                                
                                                orders_display.append({
                                                    'Time': time_str,
                                                    'Symbol': order.get('symbol', ''),
                                                    'Side': str(order.get('side', '')).upper(),
                                                    'Qty': f"{float(order.get('qty', 0)):.0f}",
                                                    'Status': str(order.get('status', '')).upper(),
                                                    'Filled Price': price_str
                                                })
                                            except Exception as order_err:
                                                st.warning(f"Could not parse order: {order_err}")
                                                continue
                                        
                                        if orders_display:
                                            st.dataframe(pd.DataFrame(orders_display), use_container_width=True, height=300)
                                        else:
                                            st.info("No valid orders to display")
                                else:
                                    st.info("No orders yet")
                            except Exception as e:
                                st.error(f"❌ Error loading order history: {str(e)}")
                        else:
                            st.info("📭 No open positions")

                    except Exception as e:
                        st.error(f"Failed to load portfolio: {e}")
            else:
                st.info("📋 Click **Refresh Now** to load portfolio data")

        with tab2:
            st.subheader("⚠️ Emergency Orders")
            st.warning(
                "🚨 **EMERGENCY ONLY** - Use this for manual emergency trades. "
                "For normal strategy execution, go to **Strategy Execution** tab."
            )

            # Place order form with dry-run
            with st.form("place_emergency_order"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    symbol = st.text_input("Symbol", "AAPL").upper()
                with col2:
                    quantity = st.number_input("Quantity", min_value=1, value=10)
                with col3:
                    side = st.selectbox("Side", ["buy", "sell"])

                order_type = st.selectbox("Order Type", ["market", "limit"])
                limit_price = st.number_input("Limit Price", min_value=0.01, step=0.01) if order_type == "limit" else None

                # Dry-run option
                col_dry1, col_dry2 = st.columns([2, 1])
                with col_dry1:
                    dry_run = st.checkbox("Dry Run (preview only, don't execute)", value=True)
                with col_dry2:
                    if dry_run:
                        st.info("ℹ️ Preview mode ON")
                    else:
                        st.error("⚠️ LIVE mode ON")

                submitted = st.form_submit_button("Place Emergency Order")
                if submitted:
                    try:
                        from trading.alpaca_manager import AlpacaManager, OrderRequest
                        manager = AlpacaManager([account])

                        order = OrderRequest(
                            symbol=symbol,
                            quantity=quantity,
                            side=side,
                            order_type=order_type,
                            limit_price=limit_price
                        )

                        if dry_run:
                            st.info(
                                f"**DRY RUN:** Would place order:\n"
                                f"- Symbol: {symbol}\n"
                                f"- Quantity: {quantity}\n"
                                f"- Side: {side}\n"
                                f"- Type: {order_type}\n"
                                f"- Limit Price: {limit_price if limit_price else 'N/A'}"
                            )
                        else:
                            response = manager.place_order(order)
                            st.success(f"✅ Order placed: {response.order_id}")

                    except Exception as e:
                        st.error(f"❌ Failed: {e}")

        with tab3:
            st.subheader("Strategy Execution")
            _show_strategy_execution(account)

        with tab4:
            st.subheader("Performance Monitoring")
            _show_performance_monitoring(account)

    except Exception as e:
        st.error(f"Trading not configured: {e}")
        st.info("Please set up Alpaca API credentials in environment variables")


def _show_performance_monitoring(account):
    """Render the Performance Monitoring tab inside Live Trading."""
    from trading.alpaca_manager import AlpacaManager
    from trading.performance_analyzer import (
        get_first_order_date, get_portfolio_history,
        get_benchmark_data, compute_performance_metrics,
    )

    manager = AlpacaManager([account])

    # ── Date range ─────────────────────────────────────────────────────────────
    col_d1, col_d2, col_d3 = st.columns([1, 1, 1])
    with col_d1:
        auto_start = st.checkbox("Tự động lấy ngày đầu tiên có lệnh", value=True)
    with col_d2:
        manual_start = st.date_input(
            "Từ ngày", value=datetime.today() - timedelta(days=30),
            disabled=auto_start, key="pm_start"
        )
    with col_d3:
        end_date_input = st.date_input("Đến ngày", value=datetime.today(), key="pm_end")

    if st.button("🔄 Tải dữ liệu", type="primary"):
        with st.spinner("Đang tải portfolio history và benchmark..."):
            try:
                import pytz
                utc = pytz.utc
                
                # === DATE HANDLING WITH TIMEZONE NORMALIZATION ===
                # Chuẩn hóa end_dt: sử dụng cuối ngày hôm đó (23:59:59) để không mất dữ liệu
                end_dt = datetime.combine(end_date_input, datetime.max.time()).replace(tzinfo=utc)
                
                # Xác định start_dt
                if auto_start:
                    first_date = get_first_order_date(manager)
                    if first_date is None:
                        st.warning("Chưa có lệnh nào trong tài khoản. Sử dụng mặc định: 30 ngày trước.")
                        start_dt = end_dt - timedelta(days=30)
                    else:
                        # Đảm bảo first_date có timezone
                        if first_date.tzinfo is None:
                            first_date = first_date.replace(tzinfo=utc)
                        # Lùi 1 ngày để có dữ liệu trước lệnh đầu tiên
                        start_dt = first_date - timedelta(days=1)
                else:
                    start_dt = datetime.combine(manual_start, datetime.min.time()).replace(tzinfo=utc)
                
                # === CRITICAL VALIDATION: Ensure start_date < end_date ===
                if start_dt.date() >= end_dt.date():
                    st.error(
                        f"❌ Lỗi: Ngày bắt đầu ({start_dt.date()}) >= ngày kết thúc ({end_dt.date()}). "
                        f"Hệ thống tự động điều chỉnh lùi ngày bắt đầu 7 ngày."
                    )
                    start_dt = end_dt - timedelta(days=7)  # Fallback: 7 days before end
                    st.info(f"✅ Ngày bắt đầu điều chỉnh thành: {start_dt.date()}")
                
                # === FETCH DATA ===
                portfolio_df = get_portfolio_history(manager, start_dt, end_dt)
                
                if portfolio_df.empty:
                    st.error("❌ Không thể tải portfolio history. Kiểm tra ngày hoặc kết nối API.")
                    return
                
                # Benchmark: sử dụng cùng date range, không cộng thêm ngày
                fmp_end = end_date_input.strftime("%Y-%m-%d")
                benchmark_df = get_benchmark_data(start_dt.date().isoformat(), fmp_end)
                
                # Debug: Show benchmark data status
                #if benchmark_df.empty:
                 #   st.warning("⚠️ Benchmark data (SPY/QQQ) không có dữ liệu - Chart sẽ chỉ show Portfolio")
                #else:
                 #   st.success(f"✅ Benchmark loaded: {list(benchmark_df.columns)}, {len(benchmark_df)} dates")

                #if portfolio_df.empty:
                 #   st.warning("Không có dữ liệu portfolio history trong khoảng thời gian này.")
                  #  return

                # ── Metrics ───────────────────────────────────────────────────
                st.markdown("#### Chỉ số hiệu suất")
                equity_series = portfolio_df.set_index("date")["equity"]
                pm = compute_performance_metrics(equity_series)

                cols_m = st.columns(5)
                cols_m[0].metric("Total Return",      f"{pm['total_return']:.2f}%")
                cols_m[1].metric("Annual Return",     f"{pm['annual_return']:.2f}%")
                cols_m[2].metric("Volatility (Ann.)", f"{pm['annual_volatility']:.2f}%")
                cols_m[3].metric("Sharpe Ratio",      f"{pm['sharpe_ratio']:.2f}")
                cols_m[4].metric("Max Drawdown",      f"{pm['max_drawdown']:.2f}%")

                # Benchmark metrics - hiển thị riêng từng dòng
                if not benchmark_df.empty:
                    st.markdown("**Benchmark Performance:**")
                    for bm in benchmark_df.columns:
                        bm_series = benchmark_df[bm].dropna()
                        if len(bm_series) > 1:
                            bm_m = compute_performance_metrics(bm_series)
                            st.markdown(f"• **{bm}**: Return {bm_m['total_return']:.2f}% | "
                                        f"Sharpe {bm_m['sharpe_ratio']:.2f} | "
                                        f"MaxDD {bm_m['max_drawdown']:.2f}%")

                st.divider()

                # ── Equity curve vs benchmarks ────────────────────────────────
                st.markdown("#### Equity Curve so với Benchmark")
                fig = go.Figure()
                
                traces_added = 0

                # === Add Benchmarks FIRST (so Portfolio is on top) ===
                colors = {"SPY": "#FF6D00", "QQQ": "#00BFA5"}
                if not benchmark_df.empty:
                    for bm in benchmark_df.columns:
                        bm_s = benchmark_df[bm].dropna()
                        if len(bm_s) > 0:
                            bm_norm = bm_s / bm_s.iloc[0]
                            fig.add_trace(go.Scatter(
                                x=bm_norm.index, y=bm_norm.values,
                                name=bm, line=dict(dash="dash", width=1.5, color=colors.get(bm, "gray"))
                            ))
                            traces_added += 1

                # === Add Portfolio LAST (so it's on top, more visible) ===
                eq = equity_series.dropna()
                
                if len(eq) > 0:
                    # FIX: Find first non-zero value to avoid division by zero → inf
                    first_nonzero_idx = (eq != 0).idxmax() if (eq != 0).any() else None
                    
                    if first_nonzero_idx is not None and eq[first_nonzero_idx] != 0:
                        eq_clean = eq[first_nonzero_idx:]  # Start from first non-zero
                        eq_norm = eq_clean / eq_clean.iloc[0]
                        
                        if not np.isinf(eq_norm.values).any():  # Check no infinity values
                            fig.add_trace(go.Scatter(
                                x=eq_norm.index, y=eq_norm.values,
                                name="Portfolio", line=dict(width=1.5, color="#1A237E"),
                                hovertemplate="<b>Portfolio</b><br>Date: %{x|%Y-%m-%d}<br>Return: %{y:.4f}<extra></extra>"
                            ))
                            traces_added += 1

                fig.update_layout(
                    title="Normalized Performance (Base = 1.0)",
                    xaxis_title="Date", yaxis_title="Return",
                    hovermode="x unified", height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0)
                )
                
                if traces_added == 0:
                    st.warning("❌ Không có dữ liệu để hiển thị chart (equity hoặc benchmark trống)")
                else:
                    st.plotly_chart(fig, use_container_width='stretch')

                # ── Daily P&L chart ───────────────────────────────────────────
                st.markdown("#### P&L hàng ngày")
                pnl = portfolio_df.set_index("date")["profit_loss"].dropna()
                if len(pnl) > 0:
                    bar_colors = ["#00C853" if v >= 0 else "#D50000" for v in pnl.values]
                    fig2 = go.Figure(go.Bar(
                        x=pnl.index, y=pnl.values,
                        marker_color=bar_colors,
                        name="Daily P&L"
                    ))
                    fig2.update_layout(
                        title="Daily Profit / Loss (USD)",
                        xaxis_title="Date", yaxis_title="P&L ($)",
                        height=300
                    )
                    st.plotly_chart(fig2, use_container_width='stretch')

                # ── Positions table ───────────────────────────────────────────
                st.markdown("#### Vị thế hiện tại")
                positions = manager.get_positions()
                if positions:
                    pos_df = pd.DataFrame(positions)
                    display_cols = [c for c in
                        ["symbol", "qty", "avg_entry_price", "current_price",
                         "market_value", "unrealized_pl", "unrealized_plpc"]
                        if c in pos_df.columns]
                    pos_df_show = pos_df[display_cols].copy()
                    for col in ["avg_entry_price", "current_price", "market_value"]:
                        if col in pos_df_show.columns:
                            pos_df_show[col] = pd.to_numeric(pos_df_show[col], errors="coerce")
                    for col in ["unrealized_pl", "unrealized_plpc"]:
                        if col in pos_df_show.columns:
                            pos_df_show[col] = pd.to_numeric(pos_df_show[col], errors="coerce")

                    def _color_pnl(val):
                        try:
                            return "color: green" if float(val) >= 0 else "color: red"
                        except:
                            return ""

                    fmt = {}
                    for c in ["avg_entry_price", "current_price", "market_value"]:
                        if c in pos_df_show.columns:
                            fmt[c] = "${:.2f}"
                    if "unrealized_pl" in pos_df_show.columns:
                        fmt["unrealized_pl"] = "${:+.2f}"
                    if "unrealized_plpc" in pos_df_show.columns:
                        fmt["unrealized_plpc"] = "{:+.2%}"

                    styled = pos_df_show.style.format(fmt)
                    if "unrealized_pl" in pos_df_show.columns:
                        styled = styled.applymap(_color_pnl, subset=["unrealized_pl"])

                    st.dataframe(styled, use_container_width='stretch', height=350)

                    # ── P&L bar chart per symbol ──────────────────────────────
                    if "unrealized_pl" in pos_df_show.columns:
                        pnl_sym = pos_df_show[["symbol", "unrealized_pl"]].copy()
                        pnl_sym["unrealized_pl"] = pd.to_numeric(pnl_sym["unrealized_pl"], errors="coerce")
                        pnl_sym = pnl_sym.sort_values("unrealized_pl")
                        bar_c = ["#00C853" if v >= 0 else "#D50000" for v in pnl_sym["unrealized_pl"]]
                        fig3 = go.Figure(go.Bar(
                            x=pnl_sym["symbol"], y=pnl_sym["unrealized_pl"],
                            marker_color=bar_c
                        ))
                        fig3.update_layout(
                            title="Unrealized P&L theo cổ phiếu",
                            xaxis_title="Symbol", yaxis_title="Unrealized P&L ($)",
                            height=350
                        )
                        st.plotly_chart(fig3, use_container_width='stretch')
                else:
                    st.info("Chưa có vị thế nào. Lệnh OPG sẽ khớp khi thị trường mở cửa.")

            except Exception as e:
                st.error(f"Lỗi tải dữ liệu: {e}")
                import traceback
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())
    else:
        st.info("Nhấn **Tải dữ liệu** để xem hiệu suất portfolio.")


def _show_strategy_execution(account):
    """Render the Strategy Execution tab inside Live Trading."""
    from trading.alpaca_manager import AlpacaManager

    manager = AlpacaManager([account])

    # ETF / index tickers to always exclude from individual stock orders
    _ETF_EXCLUDE = {"SPY", "QQQ", "IVV", "VOO", "VTI", "IWM", "DIA", "GLD", "SLV", "TLT", "BND"}

    # ── 0. Display selected strategy from Backtest ──────────────────────────
    st.markdown("#### 📊 Chiến lược đã chọn từ Backtest")
    
    if 'selected_strategy' in st.session_state and st.session_state.selected_strategy:
        strategy_data = st.session_state.selected_strategy
        
        # Display strategy info
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("📈 Strategy", strategy_data.get('name', 'N/A'))
        with col_info2:
            st.metric("📅 Period", strategy_data.get('period', 'N/A'))
        with col_info3:
            st.metric("✅ Status", "Ready to Deploy")
        
        # Display backtest metrics
        st.subheader("Backtest Metrics")
        if 'metrics' in strategy_data:
            metrics = strategy_data['metrics']
            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
            with col_m1:
                st.metric("Total Return", f"{metrics.get('total_return', 0):.2f}%")
            with col_m2:
                st.metric("Annual Return", f"{metrics.get('annual_return', 0):.2f}%")
            with col_m3:
                st.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}")
            with col_m4:
                st.metric("Volatility", f"{metrics.get('annual_volatility', 0):.2f}%")
            with col_m5:
                st.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2f}%")
        
        # Extract weights from selected strategy
        weights_df = strategy_data.get('weights', pd.DataFrame())
        
        if weights_df.empty:
            st.error("❌ Strategy weights not found!")
            return
        
        st.success(f"✅ Loaded {len(weights_df)} stocks from backtest")
    else:
        st.warning("⚠️ No strategy selected from Backtest. Please run Strategy Backtesting first and select a strategy.")
        st.info("📋 Steps:\n1. Go to 'Strategy Backtesting'\n2. Run backtest\n3. Select strategy from results\n4. Return to Live Trading")
        
        # Fallback: Allow manual load
        st.subheader("💾 Or load from file (Fallback)")
        uploaded = st.file_uploader("Upload weights CSV", type=["csv"])
        
        if uploaded:
            try:
                raw = pd.read_csv(uploaded)
                # Simple parsing for uploaded file
                if "weight" in raw.columns and "gvkey" in raw.columns:
                    weights_df = raw[["gvkey", "weight"]].copy()
                    weights_df = weights_df[weights_df["weight"] > 0]
                    st.success(f"✅ Loaded {len(weights_df)} stocks from file")
                else:
                    st.error("❌ CSV must contain 'gvkey' and 'weight' columns")
                    return
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")
                return
        else:
            return
    
    # Remove ETF tickers
    weights_df = weights_df[~weights_df["gvkey"].isin(_ETF_EXCLUDE)].copy()

    # ── 1. Preview weights ─────────────────────────────────────────────────────
    st.markdown("#### 1. Weights Preview")
    col_tbl, col_chart = st.columns([1, 1])

    with col_tbl:
        st.dataframe(
            weights_df.sort_values("weight", ascending=False)
            .style.format({"weight": "{:.2%}"}),
            use_container_width='stretch',
            height=300,
        )

    with col_chart:
        chart_data = weights_df.nlargest(10, "weight").copy()
        others_w = 1.0 - chart_data["weight"].sum()
        if others_w > 1e-4:
            chart_data = pd.concat(
                [chart_data, pd.DataFrame([{"gvkey": "Others", "weight": others_w}])],
                ignore_index=True,
            )
        fig = px.pie(chart_data, names="gvkey", values="weight",
                     title=f"Top-10 Allocation ({len(weights_df)} stocks)", hole=0.35)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width='stretch')

    target_weights = {
        str(r["gvkey"]): float(r["weight"])
        for _, r in weights_df.iterrows()
    }

    # ── 3. Execution settings ──────────────────────────────────────────────────
    st.markdown("#### 2. Execution Settings")
    
    # ✨ NEW: Max Allocation Slider (Risk Management)
    st.markdown("**Portfolio Allocation Strategy:**")
    col_alloc1, col_alloc2 = st.columns([2, 1])
    with col_alloc1:
        max_allocation_pct = st.slider(
            "Max Portfolio Allocation %",
            min_value=30,
            max_value=100,
            value=75,
            step=5,
            help="""
            📊 % danh mục để mua cổ phiếu (phần còn lại giữ cash buffer)
            - 100% = Dùng hết tiền (Full Margin Risk - ⚠️ NGUY!)
            - 75% = Khuyến nghị (đặn $25k cash buffer)
            - 50% = Very Safe (giữ $50k cash)
            """
        )
    
    # Display allocation breakdown
    col_alloc_info1, col_alloc_info2, col_alloc_info3 = st.columns(3)
    try:
        # Try to get portfolio value from manager
        account_info = manager.get_account_info()
        portfolio_value = float(account_info.get('portfolio_value', 100000))
    except:
        portfolio_value = 100000
    
    deployed_amount = portfolio_value * (max_allocation_pct / 100)
    cash_amount = portfolio_value - deployed_amount
    
    with col_alloc_info1:
        st.metric("📈 Deployed", f"${deployed_amount:,.0f}", f"{max_allocation_pct}%")
    with col_alloc_info2:
        st.metric("💰 Cash Reserve", f"${cash_amount:,.0f}", f"{100 - max_allocation_pct}%")
    with col_alloc_info3:
        if max_allocation_pct == 100:
            st.warning("⚠️ Full Margin!")
        elif max_allocation_pct >= 80:
            st.info("🟡 Medium Risk")
        else:
            st.success("🟢 Low Risk")
    
    st.divider()
    
    # Execution settings (original)
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        dry_run = st.checkbox("Dry Run (chỉ xem kế hoạch, không đặt lệnh)", value=True)
    with col_s2:
        closed_action = st.selectbox(
            "Market-closed action",
            ["opg", "skip"],
            index=0,
            help="opg = đặt lệnh limit-on-open phiên hôm sau; skip = bỏ qua",
        )

    # ── 3. Execute ──────────────────────────────────────────────────────────────
    st.markdown("#### 3. Execute")
    btn_label = "Preview Plan (Dry Run)" if dry_run else "Submit Orders"
    if st.button(btn_label, type="primary"):
        with st.spinner("Đang xử lý…"):
            try:
                # ✨ APPLY MAX ALLOCATION: Adjust weights based on allocation %
                adjusted_weights = {}
                for symbol, original_weight in target_weights.items():
                    adjusted_weights[symbol] = original_weight * (max_allocation_pct / 100)
                
                plan = manager.execute_portfolio_rebalance(
                    adjusted_weights,  # ← Use adjusted weights with max allocation
                    account_name="default",
                    dry_run=dry_run,
                    market_closed_action=closed_action if not dry_run else "opg",
                )

                if dry_run:
                    st.success("Dry-run plan đã tạo xong.")
                    
                    # ✨ NEW: Show allocation breakdown
                    col_alloc_sum1, col_alloc_sum2, col_alloc_sum3, col_alloc_sum4 = st.columns(4)
                    total_stocks_weight = sum([v for v in adjusted_weights.values()])
                    with col_alloc_sum1:
                        st.metric("Stocks Deployed", f"{total_stocks_weight:.1%}")
                    with col_alloc_sum2:
                        st.metric("Cash Reserved", f"{1 - total_stocks_weight:.1%}")
                    with col_alloc_sum3:
                        st.metric("# Planned Buys", len(plan.get("orders_plan", {}).get("buy", [])))
                    with col_alloc_sum4:
                        st.metric("# Planned Sells", len(plan.get("orders_plan", {}).get("sell", [])))
                    
                    st.divider()
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Market Open", str(plan.get("market_open", "—")))
                    col_b.metric("Total Buys", f"${sum([o.get('qty', 0) * o.get('price', 0) for o in plan.get('orders_plan', {}).get('buy', [])]):.0f}" if plan.get("orders_plan", {}).get("buy") else "$0")
                    col_c.metric("Total Sells", f"${sum([o.get('qty', 0) * o.get('price', 0) for o in plan.get('orders_plan', {}).get('sell', [])]):.0f}" if plan.get("orders_plan", {}).get("sell") else "$0")
                    
                    with st.expander("Full Plan JSON"):
                        st.json(plan)
                else:
                    n = plan.get("orders_placed", 0)
                    st.success(f"Đã đặt **{n}** lệnh.")
                    
                    # ✨ NEW: Show execution summary
                    col_exec1, col_exec2 = st.columns(2)
                    with col_exec1:
                        st.info(f"✓ {max_allocation_pct}% Portfolio Deployed")
                    with col_exec2:
                        st.success(f"✓ {100 - max_allocation_pct}% Cash Reserved (${cash_amount:,.0f})")
                    
                    with st.expander("Execution Result"):
                        st.json(plan)

            except Exception as e:
                st.error(f"Execution thất bại: {e}")
                import traceback
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())
