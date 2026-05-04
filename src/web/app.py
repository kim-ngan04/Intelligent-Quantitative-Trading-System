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
from backtest import show_strategy_backtesting

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

# Import live trading module
from live_trading import show_live_trading

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
