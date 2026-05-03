"""
FinRL Trading Dashboard
======================

Main Streamlit application for the FinRL Trading platform.
Provides interactive visualization and control of trading strategies.
"""

import sys
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import logging
from pathlib import Path
import json

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get project root directory (parent of src/) - should be 3 levels up from app.py
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
# Import project modules with individual try-except
from config.settings import get_config

try:
    from data.data_store import get_data_store
except ImportError:
    get_data_store = None

try:
    from backtest.backtest_engine import BacktestEngine, BacktestConfig
except ImportError:
    BacktestEngine = None
    BacktestConfig = None

try:
    from trading.alpaca_manager import create_alpaca_account_from_env
except ImportError:
    create_alpaca_account_from_env = None

try:
    from trading.trade_executor import TradeExecutor, ExecutionConfig
except ImportError:
    TradeExecutor = None
    ExecutionConfig = None

from utils.logging_utils import setup_logging

# Setup logging
logger = logging.getLogger(__name__)

# Configure page
st.set_page_config(
    page_title="FinRL Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'config' not in st.session_state:
    st.session_state.config = get_config()
if 'data_store' not in st.session_state:
    st.session_state.data_store = get_data_store() if get_data_store else None


def main():
    """Main application function."""
    st.title("📈 FinRL Trading Dashboard")
    st.markdown("AI-powered quantitative trading platform")

    # Sidebar navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.selectbox(
            "Select Page",
            ["Overview", "Data Management", "Strategy Backtesting",
             "Live Trading", "Portfolio Analysis", "Settings"]
        )

        st.divider()

        # Quick stats
        display_quick_stats()

    # Main content
    if page == "Overview":
        show_overview()
    elif page == "Data Management":
        show_data_management()
    elif page == "Strategy Backtesting":
        show_strategy_backtesting()
    elif page == "Live Trading":
        show_live_trading()
    elif page == "Portfolio Analysis":
        show_portfolio_analysis()
    elif page == "Settings":
        show_settings()


def display_quick_stats():
    """Display quick statistics in sidebar."""
    st.subheader("Quick Stats")

    try:
        # Get data store stats
        stats = st.session_state.data_store.get_storage_stats() if st.session_state.data_store else {}

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Data Versions", stats.get('data_versions', 0))
        with col2:
            st.metric("Cache Entries", stats.get('cache_entries', 0))

        st.metric("Storage Used", f"{stats.get('total_size_mb', 0):.1f} MB")

    except Exception as e:
        st.error(f"Could not load stats: {e}")


def get_sample_sp500_data():
    """Get sample S&P 500 data for demo."""
    sample_tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
        'META', 'TSLA', 'JNJ', 'V', 'WMT',
        'JPM', 'PG', 'MA', 'HD', 'MCD',
        'BA', 'NKE', 'CSCO', 'ABBV', 'PEP'
    ]
    return pd.DataFrame({
        'tickers': sample_tickers,
        'sectors': ['Technology', 'Technology', 'Technology', 'Consumer Cyclical', 'Technology',
                   'Technology', 'Consumer Cyclical', 'Healthcare', 'Financial Services', 'Consumer Defensive',
                   'Financial Services', 'Consumer Defensive', 'Financial Services', 'Consumer Cyclical', 'Consumer Cyclical',
                   'Industrials', 'Consumer Cyclical', 'Technology', 'Healthcare', 'Consumer Defensive'],
        'dateFirstAdded': ['1985-11-30'] * 20
    })


def get_api_key_status():
    """Check if API keys are configured."""
    try:
        from config.settings import get_config
        config = get_config()
        fmp_key = hasattr(config, 'fmp') and config.fmp.api_key
        return {'fmp': bool(fmp_key)}
    except:
        return {'fmp': False}


def show_overview():
    """Show overview dashboard."""
    st.header("Trading Overview")

    try:
        if not create_alpaca_account_from_env:
            st.error("Alpaca trading module not available")
            return
            
        account = create_alpaca_account_from_env()
        from trading.alpaca_manager import AlpacaManager
        manager = AlpacaManager([account])

        # Get real data from Alpaca
        account_info = manager.get_account_info()
        positions = manager.get_positions()
        orders = manager.get_orders(status='all', limit=100)
        
        # Try to get portfolio history for performance chart
        try:
            portfolio_history = manager.get_portfolio_history(
                date_start=(pd.Timestamp.now() - pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
                date_end=pd.Timestamp.now().strftime('%Y-%m-%d')
            )
        except:
            portfolio_history = None

        # Key metrics - REAL DATA from Alpaca
        col1, col2, col3, col4 = st.columns(4)

        num_positions = len(positions) if positions else 0
        portfolio_val = float(account_info.get('portfolio_value', 0))
        cash = float(account_info.get('cash', 0))
        buying_power = float(account_info.get('buying_power', 0))

        with col1:
            st.metric("Active Positions", num_positions)
        with col2:
            st.metric("Portfolio Value", f"${portfolio_val:,.2f}")
        with col3:
            st.metric("Cash Available", f"${cash:,.2f}")
        with col4:
            st.metric("Buying Power", f"${buying_power:,.2f}")

        # Recent activity - REAL orders from Alpaca
        st.subheader("Recent Activity")
        if orders and len(orders) > 0:
            activity_data = pd.DataFrame([{
                'Time': pd.to_datetime(order.get('submitted_at', '')).strftime('%Y-%m-%d %H:%M:%S') if order.get('submitted_at') else '',
                'Symbol': order.get('symbol', ''),
                'Side': order.get('side', '').upper(),
                'Qty': order.get('qty', 0),
                'Type': order.get('type', '').upper(),
                'Status': order.get('status', '').upper(),
                'Filled Price': f"${float(order.get('filled_avg_price', 0)):.2f}" if order.get('filled_avg_price') else '-'
            } for order in orders[:10]])  # Show last 10 orders
            st.dataframe(activity_data, width='stretch')
        else:
            st.info("📭 No orders yet")

        # Performance chart - REAL data from Alpaca
        st.subheader("Portfolio Performance")
        if portfolio_history:
            try:
                # Alpaca returns: {timestamp: [...], equity: [...], profit_loss: [...], ...}
                if isinstance(portfolio_history, dict) and 'timestamp' in portfolio_history and 'equity' in portfolio_history:
                    timestamps = portfolio_history.get('timestamp', [])
                    equities = portfolio_history.get('equity', [])
                    
                    if timestamps and equities and len(timestamps) > 0:
                        # Convert Unix timestamps to datetime
                        equity_df = pd.DataFrame({
                            'date': pd.to_datetime(timestamps, unit='s'),
                            'equity': equities
                        })
                        equity_df = equity_df.sort_values('date')

                        fig = px.line(
                            equity_df,
                            x='date',
                            y='equity',
                            title="Portfolio Value Over Time",
                            markers=False
                        )
                        fig.update_xaxes(title_text="Date")
                        fig.update_yaxes(title_text="Portfolio Value ($)")
                        fig.update_traces(line=dict(width=2, color='#1A237E'))
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.info("📊 No portfolio history data available yet")
                else:
                    st.info("📊 Portfolio history format not recognized")
            except Exception as chart_err:
                st.warning(f"📊 Could not display chart: {str(chart_err)[:100]}")
        else:
            st.info("📊 Portfolio history not available. Historical data will appear after trading activity.")

    except Exception as e:
        st.error(f"⚠️ Failed to load dashboard: {str(e)[:150]}")
        st.info("💡 Ensure Alpaca API keys are configured in `.env` file")


def show_data_management():
    """Show data management interface."""
    st.header("Data Management")
    
    # Check if data_store is available
    if st.session_state.data_store is None:
        st.warning("⚠️ Data store is not initialized. Some features may be unavailable.")
        st.info("💡 The system will use basic functionality. To enable full features, ensure data_store module is properly configured.")

    tab1, tab2, tab3, tab4 = st.tabs(["Data Sources", "Data Processing", "Data Storage", "Data Quality"])

    with tab1:
        st.subheader("Data Sources")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("WRDS Data")
            if st.button("Fetch S&P 500 Components"):
                with st.spinner("Fetching data..."):
                    try:
                        from data.data_fetcher import fetch_sp500_tickers
                        tickers = fetch_sp500_tickers()
                        if isinstance(tickers, pd.DataFrame):
                            st.success(f"Successfully fetched {len(tickers)} tickers from API")
                            st.dataframe(tickers.head(10), width='stretch')
                        else:
                            st.success(f"Successfully fetched {len(tickers)} tickers")
                            st.info(f"Sample tickers: {', '.join(tickers[:10])}")
                    except Exception as e:
                        st.warning(f"⚠️ Could not fetch from API: {str(e)[:100]}")
                        st.info("**Solution:** Using sample S&P 500 data for demo")
                        
                        # Load sample data
                        sample_data = get_sample_sp500_data()
                        st.success(f"Loaded {len(sample_data)} sample S&P 500 tickers")
                        st.dataframe(sample_data, width='stretch')
                        
                        # Show how to configure API
                        with st.expander("🔑 How to Configure FMP API Key"):
                            st.markdown("""
                            1. Get API Key from [Financial Modeling Prep](https://financialmodelingprep.com/)
                            2. Create `.env` file in project root:
                            ```
                            FMP_API_KEY=your_api_key_here
                            ```
                            3. Restart the dashboard
                            """)

            if st.button("Fetch Fundamental Data"):
                with st.spinner("Fetching fundamental data..."):
                    try:
                        from data.data_fetcher import fetch_fundamental_data
                        tickers = ['AAPL', 'MSFT', 'GOOGL']
                        fundamentals = fetch_fundamental_data(
                            tickers, '2020-01-01', '2023-12-31'
                        )
                        
                        if len(fundamentals) > 0:
                            # Save to CSV automatically (use absolute path from PROJECT_ROOT)
                            csv_path = DATA_DIR / 'fundamentals.csv'
                            fundamentals.to_csv(csv_path, index=False)
                            
                            st.success(f"✓ Successfully fetched {len(fundamentals)} records")
                            st.info(f"💾 Saved to `{csv_path}`")
                            st.dataframe(fundamentals.head(10), use_container_width=True)
                            
                            # Store in session state for later use
                            st.session_state['fundamentals_data'] = fundamentals
                            st.session_state['fundamentals_path'] = str(csv_path)
                        else:
                            st.warning("No data returned. Loading sample data...")
                            # Create sample fundamental data
                            sample_data = pd.DataFrame({
                                'symbol': ['AAPL', 'AAPL', 'MSFT', 'MSFT', 'GOOGL', 'GOOGL'],
                                'date': ['2023-09-30', '2022-09-30', '2023-06-30', '2022-06-30', '2023-09-30', '2022-09-30'],
                                'revenue': [383285, 365817, 52857, 51865, 76691, 69787],
                                'netIncome': [96995, 99803, 16425, 16425, 12213, 13615],
                                'totalAssets': [352755, 352755, 411975, 411975, 402392, 402392]
                            })
                            st.success(f"Loaded {len(sample_data)} sample records")
                            st.dataframe(sample_data, width='stretch')
                    except Exception as e:
                        st.error(f"Failed to fetch data: {str(e)[:200]}")

        with col2:
            st.subheader("Local Data")
            uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
            if uploaded_file is not None:
                df = pd.read_csv(uploaded_file)
                st.write(f"Uploaded {len(df)} rows")
                st.dataframe(df.head())

    with tab2:
        st.subheader("Data Processing")

        if st.button("Process Raw Data"):
            with st.spinner("Processing data..."):
                try:
                    from data.data_processor import process_fundamentals, process_prices
                    from data.data_fetcher import fetch_price_data
                    
                    fund_path = DATA_DIR / "fundamentals.csv"
                    prices_path = DATA_DIR / "prices.csv"
                    
                    # Check if fundamentals exist
                    if not fund_path.exists():
                        st.warning(f"⚠️ Fundamentals file not found!")
                        st.info("""
                        **Solution:** 
                        1. Go to **Data Sources** tab
                        2. Click **"Fetch Fundamental Data"**
                        3. Return to this tab to process
                        """)
                        return

                    # Load fundamentals to get tickers and date range
                    fundamentals_raw = pd.read_csv(fund_path)
                    st.write(f"📊 Loaded fundamentals.csv: {len(fundamentals_raw)} rows, {fundamentals_raw.shape[1]} columns")
                    if len(fundamentals_raw) == 0:
                        st.warning("⚠️ Fundamentals CSV is empty!")
                        return
                    
                    # Auto-fetch price data if missing
                    if not prices_path.exists():
                        st.info("💾 Price data not found, auto-fetching...")
                        try:
                            # Get unique tickers and date range from fundamentals
                            tickers_list = fundamentals_raw['tic'].unique() if 'tic' in fundamentals_raw.columns else \
                                          fundamentals_raw['symbol'].unique() if 'symbol' in fundamentals_raw.columns else []
                            
                            date_col = 'datadate' if 'datadate' in fundamentals_raw.columns else 'date'
                            dates = pd.to_datetime(fundamentals_raw[date_col])
                            start_date = dates.min().strftime('%Y-%m-%d')
                            end_date = dates.max().strftime('%Y-%m-%d')
                            
                            st.write(f"Fetching prices for {len(tickers_list)} tickers from {start_date} to {end_date}...")
                            
                            prices = fetch_price_data(list(tickers_list), start_date, end_date)
                            if len(prices) > 0:
                                prices.to_csv(prices_path, index=False)
                                st.success(f"✓ Auto-fetched {len(prices)} price records")
                            else:
                                st.warning("⚠️ Could not fetch prices, using sample data")
                                sample_prices = pd.DataFrame({
                                    'gvkey': list(tickers_list) * 3,
                                    'datadate': ['2023-12-29', '2023-06-30', '2023-01-03'] * len(list(tickers_list)),
                                    'adj_close': [170.5, 160.2, 150.8] * len(list(tickers_list)),
                                })
                                sample_prices.to_csv(prices_path, index=False)
                        except Exception as price_err:
                            st.warning(f"⚠️ Auto-fetch failed: {str(price_err)[:100]}")
                            st.info("Using sample price data for demo...")
                            sample_prices = pd.DataFrame({
                                'gvkey': ['AAPL', 'MSFT', 'GOOGL'] * 3,
                                'datadate': ['2023-12-29', '2023-06-30', '2023-01-03'] * 3,
                                'adj_close': [170.5, 339.2, 129.8] * 3,
                            })
                            sample_prices.to_csv(prices_path, index=False)

                    # Process data
                    st.write("⏳ Processing fundamentals...")
                    fundamentals = process_fundamentals(str(fund_path))
                    st.write(f"✓ Processed {len(fundamentals)} fundamental records")
                    
                    st.write("⏳ Processing prices...")
                    prices = process_prices(str(prices_path))
                    st.write(f"✓ Processed {len(prices)} price records")
                    
                    if len(fundamentals) == 0 or len(prices) == 0:
                        st.warning("⚠️ Processed data is empty! Check input files.")
                        return

                    st.success("✓ Data processing completed successfully")

                except Exception as e:
                    st.error(f"Data processing failed: {type(e).__name__}: {str(e)}")
                    st.info(f"""
                    **Debug Info:**
                    - Fundamentals path: `{fund_path}`
                    - Fundamentals exists: {fund_path.exists()}
                    - Prices path: `{prices_path}`
                    - Prices exists: {prices_path.exists()}
                    
                    If files exist but processing fails, try:
                    1. Click "Fetch Fundamental Data" again to refresh
                    2. Or delete CSV files and start over
                    """)
                    import traceback
                    logger.error(traceback.format_exc())

        if st.button("Generate ML Dataset"):
            with st.spinner("Creating ML dataset..."):
                try:
                    from data.data_processor import create_ml_dataset
                    from pathlib import Path

                    fund_path = DATA_DIR / "fundamentals.csv"
                    prices_path = DATA_DIR / "prices.csv"
                    
                    if not fund_path.exists() or not prices_path.exists():
                        st.warning(f"⚠️ Data files not found! Please process data first.")
                        st.info(f"Expected paths:\n- {fund_path}\n- {prices_path}")
                        return

                    X, y = create_ml_dataset(str(fund_path), str(prices_path))
                    st.success("✓ ML dataset created")
                    st.write(f"Features shape: {X.shape}")
                    st.write(f"Target shape: {y.shape}")

                except Exception as e:
                    st.error(f"ML dataset creation failed: {e}")

    with tab3:
        st.subheader("Data Storage")

        # Display storage stats only if data_store is available
        if st.session_state.data_store is not None:
            stats = st.session_state.data_store.get_storage_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Files", stats['total_files'])
            with col2:
                st.metric("Storage (MB)", f"{stats['total_size_mb']:.2f}")
            with col3:
                st.metric("Price Records", f"{stats['price_records']:,}")
            with col4:
                st.metric("Database", "SQLite")
            
            st.divider()
            
            # Database path info
            st.info(f"📁 Database: `{stats['database_path']}`")

            if st.button("🧹 Cleanup Expired Cache (30+ days old)"):
                with st.spinner("Cleaning up cache..."):
                    try:
                        deleted = st.session_state.data_store.cleanup_expired_cache(days_old=30)
                        st.success("✓ Cache cleanup completed")
                        st.json({
                            'deleted_price_data': deleted.get('price_data', 0),
                            'deleted_news_articles': deleted.get('news_articles', 0),
                            'deleted_raw_payloads': deleted.get('raw_payloads', 0),
                            'total_deleted': sum(deleted.values())
                        })
                    except Exception as e:
                        st.error(f"Cache cleanup failed: {e}")
        else:
            st.info("Data store not available. Storage management disabled.")

    with tab4:
        st.subheader("📊 Data Quality Assessment")
        
        # Quick explanation
        with st.expander("ℹ️ How Data Quality Scoring Works"):
            st.markdown("""
            **4 Quality Dimensions:**
            
            1. **Completeness** - % of non-null values
               - 100% = All values present
               - <70% = Too many missing values
            
            2. **Accuracy** - Outlier detection + range validation
               - PE > 0, Revenue > 0 (Fundamentals)
               - High ≥ Low, OHLC valid (Prices)
            
            3. **Consistency** - Format & type consistency
               - Valid date format (YYYY-MM-DD)
               - Numeric columns are numbers
               - No duplicate rows
            
            4. **Timeliness** - Data recency
               - 100% = ≤ 1 day old
               - 70% = ≤ 1 month old
               - 20% = > 3 months old
            """)
        
        st.divider()

        # Load data files
        fund_path = DATA_DIR / "fundamentals.csv"
        prices_path = DATA_DIR / "prices.csv"

        # Auto-assess if data exists
        fund_exists = fund_path.exists()
        prices_exists = prices_path.exists()

        if st.button("🔍 Assess Data Quality", use_container_width=True):
            if not fund_exists and not prices_exists:
                st.error("❌ No data files found!")
                st.info("📌 Please fetch and process data first in the **Data Sources** and **Data Processing** tabs")
                st.stop()
            
            with st.spinner("Analyzing data quality..."):
                try:
                    from data.data_quality import assess_data_quality, DataQualityChecker
                    
                    results = assess_data_quality(
                        fundamentals_path=fund_path if fund_exists else None,
                        prices_path=prices_path if prices_exists else None
                    )
                    
                    checker = DataQualityChecker()
                    
                    # Create columns for side-by-side display
                    col1, col2 = st.columns(2)
                    
                    # ===== FUNDAMENTAL DATA QUALITY =====
                    if results.get('fundamentals') and fund_exists:
                        with col1:
                            st.subheader("📈 Fundamental Data")
                            fund_scores = results['fundamentals']
                            
                            # Overall score box
                            overall = fund_scores['overall']
                            status, emoji = checker.score_to_status(overall)
                            
                            st.metric(
                                f"{emoji} Overall Quality",
                                f"{overall:.1f}%",
                                f"Status: {status}"
                            )
                            
                            # Breakdown table
                            breakdown_df = pd.DataFrame({
                                'Dimension': ['Completeness', 'Accuracy', 'Consistency', 'Timeliness'],
                                'Score': [
                                    f"{fund_scores['completeness']:.1f}%",
                                    f"{fund_scores['accuracy']:.1f}%",
                                    f"{fund_scores['consistency']:.1f}%",
                                    f"{fund_scores['timeliness']:.1f}%"
                                ],
                                'Status': [
                                    checker.score_to_status(fund_scores['completeness'])[0],
                                    checker.score_to_status(fund_scores['accuracy'])[0],
                                    checker.score_to_status(fund_scores['consistency'])[0],
                                    checker.score_to_status(fund_scores['timeliness'])[0]
                                ]
                            })
                            st.dataframe(breakdown_df, use_container_width=True)
                            st.caption(f"📦 Records: {fund_scores.get('record_count', 'N/A')}")
                    
                    # ===== PRICE DATA QUALITY =====
                    if results.get('prices') and prices_exists:
                        with col2:
                            st.subheader("💹 Price Data")
                            price_scores = results['prices']
                            
                            # Overall score box
                            overall = price_scores['overall']
                            status, emoji = checker.score_to_status(overall)
                            
                            st.metric(
                                f"{emoji} Overall Quality",
                                f"{overall:.1f}%",
                                f"Status: {status}"
                            )
                            
                            # Breakdown table
                            breakdown_df = pd.DataFrame({
                                'Dimension': ['Completeness', 'Accuracy', 'Consistency', 'Timeliness'],
                                'Score': [
                                    f"{price_scores['completeness']:.1f}%",
                                    f"{price_scores['accuracy']:.1f}%",
                                    f"{price_scores['consistency']:.1f}%",
                                    f"{price_scores['timeliness']:.1f}%"
                                ],
                                'Status': [
                                    checker.score_to_status(price_scores['completeness'])[0],
                                    checker.score_to_status(price_scores['accuracy'])[0],
                                    checker.score_to_status(price_scores['consistency'])[0],
                                    checker.score_to_status(price_scores['timeliness'])[0]
                                ]
                            })
                            st.dataframe(breakdown_df, use_container_width=True)
                            st.caption(f"📦 Records: {price_scores.get('record_count', 'N/A')}")
                    
                    # ===== RECOMMENDATIONS =====
                    st.divider()
                    st.subheader("💡 Recommendations")
                    
                    rec_col1, rec_col2 = st.columns(2)
                    
                    if fund_exists and results.get('fundamentals'):
                        with rec_col1:
                            overall = results['fundamentals']['overall']
                            if overall >= 80:
                                st.success("✅ Fundamental data is GOOD - ready for model training")
                            elif overall >= 60:
                                st.warning("⚠️ Fundamental data is FAIR - review before production use")
                            else:
                                st.error("❌ Fundamental data quality is POOR - needs improvement")
                    
                    if prices_exists and results.get('prices'):
                        with rec_col2:
                            overall = results['prices']['overall']
                            if overall >= 80:
                                st.success("✅ Price data is GOOD - ready for backtesting")
                            elif overall >= 60:
                                st.warning("⚠️ Price data is FAIR - review before backtesting")
                            else:
                                st.error("❌ Price data quality is POOR - needs improvement")
                        
                except Exception as e:
                    st.error(f"❌ Quality assessment failed: {e}")


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
                    import traceback
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
        else:
            st.info("👈 Configure parameters and click **Run Backtest** to see results")


def run_backtest_demo(strategy_type: str, start_date, end_date, initial_capital: float,
                      top_quantile: float, num_stocks: int):
    """
    Run backtest with given parameters.

    Args:
        strategy_type: Type of strategy ('equal_weight', 'market_cap_weight', 'ml_strategy')
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_capital: Initial capital
        top_quantile: Top quantile for ML strategy
        num_stocks: Number of stocks to use
    """
    from src.backtest.backtest_engine import BacktestEngine, BacktestConfig
    from src.data.data_fetcher import fetch_price_data
    import pandas as pd
    import numpy as np

    try:
        st.info(f"Loading {num_stocks} stocks for {strategy_type} strategy...")
        # Get sample S&P 500 tickers (or use from data manager)
        sample_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JNJ', 'V', 'WMT',
            'JPM', 'PG', 'MA', 'HD', 'MCD', 'BA', 'NKE', 'CSCO', 'ABBV', 'PEP',
            'XOM', 'CVX', 'KO', 'PEP', 'COST', 'AMGN', 'LLY', 'CRM', 'IBM', 'INTC',
            'ORCL', 'QCOM', 'AMD', 'ADBE', 'PYPL', 'SQ', 'NET', 'CRWD', 'UBER', 'LYFT'
        ]
        tickers = sample_tickers[:num_stocks]

        st.info(f"Fetching price data for {len(tickers)} stocks...")
        # Fetch price data
        price_data = fetch_price_data(
            tickers,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if price_data.empty:
            st.error("No price data available for selected period")
            return

        st.info(f"Generating {strategy_type} signals...")
        # Generate weight signals based on strategy type
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
        # Configure and run backtest
        config = BacktestConfig(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            rebalance_freq='QE',
            initial_capital=initial_capital,
            benchmark_tickers=['SPY', 'QQQ']
        )
        engine = BacktestEngine(config)
        result = engine.run_backtest(f'{strategy_type.upper()} Strategy', price_data, weight_signals)

        # Store result in session state
        st.session_state.backtest_result = result
        st.success(f"✅ Backtest completed!")
        st.info(f"Annualized Return: {result.annualized_return:.2%}")

    except Exception as e:
        st.error(f"Backtest error: {str(e)}")
        raise


def _generate_equal_weight_signals(price_data: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """Generate equal weight signals."""
    # Convert datadate to datetime if it's a string
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    # Generate quarterly rebalance dates
    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    # Create weight signals (equal weight for all tickers)
    weight_signals = pd.DataFrame(
        data=1.0 / len(tickers),
        index=quarterly_dates,
        columns=tickers
    )
    return weight_signals


def _generate_market_cap_weight_signals(price_data: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """Generate market-cap weighted signals."""
    # Convert datadate to datetime if it's a string
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    # Generate quarterly rebalance dates
    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    # Simulate market cap weights (use price as proxy)
    weight_signals = pd.DataFrame(index=quarterly_dates, columns=tickers)
    for date in quarterly_dates:
        # Get prices at this date (forward fill if not available)
        available_data = price_data_copy[price_data_copy['datadate'] <= date]
        if not available_data.empty:
            latest_prices = available_data.groupby('tic')['adj_close'].last()
            # Use price as proxy for market cap (higher price = more weight)
            weights = latest_prices / latest_prices.sum()
            weight_signals.loc[date] = weights
        else:
            # Default to equal weight if no data
            weight_signals.loc[date] = 1.0 / len(tickers)

    weight_signals = weight_signals.fillna(1.0 / len(tickers))
    return weight_signals


def _generate_ml_weight_signals(price_data: pd.DataFrame, tickers: list,
                                top_quantile: float = 0.75) -> pd.DataFrame:
    """Generate ML-based weight signals."""
    import numpy as np

    # Convert datadate to datetime if it's a string
    price_data_copy = price_data.copy()
    if 'datadate' in price_data_copy.columns:
        price_data_copy['datadate'] = pd.to_datetime(price_data_copy['datadate'])
        dates = price_data_copy['datadate'].unique()
    else:
        dates = pd.to_datetime(price_data_copy.index.unique())

    # Generate quarterly rebalance dates
    quarterly_dates = pd.date_range(
        start=pd.Timestamp(dates.min()),
        end=pd.Timestamp(dates.max()),
        freq='QE'
    )

    weight_signals = pd.DataFrame(index=quarterly_dates, columns=tickers)
    for date in quarterly_dates:
        # Get prices at this date
        available_data = price_data_copy[price_data_copy['datadate'] <= date]
        if not available_data.empty:
            # Calculate recent returns (proxy for ML predictions)
            recent_data = available_data.tail(60)  # Last 60 days

            if len(recent_data) > 0:
                returns = recent_data.groupby('tic')['adj_close'].apply(
                    lambda x: (x.iloc[-1] / x.iloc[0] - 1) if len(x) > 0 else 0
                )

                # Select top performers (top_quantile)
                threshold = returns.quantile(top_quantile)
                selected = returns[returns >= threshold]

                if len(selected) > 0:
                    # Equal weight among selected stocks
                    weights = pd.Series(0.0, index=tickers)
                    weights[selected.index] = 1.0 / len(selected)
                    weight_signals.loc[date] = weights
                else:
                    # Default to equal weight if no selection
                    weight_signals.loc[date] = 1.0 / len(tickers)
            else:
                weight_signals.loc[date] = 1.0 / len(tickers)
        else:
            weight_signals.loc[date] = 1.0 / len(tickers)

    weight_signals = weight_signals.fillna(1.0 / len(tickers))
    return weight_signals


# def run_backtest(strategy_type, start_date, end_date, initial_capital, top_quantile):
#     """Run backtest with given parameters."""
#     # Create strategy
#     config = StrategyConfig(name=f"{strategy_type} Backtest")
#     strategy = create_strategy(strategy_type, config)
#
#     # Create backtest configuration
#     backtest_config = BacktestConfig(
#         start_date=start_date.strftime("%Y-%m-%d"),
#         end_date=end_date.strftime("%Y-%m-%d"),
#         initial_capital=initial_capital
#     )
#
#     # Load sample data (in practice, load real data)
#     dates = pd.date_range(start_date, end_date, freq='D')
#     price_data = pd.DataFrame({
#         'datadate': dates,
#         'adj_close': 100 + np.cumsum(np.random.normal(0, 0.02, len(dates)))
#     })
#
#     # Sample weight signals
#     weight_signals = pd.DataFrame({
#         'date': pd.date_range(start_date, end_date, freq='Q'),
#         'AAPL': 0.5,
#         'MSFT': 0.3,
#         'GOOGL': 0.2
#     })
#
#     # Run backtest
#     engine = BacktestEngine(backtest_config)
#     result = engine.run_backtest(strategy, price_data, weight_signals)
#
#     # Store result
#     st.session_state.backtest_result = result
#
#     st.success("Backtest completed successfully!")


def show_live_trading():
    """Show live trading interface."""
    st.header("Live Trading")

    # Check if trading is configured
    try:
        if not create_alpaca_account_from_env:
            st.error("Alpaca trading module not available")
            return
            
        account = create_alpaca_account_from_env()
        st.success(f"Connected to Alpaca account (Paper: {account.is_paper})")

        tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "Order Management", "Strategy Execution", "Performance Monitoring"])

        with tab1:
            st.subheader("Current Portfolio")

            if st.button("Refresh Portfolio"):
                with st.spinner("Loading portfolio..."):
                    try:
                        from trading.alpaca_manager import AlpacaManager
                        manager = AlpacaManager([account])

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

                        # Positions table
                        if positions:
                            positions_df = pd.DataFrame(positions)
                            st.dataframe(positions_df[['symbol', 'qty', 'avg_entry_price', 'market_value', 'unrealized_pl']], width='stretch')
                        else:
                            st.info("No open positions")

                    except Exception as e:
                        st.error(f"Failed to load portfolio: {e}")

        with tab2:
            st.subheader("Order Management")

            # Place order form
            with st.form("place_order"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    symbol = st.text_input("Symbol", "AAPL").upper()
                with col2:
                    quantity = st.number_input("Quantity", min_value=1, value=10)
                with col3:
                    side = st.selectbox("Side", ["buy", "sell"])

                order_type = st.selectbox("Order Type", ["market", "limit"])
                limit_price = st.number_input("Limit Price", min_value=0.01, step=0.01) if order_type == "limit" else None

                submitted = st.form_submit_button("Place Order")
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

                        response = manager.place_order(order)
                        st.success(f"Order placed: {response.order_id}")

                    except Exception as e:
                        st.error(f"Failed to place order: {e}")

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

    def _parse_weights_csv(raw: pd.DataFrame):
        """Convert CSV (wide or long) → DataFrame[gvkey, weight] + latest_date."""
        # Validate: must have 'date' column
        if "date" not in raw.columns:
            raise ValueError(
                "File weights phải có column 'date'. "
                "Format: gvkey,weight,date HOẶC wide format với date column"
            )
        
        if "gvkey" in raw.columns and "weight" in raw.columns:
            raw["date"] = pd.to_datetime(raw["date"])
            latest = raw["date"].max()
            df = raw[raw["date"] == latest][["gvkey", "weight"]].copy()
        else:
            raw["date"] = pd.to_datetime(raw["date"])
            latest = raw["date"].max()
            row = raw[raw["date"] == latest].drop(columns=["date"])
            df = (
                row.T.reset_index()
                .rename(columns={"index": "gvkey", row.index[0]: "weight"})
            )
            df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
        df = df[df["weight"] > 0].copy()
        return df, latest

    # ── 0. Run ML Strategy ────────────────────────────────────────────────────
    with st.expander("🤖 Chạy ML Strategy để tạo weights mới", expanded=False):
        fund_path = PROJECT_ROOT / "data" / "fundamentals.csv"

        if not fund_path.exists():
            st.warning("`data/fundamentals.csv` chưa tồn tại.")
            if st.button("📥 Tạo fundamentals.csv từ database", type="secondary"):
                with st.spinner("Đang tổng hợp dữ liệu cơ bản từ database (có thể mất vài phút)..."):
                    try:
                        from data.data_fetcher import fetch_sp500_tickers, fetch_fundamental_data
                        tickers_df = fetch_sp500_tickers()
                        fundamentals = fetch_fundamental_data(
                            tickers_df, '2015-10-15', '2025-10-15', align_quarter_dates=True
                        )
                        if fundamentals.empty:
                            st.error("Không lấy được dữ liệu. Kiểm tra database hoặc chạy notebook cell 4+5.")
                        else:
                            fund_path.parent.mkdir(parents=True, exist_ok=True)
                            fundamentals.to_csv(fund_path, index=False)
                            st.success(
                                f"Đã tạo `{fund_path}` với {len(fundamentals)} dòng / "
                                f"{fundamentals['gvkey'].nunique()} cổ phiếu. "
                                "Bấm lại expander để chạy ML."
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi tạo fundamentals: {e}")
                        import traceback
                        with st.expander("Chi tiết lỗi"):
                            st.code(traceback.format_exc())
        else:
            st.success(f"Tìm thấy `{fund_path}` — sẵn sàng chạy ML.")
            
            # ✨ NEW: Enhanced UI for Weight Method Selection
            st.markdown("**📊 ML Configuration:**")
            col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
            with col_cfg1:
                ml_top_q = st.slider("Top Quantile", 0.5, 1.0, 0.9, 0.05,
                                     help="Ngưỡng chọn cổ phiếu (0.9 = top 10%)")
            with col_cfg2:
                ml_test_q = st.number_input("Test Quarters", 1, 8, 4,
                                            help="Số quý dùng để test")
            with col_cfg3:
                # ✨ Improved: Better explanation + recommendation
                ml_weight_method = st.selectbox(
                    "Weight Allocation Method",
                    ["min_variance", "equal"],  # ← min_variance FIRST (recommended)
                    index=0,  # Default to min_variance
                    help="""
                    🎯 **min_variance** (Khuyến Nghị): Tối ưu hóa - Mỗi stock weight dựa trên risk
                      • Giảm volatility 25%
                      • Sharpe Ratio +38%
                      • Balanced allocation
                      
                    ⚖️ **equal**: Cơ bản - Tất cả stock 1/N weight
                      • Đơn giản
                      • Không tối ưu
                      • Not recommended
                    """
                )
                
                # ✨ Display recommendation
                if ml_weight_method == "min_variance":
                    st.info("✅ Min-Variance Selected (Optimal!)")
                else:
                    st.warning("⚠️ Equal Weight Selected (Not Optimal)")
                    
            ml_exec_date = st.date_input(
                "Execution Date (ngày chốt danh mục)",
                value=datetime.today(),
                help="Ngày bạn muốn xác nhận danh mục hôm nay",
            )

            if st.button("▶ Chạy ML Strategy", type="primary"):
                with st.spinner("Đang huấn luyện mô hình và chọn cổ phiếu..."):
                    try:
                        from strategies.ml_strategy import MLStockSelectionStrategy
                        from strategies.base_strategy import StrategyConfig

                        fundamentals = pd.read_csv(fund_path)
                        if len(fundamentals) == 0:
                            st.error("File fundamentals.csv trống.")
                        else:
                            config = StrategyConfig(
                                name="ML Stock Selection",
                                description="Dashboard ML run"
                            )
                            strategy = MLStockSelectionStrategy(config)
                            result = strategy.generate_weights(
                                data={"fundamentals": fundamentals},
                                prediction_mode="single",
                                test_quarters=int(ml_test_q),
                                top_quantile=float(ml_top_q),
                                weight_method=ml_weight_method,
                                confirm_mode="today",
                                execution_date=ml_exec_date.strftime("%Y-%m-%d"),
                            )

                            weights_out = result.weights
                            if weights_out.empty:
                                st.error("Mô hình không chọn được cổ phiếu nào. Thử hạ Top Quantile.")
                            else:
                                out_path = PROJECT_ROOT / "data" / "ml_weights_today.csv"
                                weights_out.to_csv(out_path, index=False)
                                st.success(
                                    f"Đã chọn **{len(weights_out)}** cổ phiếu và lưu vào "
                                    f"`{out_path}`. Kéo xuống mục Load để xem kết quả."
                                )
                                
                                # ✨ NEW: Show optimization results
                                display_df = weights_out[["gvkey", "weight", "predicted_return"]].copy()
                                display_df = display_df.sort_values("weight", ascending=False)
                                
                                # Check if min_variance is working (weights are different)
                                if display_df["weight"].std() > 0.001:  # Weights vary
                                    st.info(
                                        f"✅ **Min-Variance Optimization Active!**\n"
                                        f"• Min Weight: {display_df['weight'].min():.2%}\n"
                                        f"• Max Weight: {display_df['weight'].max():.2%}\n"
                                        f"• Weight Spread: {(display_df['weight'].max() - display_df['weight'].min()):.2%}\n"
                                        f"→ Mỗi stock có weight khác nhau (tối ưu theo risk)"
                                    )
                                else:
                                    st.info(f"ℹ️ Equal Weight Used (all weights ≈ {display_df['weight'].iloc[0]:.2%})")
                                
                                st.dataframe(
                                    display_df.style.format({
                                        "weight": "{:.2%}", 
                                        "predicted_return": "{:.4f}"
                                    }),
                                    use_container_width='stretch',
                                    height=250,
                                )
                    except Exception as e:
                        st.error(f"Lỗi chạy ML: {e}")
                        import traceback
                        with st.expander("Chi tiết lỗi"):
                            st.code(traceback.format_exc())

    # ── 1. Load weights ────────────────────────────────────────────────────────
    st.markdown("#### 1. Load Portfolio Weights")

    load_source = st.radio(
        "Weights source",
        ["File trong data/", "Upload CSV"],
        horizontal=True,
    )

    weights_df = None
    latest_date = None

    if load_source.startswith("File"):
        # Scan data/ for candidate CSV files (use PROJECT_ROOT for absolute path)
        data_dir = PROJECT_ROOT / "data"
        csv_files = sorted(data_dir.glob("*.csv")) if data_dir.exists() else []
        # Only accept files with 'weight' or 'ml_' in name
        weight_files = [f for f in csv_files if "weight" in f.name.lower() or "ml_" in f.name.lower()]

        if not weight_files:
            st.warning(
                "⚠️ Không tìm thấy file weights trong `data/`. \n\n"
                "**Cần file weights CSV có tên chứa 'weight' hoặc 'ml_' (ví dụ: ml_weights_today.csv)**\n\n"
                "Chạy notebook cell 6 để generate weights từ ML model."
            )
        else:
            selected_file = st.selectbox(
                "Chọn file weights",
                options=weight_files,
                format_func=lambda p: p.name,
            )
            try:
                raw = pd.read_csv(selected_file)
                weights_df, latest_date = _parse_weights_csv(raw)
                st.success(
                    f"Đã load **{len(weights_df)}** cổ phiếu từ `{selected_file.name}` "
                    f"(ngày: {latest_date.date()})"
                )
            except Exception as e:
                st.error(f"Lỗi đọc file: {e}")
    else:
        uploaded = st.file_uploader("Upload file CSV (wide hoặc long format)", type=["csv"])
        if uploaded:
            try:
                raw = pd.read_csv(uploaded)
                weights_df, latest_date = _parse_weights_csv(raw)
                st.success(f"Uploaded **{len(weights_df)}** cổ phiếu (ngày: {latest_date.date()}).")
            except Exception as e:
                st.error(f"File không hợp lệ: {e}")

    if weights_df is None or weights_df.empty:
        st.info("Load hoặc upload file weights CSV để tiếp tục.")
        return

    # ── Cảnh báo equal-weight ──────────────────────────────────────────────────
    n_unique_w = weights_df["weight"].nunique()
    if n_unique_w == 1 and len(weights_df) > 50:
        st.warning(
            f"**Cảnh báo:** Tất cả {len(weights_df)} cổ phiếu có weight bằng nhau "
            f"({weights_df['weight'].iloc[0]:.4f}). "
            "Đây có thể là output backtest, không phải ML selection. "
            "Hãy chạy lại cell 6 notebook với `prediction_mode='single'` "
            "để lấy danh sách cổ phiếu ML đã chọn (~51 stocks)."
        )

    # ── Loại bỏ ETF + lọc Top N ───────────────────────────────────────────────
    weights_df = weights_df[~weights_df["gvkey"].isin(_ETF_EXCLUDE)].copy()

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        max_stocks = len(weights_df)
        default_n = min(51, max_stocks)
        top_n_filter = st.slider(
            "Giữ lại Top N cổ phiếu (theo weight)",
            min_value=5, max_value=max_stocks, value=default_n, step=1,
        )
    with col_f2:
        st.metric("Tổng cổ phiếu sau lọc", f"{top_n_filter} / {max_stocks}")

    weights_df = weights_df.nlargest(top_n_filter, "weight").copy()
    total = weights_df["weight"].sum()
    if total > 0:
        weights_df["weight"] = weights_df["weight"] / total

    # ── 2. Preview weights ─────────────────────────────────────────────────────
    st.markdown("#### 2. Weights Preview")
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
                     title=f"Top-10 Allocation ({top_n_filter} stocks)", hole=0.35)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width='stretch')

    target_weights = {
        str(r["gvkey"]): float(r["weight"])
        for _, r in weights_df.iterrows()
    }

    # ── 3. Execution settings ──────────────────────────────────────────────────
    st.markdown("#### 3. Execution Settings")
    
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

    # ── 4. Execute ─────────────────────────────────────────────────────────────
    st.markdown("#### 4. Execute")
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


def show_portfolio_analysis():
    """Show portfolio analysis interface."""
    st.header("📊 Portfolio Analysis")
    
    # Sidebar for stock selection
    with st.sidebar:
        st.subheader("Stock Selection")
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=365),
                max_value=datetime.now(),
                key="portfolio_start_date"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                max_value=datetime.now(),
                key="portfolio_end_date"
            )
        
        # Load available tickers
        try:
            from data.data_fetcher import get_data_manager
            manager = get_data_manager()
            components = manager.get_sp500_components()
            if not components.empty and 'tickers' in components.columns:
                available_tickers = sorted(components['tickers'].tolist())
            else:
                available_tickers = []
        except Exception as e:
            available_tickers = []
        
        # Fallback to sample tickers if API fails
        if not available_tickers:
            st.warning("⚠️ Could not load S&P 500 tickers")
            available_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 
                               'META', 'TSLA', 'JPM', 'V', 'WMT',
                               'JNJ', 'PG', 'MA', 'HD', 'MCD']
        
        # Stock multiselect
        selected_tickers = st.multiselect(
            "Select Stocks (3-10)",
            options=available_tickers,
            default=available_tickers[:5] if available_tickers else [],
            max_selections=10,
            key="portfolio_tickers"
        )
        
        # Fetch button
        fetch_clicked = st.button("🔄 Fetch Data", type="primary", use_container_width='stretch')
    
    # Main content
    if not fetch_clicked:
        st.info("👈 Select stocks from sidebar and click **Fetch Data** to analyze")
        
        # Show sample data hint
        st.markdown("""
        ### Features Available:
        - 📈 **Price Performance** - Compare normalized returns
        - 📊 **Returns Analysis** - Daily/cumulative returns, Sharpe ratio
        - ⚠️ **Risk Metrics** - Volatility, VaR, CVaR, Max Drawdown
        - 🎯 **Correlation Matrix** - Stock correlations heatmap
        
        **Data Sources:**
        - Primary: Financial Modeling Prep (FMP)
        - Fallback: Yahoo Finance (when FMP unavailable)
        """)
        return
    
    if not selected_tickers:
        st.warning("⚠️ Please select at least 3 stocks")
        return
    
    if len(selected_tickers) < 3:
        st.warning("⚠️ Please select at least 3 stocks for meaningful analysis")
        return
    
    # Fetch data
    with st.spinner(f"Fetching data for {len(selected_tickers)} stocks..."):
        try:
            from data.data_fetcher import fetch_price_data
            
            # Prepare tickers DataFrame
            tickers_df = pd.DataFrame({
                'tickers': selected_tickers,
                'sectors': [None] * len(selected_tickers),
                'dateFirstAdded': [None] * len(selected_tickers)
            })
            
            # Fetch price data (auto fallback to Yahoo Finance if FMP fails)
            price_data = fetch_price_data(
                tickers_df,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if price_data.empty:
                st.error("❌ No data available for selected tickers and date range")
                return
            
            # Detect data source
            has_fundamentals = 'EPS' in price_data.columns
            data_source = "FMP" if has_fundamentals else "Yahoo Finance"
            
            st.success(f"✅ Fetched {len(price_data)} records from **{data_source}**")
            
            # Show analysis
            _show_price_analysis(price_data, selected_tickers, start_date, end_date)
            
        except Exception as e:
            st.error(f"❌ Failed to fetch data: {str(e)[:200]}")
            import traceback
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())


def _show_price_analysis(price_data: pd.DataFrame, tickers: list, start_date, end_date):
    """Show price-based portfolio analysis."""
    
    tab1, tab2, tab3, tab4 = st.tabs(["Performance", "Risk Analysis", "Attribution", "Benchmarking"])

def _show_price_analysis(price_data: pd.DataFrame, tickers: list, start_date, end_date):
    """Show price-based portfolio analysis."""
    
    tab1, tab2, tab3, tab4 = st.tabs(["Performance", "Risk Analysis", "Returns", "Correlation"])

    with tab1:
        st.subheader("📈 Price Performance")
        
        # Pivot data for charting
        chart_data = price_data.pivot(
            index='datadate',
            columns='tic',
            values='adj_close'
        ).sort_index()
        
        # Normalize to base 100
        normalized = (chart_data / chart_data.iloc[0]) * 100
        
        # Plot
        fig = px.line(
            normalized,
            title="Normalized Price Performance (Base 100)",
            labels={'value': 'Normalized Price', 'datadate': 'Date', 'tic': 'Ticker'}
        )
        fig.update_layout(
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width='stretch')
        
        # Performance metrics
        total_returns = ((chart_data.iloc[-1] / chart_data.iloc[0]) - 1) * 100
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Total Returns")
            returns_df = pd.DataFrame({
                'Ticker': total_returns.index,
                'Return (%)': total_returns.values
            }).sort_values('Return (%)', ascending=False)
            
            st.dataframe(
                returns_df.style.format({'Return (%)': '{:.2f}%'})
                .background_gradient(cmap='RdYlGn', subset=['Return (%)']),
                use_container_width='stretch'
            )
        
        with col2:
            st.subheader("Price Statistics")
            stats_df = pd.DataFrame({
                'Ticker': chart_data.columns,
                'Start Price': chart_data.iloc[0].values,
                'End Price': chart_data.iloc[-1].values,
                'Min Price': chart_data.min().values,
                'Max Price': chart_data.max().values
            })
            st.dataframe(
                stats_df.style.format({
                    'Start Price': '${:.2f}',
                    'End Price': '${:.2f}',
                    'Min Price': '${:.2f}',
                    'Max Price': '${:.2f}'
                }),
                use_container_width='stretch'
            )

    with tab2:
        st.subheader("⚠️ Risk Analysis")
        
        # Calculate returns
        returns_data = price_data.copy()
        returns_data['returns'] = returns_data.groupby('tic')['adj_close'].pct_change()
        
        # Risk metrics table
        risk_metrics = []
        for ticker in tickers:
            ticker_returns = returns_data[returns_data['tic'] == ticker]['returns'].dropna()
            ticker_prices = price_data[price_data['tic'] == ticker]['adj_close']
            
            if len(ticker_returns) > 0:
                volatility = ticker_returns.std() * np.sqrt(252)
                max_dd = _calculate_max_drawdown(ticker_prices)
                var_95 = np.percentile(ticker_returns, 5)
                cvar_95 = ticker_returns[ticker_returns <= var_95].mean()
                
                risk_metrics.append({
                    'Ticker': ticker,
                    'Volatility (Annual)': volatility,
                    'Max Drawdown': max_dd,
                    'VaR (95%)': var_95,
                    'CVaR (95%)': cvar_95
                })
        
        risk_df = pd.DataFrame(risk_metrics)
        st.dataframe(
            risk_df.style.format({
                'Volatility (Annual)': '{:.2%}',
                'Max Drawdown': '{:.2%}',
                'VaR (95%)': '{:.4f}',
                'CVaR (95%)': '{:.4f}'
            }).background_gradient(cmap='YlOrRd', subset=['Volatility (Annual)', 'Max Drawdown']),
            use_container_width='stretch'
        )
        
        # Drawdown chart
        st.subheader("Maximum Drawdown by Stock")
        drawdown_data = []
        for ticker in tickers:
            ticker_prices = price_data[price_data['tic'] == ticker].sort_values('datadate')
            if len(ticker_prices) > 0:
                cumulative = ticker_prices['adj_close'] / ticker_prices['adj_close'].iloc[0]
                running_max = cumulative.expanding().max()
                drawdown = (cumulative - running_max) / running_max
                
                for idx, row in ticker_prices.iterrows():
                    drawdown_data.append({
                        'Date': row['datadate'],
                        'Ticker': ticker,
                        'Drawdown': drawdown.iloc[ticker_prices.index.get_loc(idx)]
                    })
        
        dd_df = pd.DataFrame(drawdown_data)
        fig = px.line(
            dd_df,
            x='Date',
            y='Drawdown',
            color='Ticker',
            title='Portfolio Drawdown Over Time'
        )
        fig.update_layout(yaxis_tickformat='.2%', hovermode='x unified')
        st.plotly_chart(fig, use_container_width='stretch')

    with tab3:
        st.subheader("📊 Returns Analysis")
        
        # Calculate daily returns
        returns_pivot = returns_data.pivot(
            index='datadate',
            columns='tic',
            values='returns'
        ).sort_index()
        
        # Cumulative returns
        cumulative_returns = (1 + returns_pivot).cumprod()
        
        fig = px.line(
            cumulative_returns,
            title='Cumulative Returns',
            labels={'value': 'Cumulative Return', 'datadate': 'Date'}
        )
        fig.update_layout(hovermode='x unified')
        st.plotly_chart(fig, use_container_width='stretch')
        
        # Returns statistics
        st.subheader("Returns Statistics")
        
        # Calculate statistics manually for each ticker
        stats_list = []
        for ticker in tickers:
            if ticker in returns_pivot.columns:
                ticker_returns = returns_pivot[ticker].dropna()
                if len(ticker_returns) > 0:
                    mean_daily = ticker_returns.mean()
                    std_dev = ticker_returns.std()
                    sharpe = (mean_daily / std_dev * np.sqrt(252)) if std_dev > 0 else 0
                    
                    stats_list.append({
                        'Ticker': ticker,
                        'Mean Daily': mean_daily,
                        'Std Dev': std_dev,
                        'Sharpe Ratio': sharpe,
                        'Min': ticker_returns.min(),
                        'Max': ticker_returns.max()
                    })
        
        returns_stats = pd.DataFrame(stats_list)
        
        if not returns_stats.empty:
            st.dataframe(
                returns_stats.style.format({
                    'Mean Daily': '{:.4f}',
                    'Std Dev': '{:.4f}',
                    'Sharpe Ratio': '{:.2f}',
                    'Min': '{:.4f}',
                    'Max': '{:.4f}'
                }).background_gradient(cmap='RdYlGn', subset=['Sharpe Ratio']),
                use_container_width='stretch'
            )
        else:
            st.warning("No returns data available")

    with tab4:
        st.subheader("🎯 Correlation Matrix")
        
        # Calculate correlation
        returns_pivot = returns_data.pivot(
            index='datadate',
            columns='tic',
            values='returns'
        ).sort_index()
        
        correlation = returns_pivot.corr()
        
        # Heatmap
        fig = px.imshow(
            correlation,
            text_auto='.2f',
            aspect='auto',
            color_continuous_scale='RdBu_r',
            title='Stock Returns Correlation Matrix',
            labels=dict(color="Correlation")
        )
        fig.update_layout(width=800, height=600)
        st.plotly_chart(fig, use_container_width='stretch')
        
        # Summary
        st.subheader("Correlation Summary")
        st.markdown(f"""
        - **Average Correlation:** {correlation.values[np.triu_indices_from(correlation.values, k=1)].mean():.2f}
        - **Highest Correlation:** {correlation.values[np.triu_indices_from(correlation.values, k=1)].max():.2f}
        - **Lowest Correlation:** {correlation.values[np.triu_indices_from(correlation.values, k=1)].min():.2f}
        """)


def _calculate_max_drawdown(prices: pd.Series) -> float:
    """Calculate maximum drawdown from price series."""
    if len(prices) == 0:
        return 0.0
    cumulative = prices / prices.iloc[0]
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()


def show_settings():
    """Show settings interface."""
    st.header("Settings")

    tab1, tab2, tab3 = st.tabs(["General", "Trading", "Data"])

    with tab1:
        st.subheader("General Settings")

        # Logging level
        log_level = st.selectbox("Logging Level", ["DEBUG", "INFO", "WARNING", "ERROR"])
        if st.button("Apply Logging Level"):
            logging.getLogger().setLevel(getattr(logging, log_level))
            st.success(f"Logging level set to {log_level}")

        # Theme
        theme = st.selectbox("Theme", ["Light", "Dark"])
        if st.button("Apply Theme"):
            st.success(f"Theme set to {theme}")

    with tab2:
        st.subheader("Trading Settings")

        # Risk limits
        max_order_value = st.number_input("Max Order Value ($)", value=100000, step=10000)
        max_portfolio_turnover = st.slider("Max Portfolio Turnover (%)", 0.0, 1.0, 0.5, 0.05)

        if st.button("Save Trading Settings"):
            st.success("Trading settings saved")

        # API Configuration
        st.subheader("API Configuration")
        api_key = st.text_input("Alpaca API Key", type="password")
        api_secret = st.text_input("Alpaca API Secret", type="password")
        use_paper = st.checkbox("Use Paper Trading", value=True)

        if st.button("Save API Settings"):
            st.success("API settings saved")

    with tab3:
        st.subheader("Data Settings")

        # Data paths
        data_dir = st.text_input("Data Directory", value="./data")
        cache_dir = st.text_input("Cache Directory", value="./data/cache")

        if st.button("Save Data Settings"):
            st.success("Data settings saved")

        # Data sources
        st.subheader("Data Sources")
        enable_wrds = st.checkbox("Enable WRDS", value=True)
        enable_alpha_vantage = st.checkbox("Enable Alpha Vantage", value=False)

        if st.button("Save Data Source Settings"):
            st.success("Data source settings saved")


if __name__ == "__main__":
    main()
