# FinRL Trading Platform

**A modular quantitative trading platform in Python — machine learning strategies, professional backtesting, and live trading.**

[![PyPI](https://img.shields.io/pypi/v/finrl-trading.svg)](https://pypi.org/project/finrl-trading/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
![License](https://img.shields.io/github/license/AI4Finance-Foundation/FinRL-Trading.svg?color=brightgreen)

---

## Key Features

- **Strategy Framework** — multiple quantitative strategies, including ML-based stock selection
- **Risk Management** — built-in risk controls and position limits
- **Live Trading** — Alpaca integration for paper and live trading
- **Modular Design** — clean, extensible architecture

## Installation

**Requirements:** Python 3.11+, an Alpaca account (for live trading), and an FMP API key (for premium data).

```bash
git clone https://github.com/your-username/FinRL-Trading.git
cd FinRL-Trading
pip install -r requirements.txt

cp .env.example .env
# edit .env with your API keys
```

### Getting started

The fastest way to learn the platform is the full workflow tutorial, covering data acquisition, ML-based stock selection, backtesting, and paper trading:

```bash
jupyter notebook examples/FinRL_Full_Workflow.ipynb
```

## Usage

### Data acquisition

```python
from src.data.data_fetcher import get_data_manager

manager = get_data_manager()
components = manager.get_sp500_components()

tickers = ['AAPL', 'MSFT', 'GOOGL']
fundamentals = manager.get_fundamental_data(tickers, '2020-01-01', '2023-12-31')
prices = manager.get_price_data(tickers, '2020-01-01', '2023-12-31')
```

### Strategy development

```python
from src.strategies.ml_strategy import MLStockSelectorStrategy
from src.strategies.base_strategy import StrategyConfig

config = StrategyConfig(
    name="ML Stock Selector",
    parameters={'model_type': 'random_forest', 'top_n': 30, 'sector_neutral': True},
    risk_limits={'max_weight': 0.1}
)

strategy = MLStockSelectorStrategy(config)
result = strategy.generate_weights({'fundamentals': fundamentals, 'prices': prices})
```

### Backtesting

```python
from src.backtest.backtest_engine import BacktestEngine, BacktestConfig

backtest_config = BacktestConfig(
    start_date='2020-01-01',
    end_date='2023-12-31',
    initial_capital=1_000_000,
    rebalance_freq='Q',
    transaction_cost=0.001,
    benchmark_tickers=['VOO', 'QQQ']
)

engine = BacktestEngine(backtest_config)
result = engine.run_backtest(
    strategy_name="ML Stock Selector",
    weight_signals=ml_weights,
    price_data=prices
)

print(f"Annualized Return: {result.annualized_return:.2%}")
print(f"Sharpe Ratio: {result.metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {result.metrics['max_drawdown']:.2%}")
```

### Live trading

```python
from src.trading.alpaca_manager import create_alpaca_account_from_env, AlpacaManager
from src.trading.trade_executor import TradeExecutor, ExecutionConfig

account = create_alpaca_account_from_env()
alpaca_manager = AlpacaManager([account])

executor = TradeExecutor(alpaca_manager, ExecutionConfig(max_order_value=100000, risk_checks_enabled=True))
result = executor.execute_portfolio_rebalance({'AAPL': 0.3, 'MSFT': 0.3, 'GOOGL': 0.4})
```

## Core Components

| Module | Description |
|---|---|
| `src/data/` | Multi-source data acquisition (Yahoo / FMP / WRDS), cleaning, and SQLite-based caching |
| `src/strategies/` | Strategy framework — equal weight, market cap weighted, ML-based selection |
| `src/backtest/` | Backtesting engine (powered by `bt`) with multi-benchmark comparison |
| `src/trading/` | Alpaca execution, order/risk management, performance tracking |
| `src/config/` | Pydantic-based settings with environment variable support |

## Configuration

Set the following in your `.env` file:

```bash
ENVIRONMENT=development

APCA_API_KEY=your_alpaca_key
APCA_API_SECRET=your_alpaca_secret
APCA_BASE_URL=https://paper-api.alpaca.markets

FMP_API_KEY=your_fmp_api_key

TRADING_MAX_ORDER_VALUE=100000
TRADING_MAX_PORTFOLIO_TURNOVER=0.5
STRATEGY_MAX_WEIGHT_PER_STOCK=0.1

DATA_CACHE_TTL_HOURS=24
DATA_MAX_CACHE_SIZE_MB=1000
```

## Performance Metrics

- **Return**: total return, annualized return, alpha
- **Risk**: volatility, Sharpe ratio, Sortino ratio, max drawdown, Calmar ratio
- **Distribution**: skewness, kurtosis
- **Benchmarking**: information ratio, beta, tracking error

## Contributing

1. Fork the repository and create a feature branch
2. Install dev dependencies: `pip install pytest black flake8 mypy`
3. Follow PEP 8 / Black formatting, add type hints and docstrings
4. Write tests for new features
5. Open a pull request

## Roadmap

- [ ] Deep reinforcement learning strategies
- [ ] Alternative data integration
- [ ] Multi-asset support (crypto, futures)
- [ ] Advanced portfolio optimization
- [ ] Real-time alerting
- [ ] Web visualization interface
- [ ] Docker containerization

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Disclaimer

This software is for **educational and research purposes only** and does not constitute financial advice. Past performance does not guarantee future results.

## References

- [FinRL](https://github.com/AI4Finance-Foundation/FinRL) — deep reinforcement learning framework for quantitative trading
- [Alpaca-py](https://github.com/alpacahq/alpaca-py) — Alpaca trading API
- [bt](https://github.com/pmorissette/bt) — backtesting framework for Python
