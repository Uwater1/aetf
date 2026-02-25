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

```
  Portfolio Backtest — Value Alpha + Momentum Guard

[1] Loading ETF data...
    Price data: 2023-10-27 → 2026-02-24, 556 days
    ETFs: 10

======================================================================
  PERFORMANCE COMPARISON
======================================================================

Metric                   Alpha Model    Equal Weight       CSI300 BM
-----------------------------------------------------------------
Total Return                  85.81%          87.67%          38.22%
CAGR                          32.62%          33.22%          15.89%
Sharpe                         1.479           1.483           0.763
Sortino                        1.990           2.010           1.041
Volatility                    18.98%          19.27%          19.10%
Max Drawdown                 -13.75%         -14.78%         -18.67%
Calmar                         2.372           2.247           0.852
Trading Days                     553             553             553

======================================================================
  WEIGHT ALLOCATION AT EACH REBALANCE
======================================================================
  2023-11-01 | Top: 工程机械ET=10%, 矿业ETF=10%, 电信ETF易=10% | Bot: 石油ETF=10%, 沪港深500=10%, 中证2000=10% | Spread: 0.2%
  2024-02-01 | Top: 沪港深500=14%, 浙商之江凤凰=14%, 电信ETF易=14% | Bot: 半导体设备E=4%, 中证2000=4%, 中证500E=4% | Spread: 9.9%
  2024-05-06 | Top: 半导体设备E=11%, 中证2000=11%, 中证500E=10% | Bot: 浙商之江凤凰=10%, 矿业ETF=10%, 工程机械ET=9% | Spread: 1.5%
  2024-08-01 | Top: 工程机械ET=10%, 中证500E=10%, 石油ETF=10% | Bot: 浙商之江凤凰=10%, 电信ETF易=10%, 银行ETF华=9% | Spread: 1.1%
  2024-11-01 | Top: 石油ETF=11%, 银行ETF华=10%, 矿业ETF=10% | Bot: 半导体设备E=10%, 中证2000=10%, 中证500E=10% | Spread: 1.2%
  2025-02-05 | Top: 石油ETF=11%, 浙商之江凤凰=10%, 中证500E=10% | Bot: 电信ETF易=10%, 半导体设备E=10%, 中证2000=9% | Spread: 1.2%
  2025-05-06 | Top: 石油ETF=11%, 电信ETF易=10%, 中证500E=10% | Bot: 银行ETF华=10%, 工程机械ET=10%, 中证2000=9% | Spread: 1.1%
  2025-08-01 | Top: 半导体设备E=10%, 石油ETF=10%, 工程机械ET=10% | Bot: 浙商之江凤凰=10%, 矿业ETF=10%, 中证2000=9% | Spread: 1.1%
  2025-11-03 | Top: 银行ETF华=11%, 石油ETF=10%, 工程机械ET=10% | Bot: 电信ETF易=10%, 浙商之江凤凰=10%, 半导体设备E=9% | Spread: 2.5%
  2026-02-02 | Top: 银行ETF华=11%, 沪港深500=11%, 工程机械ET=10% | Bot: 浙商之江凤凰=10%, 中证500E=10%, 半导体设备E=9% | Spread: 2.1%

Daily NAV saved to: /home/hallo/Documents/aetf/backtest_results.csv
```

## 🛠️ Requirements

- Python 3.x
- `pandas`, `numpy`, `baostock`, `yfinance`

## 📝 Usage Note
The pipeline is designed to transform messy raw downloads into a clean, non-redundant dataset ready for backtesting or modeling.
