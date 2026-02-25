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

## Alpha Model Result 
python backtest.py

```md
  Portfolio Backtest — 4 Strategies

[1] Loading ETF data...
    Price data: 2023-10-27 → 2026-02-24, 556 days
    ETFs: 10

================================================================================
  PERFORMANCE COMPARISON  (4 strategies + CSI300 benchmark)
================================================================================

Metric                      EqualW  EqualW+Alpha          AltW    AltW+Alpha        CSI300
--------------------------------------------------------------------------------
Total Return                87.67%        78.74%        92.42%        81.13%        38.22%
CAGR                        33.22%        30.30%        34.75%        31.09%        15.89%
Sharpe                       1.483         1.411         1.511         1.427         0.763
Sortino                      2.010         1.835         2.064         1.863         1.041
Volatility                  19.27%        18.60%        19.74%        18.84%        19.10%
Max Drawdown               -14.78%       -13.14%       -15.12%       -13.31%       -18.67%
Calmar                       2.247         2.305         2.299         2.336         0.852
Trading Days                   553           553           553           553           553

================================================================================
  WEIGHT ALLOCATION — EqualW+Alpha
================================================================================
  2023-11-01 | Top: 浙商之江凤凰=18%, 工程机械ET=11%, 中证500E=11% | Bot: 银行ETF华=8%, 半导体设备E=7%, 中证2000=6% | Spread: 11.4%
  2024-02-01 | Top: 浙商之江凤凰=18%, 石油ETF=15%, 工程机械ET=15% | Bot: 中证2000=4%, 沪港深500=4%, 中证500E=4% | Spread: 13.4%
  2024-05-06 | Top: 银行ETF华=12%, 电信ETF易=12%, 石油ETF=11% | Bot: 中证2000=9%, 工程机械ET=8%, 沪港深500=6% | Spread: 5.9%
  2024-08-01 | Top: 沪港深500=13%, 石油ETF=13%, 中证500E=13% | Bot: 电信ETF易=9%, 银行ETF华=8%, 半导体设备E=6% | Spread: 7.2%
  2024-11-01 | Top: 石油ETF=17%, 银行ETF华=13%, 沪港深500=10% | Bot: 中证500E=9%, 工程机械ET=8%, 浙商之江凤凰=7% | Spread: 9.4%
  2025-02-05 | Top: 石油ETF=17%, 浙商之江凤凰=11%, 中证500E=11% | Bot: 半导体设备E=8%, 中证2000=8%, 银行ETF华=6% | Spread: 10.4%
  2025-05-06 | Top: 石油ETF=15%, 浙商之江凤凰=12%, 中证500E=12% | Bot: 工程机械ET=8%, 半导体设备E=8%, 中证2000=6% | Spread: 8.5%
  2025-08-01 | Top: 银行ETF华=16%, 石油ETF=14%, 半导体设备E=10% | Bot: 浙商之江凤凰=8%, 电信ETF易=8%, 矿业ETF=7% | Spread: 8.9%
  2025-11-03 | Top: 银行ETF华=17%, 沪港深500=11%, 工程机械ET=10% | Bot: 电信ETF易=9%, 半导体设备E=8%, 矿业ETF=8% | Spread: 9.9%
  2026-02-02 | Top: 沪港深500=16%, 石油ETF=12%, 工程机械ET=11% | Bot: 中证2000=9%, 矿业ETF=8%, 银行ETF华=4% | Spread: 12.7%

================================================================================
  WEIGHT ALLOCATION — AltW+Alpha
================================================================================
  2023-11-01 | Top: 浙商之江凤凰=18%, 工程机械ET=12%, 矿业ETF=11% | Bot: 半导体设备E=7%, 银行ETF华=7%, 中证2000=6% | Spread: 12.1%
  2024-02-01 | Top: 浙商之江凤凰=19%, 工程机械ET=16%, 电信ETF易=16% | Bot: 中证2000=4%, 沪港深500=4%, 中证500E=4% | Spread: 14.7%
  2024-05-06 | Top: 电信ETF易=12%, 矿业ETF=12%, 银行ETF华=11% | Bot: 中证500E=9%, 工程机械ET=9%, 沪港深500=5% | Spread: 7.2%
  2024-08-01 | Top: 石油ETF=12%, 沪港深500=12%, 工程机械ET=11% | Bot: 中证2000=9%, 银行ETF华=7%, 半导体设备E=7% | Spread: 5.7%
  2024-11-01 | Top: 石油ETF=16%, 银行ETF华=12%, 矿业ETF=10% | Bot: 工程机械ET=9%, 浙商之江凤凰=8%, 中证500E=7% | Spread: 9.2%
  2025-02-05 | Top: 石油ETF=16%, 浙商之江凤凰=12%, 工程机械ET=11% | Bot: 沪港深500=9%, 中证2000=8%, 银行ETF华=6% | Spread: 10.5%
  2025-05-06 | Top: 石油ETF=14%, 浙商之江凤凰=13%, 电信ETF易=12% | Bot: 银行ETF华=8%, 沪港深500=8%, 中证2000=7% | Spread: 7.6%
  2025-08-01 | Top: 银行ETF华=15%, 石油ETF=13%, 半导体设备E=11% | Bot: 矿业ETF=8%, 电信ETF易=8%, 中证500E=7% | Spread: 8.2%
  2025-11-03 | Top: 银行ETF华=17%, 工程机械ET=11%, 沪港深500=10% | Bot: 石油ETF=8%, 中证500E=8%, 半导体设备E=8% | Spread: 8.5%
  2026-02-02 | Top: 沪港深500=15%, 工程机械ET=12%, 电信ETF易=11% | Bot: 中证2000=10%, 中证500E=8%, 银行ETF华=4% | Spread: 11.2%

Daily NAV saved to: /home/hallo/Documents/aetf/backtest_results.csv
```

## 🛠️ Requirements

- Python 3.x
- `pandas`, `numpy`, `baostock`, `yfinance`

## 📝 Usage Note
The pipeline is designed to transform messy raw downloads into a clean, non-redundant dataset ready for backtesting or modeling.
