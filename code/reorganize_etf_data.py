import os
import glob
import pandas as pd

def reorganize():
    # Source and output directories
    src_dir = '/home/hallo/Documents/aetf/ETF_data'
    out_dir = '/home/hallo/Documents/aetf/reorganized_ticker_data'
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        print(f"Created directory: {out_dir}")
    
    # Get all fractal files and sort them to ensure chronological order if processed sequentially
    files = sorted(glob.glob(os.path.join(src_dir, 'fractal*.csv')))
    num_files = len(files)
    
    print(f"Found {num_files} files in {src_dir}")
    
    ticker_data = {} # dictionary to hold lists of DataFrames per ticker
    
    # Step 1: Read files and group by stock_code
    print("Step 1/2: Processing files...")
    for i, file_path in enumerate(files):
        if (i + 1) % 100 == 0 or i == 0 or i == num_files - 1:
            print(f"  Processed {i + 1}/{num_files} files...")
            
        try:
            df = pd.read_csv(file_path)
            # Group by stock_code and append to the specific ticker list
            for ticker, group in df.groupby('stock_code'):
                if ticker not in ticker_data:
                    ticker_data[ticker] = []
                ticker_data[ticker].append(group)
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            
    # Step 2: Concatenate and write to CSV
    num_tickers = len(ticker_data)
    print(f"Step 2/2: Writing unified CSVs for {num_tickers} tickers...")
    
    for i, (ticker, dfs) in enumerate(ticker_data.items()):
        if (i + 1) % 50 == 0 or i == 0 or i == num_tickers - 1:
            print(f"  Writing {i + 1}/{num_tickers}: {ticker}")
            
        try:
            # Concatenate all daily snippets for this ticker
            full_df = pd.concat(dfs, ignore_index=True)
            
            # Ensure chronological order (should already be sorted because files were sorted)
            if 'trade_date' in full_df.columns:
                full_df = full_df.sort_values('trade_date')
            
            # Define output filename: 159923.SZ -> 159923_SZ.csv
            filename = ticker.replace('.', '_') + '.csv'
            out_path = os.path.join(out_dir, filename)
            
            full_df.to_csv(out_path, index=False)
        except Exception as e:
            print(f"  Error writing ticker {ticker}: {e}")

    print(f"Successfully reorganized {num_files} files into {num_tickers} ticker-based files in: {out_dir}")

if __name__ == "__main__":
    reorganize()
