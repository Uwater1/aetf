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

## 📈 Portfolio Backtest (`backtest.py`)

The `backtest.py` script runs a portfolio backtest implementing a custom Alpha Model designed to dynamically adjust ETF weighting.

### Alpha Model Strategy
1. **Value Signal**: Z-score mean-reversion across multiple moving average timeframes (40, 80, 120 days). It favors historically undervalued ETFs.
2. **Volatility Scaling**: Inverse-volatility weighting is used to equalize risk contributions across ETFs.
3. **Adaptive Momentum Guard**: Dynamic per-ETF thresholds (`k × rolling_std`) to enforce trend robustness.
    - *Strong rally*: Prevents the model from reducing the ETF's weight below its baseline.
    - *Strong crash*: Limits the ETF to the minimum weight to avoid catching falling knives.

**Rebalance frequency**: Quarterly (February, May, August, November).

### Execution

```bash
python backtest.py
```

```md
  Portfolio Backtest — 4 Strategies
  Params: MA=[40, 80, 120]/[0.3, 0.4, 0.3] Mom=20d(k=1.3) Vol=60d MinW=0.03 Signal=0.2 Stamp=0.001

[1] Loading ETF data...
    Price data: 2023-10-27 → 2026-02-24, 556 days
    ETFs: 10

================================================================================
  PERFORMANCE COMPARISON  (4 strategies + CSI300 benchmark)
================================================================================

Metric                      EqualW  EqualW+Alpha          AltW    AltW+Alpha        CSI300
--------------------------------------------------------------------------------
Total Return                87.62%        82.50%        92.38%        85.79%        38.22%
CAGR                        33.21%        31.54%        34.74%        32.62%        15.89%
Sharpe                       1.483         1.445         1.510         1.466         0.763
Sortino                      2.009         1.911         2.063         1.949         1.041
Volatility                  19.27%        18.85%        19.74%        19.18%        19.10%
Max Drawdown               -14.79%       -13.55%       -15.12%       -13.75%       -18.67%
Calmar                       2.246         2.328         2.297         2.372         0.852
Trading Days                   553           553           553           553           553

================================================================================
  WEIGHT ALLOCATION — EqualW+Alpha
================================================================================
  2023-11-01 | Top: 浙商之江凤凰=14%, 工程机械ET=11%, 中证500E=11% | Bot: 银行ETF华=9%, 半导体设备E=8%, 中证2000=8% | Spread: 5.7%
  2024-02-01 | Top: 浙商之江凤凰=17%, 石油ETF=15%, 工程机械ET=15% | Bot: 中证2000=5%, 沪港深500=5%, 中证500E=5% | Spread: 12.1%
  2024-05-06 | Top: 银行ETF华=11%, 电信ETF易=11%, 石油ETF=11% | Bot: 中证2000=10%, 工程机械ET=9%, 沪港深500=8% | Spread: 3.0%
  2024-08-01 | Top: 沪港深500=12%, 石油ETF=11%, 中证500E=11% | Bot: 电信ETF易=9%, 银行ETF华=9%, 半导体设备E=8% | Spread: 3.6%
  2024-11-01 | Top: 石油ETF=13%, 银行ETF华=12%, 沪港深500=10% | Bot: 中证500E=9%, 工程机械ET=9%, 浙商之江凤凰=9% | Spread: 5.0%
  2025-02-05 | Top: 石油ETF=13%, 浙商之江凤凰=11%, 中证500E=10% | Bot: 半导体设备E=9%, 中证2000=9%, 银行ETF华=8% | Spread: 5.2%
  2025-05-06 | Top: 石油ETF=12%, 浙商之江凤凰=11%, 中证500E=11% | Bot: 工程机械ET=9%, 半导体设备E=9%, 中证2000=8% | Spread: 4.3%
  2025-08-01 | Top: 银行ETF华=13%, 石油ETF=12%, 半导体设备E=10% | Bot: 浙商之江凤凰=9%, 电信ETF易=9%, 矿业ETF=8% | Spread: 4.6%
  2025-11-03 | Top: 银行ETF华=14%, 沪港深500=11%, 工程机械ET=10% | Bot: 电信ETF易=9%, 半导体设备E=9%, 矿业ETF=9% | Spread: 5.0%
  2026-02-02 | Top: 沪港深500=13%, 石油ETF=11%, 工程机械ET=11% | Bot: 中证2000=10%, 矿业ETF=10%, 银行ETF华=3% | Spread: 10.0%

================================================================================
  WEIGHT ALLOCATION — AltW+Alpha
================================================================================
  2023-11-01 | Top: 浙商之江凤凰=15%, 工程机械ET=12%, 矿业ETF=12% | Bot: 中证2000=8%, 沪港深500=8%, 银行ETF华=8% | Spread: 7.2%
  2024-02-01 | Top: 浙商之江凤凰=18%, 工程机械ET=17%, 电信ETF易=16% | Bot: 中证2000=4%, 沪港深500=4%, 中证500E=4% | Spread: 13.7%
  2024-05-06 | Top: 矿业ETF=12%, 电信ETF易=12%, 浙商之江凤凰=11% | Bot: 石油ETF=10%, 中证500E=8%, 沪港深500=7% | Spread: 5.4%
  2024-08-01 | Top: 矿业ETF=12%, 工程机械ET=11%, 浙商之江凤凰=11% | Bot: 中证500E=9%, 半导体设备E=9%, 银行ETF华=8% | Spread: 3.7%
  2024-11-01 | Top: 石油ETF=13%, 矿业ETF=11%, 银行ETF华=11% | Bot: 浙商之江凤凰=10%, 沪港深500=8%, 中证500E=7% | Spread: 5.4%
  2025-02-05 | Top: 石油ETF=12%, 浙商之江凤凰=12%, 矿业ETF=11% | Bot: 中证500E=8%, 沪港深500=8%, 银行ETF华=7% | Spread: 5.3%
  2025-05-06 | Top: 浙商之江凤凰=12%, 石油ETF=11%, 矿业ETF=11% | Bot: 银行ETF华=8%, 中证2000=8%, 沪港深500=8% | Spread: 4.4%
  2025-08-01 | Top: 银行ETF华=12%, 石油ETF=11%, 半导体设备E=11% | Bot: 电信ETF易=10%, 沪港深500=8%, 中证500E=7% | Spread: 4.7%
  2025-11-03 | Top: 银行ETF华=13%, 工程机械ET=11%, 浙商之江凤凰=11% | Bot: 沪港深500=9%, 石油ETF=9%, 中证500E=8% | Spread: 4.8%
  2026-02-02 | Top: 工程机械ET=12%, 矿业ETF=12%, 沪港深500=11% | Bot: 石油ETF=10%, 中证500E=8%, 银行ETF华=3% | Spread: 8.5%

Daily NAV saved to: /home/hallo/Documents/aetf/backtest_results.csv
```

## 📋 TODO
* Improve switching time selection (改善再平衡择时)
* Improve weight (改善ETF默认权重)
* Further prevent look ahead bias (减少用未来数据选择ETF的影响)

## 🛠️ Requirements

- Python 3.x
- `pandas`, `numpy`, `baostock`, `yfinance`

## 📝 Usage Note
The pipeline is designed to transform messy raw downloads into a clean, non-redundant dataset ready for backtesting or modeling.
