import os
import glob
import pandas as pd
import sys


def process_file(filepath):
    """Process a single downloaded yfinance CSV:
    1. Calculate dividends from close & adj_close ratio changes
    2. Round open, high, low, close, adj_close to 6 decimal places
    """
    df = pd.read_csv(filepath)

    if df.empty or 'close' not in df.columns or 'adj_close' not in df.columns:
        return False, "Missing required columns"

    # Calculate adjustment ratio
    df['ratio'] = df['adj_close'] / df['close']
    ratio_prev = df['ratio'].shift(1)
    close_prev = df['close'].shift(1)

    # Dividend = yesterday's close * (1 - yesterday's ratio / today's ratio)
    df['dividend'] = close_prev * (1 - ratio_prev / df['ratio'])

    # Only keep positive values (negative would be a reverse split artifact)
    # and filter out tiny noise (< 0.001)
    df['dividend'] = df['dividend'].clip(lower=0)
    df.loc[df['dividend'] < 0.001, 'dividend'] = 0.0
    df.loc[0, 'dividend'] = 0.0  # First row has no previous data

    # Round price columns to 6 decimal places
    price_cols = ['open', 'high', 'low', 'close', 'adj_close']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].round(6)

    # Round dividend to 6 d.p. as well
    df['dividend'] = df['dividend'].round(6)

    # Drop helper column
    df = df.drop(columns=['ratio'])

    # Remove the original (always-zero) dividends and stock_splits columns if present
    drop_cols = [c for c in ['dividends', 'stock_splits'] if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # Save back
    df.to_csv(filepath, index=False)
    return True, f"{len(df)} rows"


def process_all(folder="download"):
    if not os.path.isdir(folder):
        print(f"Error: folder '{folder}' not found.")
        return

    csv_files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    print(f"Found {len(csv_files)} files to process in '{folder}'.")

    success = 0
    fail = 0

    for i, filepath in enumerate(csv_files, 1):
        name = os.path.basename(filepath)
        try:
            ok, msg = process_file(filepath)
            if ok:
                success += 1
                print(f"[{i}/{len(csv_files)}] {name} - OK ({msg})")
            else:
                fail += 1
                print(f"[{i}/{len(csv_files)}] {name} - SKIP ({msg})")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(csv_files)}] {name} - ERROR: {e}")

    print(f"\nDone! Processed: {success}, Failed/Skipped: {fail}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "download"
    process_all(folder)
