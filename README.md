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

## 🛠️ Requirements

- Python 3.x
- `pandas`, `numpy`, `baostock`, `yfinance`

## 📝 Usage Note
The pipeline is designed to transform messy raw downloads into a clean, non-redundant dataset ready for backtesting or modeling.
