import baostock as bs
import pandas as pd
import sys
import os
import time
import re

def sanitize_filename(name):
    # Remove invalid characters for filenames
    return re.sub(r'[\\/:\*\?"<>|]', '_', name)

def get_bs_code(code):
    # Add sh. or sz. prefix if missing
    code = str(code).strip()
    if code.startswith(('sh.', 'sz.', 'bj.')):
        return code
    
    # Handle suffixes from index.csv format
    if code.endswith('.XSHG'):
        return f"sh.{code.split('.')[0]}"
    if code.endswith('.XSHE'):
        return f"sz.{code.split('.')[0]}"

    if code.startswith(('6', '5', '9', '000', '001')):
        if code.startswith(('6', '5', '9')):
            return f"sh.{code}"
        else:
            return f"sz.{code}"
    
    # Default fallback
    if len(code) == 6:
        if code.startswith(('6', '5', '9')):
            return f"sh.{code}"
        return f"sz.{code}"
        
    return code

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
        # Try standard reading first
        df = pd.read_csv(input_file, encoding='utf-8')
    except Exception:
        try:
            # Fallback for malformed CSVs like index.csv with unquoted commas
            print(f"Standard CSV parsing failed for {input_file}, trying robust mode...")
            data = []
            with open(input_file, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split(',')
                num_cols = len(header)
                for line in f:
                    parts = line.strip().split(',')
                    if not parts or not any(parts): continue
                    if len(parts) > num_cols:
                        # Attempt to fix lines like "399284.XSHE,AI,50,2020-02-18,2020-02-18,AI,50"
                        # We assume the first field is code and last two are likely dates/names
                        # For index.csv: Code, Category, Date1, Date2, ShortName
                        # If we have 7 fields instead of 5: [Code, Cat1, Cat2, Date1, Date2, Short1, Short2]
                        if num_cols == 5 and len(parts) == 7:
                            fixed = [
                                parts[0], 
                                f"{parts[1]} {parts[2]}", 
                                parts[3], 
                                parts[4], 
                                f"{parts[5]} {parts[6]}"
                            ]
                            data.append(fixed)
                        else:
                            # Just take the first num_cols and hope for the best, or slice
                            data.append(parts[:num_cols])
                    else:
                        # Pad if necessary or just append
                        while len(parts) < num_cols:
                            parts.append("")
                        data.append(parts[:num_cols])
            df = pd.DataFrame(data, columns=header)
        except Exception as e:
            print(f"Error reading {input_file} even in robust mode: {e}")
            return
            
    # Handle index.csv format columns
    if '指数代码' in df.columns:
        df = df.rename(columns={'指数代码': 'code'})
        if '指数简写' in df.columns:
            df = df.rename(columns={'指数简写': 'name'})
        elif '指数分类' in df.columns:
            df = df.rename(columns={'指数分类': 'name'})

    if 'code' not in df.columns or 'name' not in df.columns:
        print("Error: Input CSV must have 'code' and 'name' columns (or '指数代码' and '指数简写/指数分类').")
        return

    print(f"Found {len(df)} items to download.")

    #### 登陆系统 ####
    lg = bs.login()
    if lg.error_code != '0':
        print(f"login respond error_code: {lg.error_code}, error_msg: {lg.error_msg}")
        return

    try:
        for idx, row in df.iterrows():
            raw_code = str(row['code'])
            name = str(row['name'])
            bs_code = get_bs_code(raw_code)
            
            clean_name = sanitize_filename(name)
            safe_raw_code = raw_code.replace('.', '_', 1)
            filename = os.path.join(output_dir, f"{clean_name}_{safe_raw_code}.csv")
            
            if os.path.exists(filename):
                print(f"[{idx+1}/{len(df)}] Skipping {bs_code} ({name}) - {filename} already exists.")
                continue
                
            print(f"[{idx+1}/{len(df)}] Downloading {bs_code} ({name}) to {filename}...")
            
            rs = bs.query_history_k_data_plus(bs_code,
                "date,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
                start_date='2015-12-30', end_date='2026-01-23',
                frequency="d", adjustflag="2")
            
            if rs.error_code != '0':
                print(f'Error querying {bs_code}: {rs.error_msg}')
                time.sleep(0.2)
                continue
                
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
                
            if data_list:
                result = pd.DataFrame(data_list, columns=rs.fields)
                result.to_csv(filename, index=False)
                # print(f"Successfully saved {bs_code}")
            else:
                print(f"No data found for {bs_code}")
                
            time.sleep(0.2)

    finally:
        #### 登出系统 ####
        bs.logout()

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "list.csv"
    download_stock_data(input_file)
