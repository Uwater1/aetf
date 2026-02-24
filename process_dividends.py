import os
import glob
import pandas as pd
import numpy as np

def process_files():
    folder_path = '/home/hallo/Documents/aetf/selected'
    csv_files = glob.glob(os.path.join(folder_path, '*.csv'))
    
    for file in csv_files:
        try:
            df = pd.read_csv(file)
                
            # Add 'divident' column based on the difference between yesterday close and today's preclose
            if 'close' in df.columns and 'preclose' in df.columns:
                yesterday_close = df['close']/(1+df['pctChg']/100)
                
                # Difference between previous close and preclose
                div_abs = yesterday_close - df['preclose']
                
                # Calculate relative difference as percentage
                div_pct = div_abs.abs() / yesterday_close.replace(0, np.nan).abs()
                
                # Create the divident column
                df['divident'] = div_abs
                
                # Set to 0 if the change is less than 0.01% (0.0005)
                is_tiny = (div_pct < 0.0001)
                df.loc[is_tiny, 'divident'] = 0.0
                
                # Handle the first row or any NaNs
                df['divident'] = df['divident'].fillna(0.0)
            
            # Overwrite the file with the new data
            df.to_csv(file, index=False)
            
        except Exception as e:
            print(f"Error processing {file}: {e}")

    print(f"Successfully processed {len(csv_files)} files in 'selected' folder.")

if __name__ == '__main__':
    process_files()
