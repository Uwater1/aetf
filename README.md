# AETF: ETF Data Processing Pipeline

A concise pipeline for downloading, cleaning, and analyzing ETF (Exchange Traded Fund) data, with a focus on Chinese market filters and redundancy removal.

## 🚀 Workflow

1.  **Data Acquisition**:
    *   `python download.py [index.csv|list.csv]`: Downloads Chinese ETF data via BaoStock.
    *   `python download_yf.py`: Downloads global data via Yahoo Finance.
2.  **Data Cleaning & Filtering**:
    *   `python initial-clean.py`: Filters for ETFs with ≥3 years of history (pre-2023 start), valid recent data, and overall growth. Moves matches to `selected/`.
    *   `python further_clean.py`: Removes highly correlated ETFs (>0.995) to eliminate redundancy, picking the "best" specimen (highest volume/history) for the `selected2/` folder.
3.  **Data Enhancement**:
    *   `python process_dividends.py` & `initial-clean.py`: Calculate and add dividend columns based on adjustment ratios (YFinance) or `preclose` differences (BaoStock).

## 📁 Directory Structure

- `download/`: Raw CSV files from data providers.
- `selected/`: Results after initial filtering.
- `selected2/`: Final curated dataset (no high correlation).
- `selected-index/`: Specific index-related data.

## 📊 Data Statistics

- Total ETFs: 190
-宽基ETF: 70
- 红利/价值ETF: 15
- 科技/半导体/电子ETF: 40
- 新能源/绿色能源ETF: 6
- 消费/医药/医疗ETF: 15
- 行业/主题ETF: 40
- 其他: 5

## Results (After human analysis)
1. report.md: 将ETF分类
2. select.md: 将ETF进行最终筛选， 留下适合组建portfolio的ETF

## 🏆 Selected Portfolio ETFs (Top 10)

These 10 ETFs are selected for the backtest portfolio based on their performance metrics (Sharpe, Returns, and Risk).

| Name | 1y Ret | 3y Ret | Sharp | Sortino | Ann Ret | Vol | Max DD | Days |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 矿业ETF_561330 | 133.88% | 108.17% | 1.3210 | 1.8154 | 44.89% | 31.35% | -24.68% | 805 |
| 浙商之江凤凰ETF_512190 | 54.94% | 58.89% | 1.2790 | 1.6771 | 25.69% | 19.34% | -17.64% | 1567 |
| 工程机械ETF_560280 | 44.84% | - | 1.2407 | 1.8582 | 33.16% | 25.82% | -20.59% | 563 |
| 电信ETF易方达_563010 | 34.58% | - | 1.2091 | 1.9884 | 34.55% | 28.03% | -21.33% | 620 |
| 半导体设备ETF_561980 | 61.73% | - | 1.1508 | 2.1396 | 42.46% | 36.52% | -31.90% | 598 |
| 中证2000ETF华夏_562660 | 55.72% | - | 1.1198 | 1.4248 | 33.99% | 30.30% | -33.95% | 582 |
| 石油ETF_561360 | 52.78% | - | 0.9863 | 1.2376 | 21.26% | 22.06% | -21.53% | 562 |
| 银行ETF华夏_515020 | 5.56% | 47.63% | 1.0061 | 1.5302 | 15.67% | 16.13% | -15.06% | 1514 |
| 沪港深500ETF富国_517100 | 19.18% | 36.54% | 0.9297 | 1.2528 | 16.97% | 17.76% | -17.66% | 1186 |
| 中证500ETF国联_515550 | 41.67% | 38.93% | 0.8468 | 1.2052 | 20.06% | 24.55% | -22.70% | 1497 |

## 📈 Portfolio Backtest (`backtest.py`)

The `backtest.py` script implements a high-performance, Numba-optimized portfolio simulation using a **Relative Momentum & Trend-Filtering** alpha model.

### Alpha Model Strategy (V2.1)

1.  **Base-Weight Anchoring**: Strategies start from either **Equal Weights** (10% each) or **Alt Weights** (Sharpe-proportional from `etf_evaluation.csv`).
2.  **Convex Soft Rank Momentum**: Calculated daily based on 20-day returns.
    *   Replaces the old hard Top-3/Bottom-3 system with a continuous **Power-Law Ranking** formula.
    *   **Formula**: `multiplier = 1 + ALPHA_STRENGTH * scale * sign(norm) * |norm|^RANK_POWER`.
    *   **RANK_POWER (0.5)**: Concentrates the allocation shift on the extremes (top/bottom performers) while maintaining a smooth gradient for middle-ranked ETFs to prevent "cliff-edge" rebalancing.
3.  **Absolute Trend Filter (EMA60)**: If an ETF's price is below its **60-day Exponential Moving Average (EMA60)**, its weight is penalized by `1 - ALPHA_STRENGTH`.
4.  **Market Regime Overrides**:
    *   **Weak Market** (`CSI300 < EMA60` & `Volume MA5 < MA60`): Momentum tilts are DISABLED. Instead, defensive ETFs (银行, 浙商, 石油) receive a `1 + ALPHA_STRENGTH` boost.
    *   **Aggressive Mode**: If the market has been "non-weak" for ≥3 consecutive days, the momentum scale factor increases by **1.5x**.
5.  **Dynamic Rebalancing**: Efficient execution with **0.1% stamp duty**. Rebalances trigger when:
    *   Max weight deviation exceeds **10%**.
    *   A **5-day minimum cooldown** prevents over-trading.

### Performance Results (V2.1 - Convex Soft Rank)

The V2.1 strategy achieves superior risk-adjusted returns and improved efficiency (lower turnover) compared to V2.

| Metric | EqualW | Regime+Def | AltW | AltW+Reg | CSI300 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Total Return | 85.10% | 90.90% | 88.18% | 100.23% | 39.45% |
| CAGR | 32.19% | 34.05% | 33.18% | 36.98% | 16.27% |
| Sharpe | 1.527 | 1.540 | 1.550 | 1.666 | 0.915 |
| Sortino | 2.054 | 2.019 | 2.088 | 2.215 | 1.279 |
| Volatility | 19.58% | 20.43% | 19.80% | 20.15% | 18.34% |
| Max Drawdown | -15.16% | -14.75% | -15.16% | -15.27% | -16.47% |
| Calmar | 2.124 | 2.308 | 2.188 | 2.422 | 0.988 |
| Trading Days | 556 | 556 | 556 | 556 | 556 |

- **Rebalance trades fired**: 36 (Eq Base) | 40 (Alt Base)
- **Weak market days**: 130/556 (23.4%)

  
### Execution

```bash
python backtest.py
```

*Daily NAV history and weight allocations are saved to `backtest_results.csv`.*


## 📋 TODO
* Improve switching time selection (改善再平衡择时)
* Improve weight (改善ETF默认权重)
* Further prevent look ahead bias (减少用未来数据选择ETF的影响)

## 🛠️ Requirements

- Python 3.x
- `pandas`, `numpy`, `baostock`, `yfinance`

## 📝 Usage Note
The pipeline is designed to transform messy raw downloads into a clean, non-redundant dataset ready for backtesting or modeling.
