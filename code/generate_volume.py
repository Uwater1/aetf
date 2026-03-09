import os
import pandas as pd
from datetime import datetime

def generate_volume_range():
    base_dir = '/home/hallo/Documents/aetf'
    folders = ['download', 'selected']
    start_date = '2023-01-03'
    end_date = '2026-02-24'
    output_file = os.path.join(base_dir, 'volume.csv')
    
    # Use a dictionary to keep track of unique ETFs by filename
    unique_etf_files = {}
    
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"Warning: Folder {folder_path} does not exist.")
            continue
            
        for filename in os.listdir(folder_path):
            if filename.endswith('.csv'):
                if filename not in unique_etf_files:
                    unique_etf_files[filename] = os.path.join(folder_path, filename)

    print(f"Found {len(unique_etf_files)} unique ETF files in {folders}.")
    
    # Dictionary to store total volume per date
    daily_volumes = {}
    
    count_files = 0
    total_files = len(unique_etf_files)
    
    for filename, file_path in unique_etf_files.items():
        count_files += 1
        if count_files % 50 == 0:
            print(f"Processing file {count_files}/{total_files}...")
            
        try:
            df = pd.read_csv(file_path)
            
            if 'date' not in df.columns:
                continue
                
            # Filter by date range
            mask = (df['date'] >= start_date) & (df['date'] <= end_date)
            df_filtered = df.loc[mask].copy()
            
            if df_filtered.empty:
                continue
            
            # Check for necessary columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if all(col in df_filtered.columns for col in required_cols):
                # Calculate daily amount: ((open + high + low + close) / 4) * volume
                df_filtered['amount'] = ((df_filtered['open'] + df_filtered['high'] + 
                                         df_filtered['low'] + df_filtered['close']) / 4) * df_filtered['volume']
                
                # Update the aggregate dictionary
                for _, row in df_filtered.iterrows():
                    d = row['date']
                    amt = row['amount']
                    daily_volumes[d] = daily_volumes.get(d, 0) + amt
                    
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if not daily_volumes:
        print("No data found for the specified range.")
        return

    # Convert to DataFrame and sort by date
    result_df = pd.DataFrame(list(daily_volumes.items()), columns=['date', 'volume_k'])
    
    # Handle NaN or Inf values that might have been introduced
    result_df['volume_k'] = pd.to_numeric(result_df['volume_k'], errors='coerce').fillna(0)
    import numpy as np
    result_df['volume_k'] = result_df['volume_k'].replace([np.inf, -np.inf], 0)
    
    # Divide by 1000 as requested
    result_df['volume_k'] = result_df['volume_k'] / 1000
    
    result_df = result_df.sort_values('date')
    
    # Convert volume to integer
    result_df['volume_k'] = result_df['volume_k'].astype(int)
    
    # Save to CSV
    result_df.to_csv(output_file, index=False)
    
    print(f"Successfully processed {len(unique_etf_files)} ETFs.")
    print(f"Aggregated data for {len(result_df)} dates.")
    print(f"Result saved to {output_file}")

if __name__ == "__main__":
    generate_volume_range()
