try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    yf = None
    pd = None
import sys
import os
import re
import time


def sanitize_filename(name):
    """Remove invalid characters for filenames."""
    return re.sub(r'[\\/:\*\?"<>|]', '_', name)


def get_yf_ticker(code):
    """Convert a numeric stock code to a yfinance ticker symbol.
    
    Shanghai (starts with 5, 6, 9): append .SS
    Shenzhen (starts with 0, 1, 2, 3): append .SZ
    """
    code = str(code).strip()
    if code.startswith(('5', '6', '9')):
        return f"{code}.SS"
    else:
        return f"{code}.SZ"


def download_stock_data(input_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    output_dir = "download"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # Read stock list
    try:
        df = pd.read_csv(input_file, encoding='utf-8')
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    if 'code' not in df.columns or 'name' not in df.columns:
        print("Error: Input CSV must have 'code' and 'name' columns.")
        return

    print(f"Found {len(df)} items to download.")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        raw_code = str(row['code']).strip()
        name = str(row['name']).strip()
        ticker = get_yf_ticker(raw_code)

        clean_name = sanitize_filename(name)
        filename = os.path.join(output_dir, f"{clean_name}_{raw_code}.csv")

        if os.path.exists(filename):
            print(f"[{idx+1}/{len(df)}] Skipping {ticker} ({name}) - already exists.")
            skip_count += 1
            continue

        print(f"[{idx+1}/{len(df)}] Downloading {ticker} ({name})...", end=" ")

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start="2015-01-01", end="2026-02-25", auto_adjust=False)

            if hist.empty:
                print("No data found.")
                fail_count += 1
                continue

            # Reset index to make Date a column
            hist = hist.reset_index()

            # Format Date column
            if 'Date' in hist.columns:
                hist['Date'] = pd.to_datetime(hist['Date']).dt.strftime('%Y-%m-%d')
            
            # Rename columns to lowercase for consistency with existing pipeline
            hist.columns = [c.lower().replace(' ', '_') for c in hist.columns]

            hist.to_csv(filename, index=False)
            print(f"OK ({len(hist)} rows)")
            success_count += 1

        except Exception as e:
            print(f"Error: {e}")
            fail_count += 1

        time.sleep(0.3)  # Rate limiting

    print(f"\nDone! Success: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "list.csv"
    download_stock_data(input_file)
