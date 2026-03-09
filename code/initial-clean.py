import os
import shutil
import pandas as pd


def clean_file(filepath):
    """Clean a yfinance CSV in-place:
    1. Calculate dividends from close & adj_close ratio changes
    2. Round open, high, low, close, adj_close to 6 decimal places
    3. Remove unused columns (dividends, stock_splits)
    """
    df = pd.read_csv(filepath)

    if df.empty or 'close' not in df.columns or 'adj_close' not in df.columns:
        return

    # Calculate adjustment ratio
    df['ratio'] = df['adj_close'] / df['close']
    ratio_prev = df['ratio'].shift(1)
    close_prev = df['close'].shift(1)

    # Dividend = yesterday's close * (1 - yesterday's ratio / today's ratio)
    df['dividend'] = close_prev * (1 - ratio_prev / df['ratio'])

    # Only keep positive values and filter out tiny noise (< 0.001)
    df['dividend'] = df['dividend'].clip(lower=0)
    df.loc[df['dividend'] < 0.001, 'dividend'] = 0.0
    df.loc[0, 'dividend'] = 0.0  # First row has no previous data

    # Round price columns and dividend to 6 decimal places
    cols_to_round = [col for col in ['open', 'high', 'low', 'close', 'adj_close', 'dividend'] if col in df.columns]
    df[cols_to_round] = df[cols_to_round].round(6)

    # Drop helper column and unused columns
    df = df.drop(columns=['ratio'])
    drop_cols = [c for c in ['dividends', 'stock_splits'] if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # Save back
    df.to_csv(filepath, index=False)


def process_files():
    download_dir = 'download'
    selected_dir = 'selected'
    
    # Create selected directory if it doesn't exist
    if not os.path.exists(selected_dir):
        os.makedirs(selected_dir)

    moved = 0
    skipped = 0

    for filename in sorted(os.listdir(download_dir)):
        if not filename.endswith('.csv'):
            continue
            
        filepath = os.path.join(download_dir, filename)
        try:
            df = pd.read_csv(filepath)
            if df.empty or 'date' not in df.columns or 'adj_close' not in df.columns:
                continue
            
            # 1. Has been in market for 3 years (first year <= 2023)
            first_date = str(df['date'].iloc[0])
            first_year = int(first_date.split('-')[0])
            in_market_3_years = (first_year <= 2023)
            
            # 2. Has data for 2026-01-23 and it is valid
            target_row = df[df['date'] == '2026-01-23']
            has_target_date = not target_row.empty and target_row[['open', 'high', 'low']].notna().all().all()
            
            # 3. Price has grown (using adj_close to account for dividends)
            first_adj_close = df['adj_close'].iloc[0]
            last_adj_close = df['adj_close'].iloc[-1]
            price_grew = (first_adj_close < last_adj_close)
            
            if in_market_3_years and has_target_date and price_grew:
                target_path = os.path.join(selected_dir, filename)
                shutil.move(filepath, target_path)
                clean_file(target_path)
                moved += 1
                print(f"[{moved}] Moved & cleaned: {filename}")
            else:
                skipped += 1
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"\nDone! Moved & cleaned: {moved}, Skipped: {skipped}")


if __name__ == '__main__':
    process_files()
