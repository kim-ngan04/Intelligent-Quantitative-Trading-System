import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import traceback

def show_strategy_backtesting():
    """Show strategy backtesting interface."""
    st.header("Strategy Backtesting")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Backtest Configuration")

        # Strategy selection
        strategy_type = st.selectbox(
            "Strategy Type",
            ["equal_weight", "market_cap_weight", "ml_strategy"]
        )

        # Backtest parameters
        start_date = st.date_input("Start Date", datetime(2020, 1, 1))
        end_date = st.date_input("End Date", datetime(2023, 12, 31))
        initial_capital = st.number_input("Initial Capital", value=1000000, step=100000)

        # ML strategy parameters
        top_quantile = 0.75
        if strategy_type == "ml_strategy":
            top_quantile = st.slider("Top Quantile", 0.5, 1.0, 0.75, 0.05)

        # Number of stocks
        num_stocks = st.number_input("Number of Stocks", value=20, min_value=5, max_value=100, step=5)

        if st.button("Run Backtest", type="primary"):
            with st.spinner("Running backtest..."):
                try:
                    run_backtest_demo(
                        strategy_type=strategy_type,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=initial_capital,
                        top_quantile=top_quantile if strategy_type == "ml_strategy" else 0.75,
                        num_stocks=num_stocks
                    )
                except Exception as e:
                    st.error(f"Backtest failed: {str(e)[:200]}")
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

    with col2:
        st.subheader("Backtest Results")

        # Display results if available
        if 'backtest_result' in st.session_state and st.session_state.backtest_result:
            result = st.session_state.backtest_result

            # Key metrics - 4 columns
            metrics_cols = st.columns(4)
            with metrics_cols[0]:
                st.metric(
                    "Final Value",
                    f"${result.portfolio_values.iloc[-1]:,.0f}",
                    f"${result.portfolio_values.iloc[-1] - result.portfolio_values.iloc[0]:,.0f}"
                )
            with metrics_cols[1]:
                st.metric(
                    "Total Return",
                    f"{result.metrics.get('total_return', 0):.2%}"
                )
            with metrics_cols[2]:
                st.metric(
                    "Annual Return",
                    f"{result.annualized_return:.2%}"
                )
            with metrics_cols[3]:
                st.metric(
                    "Sharpe Ratio",
                    f"{result.metrics.get('sharpe_ratio', 0):.2f}"
                )

            # Performance chart
            st.subheader("Portfolio Performance")
            fig_perf = px.line(
                x=result.portfolio_values.index,
                y=result.portfolio_values.values,
                title="Portfolio Value Over Time",
                labels={'x': 'Date', 'y': 'Portfolio Value ($)'}
            )
            fig_perf.update_layout(hovermode='x unified')
            st.plotly_chart(fig_perf, use_container_width=True)

            # Returns distribution
            st.subheader("Returns Distribution")
            fig_ret = px.histogram(
                x=result.portfolio_returns.values,
                nbins=50,
                title="Daily Returns Distribution",
                labels={'x': 'Daily Return', 'y': 'Frequency'}
            )
            st.plotly_chart(fig_ret, use_container_width=True)

            # Detailed metrics table
            st.subheader("Detailed Metrics")

            # Compare with benchmarks if available
            if result.benchmark_metrics:
                metrics_comparison = result.to_metrics_dataframe()
                st.dataframe(
                    metrics_comparison.style.format('{:.4f}'),
                    use_container_width=True
                )
            else:
                # Show only strategy metrics
                metrics_df = pd.DataFrame({
                    'Metric': list(result.metrics.keys()),
                    'Value': list(result.metrics.values())
                })
                st.dataframe(
                    metrics_df.style.format({'Value': '{:.4f}'}),
                    use_container_width=True
                )

            # Risk analysis
            st.subheader("Risk Metrics")
            risk_cols = st.columns(3)
            with risk_cols[0]:
                st.metric(
                    "Annual Volatility",
                    f"{result.metrics.get('annual_volatility', 0):.2%}"
                )
            with risk_cols[1]:
                st.metric(
                    "Max Drawdown",
                    f"{result.metrics.get('max_drawdown', 0):.2%}",
                    delta=None
                )
            with risk_cols[2]:
                st.metric(
                    "Sortino Ratio",
                    f"{result.metrics.get('sortino_ratio', 0):.2f}"
                )

            # Drawdown chart
            st.subheader("Portfolio Drawdown")
            cumulative = (1 + result.portfolio_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            fig_dd = px.area(
                x=drawdown.index,
                y=drawdown.values,
                title="Drawdown Over Time",
                labels={'x': 'Date', 'y': 'Drawdown'}
            )
            fig_dd.update_yaxes(tickformat=".2%")
            st.plotly_chart(fig_dd, use_container_width=True)

            # Benchmark comparison if available
            if result.benchmark_annualized:
                st.subheader("vs Benchmarks")
                benchmark_comparison = pd.DataFrame({
                    'Strategy/Benchmark': list(result.benchmark_annualized.keys()),
                    'Annualized Return': list(result.benchmark_annualized.values())
                })
                benchmark_comparison = pd.concat([
                    pd.DataFrame({
                        'Strategy/Benchmark': [result.strategy_name],
                        'Annualized Return': [result.annualized_return]
                    }),
                    benchmark_comparison
                ], ignore_index=True)
                fig_bm = px.bar(
                    benchmark_comparison,
                    x='Strategy/Benchmark',
                    y='Annualized Return',
                    title="Strategy vs Benchmarks",
                    color='Strategy/Benchmark'
                )
                fig_bm.update_yaxes(tickformat=".2%")
                st.plotly_chart(fig_bm, use_container_width=True)
                st.dataframe(
                    benchmark_comparison.style.format({'Annualized Return': '{:.2%}'}),
                    use_container_width=True
                )

            # ✨ NEW: Select Strategy for Live Trading
            st.divider()
            st.subheader("🚀 Deploy to Live Trading")
            
            col_select1, col_select2 = st.columns([2, 1])
            with col_select1:
                st.write("Save this strategy configuration to use in **Live Trading** tab.")
            with col_select2:
                if st.button("📌 SELECT STRATEGY", type="primary", use_container_width=True):
                    # Extract weights from backtest results
                    weights_df = pd.DataFrame()
                    if hasattr(result, 'final_weights') and result.final_weights is not None and not result.final_weights.empty:
                        weights_df = result.final_weights.copy()
                    
                    # Save strategy to session state
                    st.session_state.selected_strategy = {
                        'name': result.strategy_name or 'Backtest Strategy',
                        'period': f"{result.portfolio_values.index[0].date()} to {result.portfolio_values.index[-1].date()}",
                        'metrics': {
                            'total_return': result.metrics.get('total_return', 0) * 100,
                            'annual_return': result.annualized_return * 100,
                            'sharpe_ratio': result.metrics.get('sharpe_ratio', 0),
                            'annual_volatility': result.metrics.get('annual_volatility', 0) * 100,
                            'max_drawdown': result.metrics.get('max_drawdown', 0) * 100,
                            'sortino_ratio': result.metrics.get('sortino_ratio', 0),
                        },
                        'weights': weights_df,
                        'selected_at': datetime.now().isoformat()
                    }
                    st.success("✅ Strategy selected! Go to **Live Trading** tab to deploy.")
            
            # Show if strategy is selected
            if 'selected_strategy' in st.session_state and st.session_state.selected_strategy:
                st.info(
                    f"✓ **{st.session_state.selected_strategy['name']}** "
                    f"selected at {st.session_state.selected_strategy['selected_at'][:10]}"
                )
        else:
            st.info("👈 Configure parameters and click **Run Backtest** to see results")


def run_backtest_demo(strategy_type: str, start_date, end_date, initial_capital: float,
                      top_quantile: float, num_stocks: int):
    """
    Run backtest with given parameters.
    """
    from src.backtest.backtest_engine import BacktestEngine, BacktestConfig
    from src.data.data_fetcher import fetch_price_data

    try:
        st.info(f"Loading {num_stocks} stocks for {strategy_type} strategy...")
        sample_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JNJ', 'V', 'WMT',
            'JPM', 'PG', 'MA', 'HD', 'MCD', 'BA', 'NKE', 'CSCO', 'ABBV', 'PEP',
            'XOM', 'CVX', 'KO', 'PEP', 'COST', 'AMGN', 'LLY', 'CRM', 'IBM', 'INTC',
            'ORCL', 'QCOM', 'AMD', 'ADBE', 'PYPL', 'SQ', 'NET', 'CRWD', 'UBER', 'LYFT'
        ]
        tickers = sample_tickers[:num_stocks]

        st.info(f"Fetching price data for {len(tickers)} stocks...")
        price_data = fetch_price_data(
            tickers,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if price_data.empty:
            st.error("No price data available for selected period")
            return

        st.info(f"Generating {strategy_type} signals...")
        if strategy_type == "equal_weight":
            weight_signals = _generate_equal_weight_signals(price_data, tickers)
        elif strategy_type == "market_cap_weight":
            weight_signals = _generate_market_cap_weight_signals(price_data, tickers)
        elif strategy_type == "ml_strategy":
            weight_signals = _generate_ml_weight_signals(price_data, tickers, top_quantile)
        else:
            weight_signals = _generate_equal_weight_signals(price_data, tickers)

        if weight_signals.empty:
            st.error("Could not generate weight signals")
            return

        st.info("Running backtest...")
        config = BacktestConfig(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            rebalance_freq='QE',
            initial_capital=initial_capital,
            benchmark_tickers=['SPY', 'QQQ']
        )
        engine = BacktestEngine(config)
        result = engine.run_backtest(f'{strategy_type.upper()} Strategy', price_data, weight_signals)

        # ✨ Add weights to result for Live Trading
        # Convert weight_signals to format suitable for Live Trading
        final_weights = weight_signals.iloc[-1] if len(weight_signals) > 0 else pd.Series()
        if len(final_weights) > 0 and final_weights.sum() > 0:
            # Create weights dataframe with gvkey (ticker) and weight
            weights_for_trading = pd.DataFrame({
                'gvkey': final_weights.index,
                'weight': final_weights.values
            })
            weights_for_trading = weights_for_trading[weights_for_trading['weight'] > 0].copy()
            weights_for_trading['weight'] = weights_for_trading['weight'] / weights_for_trading['weight'].sum()
            
            # Add to result object
            result.final_weights = weights_for_trading
        else:
            result.final_weights = pd.DataFrame()

        st.session_state.backtest_result = result
        st.success(f"✅ Backtest completed!")
        st.info(f"Annualized Return: {result.annualized_return:.2%}")

    except Exception as e:
        st.error(f"Backtest error: {str(e)}")
        raise


def _generate_equal_weight_signals(price_data: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """Generate equal weight signals."""
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    weight_signals = pd.DataFrame(
        data=1.0 / len(tickers),
        index=quarterly_dates,
        columns=tickers
    )
    return weight_signals


def _generate_market_cap_weight_signals(price_data: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """Generate market-cap weighted signals."""
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    weight_signals = pd.DataFrame(index=quarterly_dates, columns=tickers)
    for date in quarterly_dates:
        available_data = price_data_copy[price_data_copy['datadate'] <= date]
        if not available_data.empty:
            latest_prices = available_data.groupby('tic')['adj_close'].last()
            weights = latest_prices / latest_prices.sum()
            weight_signals.loc[date] = weights
        else:
            weight_signals.loc[date] = 1.0 / len(tickers)

    weight_signals = weight_signals.fillna(1.0 / len(tickers))
    return weight_signals


def _generate_ml_weight_signals(price_data: pd.DataFrame, tickers: list,
                                top_quantile: float = 0.75) -> pd.DataFrame:
    """Generate ML-based weight signals."""
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    weight_signals = pd.DataFrame(index=quarterly_dates, columns=tickers)
    for date in quarterly_dates:
        available_data = price_data_copy[price_data_copy['datadate'] <= date]
        if not available_data.empty:
            recent_data = available_data.tail(60)
            if len(recent_data) > 0:
                returns = recent_data.groupby('tic')['adj_close'].apply(
                    lambda x: (x.iloc[-1] / x.iloc[0] - 1) if len(x) > 0 else 0
                )
                threshold = returns.quantile(top_quantile)
                selected = returns[returns >= threshold]

                if len(selected) > 0:
                    weights = pd.Series(0.0, index=tickers)
                    weights[selected.index] = 1.0 / len(selected)
                    weight_signals.loc[date] = weights
                else:
                    weight_signals.loc[date] = 1.0 / len(tickers)
            else:
                weight_signals.loc[date] = 1.0 / len(tickers)
        else:
            weight_signals.loc[date] = 1.0 / len(tickers)

    weight_signals = weight_signals.fillna(1.0 / len(tickers))
    return weight_signals
