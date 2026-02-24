import os
import shutil
import pandas as pd

def process_files():
    download_dir = 'download'
    selected_dir = 'selected'
    
    # Create selected directory if it doesn't exist
    if not os.path.exists(selected_dir):
        os.makedirs(selected_dir)
        
    for filename in os.listdir(download_dir):
        if not filename.endswith('.csv'):
            continue
            
        filepath = os.path.join(download_dir, filename)
        try:
            df = pd.read_csv(filepath)
            if df.empty or 'date' not in df.columns or 'open' not in df.columns:
                continue
            
            # Get first and last valid rows for dates and opens
            first_date = str(df['date'].iloc[0])
            
            # 1. Has been in market for 3 years (assumed year <= 2023 to have 3 years of data by 2026)
            # The prompt mentions "( first date > 2023)" which may be a typo for "<= 2023" 
            # given it requires 3 years in the market. We use year <= 2023 here.
            first_year = int(first_date.split('-')[0])
            in_market_3_years = (first_year <= 2023)
            
            # 2. Has data for 2026-01-23 and it is valid
            target_row = df[df['date'] == '2026-01-23']
            has_target_date = not target_row.empty and target_row[['open', 'high', 'low']].notna().all().all()
            
            # 3. First low < last high
            first_low = df['low'].iloc[0]
            last_high = df['high'].iloc[-1]
            first_less = (first_low < last_high)
            
            if in_market_3_years and has_target_date and first_less:
                target_path = os.path.join(selected_dir, filename)
                shutil.move(filepath, target_path)
                print(f"Moved {filename} to {selected_dir}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == '__main__':
    process_files()
